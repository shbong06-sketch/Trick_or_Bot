#!/usr/bin/env python3
"""Phase 4: evaluate the two frozen Phase 3 winners on the fixed test split."""
import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

import evaluate_models as evaluation

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/final"
SELECTION = ROOT / "results/phase3/exp05_selection.json"
EXPECTED = {
    "yolo11n": dict(experiment="004", optimizer="SGD", lr0=0.02, momentum=0.937,
                    batch_size=16, weight_decay=0.0005, scheduler="LambdaLR"),
    "yolov8n": dict(experiment="007", optimizer="SGD", lr0=0.01, momentum=0.937,
                    batch_size=16, weight_decay=0.001, scheduler="LambdaLR"),
}
FIELDS = ("model", "selected_experiment", "checkpoint", "checkpoint_sha256", "optimizer", "lr0",
          "momentum", "batch_size", "weight_decay", "scheduler", "training_hyperparameters",
          "ending_epoch", "run_info_epochs_ending", "total_training_seconds", "validation_map50", "validation_map50_95",
          "validation_precision", "validation_recall", "validation_f1", "validation_f1_peak",
          "validation_f1_confidence", "test_map50", "test_map50_95", "test_precision", "test_recall",
          "test_f1", "test_tp", "test_fp",
          "test_fn", "test_correct_predictions_percent", "test_inference_ms_per_image",
          "test_average_confidence", "model_size_bytes", "parameter_count", "training_peak_vram_bytes",
          "evaluation_peak_vram_bytes", "hardware", "precision", "input_size", "confidence",
          "matching_iou", "nms_iou", "ap_score_cutoff", "warmup", "measured_iterations",
          "test_image_count", "test_annotation_sha256", "phase1_source", "phase2_source",
          "phase3_source", "validation_source")
ERROR_FIELDS = ("model", "image_name", "image_id", "gt_count", "prediction_count", "tp", "fp",
                "fn", "confidence", "iou", "error_type", "prediction_json", "sample_image")


def relative(path):
    return str(path.relative_to(ROOT))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv_row(path, predicate):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="") as stream:
        matches = [row for row in csv.DictReader(stream) if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"Expected one matching history row in {path}, got {len(matches)}")
    return matches[0]


def selected_records():
    chosen = json.loads(SELECTION.read_text())
    if set(chosen) != set(EXPECTED):
        raise ValueError(f"Unexpected final candidates in {SELECTION}")
    records = {}
    for name, expected in EXPECTED.items():
        selection = chosen[name]
        if selection.get("status") != "complete":
            raise ValueError(f"Incomplete Phase 3 selection: {name}")
        for key, value in expected.items():
            actual = selection.get("selected_experiment" if key == "experiment" else key)
            if isinstance(value, float):
                valid = isinstance(actual, (float, int)) and math.isclose(actual, value)
            else:
                valid = actual == value
            if not valid:
                raise ValueError(f"Phase 3 selection changed for {name}: {key}={actual!r}")
        folder = ROOT / "experiments/phase3" / expected["experiment"] / name
        best_path = ROOT / "results/phase3" / f"{name}_best.yaml"
        best = yaml.safe_load(best_path.read_text())
        config_path = ROOT / best["source_config"]
        applied = yaml.safe_load(config_path.read_text())
        native = yaml.safe_load((folder / "native.yaml").read_text())
        info_path = folder / "run_info.json"
        info = json.loads(info_path.read_text())
        validation_path = folder / "evaluation/validation_metrics.json"
        validation = json.loads(validation_path.read_text())
        checkpoint = folder / info["best_checkpoint"]
        if (best["status"] != "complete" or best["selected_experiment"] != expected["experiment"]
                or best["model"] != name or config_path.parent != folder
                or applied["native"] != native or best["native"] != native
                or best["training"] != applied["training"] or info["training"] != applied["training"]
                or info["model"] != name or info["status"] != "complete"
                or info["optimizer"] != expected["optimizer"] or info["scheduler"] != expected["scheduler"]
                or native["optimizer"] != expected["optimizer"] or native["cos_lr"] is not False
                or applied["training"]["batch_size"] != expected["batch_size"]
                or native["nbs"] != expected["batch_size"] or not checkpoint.is_file()):
            raise ValueError(f"Selected run provenance mismatch: {folder}")
        for key in ("lr0", "momentum", "weight_decay"):
            if not math.isclose(native[key], expected[key]):
                raise ValueError(f"Selected native {key} differs: {folder}")
        if info["model_size_bytes"] != checkpoint.stat().st_size:
            raise ValueError(f"Checkpoint size differs from run record: {checkpoint}")
        for key, val_key in (("validation_map50", "map50"), ("validation_map50_95", "map50_95"),
                             ("validation_recall", "recall"), ("validation_f1", "f1")):
            if not math.isclose(best["validation"][key], validation[val_key]):
                raise ValueError(f"Validation history disagrees: {validation_path}")
        phase1 = read_csv_row(ROOT / "results/phase1/model_comparison.csv", lambda row: row["model"] == name)
        phase2 = read_csv_row(ROOT / "results/phase2/augmentation_summary.csv",
                              lambda row: row["model"] == name and row["condition"] == "baseline")
        phase3 = read_csv_row(ROOT / "results/phase3/hyperparameter_summary.csv",
                              lambda row: row["model"] == name and row["experiment"] == expected["experiment"])
        if phase3["status"] not in ("complete", "reused_exp04", "reused_exp02"):
            raise ValueError(f"Selected Phase 3 history is incomplete: {name}")
        if (int(phase3["ending_epoch"]) not in (info["epochs_ending"], info["epochs_ending"] - 1)
                or not math.isclose(float(phase3["total_training_seconds"]), info["total_training_seconds"])):
            raise ValueError(f"Phase 3 training history disagrees with run_info: {name}")
        records[name] = dict(folder=folder, info=info, native=native, best=best, checkpoint=checkpoint,
                             validation=validation, validation_path=validation_path, phase1=phase1,
                             phase2=phase2, phase3=phase3, phase3_config=config_path)
    return records


def protocol(records):
    ev = yaml.safe_load((ROOT / "configs/phase1/evaluation.yaml").read_text())
    sizes = {tuple(r["info"]["training"]["input_size"]) for r in records.values()}
    if sizes != {(704, 704)} or ev["benchmark_precision"] != "fp32" or ev["benchmark_batch_size"] != 1:
        raise ValueError("Final benchmark requires the same 704x704 input and batch-one FP32 inference")
    for r in records.values():
        for key in ("confidence", "matching_iou", "nms_iou", "ap_score_cutoff"):
            if not math.isclose(r["validation"][key], ev[key]):
                raise ValueError(f"Validation protocol mismatch: {r['validation_path']}: {key}")
    if ev["warmup"] < 0 or ev["repeats"] < 1 or not 0 < ev["ap_score_cutoff"] < ev["confidence"] < 1:
        raise ValueError("Invalid evaluation protocol")
    return ev


def image_matches(truth, predictions, confidence, threshold):
    """Greedy, confidence ordered, class aware matching, like evaluation.counts."""
    active = [p for p in predictions if p["score"] >= confidence]
    used = set()
    annotated = []
    for pred in sorted(active, key=lambda p: -p["score"]):
        options = [(evaluation.iou(pred["bbox"], gt["bbox"]), index)
                   for index, gt in enumerate(truth)
                   if index not in used and pred["category_id"] == gt["category_id"]]
        overlap, index = max(options, default=(0.0, None))
        is_tp = overlap >= threshold
        if is_tp:
            used.add(index)
        annotated.append({**pred, "match_iou": overlap, "matched_gt_index": index if is_tp else None,
                          "outcome": "TP" if is_tp else "FP"})
    missed = [{**gt, "gt_index": index} for index, gt in enumerate(truth) if index not in used]
    return annotated, missed


def render_sample(rgb, truth, annotated, missed, path):
    from PIL import Image, ImageDraw
    canvas = Image.fromarray(rgb.copy())
    draw = ImageDraw.Draw(canvas)
    for gt in truth:
        draw.rectangle(gt["bbox"], outline="lime", width=3)
    for pred in annotated:
        color = "red" if pred["outcome"] == "FP" else "cyan"
        draw.rectangle(pred["bbox"], outline=color, width=3)
        draw.text((pred["bbox"][0], max(0, pred["bbox"][1] - 12)),
                  f"{pred['outcome']} {pred['score']:.3f}", fill=color)
    for gt in missed:
        draw.text((gt["bbox"][0], max(0, gt["bbox"][1] - 24)), "FN", fill="yellow")
    canvas.save(path)


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def compare_key(row):
    # Validation is already fixed; use test recall/F1 before mAP50, exact detection rate, then latency.
    return (row["test_recall"], row["test_f1"], row["test_map50"] or 0.0,
            row["test_correct_predictions_percent"], -row["test_inference_ms_per_image"])


def report(rows, ev):
    winner = max(rows, key=compare_key)
    lines = ["# Phase 4 Final Benchmark", "", "## 공통 평가 조건", "",
             f"- Test: `dataset/images/test` ({rows[0]['test_image_count']}장), COCO annotation SHA-256 `{rows[0]['test_annotation_sha256']}`",
             f"- 입력: 704×704, confidence {ev['confidence']}, matching IoU {ev['matching_iou']}, NMS IoU {ev['nms_iou']}, AP cutoff {ev['ap_score_cutoff']}",
             f"- 하드웨어: {rows[0]['hardware']}; FP32, batch 1, warmup {ev['warmup']}회, 전체 test {ev['repeats']}회 측정",
             "- 속도 범위: 디코딩된 RGB에서 전처리·GPU 전송·추론·후처리·CPU 박스 반환까지. 파일 읽기, 모델 로드, 매칭, 저장 제외.",
             "- Correct Prediction Rate = TP / (TP + FP + FN) × 100. Average Confidence = 운영 threshold 이상 예측의 평균.",
             "", "## 최종 비교", "",
             "| Model | Recall | F1 | mAP50 | Correct % | ms/image | mAP50-95 | TP/FP/FN |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        tp, fp, fn = (row[f"test_{key}"] for key in ("tp", "fp", "fn"))
        lines.append(f"| {row['model']} | {row['test_recall']:.4f} | {row['test_f1']:.4f} | {row['test_map50']:.4f} | "
                     f"{row['test_correct_predictions_percent']:.2f} | {row['test_inference_ms_per_image']:.3f} | "
                     f"{row['test_map50_95']:.4f} | {tp}/{fp}/{fn} |")
    lines += ["", "## 선정 근거", "",
              f"**{winner['model']}** 선택. Test Recall → F1 → mAP50 → Correct Prediction Rate → 추론 속도 순으로 비교했습니다.",
              "동률이면 다음 지표를 사용합니다. Test 성능은 모델 선택에만 사용하며 threshold 조정이나 재학습은 하지 않았습니다.",
              "", "## 학습 및 검증 이력", ""]
    runner_up = next(row for row in rows if row["model"] != winner["model"])
    lines[lines.index("## 학습 및 검증 이력"):lines.index("## 학습 및 검증 이력")] = [
        f"{winner['model']}은 FN {winner['test_fn']}개, {runner_up['model']}은 FN {runner_up['test_fn']}개입니다. "
        f"{runner_up['model']}은 추론 속도({runner_up['test_inference_ms_per_image']:.3f} ms/image)와 "
        f"mAP50-95({runner_up['test_map50_95']:.4f})에서 앞섭니다.", ""]
    for row in rows:
        lines += [f"### {row['model']}", "",
                  f"- Phase 3 실험 {row['selected_experiment']}: SGD, lr0={row['lr0']}, momentum={row['momentum']}, batch={row['batch_size']}, weight decay={row['weight_decay']}, LambdaLR",
                  f"- 마지막 학습 epoch: {row['ending_epoch']} (run_info epochs_ending={row['run_info_epochs_ending']}); 총 학습 시간: {row['total_training_seconds']:.2f}초",
                  f"- Validation mAP50={row['validation_map50']:.4f}, Precision={row['validation_precision']:.4f}, Recall={row['validation_recall']:.4f}, F1 peak={row['validation_f1_peak']:.4f} @ confidence={row['validation_f1_confidence']:.4f}",
                  f"- Test 평균 confidence={row['test_average_confidence']:.4f}; checkpoint={row['model_size_bytes']} bytes, params={row['parameter_count']}, training peak VRAM={row['training_peak_vram_bytes']} bytes, evaluation peak VRAM={row['evaluation_peak_vram_bytes']} bytes",
                  f"- 이력: `{row['phase1_source']}`, `{row['phase2_source']}`, `{row['phase3_source']}`; validation: `{row['validation_source']}`",
                  ""]
    lines += ["## Error analysis", "",
              "`error_analysis.csv`에 이미지별 TP/FP/FN, 예측 confidence와 최대 미매칭 GT IoU를 기록했습니다.",
              "`predictions/<model>/`에는 운영 threshold 이상 예측과 매칭 결과가 이미지마다 JSON으로 저장됩니다.",
              "FP/FN 샘플은 각 디렉터리에 모델명 접두어로 저장됩니다. 초록=GT, 청록=TP, 빨강=FP, 노랑=FN입니다.",
              "`error_type`은 수동 분류를 위한 빈 칸입니다.", ""]
    return "\n".join(lines), winner["model"]


def run():
    import torch
    records = selected_records()
    ev = protocol(records)
    if not torch.cuda.is_available():
        raise RuntimeError("Final benchmark requires an NVIDIA L4 GPU")
    hardware = torch.cuda.get_device_name(0)
    if not hardware.endswith("L4"):
        raise RuntimeError(f"Expected NVIDIA L4, found {hardware}")
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    dataset = ROOT / "dataset"
    data, images, truth, category_id = evaluation.load_split(dataset, "test")
    if not images:
        raise ValueError("Empty test split")
    annotation_hash = digest(dataset / "annotations/instances_test.json")
    for folder in (OUTPUT / "predictions", OUTPUT / "fp_samples", OUTPUT / "fn_samples"):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        if folder.name in ("fp_samples", "fn_samples"):
            (folder / ".gitkeep").touch()
    rows, errors = [], []
    for name, record in records.items():
        print(f"[{name}] test prediction and benchmark", flush=True)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(0)
        model = evaluation.load_model("yolo", record["folder"], record["checkpoint"])
        predictions, rgb_images = {}, []
        pred_dir = OUTPUT / "predictions" / name
        pred_dir.mkdir()
        for image in images:
            rgb = evaluation.read_rgb(dataset, "test", image)
            rgb_images.append(rgb)
            predicted = evaluation.predict(model, "yolo", rgb, category_id, ev)
            predictions[image["id"]] = predicted
            annotated, missed = image_matches(truth[image["id"]], predicted, ev["confidence"], ev["matching_iou"])
            stem = Path(image["file_name"]).stem
            prediction_path = pred_dir / f"{image['id']}_{stem}.json"
            prediction_path.write_text(json.dumps(dict(model=name, image_name=image["file_name"],
                                                       image_id=image["id"], ground_truth=truth[image["id"]],
                                                       predictions=annotated, false_negatives=missed), indent=2) + "\n")
            fp = sum(p["outcome"] == "FP" for p in annotated)
            fn = len(missed)
            sample = ""
            for kind, folder in (("fp", OUTPUT / "fp_samples"), ("fn", OUTPUT / "fn_samples")):
                if (fp if kind == "fp" else fn):
                    sample_path = folder / f"{name}_{image['id']}_{stem}.png"
                    render_sample(rgb, truth[image["id"]], annotated, missed, sample_path)
                    sample = relative(sample_path) if not sample else sample + ";" + relative(sample_path)
            errors.append(dict(model=name, image_name=image["file_name"], image_id=image["id"],
                               gt_count=len(truth[image["id"]]), prediction_count=len(annotated),
                               tp=len(annotated)-fp, fp=fp, fn=fn,
                               confidence=[p["score"] for p in annotated],
                               iou=[p["match_iou"] for p in annotated], error_type="",
                               prediction_json=relative(prediction_path), sample_image=sample))
        test = evaluation.split_metrics(data, images, truth, predictions, ev)
        totals = tuple(sum(e[k] for e in errors if e["model"] == name) for k in ("tp", "fp", "fn"))
        if totals != (test["tp"], test["fp"], test["fn"]):
            raise AssertionError(f"Per-image matching differs from aggregate for {name}: {totals}")
        speed = evaluation.benchmark(model, "yolo", rgb_images, category_id, ev)
        peak = torch.cuda.max_memory_allocated(0)
        info, validation = record["info"], record["validation"]
        row = dict(model=name, selected_experiment=EXPECTED[name]["experiment"],
                   checkpoint=relative(record["checkpoint"]), checkpoint_sha256=digest(record["checkpoint"]),
                   optimizer=info["optimizer"], lr0=record["native"]["lr0"],
                   momentum=record["native"]["momentum"], batch_size=info["training"]["batch_size"],
                   weight_decay=record["native"]["weight_decay"], scheduler=info["scheduler"],
                   training_hyperparameters={"training": info["training"], "native": record["native"]},
                   ending_epoch=int(record["phase3"]["ending_epoch"]),
                   run_info_epochs_ending=info["epochs_ending"],
                   total_training_seconds=info["total_training_seconds"],
                   validation_map50=validation["map50"], validation_map50_95=validation["map50_95"],
                   validation_precision=validation["precision"], validation_recall=validation["recall"],
                   validation_f1=validation["f1"], validation_f1_peak=validation["f1_peak"],
                   validation_f1_confidence=validation["f1_confidence"], test_map50=test["map50"],
                   test_map50_95=test["map50_95"],
                   test_precision=evaluation.prf(test["tp"], test["fp"], test["fn"])[0],
                   test_recall=evaluation.prf(test["tp"], test["fp"], test["fn"])[1],
                   test_f1=evaluation.prf(test["tp"], test["fp"], test["fn"])[2],
                   test_tp=test["tp"], test_fp=test["fp"], test_fn=test["fn"],
                   test_correct_predictions_percent=test["correct_predictions_percent"],
                   test_inference_ms_per_image=speed, test_average_confidence=test["average_confidence"],
                   model_size_bytes=record["checkpoint"].stat().st_size,
                   parameter_count=info["parameter_count"], training_peak_vram_bytes=info.get("peak_vram_bytes"),
                   evaluation_peak_vram_bytes=peak, hardware=hardware, precision="fp32", input_size=[704, 704],
                   confidence=ev["confidence"], matching_iou=ev["matching_iou"], nms_iou=ev["nms_iou"],
                   ap_score_cutoff=ev["ap_score_cutoff"], warmup=ev["warmup"],
                   measured_iterations=ev["repeats"] * len(images), test_image_count=len(images),
                   test_annotation_sha256=annotation_hash,
                   phase1_source="results/phase1/model_comparison.csv",
                   phase2_source="results/phase2/augmentation_summary.csv",
                   phase3_source="results/phase3/hyperparameter_summary.csv",
                   validation_source=relative(record["validation_path"]))
        rows.append(row)
        del model
    write_csv(OUTPUT / "final_comparison.csv", FIELDS, rows)
    write_csv(OUTPUT / "error_analysis.csv", ERROR_FIELDS, errors)
    markdown, winner = report(rows, ev)
    lineage = {}
    for name, record in records.items():
        lineage[name] = {
            "phase1": {key: record["phase1"][key] for key in
                       ("checkpoint", "validation_map50", "validation_recall", "validation_f1")},
            "phase2_baseline": {key: record["phase2"][key] for key in
                                ("checkpoint", "validation_map50", "validation_recall", "validation_f1")},
            "phase3_selected": {key: record["phase3"][key] for key in
                                ("experiment", "step", "inherited_from", "config", "validation_map50",
                                 "validation_recall", "validation_f1", "ending_epoch", "total_training_seconds")},
        }
    (OUTPUT / "final_comparison.json").write_text(json.dumps(dict(protocol=ev, selected_model=winner,
                                                                 models=rows, lineage=lineage), indent=2) + "\n")
    (OUTPUT / "report.md").write_text(markdown)
    print(f"Final benchmark complete: {OUTPUT}; selected {winner}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run in the YOLO Docker GPU environment")
    parser.add_argument("--inside-docker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    records = selected_records()
    protocol(records)
    command = ["docker", "compose", "-f", str(ROOT / "docker/yolo/docker-compose.yaml"), "run", "--rm",
               "--no-deps", "-T", "--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp",
               "--env", "YOLO_CONFIG_DIR=/tmp/ultralytics", "yolo-trainer", "python", "-u",
               "/workspace/scripts/final_benchmark.py",
               "--execute", "--inside-docker"]
    if not args.execute:
        print("Preflight OK. Run: " + subprocess.list2cmdline(command))
    elif args.inside_docker:
        run()
    else:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
