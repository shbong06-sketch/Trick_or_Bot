#!/usr/bin/env python3
"""Phase 1 CLI. train/evaluate print commands unless --execute is supplied."""
import argparse
import csv
import json
import shlex
import shutil
import subprocess
from pathlib import Path

import yaml

from results import FIELDS, MODEL_NAMES, ROOT, digest, identifier, load_config, save_json, verify_dataset


def source_paths(cfg):
    paths = set((ROOT/"scripts/phase1").glob("*.py"))
    paths.update((ROOT/"configs/phase1").glob("*.yaml"))
    paths.update((ROOT/"configs").glob("*.yaml"))
    paths.update((ROOT/"docker").glob("*/Dockerfile"))
    paths.update((ROOT/"docker").glob("*/docker-compose.yaml"))
    paths.add(ROOT/"scripts/phase1/requirements.txt")
    paths.add(ROOT/".dockerignore")
    return sorted(paths)


def prepare(cfg, name, run):
    frozen = verify_dataset(cfg)
    sources = {str(path.relative_to(ROOT)):digest(path) for path in source_paths(cfg)}
    run.mkdir(parents=True,exist_ok=False)
    config_path = run/"resolved_config.yaml"
    config_path.write_text(yaml.safe_dump(cfg,sort_keys=False))
    save_json(run/"dataset_snapshot.json",frozen)
    shutil.copyfile(ROOT/cfg["dataset"]["manifest"],run/"dataset_manifest.csv")
    save_json(run/"run.json",dict(model=name,run_id=run.name,config_sha256=digest(config_path),source_sha256=sources))
    print(f"Prepared {name}/{run.name}; train/evaluate have not been executed.")


def frozen_config(run, name):
    metadata = json.loads((run/"run.json").read_text())
    if metadata["model"] != name:
        raise ValueError("Run model mismatch")
    path = run/"resolved_config.yaml"
    if digest(path) != metadata["config_sha256"]:
        raise ValueError("Prepared config changed; prepare a new run")
    for relative, expected in metadata["source_sha256"].items():
        if digest(ROOT/relative) != expected:
            raise ValueError(f"Source changed since preparation: {relative}; prepare a new run")
    cfg = load_config(path)
    snapshot = json.loads((run/"dataset_snapshot.json").read_text())
    if verify_dataset(cfg)["manifest_sha256"] != snapshot["manifest_sha256"]:
        raise ValueError("Dataset manifest changed since preparation")
    return cfg


def docker_command(action, cfg, name, run_id, eval_id=None):
    framework = cfg["models"][name]["framework"]
    service = "yolo-trainer" if framework == "yolo" else "trainer"
    command = ["docker","compose","-f",str(ROOT/"docker"/framework/"docker-compose.yaml"),
               "run","--rm",service,"python","/workspace/scripts/phase1/run.py",action,
               "--model",name,"--run-name",run_id,"--worker","--execute"]
    if eval_id:
        command.extend(["--eval-name",eval_id])
    return command


def summarize(output):
    rows = []
    for path in sorted((ROOT/"experiments/phase1").glob("*/*/evaluation/*/model_screening_summary.json")):
        status = json.loads((path.parent/"status.json").read_text())
        if status["status"] != "complete":
            continue
        row = json.loads(path.read_text())
        if set(row) != set(FIELDS):
            raise ValueError(f"Unexpected summary schema: {path}")
        rows.append(row)
    if not rows:
        raise ValueError("No completed evaluation results; no metrics have been fabricated")
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    print(f"Saved {len(rows)} completed results -> {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("prepare","train","evaluate","summarize"))
    parser.add_argument("--config",type=Path,default=ROOT/"configs/phase1/screening.yaml")
    parser.add_argument("--model",choices=MODEL_NAMES)
    parser.add_argument("--run-name")
    parser.add_argument("--eval-name")
    parser.add_argument("--output",type=Path,help="New CSV path for summarize (existing files are refused)")
    parser.add_argument("--execute",action="store_true",help="Explicitly run training/evaluation via existing Docker")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action == "summarize":
        if args.output is None:
            parser.error("summarize requires --output")
        summarize(args.output)
        return
    if not args.model or not args.run_name:
        parser.error("--model and --run-name are required")
    run_id = identifier(args.run_name)
    run = ROOT/"experiments/phase1"/args.model/run_id
    if args.action == "prepare":
        if args.execute or args.worker:
            parser.error("prepare never executes models")
        prepare(load_config(args.config),args.model,run)
        return
    if args.action == "evaluate" and not args.eval_name:
        parser.error("evaluate requires --eval-name")
    eval_id = identifier(args.eval_name) if args.eval_name else None
    if not args.execute:
        # A command preview may be generated before prepare, without dataset/GPU access.
        cfg = load_config(run/"resolved_config.yaml" if run.exists() else args.config)
        print(shlex.join(docker_command(args.action,cfg,args.model,run_id,eval_id)))
        return
    cfg = frozen_config(run,args.model)
    if args.worker:
        if args.action == "train":
            from train import execute_training
            execute_training(cfg,args.model,run)
        else:
            from evaluate import execute_evaluation
            execute_evaluation(cfg,args.model,run,eval_id)
    else:
        subprocess.run(docker_command(args.action,cfg,args.model,run_id,eval_id),check=True)


if __name__ == "__main__":
    main()
