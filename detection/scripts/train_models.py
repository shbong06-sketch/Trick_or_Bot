#!/usr/bin/env python3
"""Train one model in its prebuilt Docker environment; --execute starts training."""
import argparse
import copy
import importlib
import importlib.metadata
import json
import math
import random
import shlex
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VENDORS = {
    "dfine": ("/opt/dfine", "src"),
    "deim": ("/opt/deim", "engine"),
    "rtdetrv2": ("/opt/rtdetr/rtdetrv2_pytorch", "src"),
}


def save_info(directory, info):
    (directory/"run_info.json").write_text(json.dumps(info, indent=2, default=str, allow_nan=False)+"\n")


def save_config(directory, common, model, settings):
    value = dict(training=common, model=model, settings=settings)
    value = json.loads(json.dumps(value, default=str))
    (directory/"config.yaml").write_text(yaml.safe_dump(value, sort_keys=False))


def record_optimizer(info, model, optimizer, scheduler=None):
    info.update(parameter_count=sum(p.numel() for p in model.parameters()),
                optimizer=type(optimizer).__name__,
                optimizer_param_groups=[{k:v for k,v in group.items() if k != "params"} for group in optimizer.param_groups],
                scheduler=type(scheduler).__name__ if scheduler is not None else None)


class EarlyStop:
    def __init__(self, patience):
        self.patience, self.best, self.bad_epochs = patience, -math.inf, 0

    def update(self, metric):
        if not math.isfinite(metric):
            raise ValueError("Non-finite validation mAP")
        improved = metric > self.best
        if improved:
            self.best, self.bad_epochs = metric, 0
        else:
            self.bad_epochs += 1
        return improved, self.bad_epochs >= self.patience


class TrainingFinished(Exception):
    """Normal patience-based termination of the vendor fit loop."""


def train_yolo(cfg, model, directory, info, torch):
    from ultralytics import YOLO
    common = cfg["training"]
    options = yaml.safe_load((ROOT/model["config"]).read_text())
    options.update(data=str(ROOT/cfg["dataset"]/"data.yaml"), seed=common["seed"],
                   imgsz=common["input_size"][0], epochs=common["epochs"], batch=common["batch_size"],
                   patience=common["patience"] if common["early_stopping"] else 0,
                   workers=common["workers"], device=0, project=str(directory.parent),
                   name=directory.name, exist_ok=True)
    detector = YOLO(model["weights"])
    save_config(directory, common, model, options)

    def started(trainer):
        record_optimizer(info, trainer.model, trainer.optimizer, trainer.scheduler)
        save_config(directory, common, model, vars(trainer.args))
        save_info(directory, info)

    def epoch_ended(trainer):
        info["epochs_ending"] = trainer.epoch+1

    detector.add_callback("on_train_start", started)
    detector.add_callback("on_fit_epoch_end", epoch_ended)
    info["early_stop_monitor"] = "ultralytics_validation_fitness"
    detector.train(**options)
    info["best_checkpoint"] = "weights/best.pt"


def train_rfdetr(cfg, model, directory, info, torch):
    from pytorch_lightning import Callback
    from rfdetr import RFDETRNano
    import rfdetr.training as training
    common = cfg["training"]
    options = yaml.safe_load((ROOT/model["config"]).read_text())
    options.update(dataset_dir=str(ROOT/cfg["dataset"]), output_dir=str(directory), seed=common["seed"],
                   epochs=common["epochs"], batch_size=common["batch_size"], num_workers=common["workers"],
                   resolution=common["input_size"][0], device="cuda", early_stopping=common["early_stopping"],
                   early_stopping_patience=common["patience"], run_test=False)
    detector = RFDETRNano(resolution=common["input_size"][0], num_classes=1, device="cuda")
    save_config(directory, common, model, options)

    class Record(Callback):
        def on_train_start(self, trainer, module):
            scheduler = trainer.lr_scheduler_configs[0].scheduler if trainer.lr_scheduler_configs else None
            record_optimizer(info, module, trainer.optimizers[0], scheduler)
            info["precision"] = trainer.precision
            save_info(directory, info)

        def on_train_epoch_end(self, trainer, module):
            info["epochs_ending"] = trainer.current_epoch+1

    original_build = training.build_trainer

    def build(*args, **kwargs):
        save_config(directory, common, model, dict(train=args[0].model_dump(mode="json"),
                                                  architecture=args[1].model_dump(mode="json")))
        trainer = original_build(*args, **kwargs)
        trainer.callbacks.append(Record())
        return trainer

    training.build_trainer = build
    info["early_stop_monitor"] = "validation_ema_mAP50_95"
    try:
        detector.train(**options)
    finally:
        training.build_trainer = original_build
    info["best_checkpoint"] = "checkpoint_best_total.pth"


def train_vendor(cfg, model, directory, info, torch):
    location, package = VENDORS[model["framework"]]
    sys.path.insert(0, location)
    core = importlib.import_module(f"{package}.core")
    module = importlib.import_module(f"{package}.solver.det_solver")
    common = cfg["training"]
    settings = copy.deepcopy(core.YAMLConfig(str(ROOT/model["config"])).yaml_cfg)
    settings.pop("__include__", None)
    settings.update(output_dir=str(directory), tuning=str(ROOT/model["weights"]),
                    device="cuda:0", use_amp=True, seed=common["seed"], eval_spatial_size=common["input_size"])
    settings["epochs" if model["framework"] == "dfine" else "epoches"] = common["epochs"]
    for split, loader in (("train", "train_dataloader"), ("valid", "val_dataloader")):
        data = settings[loader]
        data.update(total_batch_size=common["batch_size"], num_workers=common["workers"])
        data["dataset"].update(img_folder=str(ROOT/cfg["dataset"]/"images"/split),
                               ann_file=str(ROOT/cfg["dataset"]/"annotations"/f"instances_{split}.json"))
        for op in data["dataset"]["transforms"]["ops"]:
            if op["type"] == "Resize":
                op["size"] = common["input_size"]
    for backbone in ("HGNetv2", "PResNet"):
        if backbone in settings:
            settings[backbone]["pretrained"] = False
    save_config(directory, common, model, settings)
    native_path = directory/"framework_config.yaml"
    native_path.write_text(yaml.safe_dump(settings, sort_keys=False))
    solver = module.DetSolver(core.YAMLConfig(str(native_path)))
    stopper = EarlyStop(common["patience"])
    original_evaluate = module.evaluate
    info.update(epochs_ending=0, early_stop_monitor="validation_mAP50_95")

    def evaluate(*args, **kwargs):
        result = original_evaluate(*args, **kwargs)
        stats = result[0]["coco_eval_bbox"]
        info["epochs_ending"] += 1
        improved, stop = stopper.update(float(stats[0]))
        record_optimizer(info, solver.model, solver.optimizer, solver.lr_scheduler)
        if improved:
            # Save the evaluated model (EMA where enabled), not a different weight track.
            torch.save(dict(model=args[0].state_dict(), epoch=info["epochs_ending"]-1), directory/"best_phase1.pth")
            info["best_epoch"] = info["epochs_ending"]
        with (directory/"metrics.jsonl").open("a") as stream:
            stream.write(json.dumps(dict(epoch=info["epochs_ending"], map50_95=float(stats[0]), map50=float(stats[1])))+"\n")
        save_info(directory, info)
        if common["early_stopping"] and stop:
            raise TrainingFinished
        return result

    (directory/"metrics.jsonl").write_text("")
    module.evaluate = evaluate
    try:
        solver.fit()
    except TrainingFinished:
        print(f"Early stopping after {info['epochs_ending']} epochs")
    finally:
        module.evaluate = original_evaluate
        if getattr(solver, "writer", None):
            solver.writer.close()
    info["best_checkpoint"] = "best_phase1.pth"


def train_inside_docker(cfg, name):
    model, common = cfg["models"][name], cfg["training"]
    directory = ROOT/cfg["output_dir"]/name
    directory.mkdir(parents=True, exist_ok=True)
    info = dict(model=name, status="running", training=common)
    save_config(directory, common, model, yaml.safe_load((ROOT/model["config"]).read_text()))
    start = time.perf_counter()
    torch = None
    try:
        import numpy as np
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required")
        gpu = torch.cuda.get_device_name(0)
        if gpu.split()[-1] != common["gpu"]:
            raise RuntimeError(f"Expected {common['gpu']}, detected {gpu}")
        info.update(gpu=gpu, cuda=torch.version.cuda, packages={})
        for package in ("torch", "torchvision", "ultralytics", "rfdetr", "PyYAML"):
            try:
                info["packages"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                pass
        random.seed(common["seed"])
        np.random.seed(common["seed"])
        torch.manual_seed(common["seed"])
        torch.cuda.manual_seed_all(common["seed"])
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.cuda.reset_peak_memory_stats()
        save_info(directory, info)
        if model["framework"] == "yolo":
            train_yolo(cfg, model, directory, info, torch)
        elif model["framework"] == "rfdetr":
            train_rfdetr(cfg, model, directory, info, torch)
        else:
            train_vendor(cfg, model, directory, info, torch)
        torch.cuda.synchronize()
        checkpoint = directory/info["best_checkpoint"]
        info.update(status="complete", model_size_bytes=checkpoint.stat().st_size)
    except Exception as error:
        info.update(status="failed", error=str(error))
        raise
    finally:
        info["total_training_seconds"] = time.perf_counter()-start
        if torch is not None and torch.cuda.is_available():
            info["peak_vram_bytes"] = torch.cuda.max_memory_allocated()
        save_info(directory, info)


def docker_command(cfg, name):
    framework = cfg["models"][name]["framework"]
    service = "yolo-trainer" if framework == "yolo" else "trainer"
    return ["docker", "compose", "-f", str(ROOT/"docker"/framework/"docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", service, "python", "-u", "/workspace/scripts/train_models.py",
            "--model", name, "--execute", "--inside-docker"]


def launch(cfg, name):
    directory = ROOT/cfg["output_dir"]/name
    directory.mkdir(parents=True, exist_ok=True)
    save_info(directory, dict(model=name, status="starting"))
    try:
        with (directory/"training.log").open("w", encoding="utf-8") as log:
            with subprocess.Popen(docker_command(cfg, name), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace") as process:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
    except OSError as error:
        save_info(directory, dict(model=name, status="failed", error=str(error)))
        raise
    if code:
        info = json.loads((directory/"run_info.json").read_text())
        info.update(status="failed", exit_code=code)
        save_info(directory, info)
        raise SystemExit(code)


def main():
    cfg = yaml.safe_load((ROOT/"configs/phase1/common.yaml").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=cfg["models"], required=True)
    parser.add_argument("--execute", action="store_true", help="Start training in the prebuilt Docker image")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.execute:
        print(shlex.join(docker_command(cfg, args.model)))
    elif args.inside_docker:
        train_inside_docker(cfg, args.model)
    else:
        launch(cfg, args.model)


if __name__ == "__main__":
    main()
