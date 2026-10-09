"""Shared result schema and immutable run metadata; no model imports."""
import csv
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_NAMES = ("yolov8n", "yolo11n", "yolo26n", "dfine_n", "deim_dfine_n", "rfdetr_n", "rtdetrv2_s")
FIELDS = (
    "schema_version", "dataset", "dataset_manifest_sha256", "model", "run_id", "eval_id",
    "checkpoint_sha256", "gpu", "seed", "input_size", "batch_size", "training_hyperparameters",
    "epochs_ending", "best_epoch", "total_training_seconds", "val_map50", "val_map50_95",
    "val_precision", "val_recall", "val_f1_peak", "val_f1_confidence", "val_tp", "val_fp", "val_fn",
    "test_correct_predictions_percent", "test_image_exact_match_percent", "test_map50", "test_map50_95",
    "test_tp", "test_fp", "test_fn", "test_inference_ms_per_image", "test_average_confidence",
    "test_confidence_threshold", "matching_iou_threshold", "model_size_bytes", "parameter_count",
    "peak_vram_bytes", "evaluation_precision", "speed_protocol",
)


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise ValueError("Run/evaluation ID must be 1..100 safe filename characters")
    return value


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            result.update(chunk)
    return result.hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str)+"\n")


def load_config(path):
    cfg = yaml.safe_load(Path(path).read_text())
    common = cfg["common"]
    fixed = dict(seed=42, input_size=[704,704], epochs=100, batch_size=16, early_stopping=True, patience=20, gpu="L4")
    for key, value in fixed.items():
        if common.get(key) != value:
            raise ValueError(f"Phase 1 requires {key}={value!r}")
    if common["min_delta"] != 0:
        raise ValueError("Phase 1 uses min_delta=0")
    if cfg["dataset"]["root"] != "dataset" or cfg["dataset"]["split_dirs"] != {"train":"train","val":"valid","test":"test"}:
        raise ValueError("Phase 1 uses detection/dataset and the existing train/valid/test split")
    if set(cfg["models"]) != set(MODEL_NAMES):
        raise ValueError("Config must contain all seven screening models")
    evaluation = cfg["evaluation"]
    for key in ("confidence", "match_iou", "ap_score_floor", "nms_iou"):
        if not 0 < evaluation[key] <= 1:
            raise ValueError(f"Invalid evaluation {key}")
    if evaluation["ap_score_floor"] > evaluation["confidence"]:
        raise ValueError("AP score floor must not exceed test confidence")
    if not 0 < evaluation["f1_confidence_step"] <= 1:
        raise ValueError("Invalid F1 sweep step")
    if evaluation["warmup"] < 1 or evaluation["repeats"] < 1 or evaluation["max_detections"] != 100:
        raise ValueError("Warmup/repeats must be positive; COCO max detections must be 100")
    if evaluation["precision"] != "fp32":
        raise ValueError("Phase 1 evaluation uses fp32")
    for name, model in cfg["models"].items():
        forbidden = set(model.get("train", {})) & {"seed", "epochs", "batch_size", "imgsz", "resolution", "patience", "early_stopping", "device", "dataset_dir", "output_dir", "data"}
        if forbidden:
            raise ValueError(f"{name} overrides shared conditions: {sorted(forbidden)}")
        if model.get("train", {}).get("multi_scale", False):
            raise ValueError("Multi-scale violates fixed input size")
        if model.get("train", {}).get("grad_accum_steps", 1) != 1:
            raise ValueError("Effective batch must remain 16")
        if model.get("train", {}).get("nbs", 16) != 16:
            raise ValueError("YOLO nominal batch must be 16 to avoid extra gradient accumulation")
    return cfg


def verify_dataset(cfg):
    dataset = ROOT/cfg["dataset"]["root"]
    manifest = ROOT/cfg["dataset"]["manifest"]
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        path = dataset/row["path"]
        if not path.is_file() or digest(path) != row["sha256"]:
            raise ValueError(f"Dataset freeze mismatch: {path}")
    relevant = {str(p.relative_to(dataset)) for part in ("images", "labels", "annotations")
                for p in (dataset/part).rglob("*") if p.is_file()}
    relevant.add("data.yaml")
    if relevant != {r["path"] for r in rows}:
        raise ValueError("Dataset files were added/removed since Phase 0")
    counts = {}
    for split, directory in cfg["dataset"]["split_dirs"].items():
        coco = json.loads((dataset/"annotations"/f"instances_{directory}.json").read_text())
        if len(coco["categories"]) != 1 or coco["categories"][0]["name"] != "pumpkin":
            raise ValueError("Phase 1 expects one pumpkin category")
        if any(a.get("iscrowd", 0) for a in coco["annotations"]):
            raise ValueError("Crowd annotations require an explicit matching policy")
        counts[split] = len(coco["images"])
    if sum(counts.values()) != cfg["dataset"]["observed_images"]:
        raise ValueError("Dataset image count differs from screening config")
    return dict(manifest_sha256=digest(manifest), image_counts=counts,
                freeze_notes="Phase 0: 417 vs expected 416 images; 675 unresolved dHash candidate pairs")


def environment(torch):
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Phase 1 requires exactly one visible CUDA GPU")
    gpu = torch.cuda.get_device_name(0)
    if not re.search(r"\bL4\b", gpu):
        raise RuntimeError(f"Phase 1 requires L4; detected {gpu}")
    packages = {}
    for name in ("torch", "torchvision", "ultralytics", "rfdetr", "pycocotools", "numpy", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return dict(gpu=gpu, cuda=torch.version.cuda, cudnn=torch.backends.cudnn.version(), packages=packages,
                matmul_tf32=torch.backends.cuda.matmul.allow_tf32, cudnn_tf32=torch.backends.cudnn.allow_tf32)


def write_summary(directory, row):
    if set(row) != set(FIELDS):
        raise ValueError(f"Summary schema mismatch: {set(row)^set(FIELDS)}")
    save_json(directory/"model_screening_summary.json", row)
    with (directory/"model_screening_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict,list)) else v for k,v in row.items()})
