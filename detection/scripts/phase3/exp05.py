#!/usr/bin/env python3
"""Phase 3 experiment 05: cosine schedule versus a reused LambdaLR run."""
import argparse
import copy
import json
import math
import shlex
import subprocess
from pathlib import Path

import yaml

import exp01
import exp04
import train_models

ROOT = exp01.ROOT
SPEC_PATH = ROOT / "configs/phase3/exp05.yaml"
EXPERIMENTS = ROOT / "experiments/phase3"
RESULTS = ROOT / "results/phase3"


def spec():
    plan = yaml.safe_load(SPEC_PATH.read_text())
    if (plan["step"] != "scheduler" or plan["new_experiment"] != "008"
            or plan["reference_scheduler"] != "LambdaLR" or plan["new_scheduler"] != "CosineLR"
            or set(plan["models"]) != {"yolo11n", "yolov8n"}):
        raise ValueError(f"Unexpected exp05 design: {SPEC_PATH}")
    return plan


def run_dir(model):
    return EXPERIMENTS / spec()["new_experiment"] / model


def reference(model):
    plan = spec()
    expected = plan["models"].get(model)
    if expected is None:
        raise ValueError(f"Unknown model: {model}")
    selected = json.loads((ROOT / plan["inherited_selection"]).read_text())[model]
    number = expected["reference_experiment"]
    if (selected["status"] != "complete" or selected["selected_experiment"] != number
            or selected["optimizer"] != expected["optimizer"]
            or not math.isclose(selected["lr0"], expected["lr0"])
            or not math.isclose(selected["momentum"], expected["momentum"])
            or selected["batch_size"] != expected["batch_size"]
            or not math.isclose(selected["weight_decay"], expected["weight_decay"])):
        raise ValueError(f"exp04 selection disagrees with exp05 plan for {model}")
    if number == "004":
        applied, metrics, inherited_from = exp04.reference(model)
    else:
        metrics = exp04.measured(model, number)
        inherited_from = f"experiments/phase3/{number}/{model}/exp04_config.yaml"
        applied = yaml.safe_load((ROOT / inherited_from).read_text())
    if metrics is None:
        raise ValueError(f"Missing selected validation result: {model} {number}")
    if Path(inherited_from).parent != Path(f"experiments/phase3/{number}/{model}"):
        raise ValueError(f"Unexpected selected exp04 source: {inherited_from}")
    native = yaml.safe_load((ROOT / f"experiments/phase3/{number}/{model}/native.yaml").read_text())
    if (applied["native"] != native or native["optimizer"] != expected["optimizer"]
            or not math.isclose(native["lr0"], expected["lr0"])
            or not math.isclose(native["momentum"], expected["momentum"])
            or not math.isclose(native["weight_decay"], expected["weight_decay"])
            or applied["training"]["batch_size"] != expected["batch_size"]
            or native["nbs"] != expected["batch_size"] or native["cos_lr"] is not False):
        raise ValueError(f"Selected LambdaLR settings disagree with exp05 plan: {inherited_from}")
    return applied, metrics, inherited_from


def prepare(model):
    plan = spec()
    parent, _, inherited_from = reference(model)
    cfg = yaml.safe_load((ROOT / "configs/phase1/common.yaml").read_text())
    if (cfg["training"] != parent["training"]
            or cfg["models"][model]["weights"] != parent["pretrained_weights"]):
        raise ValueError(f"Fixed Phase 1 settings differ from selected run: {model}")
    cfg["models"] = {model: cfg["models"][model]}
    cfg["output_dir"] = f"experiments/phase3/{plan['new_experiment']}"
    native = copy.deepcopy(parent["native"])
    native["cos_lr"] = True
    directory = run_dir(model)
    directory.mkdir(parents=True, exist_ok=True)
    applied = {"experiment": plan["new_experiment"], "model": model, "step": "scheduler",
               "inherited_from": inherited_from, "training": cfg["training"],
               "pretrained_weights": parent["pretrained_weights"],
               "evaluation": parent["evaluation"], "native": native}
    for filename, value in (("exp05_config.yaml", applied), ("native.yaml", native)):
        path = directory / filename
        if path.is_file() and yaml.safe_load(path.read_text()) != value:
            raise ValueError(f"Existing run has different settings: {path}")
        path.write_text(yaml.safe_dump(value, sort_keys=False))
    cfg["models"][model]["config"] = str((directory / "native.yaml").relative_to(ROOT))
    return cfg


def docker_command(task, model):
    return ["docker", "compose", "-f", str(ROOT / "docker/yolo/docker-compose.yaml"),
            "run", "--rm", "--no-deps", "-T", "yolo-trainer", "python", "-u",
            "/workspace/scripts/phase3/exp05.py", task, "--model", model, "--inside-docker"]


def measured(model):
    directory = run_dir(model)
    metrics_path = directory / "evaluation/validation_metrics.json"
    info_path = directory / "run_info.json"
    if not metrics_path.is_file() or not info_path.is_file():
        return None
    info = json.loads(info_path.read_text())
    if info.get("status") != "complete" or info.get("model") != model:
        raise ValueError(f"Incomplete training record: {info_path}")
    parent, _, inherited_from = reference(model)
    applied = yaml.safe_load((directory / "exp05_config.yaml").read_text())
    expected_native = copy.deepcopy(parent["native"])
    expected_native["cos_lr"] = True
    if (applied["model"] != model or applied["experiment"] != spec()["new_experiment"]
            or applied["inherited_from"] != inherited_from
            or applied["native"] != expected_native
            or yaml.safe_load((directory / "native.yaml").read_text()) != expected_native
            or applied["training"] != parent["training"] or info["training"] != parent["training"]
            or applied["pretrained_weights"] != parent["pretrained_weights"]):
        raise ValueError(f"Run did not inherit selected settings with only scheduler changed: {directory}")
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
    models = tuple(spec()["models"])
    for model in models:
        _, _, inherited_from = reference(model)
        print(f"Reuse {model} LambdaLR: {inherited_from}", flush=True)
    for index, model in enumerate(models, 1):
        print(f"[{index}/{len(models)}] {model} experiment 008, cosine LR", flush=True)
        for task in ("train", "evaluate"):
            command = docker_command(task, model)
            print(shlex.join(command), flush=True)
            if execute:
                prepare(model)
                subprocess.run(command, check=True)
    if execute:
        collect()
    else:
        print("python3 scripts/phase3/exp05.py collect")


def collect():
    plan = spec()
    stage_rows, stage_deltas, global_rows, global_deltas, selection = [], [], [], [], {}
    RESULTS.mkdir(parents=True, exist_ok=True)
    for model, expected in plan["models"].items():
        parent, reference_value, inherited_from = reference(model)
        new_value = measured(model)
        complete = new_value is not None
        winner = (max((expected["reference_experiment"], plan["new_experiment"]),
                      key=lambda number: exp01.rank(reference_value if number == expected["reference_experiment"]
                                                    else new_value)) if complete else None)
        scheduler = (plan["reference_scheduler"] if winner == expected["reference_experiment"]
                     else plan["new_scheduler"] if winner else None)
        selection[model] = {"status": "complete" if complete else "pending",
                            "selected_experiment": winner, "optimizer": expected["optimizer"],
                            "lr0": expected["lr0"], "momentum": expected["momentum"],
                            "batch_size": expected["batch_size"], "weight_decay": expected["weight_decay"],
                            "scheduler": scheduler}
        baseline = exp01.baseline_metrics(model)
        for number, value in ((expected["reference_experiment"], reference_value),
                              (plan["new_experiment"], new_value)):
            reused = number == expected["reference_experiment"]
            directory = (ROOT / inherited_from).parent if reused else run_dir(model)
            info_path = directory / "run_info.json"
            recorded = json.loads(info_path.read_text()).get("status") if info_path.is_file() else None
            status = ("reused_exp04" if reused else "complete" if value else
                      "awaiting_validation" if recorded == "complete" else
                      "failed" if recorded == "failed" else "pending")
            row = {"experiment": number, "model": model, "step": "scheduler",
                   "optimizer": expected["optimizer"], "lr0": expected["lr0"],
                   "momentum": expected["momentum"], "batch_size": expected["batch_size"],
                   "weight_decay": expected["weight_decay"],
                   "scheduler": plan["reference_scheduler"] if reused else plan["new_scheduler"],
                   "status": status, "selected": number == winner,
                   "inherited_from": parent["inherited_from"] if reused else inherited_from,
                   "config": inherited_from if reused else
                   str((directory / "exp05_config.yaml").relative_to(ROOT)), **(value or {})}
            stage_rows.append(row)
            relative = {"experiment": number, "model": model, "status": status,
                        "reference_experiment": expected["reference_experiment"]}
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
        best_config = (parent if winner == expected["reference_experiment"] else
                       yaml.safe_load((run_dir(model) / "exp05_config.yaml").read_text()) if winner else None)
        best = {"model": model, "status": selection[model]["status"],
                "selected_experiment": winner, "scheduler": scheduler,
                "source_config": (inherited_from if winner == expected["reference_experiment"] else
                                  f"experiments/phase3/008/{model}/exp05_config.yaml" if winner else None),
                "training": best_config["training"] if best_config else None,
                "native": best_config["native"] if best_config else None,
                "validation": (reference_value if winner == expected["reference_experiment"] else new_value
                               if winner else None)}
        (RESULTS / f"{model}_best.yaml").write_text(yaml.safe_dump(best, sort_keys=False))
    exp01.write_csv(RESULTS / "exp05_summary.csv", exp01.FIELDS, stage_rows)
    relative_fields = ("experiment", "model", "status", "reference_experiment",
                       *("delta_" + key for key in (*exp01.METRICS, *exp01.TIMING)))
    exp01.write_csv(RESULTS / "exp05_delta.csv", relative_fields, stage_deltas)
    exp01.merge_csv(RESULTS / "hyperparameter_summary.csv", exp01.FIELDS, global_rows,
                    {plan["new_experiment"]})
    exp01.merge_csv(RESULTS / "hyperparameter_delta.csv", exp01.DELTA_FIELDS, global_deltas,
                    {plan["new_experiment"]})
    (RESULTS / "exp05_selection.json").write_text(json.dumps(selection, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("list", "train", "evaluate", "collect", "run-all"))
    parser.add_argument("--model", choices=spec()["models"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.task == "list":
        for model, expected in spec()["models"].items():
            reference(model)
            print(model, expected["reference_experiment"], "LambdaLR reused")
            print(model, spec()["new_experiment"], "CosineLR new")
        return
    if args.task == "collect":
        collect()
        return
    if args.task == "run-all":
        if args.model or args.inside_docker:
            parser.error("run-all is a host command for both new cosine runs")
        run_all(args.execute)
        return
    if not args.model:
        parser.error("train/evaluate require --model")
    if not args.execute and not args.inside_docker:
        reference(args.model)
        print(shlex.join(docker_command(args.task, args.model)))
        return
    cfg = prepare(args.model)
    if args.inside_docker:
        if args.task == "train":
            train_models.train_inside_docker(cfg, args.model)
        else:
            exp01.evaluate_valid(cfg, args.model)
    else:
        subprocess.run(docker_command(args.task, args.model), check=True)


if __name__ == "__main__":
    main()
