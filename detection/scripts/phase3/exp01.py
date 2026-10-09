#!/usr/bin/env python3
"""Phase 3 experiment 01: compare AdamW and SGD for each YOLO model."""
import argparse
import csv
import json
import math
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_models
import train_models

SPEC_PATH = ROOT / "configs/phase3/exp01.yaml"
EXPERIMENTS = ROOT / "experiments/phase3"
RESULTS = ROOT / "results/phase3"
METRICS = ("validation_recall", "validation_f1", "validation_map50_95", "validation_map50")
TIMING = ("best_epoch", "time_to_best_seconds", "ending_epoch", "total_training_seconds")
FIELDS = ("experiment", "model", "step", "optimizer", "lr0", "momentum", "status", "selected",
          "inherited_from", "config", *METRICS, *TIMING)
DELTA_FIELDS = ("experiment", "model", "status", "baseline", *("delta_" + key for key in (*METRICS, *TIMING)))


def spec():
    value = yaml.safe_load(SPEC_PATH.read_text())
    if value["step"] != "optimizer" or set(value["runs"]) != {"001", "002"}:
        raise ValueError(f"Invalid experiment specification: {SPEC_PATH}")
    return value


def run_dir(model, experiment):
    return EXPERIMENTS / experiment / model


def prepare(model, experiment):
    plan = spec()
    if model not in plan["models"] or experiment not in plan["runs"]:
        raise ValueError(f"Unknown model or run: {model} {experiment}")
    baseline_path = ROOT / plan["baseline"].format(model=model)
    baseline = yaml.safe_load(baseline_path.read_text())
    if baseline != {"model": model, "condition": "baseline", "source_phase": "phase1",
                    "train": False, "recipe": "official_phase1_unchanged"}:
        raise ValueError(f"Phase 2 baseline changed: {baseline_path}")
    cfg = yaml.safe_load((ROOT / plan["base_training"]).read_text())
    original = cfg["models"][model]
    if original["config"] != plan["base_yolo"] or original["framework"] != "yolo":
        raise ValueError(f"Phase 1 YOLO settings changed for {model}")
    cfg["models"] = {model: original}
    cfg["output_dir"] = f"experiments/phase3/{experiment}"
    options = yaml.safe_load((ROOT / plan["base_yolo"]).read_text())
    options.update(plan["runs"][experiment])
    options.update(weight_decay=0.0005, cos_lr=False, nbs=cfg["training"]["batch_size"])
    directory = run_dir(model, experiment)
    directory.mkdir(parents=True, exist_ok=True)
    applied = {"experiment": experiment, "model": model, "step": "optimizer",
               "inherited_from": str(baseline_path.relative_to(ROOT)),
               "training": cfg["training"], "pretrained_weights": original["weights"],
               "evaluation": plan["evaluation"], "native": options}
    for filename, value in (("exp01_config.yaml", applied), ("native.yaml", options)):
        path = directory / filename
        if path.is_file() and yaml.safe_load(path.read_text()) != value:
            raise ValueError(f"Existing run has different settings: {path}")
        path.write_text(yaml.safe_dump(value, sort_keys=False))
    original["config"] = str((directory / "native.yaml").relative_to(ROOT))
    return cfg


def docker_command(task, model, experiment):
    return ["docker", "compose", "-f", str(ROOT / "docker/yolo/docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", "yolo-trainer", "python", "-u",
            "/workspace/scripts/phase3/exp01.py", task, "--model", model,
            "--experiment", experiment, "--inside-docker"]


def evaluate_valid(cfg, model):
    import torch
    directory, _, checkpoint = evaluate_models.training_record(cfg, model)
    if not torch.cuda.is_available() or not torch.cuda.get_device_name(0).endswith(cfg["training"]["gpu"]):
        raise RuntimeError("Configured L4 GPU is required")
    _, protocol = evaluate_models.settings()
    dataset = ROOT / cfg["dataset"]
    data, images, truth, category_id = evaluate_models.load_split(dataset, "valid")
    detector = evaluate_models.load_model("yolo", directory, checkpoint)
    predictions = {}
    for image in images:
        rgb = evaluate_models.read_rgb(dataset, "valid", image)
        predictions[image["id"]] = evaluate_models.predict(detector, "yolo", rgb, category_id, protocol)
    metrics = evaluate_models.split_metrics(data, images, truth, predictions, protocol, validation=True)
    output = directory / "evaluation"
    output.mkdir(exist_ok=True)
    (output / "validation_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")


def history_metrics(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"Empty epoch history: {path}")
    best = max(rows, key=lambda row: float(row["metrics/mAP50-95(B)"]))
    return {"best_epoch": int(best["epoch"]), "time_to_best_seconds": float(best["time"]),
            "ending_epoch": int(rows[-1]["epoch"])}


def baseline_metrics(model):
    detail = json.loads((ROOT / f"results/phase2/{model}/details.json").read_text())
    row = detail["conditions"]["baseline"]["metrics"]
    return {**{key: row[key] for key in METRICS},
            **history_metrics(ROOT / f"experiments/phase1/{model}/results.csv"),
            "total_training_seconds": row["total_training_seconds"]}


def measured(model, experiment):
    directory = run_dir(model, experiment)
    metrics_path = directory / "evaluation/validation_metrics.json"
    info_path = directory / "run_info.json"
    if not metrics_path.is_file() or not info_path.is_file():
        return None
    info = json.loads(info_path.read_text())
    if info.get("status") != "complete" or info.get("model") != model:
        raise ValueError(f"Incomplete training record: {info_path}")
    applied = yaml.safe_load((directory / "exp01_config.yaml").read_text())
    if applied["model"] != model or applied["experiment"] != experiment:
        raise ValueError(f"Run config mismatch: {directory}")
    expected = spec()["runs"][experiment]
    if any(applied["native"].get(key) != val for key, val in expected.items()):
        raise ValueError(f"Optimizer settings changed after training: {directory}")
    if info["training"] != applied["training"]:
        raise ValueError(f"Training settings disagree with run record: {directory}")
    validation = json.loads(metrics_path.read_text())
    protocol = yaml.safe_load((ROOT / spec()["evaluation"]).read_text())
    for key in ("confidence", "matching_iou", "nms_iou", "ap_score_cutoff"):
        if not math.isclose(validation[key], protocol[key]):
            raise ValueError(f"Evaluation protocol mismatch: {metrics_path}: {key}")
    value = {"validation_recall": validation["recall"], "validation_f1": validation["f1"],
             "validation_map50_95": validation["map50_95"], "validation_map50": validation["map50"],
             **history_metrics(directory / "results.csv"),
             "total_training_seconds": info["total_training_seconds"]}
    if not all(math.isfinite(float(v)) for v in value.values()):
        raise ValueError(f"Non-finite metrics: {directory}")
    if info["epochs_ending"] not in (value["ending_epoch"], value["ending_epoch"] + 1):
        raise ValueError(f"Epoch count mismatch: {directory}")
    return value


def rank(value):
    return (value["validation_map50_95"], value["validation_f1"],
            value["validation_recall"], value["validation_map50"],
            -value["time_to_best_seconds"], -value["total_training_seconds"])


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def collect():
    plan = spec()
    summary, deltas, selection = [], [], {}
    RESULTS.mkdir(parents=True, exist_ok=True)
    for model in plan["models"]:
        baseline = baseline_metrics(model)
        measured_runs = {number: measured(model, number) for number in plan["runs"]}
        complete = all(value is not None for value in measured_runs.values())
        winner = max(measured_runs, key=lambda number: rank(measured_runs[number])) if complete else None
        selection[model] = {"status": "complete" if complete else "pending",
                            "selected_experiment": winner,
                            "optimizer": plan["runs"][winner]["optimizer"] if winner else None,
                            "lr0": plan["runs"][winner]["lr0"] if winner else None}
        for number, settings in plan["runs"].items():
            value = measured_runs[number]
            directory = run_dir(model, number)
            info_path = directory / "run_info.json"
            recorded_status = json.loads(info_path.read_text()).get("status") if info_path.is_file() else None
            status = ("complete" if value else "awaiting_validation" if recorded_status == "complete"
                      else "failed" if recorded_status == "failed" else "pending")
            summary.append({"experiment": number, "model": model, "step": "optimizer",
                            **settings, "status": status, "selected": number == winner,
                            "inherited_from": plan["baseline"].format(model=model),
                            "config": str((directory / "exp01_config.yaml").relative_to(ROOT)),
                            **(value or {})})
            delta = {"experiment": number, "model": model, "status": status,
                     "baseline": "phase2_baseline"}
            if value:
                delta.update({"delta_" + key: value[key] - baseline[key] for key in (*METRICS, *TIMING)})
            deltas.append(delta)
    write_csv(RESULTS / "hyperparameter_summary.csv", FIELDS, summary)
    write_csv(RESULTS / "hyperparameter_delta.csv", DELTA_FIELDS, deltas)
    (RESULTS / "exp01_selection.json").write_text(json.dumps(selection, indent=2) + "\n")


def run_all(execute):
    combinations = [(model, experiment) for model in spec()["models"]
                    for experiment in spec()["runs"]]
    for index, (model, experiment) in enumerate(combinations, 1):
        print(f"[{index}/{len(combinations)}] {model} experiment {experiment}", flush=True)
        for task in ("train", "evaluate"):
            command = docker_command(task, model, experiment)
            print(shlex.join(command), flush=True)
            if execute:
                prepare(model, experiment)
                subprocess.run(command, check=True)
    if execute:
        collect()
    else:
        print("python3 scripts/phase3/exp01.py collect")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("list", "train", "evaluate", "collect", "run-all"))
    parser.add_argument("--model", choices=spec()["models"])
    parser.add_argument("--experiment", choices=spec()["runs"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.task == "list":
        for model in spec()["models"]:
            for number, options in spec()["runs"].items():
                print(model, number, options["optimizer"], options["lr0"])
        return
    if args.task == "collect":
        collect()
        return
    if args.task == "run-all":
        if args.model or args.experiment or args.inside_docker:
            parser.error("run-all is a host command for all four model/optimizer combinations")
        run_all(args.execute)
        return
    if not args.model or not args.experiment:
        parser.error("train/evaluate require --model and --experiment")
    if not args.execute and not args.inside_docker:
        print(shlex.join(docker_command(args.task, args.model, args.experiment)))
        return
    cfg = prepare(args.model, args.experiment)
    if args.inside_docker:
        if args.task == "train":
            train_models.train_inside_docker(cfg, args.model)
        else:
            evaluate_valid(cfg, args.model)
    else:
        subprocess.run(docker_command(args.task, args.model, args.experiment), check=True)


if __name__ == "__main__":
    main()
