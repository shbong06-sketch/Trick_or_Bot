#!/usr/bin/env python3
"""Evaluate one Phase 1 checkpoint, or combine completed JSON results."""
import argparse
import csv
import importlib
import json
import math
import shlex
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VENDORS = {"dfine": ("/opt/dfine", "src"), "deim": ("/opt/deim", "engine"),
           "rtdetrv2": ("/opt/rtdetr/rtdetrv2_pytorch", "src")}
FIELDS = ("model", "framework", "checkpoint", "training_hyperparameters", "optimizer",
          "optimizer_param_groups", "scheduler", "ending_epochs", "total_training_seconds",
          "validation_map50", "validation_map50_95", "validation_precision", "validation_recall",
          "validation_f1", "validation_f1_peak", "validation_f1_confidence", "validation_tp",
          "validation_fp", "validation_fn", "test_map50", "test_map50_95", "test_tp",
          "test_fp", "test_fn", "test_correct_predictions_percent", "test_inference_ms_per_image",
          "test_average_confidence", "model_size_bytes", "parameter_count", "training_peak_vram_bytes",
          "operating_confidence", "matching_iou", "nms_iou", "ap_score_cutoff",
          "benchmark_precision", "benchmark_scope", "benchmark_warmup", "benchmark_repeats",
          "benchmark_batch_size")


def settings():
    cfg = yaml.safe_load((ROOT/"configs/phase1/common.yaml").read_text())
    ev = yaml.safe_load((ROOT/"configs/phase1/evaluation.yaml").read_text())
    for key in ("confidence", "matching_iou", "nms_iou", "ap_score_cutoff"):
        if not 0 < ev[key] < 1:
            raise ValueError(f"evaluation.yaml: {key} must be in (0, 1)")
    if ev["ap_score_cutoff"] >= ev["confidence"]:
        raise ValueError("AP cutoff must be below operating confidence")
    if ev["benchmark_batch_size"] != 1 or ev["benchmark_precision"] != "fp32":
        raise ValueError("Benchmark requires batch 1 and fp32")
    if ev["warmup"] < 0 or ev["repeats"] < 1:
        raise ValueError("Invalid benchmark warmup/repeats")
    return cfg, ev


def training_record(cfg, name):
    folder = ROOT/cfg["output_dir"]/name
    path = folder/"run_info.json"
    if not path.is_file():
        raise ValueError(f"Missing {path}; restore the training run_info.json")
    info = json.loads(path.read_text())
    required = ("training", "epochs_ending", "total_training_seconds", "optimizer",
                "optimizer_param_groups", "scheduler", "parameter_count", "best_checkpoint")
    missing = [key for key in required if info.get(key) is None]
    if info.get("status") != "complete" or missing:
        raise ValueError(f"{name}: training record incomplete (status={info.get('status')}, "
                         f"missing={missing}). Finish the training run or restore only its missing "
                         "run_info.json fields from the original run; do not infer them.")
    checkpoint = folder/info["best_checkpoint"]
    if not checkpoint.is_file():
        raise ValueError(f"Missing recorded best checkpoint: {checkpoint}")
    if not (folder/"config.yaml").is_file():
        raise ValueError(f"Missing applied training config: {folder/'config.yaml'}")
    return folder, info, checkpoint


def docker_command(cfg, name):
    framework = cfg["models"][name]["framework"]
    service = "yolo-trainer" if framework == "yolo" else "trainer"
    return ["docker", "compose", "-f", str(ROOT/"docker"/framework/"docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", service, "python", "-u",
            "/workspace/scripts/evaluate_models.py", "--model", name, "--execute", "--inside-docker"]


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2-x1)*max(0, y2-y1)
    aa, bb = max(0, a[2]-a[0])*max(0, a[3]-a[1]), max(0, b[2]-b[0])*max(0, b[3]-b[1])
    return intersection/(aa+bb-intersection) if aa+bb-intersection else 0.0


def counts(images, truth, predictions, threshold, match_iou):
    tp = fp = fn = 0
    for image in images:
        image_id = image["id"]
        gt = defaultdict(list)
        for item in truth[image_id]:
            gt[item["category_id"]].append(item["bbox"])
        pred = defaultdict(list)
        for item in predictions[image_id]:
            if item["score"] >= threshold:
                pred[item["category_id"]].append(item)
        for category in set(gt) | set(pred):
            used = set()
            for item in sorted(pred[category], key=lambda x: -x["score"]):
                candidates = [(iou(item["bbox"], box), j) for j, box in enumerate(gt[category]) if j not in used]
                overlap, j = max(candidates, default=(0, None))
                if overlap >= match_iou:
                    tp += 1
                    used.add(j)
                else:
                    fp += 1
            fn += len(gt[category])-len(used)
    return tp, fp, fn


def prf(tp, fp, fn):
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0
    return precision, recall, f1


def f1_peak(images, truth, predictions, match_iou):
    # A descending threshold only adds predictions. Match each one once, then
    # score the complete group at every observed confidence boundary.
    gt = defaultdict(list)
    items = []
    total_gt = 0
    for image in images:
        image_id = image["id"]
        for item in truth[image_id]:
            gt[image_id, item["category_id"]].append(item["bbox"])
            total_gt += 1
        for item in predictions[image_id]:
            items.append((item["score"], image_id, item["category_id"], item["bbox"]))
    if not items:
        return 0.0, 1.0
    items.sort(key=lambda item: -item[0])  # Stable order preserves same-score ties.
    best = (0.0, math.nextafter(items[0][0], math.inf))
    used = defaultdict(set)
    tp = fp = index = 0
    while index < len(items):
        threshold = items[index][0]
        while index < len(items) and items[index][0] == threshold:
            _, image_id, category, box = items[index]
            key = image_id, category
            candidates = [(iou(box, target), j) for j, target in enumerate(gt[key])
                          if j not in used[key]]
            overlap, j = max(candidates, default=(0, None))
            if overlap >= match_iou:
                tp += 1
                used[key].add(j)
            else:
                fp += 1
            index += 1
        fn = total_gt-tp
        f1 = prf(tp, fp, fn)[2]
        if (f1, threshold) > best:
            best = f1, threshold
    return best


def load_split(dataset, split):
    data = json.loads((dataset/"annotations"/f"instances_{split}.json").read_text())
    categories = [c for c in data["categories"] if c["name"].lower() == "pumpkin"]
    if len(categories) != 1 or len(data["categories"]) != 1:
        raise ValueError(f"{split}: expected one pumpkin category")
    category_id = categories[0]["id"]
    images = sorted(data["images"], key=lambda x: x["id"])
    truth = {image["id"]: [] for image in images}
    for ann in data["annotations"]:
        if ann["category_id"] != category_id or ann.get("iscrowd", 0):
            continue
        x, y, w, h = ann["bbox"]
        truth[ann["image_id"]].append({"bbox": [x, y, x+w, y+h], "category_id": category_id})
    for image in images:
        if not (dataset/"images"/split/image["file_name"]).is_file():
            raise ValueError(f"Missing image: {image['file_name']}")
    return data, images, truth, category_id


def coco_ap(data, images, predictions, cutoff):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    import contextlib
    import io
    if not any(not ann.get("iscrowd", 0) for ann in data["annotations"]):
        return None, None
    coco = COCO()
    coco.dataset = data
    with contextlib.redirect_stdout(io.StringIO()):
        coco.createIndex()
        results = []
        for image in images:
            for pred in predictions[image["id"]]:
                if pred["score"] >= cutoff:
                    x1, y1, x2, y2 = pred["bbox"]
                    results.append(dict(image_id=image["id"], category_id=pred["category_id"],
                                        bbox=[x1, y1, x2-x1, y2-y1], score=pred["score"]))
        if not results:
            return 0.0, 0.0
        detected = coco.loadRes(results)
        evaluator = COCOeval(coco, detected, "bbox")
        evaluator.params.imgIds = [image["id"] for image in images]
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()
    return (float(evaluator.stats[1]) if evaluator.stats[1] >= 0 else None,
            float(evaluator.stats[0]) if evaluator.stats[0] >= 0 else None)


def normalize(rows, category_id, width, height, cutoff):
    output = []
    for box, score, label in rows:
        score = float(score)
        if int(label) != 0 or score < cutoff:
            continue
        coords = [float(box[0]), float(box[1]), float(box[2]), float(box[3])]
        coords = [max(0.0, min(coords[0], width)), max(0.0, min(coords[1], height)),
                  max(0.0, min(coords[2], width)), max(0.0, min(coords[3], height))]
        if not math.isfinite(score) or not all(map(math.isfinite, coords)) or coords[2] <= coords[0] or coords[3] <= coords[1]:
            continue
        output.append(dict(bbox=coords, score=score, category_id=category_id))
    return output


def load_model(framework, folder, checkpoint):
    import torch
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    if framework == "yolo":
        from ultralytics import YOLO
        detector = YOLO(str(checkpoint))
        detector.model.float()
        return detector
    if framework == "rfdetr":
        from rfdetr import RFDETRNano
        detector = RFDETRNano(pretrain_weights=str(checkpoint), resolution=704, num_classes=1, device="cuda")
        detector.model.model.float()
        return detector
    location, package = VENDORS[framework]
    sys.path.insert(0, location)
    core = importlib.import_module(f"{package}.core")
    cfg = core.YAMLConfig(str(folder/"framework_config.yaml"))
    model, post = cfg.model, cfg.postprocessor
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    weights = state.get("model")
    if weights is None:
        raise ValueError(f"{checkpoint}: missing model state")
    model.load_state_dict(weights, strict=True)
    return model.float().cuda().eval(), post.cuda().eval()


def predict(model, framework, rgb, category_id, ev):
    import numpy as np
    import torch
    from PIL import Image
    height, width = rgb.shape[:2]
    if framework == "yolo":
        result = model.predict(source=rgb[:, :, ::-1].copy(), imgsz=704, rect=False,
                               conf=ev["ap_score_cutoff"], iou=ev["nms_iou"], device=0,
                               half=False, verbose=False)[0]
        boxes = result.boxes
        rows = zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(), boxes.cls.cpu().tolist())
    elif framework == "rfdetr":
        detections = model.predict(Image.fromarray(rgb), threshold=ev["ap_score_cutoff"],
                                   include_source_image=False)
        rows = zip(detections.xyxy, detections.confidence, detections.class_id)
    else:
        native, post = model
        resized = np.asarray(Image.fromarray(rgb).resize((704, 704), Image.Resampling.BILINEAR), dtype=np.float32)
        tensor = torch.from_numpy(resized).permute(2, 0, 1).unsqueeze(0).cuda().div_(255)
        size = torch.tensor([[width, height]], device="cuda")
        with torch.inference_mode():
            result = post(native(tensor), size)[0]
        rows = zip(result["boxes"].cpu().tolist(), result["scores"].cpu().tolist(),
                   result["labels"].cpu().tolist())
    return normalize(rows, category_id, width, height, ev["ap_score_cutoff"])


def read_rgb(dataset, split, image):
    import numpy as np
    from PIL import Image
    with Image.open(dataset/"images"/split/image["file_name"]) as source:
        rgb = np.asarray(source.convert("RGB"))
    if rgb.shape[1] != image["width"] or rgb.shape[0] != image["height"]:
        raise ValueError(f"Image dimensions disagree with COCO: {image['file_name']}")
    return rgb


def benchmark(model, framework, rgb_images, category_id, ev):
    import torch
    if not rgb_images:
        raise ValueError("Empty test split")
    for i in range(ev["warmup"]):
        predict(model, framework, rgb_images[i % len(rgb_images)], category_id, ev)
    torch.cuda.synchronize()
    elapsed = 0.0
    for _ in range(ev["repeats"]):
        for rgb in rgb_images:
            torch.cuda.synchronize()
            start = time.perf_counter()
            predict(model, framework, rgb, category_id, ev)
            torch.cuda.synchronize()
            elapsed += time.perf_counter()-start
    return 1000*elapsed/(ev["repeats"]*len(rgb_images))


def split_metrics(data, images, truth, predictions, ev, validation=False):
    tp, fp, fn = counts(images, truth, predictions, ev["confidence"], ev["matching_iou"])
    precision, recall, f1 = prf(tp, fp, fn)
    map50, map50_95 = coco_ap(data, images, predictions, ev["ap_score_cutoff"])
    result = dict(map50=map50, map50_95=map50_95, tp=tp, fp=fp, fn=fn,
                  confidence=ev["confidence"], matching_iou=ev["matching_iou"],
                  nms_iou=ev["nms_iou"], ap_score_cutoff=ev["ap_score_cutoff"])
    if validation:
        peak, threshold = f1_peak(images, truth, predictions, ev["matching_iou"])
        result.update(precision=precision, recall=recall, f1=f1, f1_peak=peak, f1_confidence=threshold)
    else:
        scores = [item["score"] for image in images for item in predictions[image["id"]]
                  if item["score"] >= ev["confidence"]]
        result.update(correct_predictions_percent=100*tp/(tp+fp+fn) if tp+fp+fn else 0.0,
                      average_confidence=sum(scores)/len(scores) if scores else None)
    return result


def summary(name, framework, info, checkpoint, applied, validation, test, ev):
    row = {key: None for key in FIELDS}
    row.update(model=name, framework=framework, checkpoint=str(checkpoint.relative_to(ROOT)),
               training_hyperparameters=applied, optimizer=info["optimizer"],
               optimizer_param_groups=info["optimizer_param_groups"], scheduler=info["scheduler"],
               ending_epochs=info["epochs_ending"], total_training_seconds=info["total_training_seconds"],
               model_size_bytes=checkpoint.stat().st_size, parameter_count=info["parameter_count"],
               training_peak_vram_bytes=info.get("peak_vram_bytes"),
               operating_confidence=ev["confidence"], matching_iou=ev["matching_iou"],
               nms_iou=ev["nms_iou"], ap_score_cutoff=ev["ap_score_cutoff"],
               benchmark_precision=ev["benchmark_precision"], benchmark_warmup=ev["warmup"],
               benchmark_repeats=ev["repeats"], benchmark_batch_size=ev["benchmark_batch_size"],
               benchmark_scope="decoded RGB -> preprocessing -> GPU transfer -> inference -> postprocessing -> CPU boxes; excludes file read, model load, matching, save")
    for key in ("map50", "map50_95", "precision", "recall", "f1", "f1_peak", "f1_confidence", "tp", "fp", "fn"):
        if key in validation:
            row["validation_"+key] = validation[key]
    for key in ("map50", "map50_95", "tp", "fp", "fn", "correct_predictions_percent", "inference_ms_per_image", "average_confidence"):
        if key in test:
            row["test_"+key] = test[key]
    return row


def write_row(path, row):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()})


def evaluate(cfg, ev, name):
    import torch
    folder, info, checkpoint = training_record(cfg, name)
    applied = yaml.safe_load((folder/"config.yaml").read_text())
    if "settings" not in applied or "training" not in applied:
        raise ValueError(f"Incomplete applied config: {folder/'config.yaml'}")
    if not torch.cuda.is_available() or not torch.cuda.get_device_name(0).endswith(cfg["training"]["gpu"]):
        raise RuntimeError("Evaluation requires the configured L4 GPU")
    framework = cfg["models"][name]["framework"]
    ev = dict(ev)
    if framework != "yolo":
        ev["nms_iou"] = None  # Query-based detectors do not run NMS.
    print(f"[{name}] loading best checkpoint", flush=True)
    model = load_model(framework, folder, checkpoint)
    dataset = ROOT/cfg["dataset"]
    metrics = {}
    for split in ("valid", "test"):
        data, images, truth, category_id = load_split(dataset, split)
        print(f"[{name}] {split}: predicting {len(images)} images", flush=True)
        predictions = {}
        rgb_images = []
        for index, image in enumerate(images, 1):
            rgb = read_rgb(dataset, split, image)
            if split == "test":
                rgb_images.append(rgb)
            predictions[image["id"]] = predict(model, framework, rgb, category_id, ev)
            if index % 20 == 0 or index == len(images):
                print(f"[{name}] {split}: {index}/{len(images)} images", flush=True)
        print(f"[{name}] {split}: computing metrics", flush=True)
        result = split_metrics(data, images, truth, predictions, ev, split == "valid")
        if split == "test":
            print(f"[{name}] test: benchmarking {ev['warmup']} warmup + "
                  f"{ev['repeats']} passes", flush=True)
            result["inference_ms_per_image"] = benchmark(model, framework, rgb_images, category_id, ev)
            result.update(benchmark_precision="fp32", benchmark_warmup=ev["warmup"],
                          benchmark_repeats=ev["repeats"], benchmark_batch_size=1)
        metrics[split] = result
    row = summary(name, framework, info, checkpoint, applied, metrics["valid"], metrics["test"], ev)
    output = folder/"evaluation"
    output.mkdir(exist_ok=True)
    (output/"validation_metrics.json").write_text(json.dumps(metrics["valid"], indent=2)+"\n")
    (output/"test_metrics.json").write_text(json.dumps(metrics["test"], indent=2)+"\n")
    (output/"model_screening_summary.json").write_text(json.dumps(row, indent=2)+"\n")
    write_row(output/"model_screening_summary.csv", row)
    print(output)


def collect(cfg):
    rows = []
    for name in cfg["models"]:
        folder = ROOT/cfg["output_dir"]/name
        path = folder/"evaluation/model_screening_summary.json"
        if not path.is_file():
            continue
        try:
            _, _, checkpoint = training_record(cfg, name)
        except ValueError as error:
            print(f"Skipping {name}: {error}", file=sys.stderr)
            continue
        if path.stat().st_mtime_ns < max(checkpoint.stat().st_mtime_ns,
                                         (folder/"run_info.json").stat().st_mtime_ns,
                                         (folder/"config.yaml").stat().st_mtime_ns):
            print(f"Skipping stale evaluation for {name}: {path}", file=sys.stderr)
            continue
        row = json.loads(path.read_text())
        if set(row) != set(FIELDS) or row["model"] != name:
            raise ValueError(f"Invalid summary schema or model name: {path}")
        if row["model_size_bytes"] != checkpoint.stat().st_size:
            raise ValueError(f"Checkpoint size changed since evaluation: {path}")
        rows.append(row)
    if not rows:
        raise ValueError("No completed model screening summaries found")
    path = ROOT/"records/phase1/model_comparison.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})
    print(f"{path}: {len(rows)} models")


def main():
    cfg, ev = settings()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--model", choices=cfg["models"])
    group.add_argument("--collect", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.collect:
        collect(cfg)
    elif not args.execute:
        print(shlex.join(docker_command(cfg, args.model)))
    elif args.inside_docker:
        evaluate(cfg, ev, args.model)
    else:
        training_record(cfg, args.model)
        subprocess.run(docker_command(cfg, args.model), check=True)


if __name__ == "__main__":
    main()
