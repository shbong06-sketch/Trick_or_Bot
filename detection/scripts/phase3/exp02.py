#!/usr/bin/env python3
"""Phase 3 experiment 02: compare two new LRs with exp01's SGD run."""
import argparse
import copy
import json
import math
import shlex
import subprocess
from pathlib import Path

import yaml

import exp01
import train_models

ROOT = exp01.ROOT
SPEC_PATH = ROOT / "configs/phase3/exp02.yaml"
EXPERIMENTS = ROOT / "experiments/phase3"
RESULTS = ROOT / "results/phase3"


def spec():
    plan = yaml.safe_load(SPEC_PATH.read_text())
    if (plan["step"] != "learning_rate" or plan["reference_experiment"] != "002"
            or plan["optimizer"] != "SGD" or plan["baseline_lr"] != 0.01
            or plan["runs"] != {"003": 0.005, "004": 0.02}):
        raise ValueError(f"Unexpected exp02 design: {SPEC_PATH}")
    return plan


def run_dir(model, experiment):
    return EXPERIMENTS / experiment / model


def reference(model):
    plan = spec()
    if model not in plan["models"]:
        raise ValueError(f"Unknown model: {model}")
    selection = json.loads((ROOT / plan["inherited_selection"]).read_text())[model]
    number = plan["reference_experiment"]
    if (selection["status"] != "complete" or selection["selected_experiment"] != number
            or selection["optimizer"] != plan["optimizer"]
            or not math.isclose(selection["lr0"], plan["baseline_lr"])):
        raise ValueError(f"exp01 did not select the expected SGD baseline for {model}")
    metrics = exp01.measured(model, number)
    if metrics is None:
        raise ValueError(f"Missing exp01 validation result for {model} {number}")
    folder = ROOT / f"experiments/phase3/{number}/{model}"
    applied = yaml.safe_load((folder / "exp01_config.yaml").read_text())
    native = yaml.safe_load((folder / "native.yaml").read_text())
    if (applied["native"] != native or native["optimizer"] != plan["optimizer"]
            or not math.isclose(native["lr0"], plan["baseline_lr"])):
        raise ValueError(f"exp01 applied settings disagree with the selected reference: {folder}")
    return applied, metrics


def prepare(model, experiment):
    plan = spec()
    if model not in plan["models"] or experiment not in plan["runs"]:
        raise ValueError(f"Unknown model or new run: {model} {experiment}")
    parent, _ = reference(model)
    cfg = yaml.safe_load((ROOT / "configs/phase1/common.yaml").read_text())
    if cfg["training"] != parent["training"] or cfg["models"][model]["weights"] != parent["pretrained_weights"]:
        raise ValueError(f"Phase 1 fixed settings differ from exp01 for {model}")
    cfg["models"] = {model: cfg["models"][model]}
    cfg["output_dir"] = f"experiments/phase3/{experiment}"
    native = copy.deepcopy(parent["native"])
    native["lr0"] = plan["runs"][experiment]
    directory = run_dir(model, experiment)
    directory.mkdir(parents=True, exist_ok=True)
    applied = {"experiment": experiment, "model": model, "step": "learning_rate",
               "inherited_from": f"experiments/phase3/002/{model}/exp01_config.yaml",
               "training": cfg["training"], "pretrained_weights": parent["pretrained_weights"],
               "evaluation": parent["evaluation"], "native": native}
    for filename, value in (("exp02_config.yaml", applied), ("native.yaml", native)):
        path = directory / filename
        if path.is_file() and yaml.safe_load(path.read_text()) != value:
            raise ValueError(f"Existing run has different settings: {path}")
        path.write_text(yaml.safe_dump(value, sort_keys=False))
    cfg["models"][model]["config"] = str((directory / "native.yaml").relative_to(ROOT))
    return cfg


def docker_command(task, model, experiment):
    return ["docker", "compose", "-f", str(ROOT / "docker/yolo/docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", "yolo-trainer", "python", "-u",
            "/workspace/scripts/phase3/exp02.py", task, "--model", model,
            "--experiment", experiment, "--inside-docker"]


def measured(model, experiment):
    directory = run_dir(model, experiment)
    metrics_path = directory / "evaluation/validation_metrics.json"
    info_path = directory / "run_info.json"
    if not metrics_path.is_file() or not info_path.is_file():
        return None
    info = json.loads(info_path.read_text())
    if info.get("status") != "complete" or info.get("model") != model:
        raise ValueError(f"Incomplete training record: {info_path}")
    parent, _ = reference(model)
    applied = yaml.safe_load((directory / "exp02_config.yaml").read_text())
    expected_native = copy.deepcopy(parent["native"])
    expected_native["lr0"] = spec()["runs"][experiment]
    if (applied["model"] != model or applied["experiment"] != experiment
            or applied["native"] != expected_native or applied["training"] != info["training"]
            or applied["pretrained_weights"] != parent["pretrained_weights"]):
        raise ValueError(f"Run did not inherit exp01 settings with only LR changed: {directory}")
    validation = json.loads(metrics_path.read_text())
    protocol = yaml.safe_load((ROOT / parent["evaluation"]).read_text())
    for key in ("confidence", "matching_iou", "nms_iou", "ap_score_cutoff"):
        if not math.isclose(validation[key], protocol[key]):
            raise ValueError(f"Evaluation protocol changed: {metrics_path}: {key}")
    value = {"validation_recall": validation["recall"], "validation_f1": validation["f1"],
             "validation_map50_95": validation["map50_95"], "validation_map50": validation["map50"],
             **exp01.history_metrics(directory / "results.csv"),
             "total_training_seconds": info["total_training_seconds"]}
    if not all(math.isfinite(float(item)) for item in value.values()):
        raise ValueError(f"Non-finite validation result: {directory}")
    if info["epochs_ending"] not in (value["ending_epoch"], value["ending_epoch"] + 1):
        raise ValueError(f"Epoch count mismatch: {directory}")
    return value


def run_all(execute):
    plan = spec()
    combinations = [(model, number) for model in plan["models"] for number in plan["runs"]]
    for model in plan["models"]:
        reference(model)
    print("Reuse exp01 experiment 002 (SGD, lr0=0.01) for both models", flush=True)
    for index, (model, number) in enumerate(combinations, 1):
        print(f"[{index}/{len(combinations)}] {model} experiment {number}", flush=True)
        for task in ("train", "evaluate"):
            command = docker_command(task, model, number)
            print(shlex.join(command), flush=True)
            if execute:
                prepare(model, number)
                subprocess.run(command, check=True)
    if execute:
        collect()
    else:
        print("python3 scripts/phase3/exp02.py collect")


def collect():
    plan = spec()
    stage_rows, stage_deltas, global_rows, global_deltas, selection = [], [], [], [], {}
    RESULTS.mkdir(parents=True, exist_ok=True)
    for model in plan["models"]:
        parent, reference_value = reference(model)
        baseline = exp01.baseline_metrics(model)
        measurements = {number: measured(model, number) for number in plan["runs"]}
        all_values = {plan["reference_experiment"]: reference_value, **measurements}
        complete = all(value is not None for value in measurements.values())
        winner = max(all_values, key=lambda number: exp01.rank(all_values[number])) if complete else None
        selection[model] = {"status": "complete" if complete else "pending",
                            "selected_experiment": winner, "optimizer": plan["optimizer"],
                            "lr0": (plan["baseline_lr"] if winner == "002" else plan["runs"].get(winner))}
        for number, value in all_values.items():
            reused = number == plan["reference_experiment"]
            directory = (ROOT / f"experiments/phase3/002/{model}") if reused else run_dir(model, number)
            info_path = directory / "run_info.json"
            recorded = json.loads(info_path.read_text()).get("status") if info_path.is_file() else None
            status = ("reused_exp01" if reused else "complete" if value else
                      "awaiting_validation" if recorded == "complete" else
                      "failed" if recorded == "failed" else "pending")
            lr = plan["baseline_lr"] if reused else plan["runs"][number]
            row = {"experiment": number, "model": model, "step": "learning_rate",
                   "optimizer": plan["optimizer"], "lr0": lr,
                   "momentum": parent["native"]["momentum"], "status": status,
                   "selected": number == winner,
                   "inherited_from": parent["inherited_from"] if reused else
                   f"experiments/phase3/002/{model}/exp01_config.yaml",
                   "config": str((directory / ("exp01_config.yaml" if reused else "exp02_config.yaml")).relative_to(ROOT)),
                   **(value or {})}
            stage_rows.append(row)
            relative = {"experiment": number, "model": model, "status": status,
                        "reference_experiment": "002"}
            if value:
                relative.update({"delta_" + key: value[key] - reference_value[key]
                                 for key in (*exp01.METRICS, *exp01.TIMING)})
            stage_deltas.append(relative)
            if not reused:
                global_rows.append(row)
                absolute = {"experiment": number, "model": model, "status": status,
                            "baseline": "phase2_baseline"}
                if value:
                    absolute.update({"delta_" + key: value[key] - baseline[key]
                                     for key in (*exp01.METRICS, *exp01.TIMING)})
                global_deltas.append(absolute)
    exp01.write_csv(RESULTS / "exp02_summary.csv", exp01.FIELDS, stage_rows)
    relative_fields = ("experiment", "model", "status", "reference_experiment",
                       *("delta_" + key for key in (*exp01.METRICS, *exp01.TIMING)))
    exp01.write_csv(RESULTS / "exp02_delta.csv", relative_fields, stage_deltas)
    exp01.merge_csv(RESULTS / "hyperparameter_summary.csv", exp01.FIELDS, global_rows, set(plan["runs"]))
    exp01.merge_csv(RESULTS / "hyperparameter_delta.csv", exp01.DELTA_FIELDS, global_deltas, set(plan["runs"]))
    (RESULTS / "exp02_selection.json").write_text(json.dumps(selection, indent=2) + "\n")


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
            reference(model)
            print(model, "002", "SGD", 0.01, "reused")
            for number, lr in spec()["runs"].items():
                print(model, number, "SGD", lr, "new")
        return
    if args.task == "collect":
        collect()
        return
    if args.task == "run-all":
        if args.model or args.experiment or args.inside_docker:
            parser.error("run-all is a host command for all four new runs")
        run_all(args.execute)
        return
    if not args.model or not args.experiment:
        parser.error("train/evaluate require --model and --experiment")
    if not args.execute and not args.inside_docker:
        reference(args.model)
        print(shlex.join(docker_command(args.task, args.model, args.experiment)))
        return
    cfg = prepare(args.model, args.experiment)
    if args.inside_docker:
        if args.task == "train":
            train_models.train_inside_docker(cfg, args.model)
        else:
            exp01.evaluate_valid(cfg, args.model)
    else:
        subprocess.run(docker_command(args.task, args.model, args.experiment), check=True)


if __name__ == "__main__":
    main()
