#!/usr/bin/env python3
"""Run and collect Phase 2 augmentation comparisons for the selected Phase 1 models."""
import argparse
import copy
import csv
import json
import os
import shlex
import subprocess
from pathlib import Path

import yaml

import evaluate_models
import train_models

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("yolo11n", "yolov8n", "rfdetr_n", "dfine_n")
CONDITIONS = ("baseline", "spatial", "photometric", "combined")
RESULTS = ROOT / "results/phase2"
METRICS = {
    "map50": "validation_map50",
    "precision": "validation_precision",
    "recall": "validation_recall",
    "f1": "validation_f1",
    "correct_prediction_rate": "test_correct_predictions_percent",
    "inference_ms_per_image": "test_inference_ms_per_image",
}


def selected_phase1():
    path = ROOT / "records/phase1/model_comparison.csv"
    with path.open(newline="") as stream:
        rows = {row["model"]: row for row in csv.DictReader(stream)}
    missing = set(MODELS) - rows.keys()
    if missing:
        raise ValueError(f"Selected Phase 1 models missing from {path}: {sorted(missing)}")
    output = {}
    for name in MODELS:
        detail = ROOT / "experiments/phase1" / name / "evaluation/model_screening_summary.json"
        row = json.loads(detail.read_text())
        if row["model"] != name or str(row["checkpoint"]) != rows[name]["checkpoint"]:
            raise ValueError(f"Phase 1 summary disagrees with comparison CSV: {name}")
        output[name] = row
    return output


def condition_config(name, condition):
    path = ROOT / "configs/phase2" / name / f"{condition}.yaml"
    value = yaml.safe_load(path.read_text())
    if value["model"] != name or value["condition"] != condition:
        raise ValueError(f"Invalid Phase 2 config: {path}")
    return value


def prepare(name, condition):
    if condition == "baseline":
        raise ValueError("Baseline reuses Phase 1 and must not be trained")
    phase1 = selected_phase1()[name]
    spec = condition_config(name, condition)
    cfg = yaml.safe_load((ROOT / "configs/phase1/common.yaml").read_text())
    cfg["phase2"] = True
    cfg["output_dir"] = f"experiments/phase2/{condition}"
    cfg["models"] = {name: copy.deepcopy(cfg["models"][name])}
    model = cfg["models"][name]
    source = ROOT / model["config"]
    native = yaml.safe_load(source.read_text())
    framework = model["framework"]
    if framework == "dfine":
        native["train_dataloader"]["dataset"]["transforms"]["ops"] = spec["native"]["ops"]
    else:
        native.update(spec["native"])
    directory = ROOT / cfg["output_dir"] / name
    directory.mkdir(parents=True, exist_ok=True)
    native_path = directory / "phase2_native.yaml"
    if "__include__" in native:
        native["__include__"] = [os.path.relpath((source.parent / item).resolve(), directory)
                                 for item in native["__include__"]]
    native_path.write_text(yaml.safe_dump(native, sort_keys=False))
    model["config"] = str(native_path.relative_to(ROOT))
    model["weights"] = phase1["training_hyperparameters"]["model"]["weights"]
    # Compare training from the same pretrained checkpoint, not a continued Phase 1 run.
    return cfg


def docker_command(name, condition, task):
    framework = selected_phase1()[name]["framework"]
    service = "yolo-trainer" if framework == "yolo" else "trainer"
    return ["docker", "compose", "-f", str(ROOT / "docker" / framework / "docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", service, "python", "-u",
            "/workspace/scripts/phase2.py", task, "--model", name,
            "--condition", condition, "--inside-docker"]


def run_train(name, condition, inside):
    cfg = prepare(name, condition)
    if inside:
        train_models.train_inside_docker(cfg, name)
    else:
        subprocess.run(docker_command(name, condition, "train"), check=True)


def run_evaluate(name, condition, inside):
    cfg = prepare(name, condition)
    _, ev = evaluate_models.settings()
    if inside:
        evaluate_models.evaluate(cfg, ev, name)
    else:
        evaluate_models.training_record(cfg, name)
        subprocess.run(docker_command(name, condition, "evaluate"), check=True)


def run_all(models, execute):
    selected_phase1()
    for name in models:
        for condition in CONDITIONS[1:]:
            condition_config(name, condition)
    jobs = [(name, condition) for name in models for condition in CONDITIONS[1:]]
    for index, (name, condition) in enumerate(jobs, 1):
        print(f"[{index}/{len(jobs)}] {name} / {condition}", flush=True)
        if execute:
            run_train(name, condition, inside=False)
            run_evaluate(name, condition, inside=False)
        else:
            print(shlex.join(docker_command(name, condition, "train")))
            print(shlex.join(docker_command(name, condition, "evaluate")))
    if execute:
        collect()
    else:
        print(shlex.join(["python3", str(Path(__file__).resolve()), "collect"]))


def collect():
    baseline = selected_phase1()
    summary_rows, delta_rows = [], []
    RESULTS.mkdir(parents=True, exist_ok=True)
    for name in MODELS:
        details = {"model": name, "phase1_comparison": "records/phase1/model_comparison.csv",
                   "conditions": {}}
        for condition in CONDITIONS:
            condition_config(name, condition)
            if condition == "baseline":
                row = baseline[name]
                status = "reused_phase1"
            else:
                path = ROOT / "experiments/phase2" / condition / name / "evaluation/model_screening_summary.json"
                row = json.loads(path.read_text()) if path.is_file() else None
                if row is not None:
                    cfg = prepare(name, condition)
                    folder, _, checkpoint = evaluate_models.training_record(cfg, name)
                    if set(row) != set(evaluate_models.FIELDS) or row["model"] != name:
                        raise ValueError(f"Invalid Phase 2 summary: {path}")
                    if row["checkpoint"] != str(checkpoint.relative_to(ROOT)) or row["model_size_bytes"] != checkpoint.stat().st_size:
                        raise ValueError(f"Phase 2 summary checkpoint disagrees with run record: {path}")
                status = "complete" if row is not None else "pending"
            summary_rows.append({"model": name, "condition": condition, "status": status,
                                 **({key: row.get(key) for key in evaluate_models.FIELDS} if row else {})})
            deltas = {}
            for metric, key in METRICS.items():
                current, reference = (row or {}).get(key), baseline[name].get(key)
                deltas[f"delta_{metric}"] = current - reference if current is not None and reference is not None else None
            ms = (row or {}).get("test_inference_ms_per_image")
            ref_ms = baseline[name].get("test_inference_ms_per_image")
            deltas["delta_inference_speed_percent"] = (100 * (ref_ms / ms - 1)
                                                       if ms and ref_ms else None)
            delta_row = {"model": name, "condition": condition, "status": status, **deltas}
            delta_rows.append(delta_row)
            details["conditions"][condition] = {"status": status, "config": f"configs/phase2/{name}/{condition}.yaml",
                                                  "metrics": row, "delta_from_baseline": deltas}
        folder = RESULTS / name
        folder.mkdir(exist_ok=True)
        (folder / "details.json").write_text(json.dumps(details, indent=2, allow_nan=False) + "\n")
    write_csv(RESULTS / "augmentation_summary.csv",
              ("model", "condition", "status", *(key for key in evaluate_models.FIELDS if key != "model")), summary_rows)
    write_csv(RESULTS / "augmentation_delta.csv", tuple(delta_rows[0]), delta_rows)


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("train", "evaluate", "collect", "run-all"))
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--condition", choices=CONDITIONS[1:])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.task == "collect":
        collect()
        return
    if args.task == "run-all":
        if args.inside_docker or args.condition:
            parser.error("run-all is a host command; --condition is not used")
        run_all((args.model,) if args.model else MODELS, args.execute)
        return
    if not args.model or not args.condition:
        parser.error("train/evaluate require --model and --condition")
    if not args.execute and not args.inside_docker:
        print(shlex.join(docker_command(args.model, args.condition, args.task)))
    elif args.task == "train":
        run_train(args.model, args.condition, args.inside_docker)
    else:
        run_evaluate(args.model, args.condition, args.inside_docker)


if __name__ == "__main__":
    main()
