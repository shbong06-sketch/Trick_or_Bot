"""Framework adapters. Model imports occur only in explicit worker commands."""
import ast
import copy
import importlib
import inspect
import json
import random
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import yaml

from results import ROOT, digest, environment, save_json

UPSTREAM = {
    "dfine": ("/opt/dfine", "src", "956d1709314c2c6a4df6f34de232054578a7449f"),
    "deim": ("/opt/deim", "engine", "09d35d53d39ee3145a1e61e3a989b28b9468d1dd"),
    "rtdetrv2": ("/opt/rtdetr/rtdetrv2_pytorch", "src", "df2a96c8c3a098567a1149bf0248da6efe6d495d"),
}


class EarlyStop:
    def __init__(self, patience, min_delta=0):
        self.patience, self.min_delta = patience, min_delta
        self.best, self.bad_epochs, self.best_epoch = -float("inf"), 0, None

    def update(self, metric, epoch):
        import math
        if not math.isfinite(metric):
            raise ValueError("Non-finite validation metric")
        improved = metric > self.best + self.min_delta
        if improved:
            self.best, self.best_epoch, self.bad_epochs = metric, epoch, 0
        else:
            self.bad_epochs += 1
        return improved, self.bad_epochs >= self.patience


def install_epoch_hook(method, observe):
    """Inject after validation and at epoch end, without editing vendor files."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    function = tree.body[0]
    loops = [node for node in function.body if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "epoch"]
    if len(loops) != 1:
        raise RuntimeError("Unsupported vendor fit loop: expected one epoch loop")
    loop = loops[0]
    matches = [i for i,node in enumerate(loop.body) if isinstance(node, ast.Assign)
               and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
               and node.value.func.id == "evaluate"]
    if len(matches) != 1:
        raise RuntimeError("Unsupported vendor fit loop: expected one validation call")
    loop.body[matches[0]+1:matches[0]+1] = ast.parse("_phase1_stop = _phase1_observe(self, epoch, test_stats)").body
    loop.body.extend(ast.parse("if _phase1_stop:\n    break").body)
    function.decorator_list = []
    scope = dict(method.__globals__, _phase1_observe=observe)
    exec(compile(ast.fix_missing_locations(tree), inspect.getfile(method), "exec"), scope)
    return scope[function.name]


def runtime_hyperparameters(model, optimizer, scheduler, recipe):
    groups = [{k:v for k,v in group.items() if k != "params"} for group in optimizer.param_groups]
    return dict(recipe=recipe, optimizer=type(optimizer).__name__, optimizer_defaults=optimizer.defaults,
                optimizer_param_groups=groups, scheduler=type(scheduler).__name__ if scheduler else None,
                scheduler_state=scheduler.state_dict() if scheduler else None,
                parameter_count=sum(p.numel() for p in model.parameters()))


def vendor_config(cfg, model_name, directory, *, training):
    framework = cfg["models"][model_name]["framework"]
    location, package, commit = UPSTREAM[framework]
    git_root = "/opt/rtdetr" if framework == "rtdetrv2" else location
    actual = subprocess.check_output(["git", "-C", git_root, "rev-parse", "HEAD"], text=True).strip()
    if actual != commit:
        raise RuntimeError(f"Vendor commit mismatch: {actual} != {commit}")
    sys.path.insert(0, location)
    core = importlib.import_module(f"{package}.core")
    recipe = ROOT/cfg["models"][model_name]["recipe"]
    # Flatten includes with the vendor loader; preserve architecture-specific ops.
    vendor = core.YAMLConfig(str(recipe))
    values = copy.deepcopy(vendor.yaml_cfg)
    common = cfg["common"]
    values.update(device="cuda:0", use_amp=True, output_dir=str(directory),
                  seed=common["seed"], eval_spatial_size=common["input_size"])
    values["epochs" if framework == "dfine" else "epoches"] = common["epochs"]
    for split, loader in (("train", "train_dataloader"), ("val", "val_dataloader")):
        data = values[loader]
        data.update(total_batch_size=common["batch_size"], num_workers=common["workers"])
        split_dir = cfg["dataset"]["split_dirs"][split]
        data["dataset"].update(img_folder=str(ROOT/cfg["dataset"]["root"]/"images"/split_dir),
                               ann_file=str(ROOT/cfg["dataset"]["root"]/"annotations"/f"instances_{split_dir}.json"))
        resize_ops = [op for op in data["dataset"]["transforms"]["ops"] if op["type"] == "Resize"]
        if len(resize_ops) != 1:
            raise RuntimeError("Expected one final Resize operation")
        resize_ops[0]["size"] = common["input_size"]
    for key in ("HGNetv2", "PResNet"):
        if key in values:
            values[key]["pretrained"] = False
    values["num_top_queries"] = cfg["evaluation"]["max_detections"]
    if training:
        values["tuning"] = str(ROOT/cfg["models"][model_name]["weights"])
    values.pop("__include__", None)
    path = directory/"vendor_resolved.yaml"
    path.write_text(yaml.safe_dump(values, sort_keys=False))
    return core.YAMLConfig(str(path)), package


def train_vendor(cfg, name, directory, torch):
    weights = ROOT/cfg["models"][name]["weights"]
    initial_hash = digest(weights)
    vendor, package = vendor_config(cfg, name, directory, training=True)
    solver_cls = importlib.import_module(f"{package}.solver.det_solver").DetSolver
    controller = EarlyStop(cfg["common"]["patience"], cfg["common"]["min_delta"])
    history = []

    def observe(solver, epoch, stats):
        metric = float(stats["coco_eval_bbox"][0])
        improved, stop = controller.update(metric, epoch+1)
        if improved:
            torch.save(solver.state_dict(), directory/"best_phase1.pth")
        details["active_scheduler"] = type(solver.lr_scheduler).__name__
        if hasattr(solver.lr_scheduler, "state_dict"):
            details["active_scheduler_state"] = solver.lr_scheduler.state_dict()
        save_json(directory/"applied_hyperparameters.json", details)
        history.append(dict(epoch=epoch+1, val_map50_95=metric, val_map50=float(stats["coco_eval_bbox"][1]),
                            learning_rates=[group["lr"] for group in solver.optimizer.param_groups]))
        save_json(directory/"epoch_history.json", history)
        return stop

    solver = solver_cls(vendor)
    original_train = solver.train
    details = {}

    def setup():
        original_train()
        details.update(runtime_hyperparameters(solver.model, solver.optimizer, solver.lr_scheduler, vendor.yaml_cfg))
        details["initial_weights_sha256"] = initial_hash
        save_json(directory/"applied_hyperparameters.json", details)

    solver.train = setup
    fit = install_epoch_hook(solver_cls.fit, observe)
    fit(solver)
    return dict(epochs_ending=history[-1]["epoch"], best_epoch=controller.best_epoch,
                checkpoint="best_phase1.pth", hyperparameters=details,
                early_stop_monitor="val_mAP50_95", parameter_count=details["parameter_count"])


def train_yolo(cfg, name, directory, torch):
    from ultralytics import YOLO
    model = YOLO(cfg["models"][name]["weights"])
    common = cfg["common"]
    history, details = [], {"initial_weights_sha256":digest(model.ckpt_path)}

    def setup(trainer):
        details.update(runtime_hyperparameters(trainer.model, trainer.optimizer, trainer.scheduler, vars(trainer.args)))
        details["gradient_accumulation_steps"] = trainer.accumulate
        save_json(directory/"applied_hyperparameters.json", details)

    def epoch(trainer):
        history.append(dict(epoch=trainer.epoch+1, fitness=float(trainer.fitness),
                            learning_rates=[group["lr"] for group in trainer.optimizer.param_groups],
                            gradient_accumulation_steps=trainer.accumulate))
        save_json(directory/"epoch_history.json", history)

    model.add_callback("on_train_start", setup)
    model.add_callback("on_fit_epoch_end", epoch)
    options = dict(cfg["models"][name]["train"])
    options.update(data=str(ROOT/cfg["dataset"]["root"]/"data.yaml"), seed=common["seed"],
                   imgsz=common["input_size"][0], epochs=common["epochs"], batch=common["batch_size"],
                   patience=common["patience"], workers=common["workers"], device=0,
                   deterministic=True, project=str(directory.parent), name=directory.name,
                   exist_ok=True, rect=False, save=True)
    model.train(**options)
    best = max(history, key=lambda row:row["fitness"])
    return dict(epochs_ending=max(r["epoch"] for r in history), best_epoch=best["epoch"],
                checkpoint="weights/best.pt", hyperparameters=details,
                early_stop_monitor="ultralytics_validation_fitness", parameter_count=details["parameter_count"])


def train_rfdetr(cfg, name, directory, torch):
    from pytorch_lightning import Callback
    from rfdetr import RFDETRNano
    import rfdetr.training as training
    details, history = {}, []

    class Record(Callback):
        def on_train_start(self, trainer, module):
            details.update(runtime_hyperparameters(module, trainer.optimizers[0],
                           trainer.lr_scheduler_configs[0].scheduler if trainer.lr_scheduler_configs else None,
                           dict(train_options=options, model_config=model.model_config.model_dump(mode="json"))))
            details["precision"] = trainer.precision
            details["gradient_accumulation_steps"] = trainer.accumulate_grad_batches
            save_json(directory/"applied_hyperparameters.json", details)

        def on_train_epoch_end(self, trainer, module):
            metric = trainer.callback_metrics.get("val/ema_mAP_50_95", trainer.callback_metrics.get("val/mAP_50_95"))
            if metric is None:
                raise RuntimeError("RF-DETR did not publish the validation mAP metric")
            history.append(dict(epoch=trainer.current_epoch+1, val_map50_95=float(metric)))
            save_json(directory/"epoch_history.json", history)

    original_build = training.build_trainer

    def build(*args, **kwargs):
        details["resolved_train_config"] = args[0].model_dump(mode="json")
        trainer = original_build(*args, **kwargs)
        trainer.callbacks.append(Record())
        return trainer

    model = RFDETRNano(resolution=704, device="cuda", num_classes=1,
                       num_select=cfg["evaluation"]["max_detections"])
    details["initial_weights_sha256"] = digest(model.model_config.pretrain_weights)
    common = cfg["common"]
    options = dict(cfg["models"][name]["train"])
    options.update(dataset_dir=str(ROOT/cfg["dataset"]["root"]), dataset_file="yolo",
                   output_dir=str(directory), epochs=common["epochs"], seed=common["seed"],
                   batch_size=common["batch_size"], num_workers=common["workers"],
                   resolution=704, device="cuda", early_stopping=True,
                   early_stopping_patience=common["patience"])
    training.build_trainer = build
    try:
        model.train(**options)
    finally:
        training.build_trainer = original_build
    details["native_training_config"] = json.loads((directory/"training_config.json").read_text())
    save_json(directory/"applied_hyperparameters.json", details)
    checkpoint = directory/"checkpoint_best_total.pth"
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    return dict(epochs_ending=max(row["epoch"] for row in history), best_epoch=int(saved["epoch"])+1,
                checkpoint=checkpoint.name, hyperparameters=details,
                early_stop_monitor="val_mAP50_95", parameter_count=details["parameter_count"])


def execute_training(cfg, name, run):
    import numpy as np
    import torch
    env = environment(torch)
    common = cfg["common"]
    random.seed(common["seed"])
    np.random.seed(common["seed"])
    torch.manual_seed(common["seed"])
    torch.cuda.manual_seed_all(common["seed"])
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    directory = run/"training"
    directory.mkdir()  # Existing training, even failed training, must never be overwritten.
    save_json(directory/"environment.json", env)
    save_json(directory/"status.json", dict(status="running"))
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    framework = cfg["models"][name]["framework"]
    try:
        expected = {"yolo":("ultralytics","8.4.152"), "rfdetr":("rfdetr","1.11.2")}
        if framework in expected:
            package, version = expected[framework]
            if env["packages"].get(package) != version:
                raise RuntimeError(f"Expected {package}=={version}")
        if framework == "yolo":
            result = train_yolo(cfg, name, directory, torch)
        elif framework == "rfdetr":
            result = train_rfdetr(cfg, name, directory, torch)
        else:
            result = train_vendor(cfg, name, directory, torch)
        torch.cuda.synchronize()
        checkpoint = directory/result["checkpoint"]
        result.update(total_training_seconds=time.perf_counter()-start,
                      peak_vram_bytes=torch.cuda.max_memory_allocated(), gpu=env["gpu"],
                      model_size_bytes=checkpoint.stat().st_size, checkpoint_sha256=digest(checkpoint))
        save_json(directory/"training_summary.json", result)
        save_json(directory/"status.json", dict(status="complete"))
    except Exception as error:
        save_json(directory/"status.json", dict(status="failed", error=str(error)))
        raise


def predictor(cfg, name, checkpoint, directory, torch):
    """Return a PIL RGB -> canonical class-0 xyxy/score callable, in fp32."""
    framework = cfg["models"][name]["framework"]
    evaluation = cfg["evaluation"]
    if framework == "yolo":
        from ultralytics import YOLO
        model = YOLO(str(checkpoint))

        def predict(image):
            result = model.predict(image, imgsz=704, device=0, half=False, rect=False,
                                   conf=evaluation["ap_score_floor"], iou=evaluation["nms_iou"],
                                   max_det=evaluation["max_detections"], verbose=False)[0]
            return [dict(bbox=box, score=score, category_id=int(category)) for box,score,category in
                    zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist())]
        return predict
    if framework == "rfdetr":
        from rfdetr import RFDETR
        model = RFDETR.from_checkpoint(str(checkpoint), device="cuda",
                                      num_select=evaluation["max_detections"])
        model.model.model.float().eval()
        if model.model_config.resolution != 704:
            raise RuntimeError("RF-DETR checkpoint resolution is not 704")

        def predict(image):
            result = model.predict(image, threshold=evaluation["ap_score_floor"])
            # The pinned YOLO loader preserves zero-based foreground IDs.
            return [dict(bbox=box.tolist(), score=float(score), category_id=int(category))
                    for box,score,category in zip(result.xyxy,result.confidence,result.class_id)]
        return predict
    vendor, _ = vendor_config(cfg, name, directory, training=False)
    model = vendor.model
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    weights = state["ema"]["module"] if state.get("ema") else state["model"]
    model.load_state_dict(weights, strict=True)
    model = model.to("cuda").float().eval()
    postprocessor = vendor.postprocessor.to("cuda").eval()
    import numpy as np

    def predict(image):
        resized = image.resize((704,704))
        tensor = torch.from_numpy(np.asarray(resized).copy()).permute(2,0,1).float().div(255).unsqueeze(0).cuda()
        sizes = torch.tensor([[image.width,image.height]], device="cuda")
        result = postprocessor(model(tensor), sizes)[0]
        return [dict(bbox=box, score=score, category_id=int(category)) for box,score,category in
                zip(result["boxes"].cpu().tolist(),result["scores"].cpu().tolist(),result["labels"].cpu().tolist())]
    return predict
