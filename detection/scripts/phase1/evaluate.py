"""One matching/AP/speed protocol for every framework."""
import contextlib
import copy
import io
import json
import math
import statistics
import time

from results import FIELDS, ROOT, digest, environment, save_json, write_summary


def iou(a, b):
    intersection = max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection/union if union > 0 else 0


def detection_metrics(ground_truth, predictions, confidence, match_iou):
    if set(ground_truth) != set(predictions):
        raise ValueError("Predictions must include every image, including negative images")
    tp = fp = fn = exact = 0
    scores = []
    for image_id, targets in ground_truth.items():
        matched = set()
        candidates = sorted((p for p in predictions[image_id] if p["score"] >= confidence), key=lambda p:-p["score"])
        image_tp = image_fp = 0
        for prediction in candidates:
            scores.append(prediction["score"])
            available = [(index, iou(prediction["bbox"], target["bbox"])) for index,target in enumerate(targets)
                         if index not in matched and target["category_id"] == prediction["category_id"]]
            index, overlap = max(available, key=lambda item:item[1], default=(-1,0))
            if index >= 0 and overlap >= match_iou:
                matched.add(index)
                image_tp += 1
            else:
                image_fp += 1
        image_fn = len(targets)-len(matched)
        tp += image_tp
        fp += image_fp
        fn += image_fn
        exact += image_fp == 0 and image_fn == 0
    precision = tp/(tp+fp) if tp+fp else 0
    recall = tp/(tp+fn) if tp+fn else 0
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                correct_predictions_percent=100*tp/(tp+fp+fn) if tp+fp+fn else None,
                image_exact_match_percent=100*exact/len(ground_truth) if ground_truth else None,
                average_confidence=statistics.mean(scores) if scores else None)


def f1_peak(ground_truth, predictions, evaluation):
    floor, step = evaluation["ap_score_floor"], evaluation["f1_confidence_step"]
    thresholds = sorted(set([floor,1.0] + [round(i*step,10) for i in range(1,math.ceil(1/step)) if floor <= i*step <= 1]))
    # Include score breakpoints so a narrow optimum between grid steps is not missed.
    thresholds = sorted(set(thresholds) | {p["score"] for rows in predictions.values() for p in rows if p["score"] >= floor})
    values = [(detection_metrics(ground_truth,predictions,c,evaluation["match_iou"])["f1"],c) for c in thresholds]
    # Tie: lowest confidence on the fixed grid.
    peak, confidence = max(values, key=lambda item:(item[0],-item[1]))
    return dict(f1_peak=peak, f1_confidence=confidence)


def coco_ap(coco, predictions, maximum):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    truth, detected = COCO(), COCO()
    truth.dataset = copy.deepcopy(coco)
    truth.dataset["categories"] = [dict(id=0,name="pumpkin")]
    for ann in truth.dataset["annotations"]:
        ann["category_id"] = 0
        ann.setdefault("iscrowd",0)
        ann["area"] = ann["bbox"][2]*ann["bbox"][3]
    rows = []
    for image_id, boxes in predictions.items():
        for box in boxes:
            x1,y1,x2,y2 = box["bbox"]
            rows.append(dict(id=len(rows)+1,image_id=image_id,category_id=box["category_id"],
                             bbox=[x1,y1,x2-x1,y2-y1],score=box["score"],area=(x2-x1)*(y2-y1),iscrowd=0))
    detected.dataset = dict(images=copy.deepcopy(coco["images"]),categories=[dict(id=0,name="pumpkin")],annotations=rows)
    with contextlib.redirect_stdout(io.StringIO()):
        truth.createIndex()
        detected.createIndex()
        evaluator = COCOeval(truth,detected,"bbox")
        evaluator.params.maxDets = [1,10,maximum]
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()
    # COCO uses -1 when no eligible ground truth exists; report null.
    return dict(map50=float(evaluator.stats[1]) if evaluator.stats[1]>=0 else None,
                map50_95=float(evaluator.stats[0]) if evaluator.stats[0]>=0 else None)


def normalize_predictions(rows, evaluation):
    cleaned = []
    for row in rows:
        box = list(map(float,row["bbox"]))
        score = float(row["score"])
        if len(box) != 4 or not all(math.isfinite(v) for v in box+[score]) or not 0 <= score <= 1:
            raise ValueError("Invalid model prediction")
        if row["category_id"] != 0:
            raise ValueError("Unexpected predicted category; check foreground mapping")
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        if score >= evaluation["ap_score_floor"]:
            cleaned.append(dict(bbox=box,score=score,category_id=0))
    return sorted(cleaned,key=lambda p:-p["score"])[:evaluation["max_detections"]]


def evaluate_split(cfg, split, predict, directory, torch):
    from PIL import Image
    dataset = ROOT/cfg["dataset"]["root"]
    split_dir = cfg["dataset"]["split_dirs"][split]
    coco = json.loads((dataset/"annotations"/f"instances_{split_dir}.json").read_text())
    images = []
    for entry in sorted(coco["images"],key=lambda row:row["file_name"]):
        with Image.open(dataset/"images"/split_dir/entry["file_name"]) as image:
            images.append((entry["id"], image.convert("RGB").copy()))
    if not images:
        raise ValueError(f"Empty {split} split")
    truth = {image_id:[] for image_id,_ in images}
    for ann in coco["annotations"]:
        x,y,w,h = ann["bbox"]
        truth[ann["image_id"]].append(dict(bbox=[x,y,x+w,y+h],category_id=0))
    predictions, times = {}, []
    evaluation = cfg["evaluation"]
    with torch.inference_mode():
        for i in range(evaluation["warmup"]):
            predict(images[i%len(images)][1])
        torch.cuda.synchronize()
        for repeat in range(evaluation["repeats"]):
            for image_id,image in images:
                torch.cuda.synchronize()
                start = time.perf_counter()
                raw = predict(image)
                torch.cuda.synchronize()
                times.append(dict(repeat=repeat+1,image_id=image_id,ms=(time.perf_counter()-start)*1000))
                if repeat == 0:
                    predictions[image_id] = normalize_predictions(raw,evaluation)
    metrics = detection_metrics(truth,predictions,evaluation["confidence"],evaluation["match_iou"])
    metrics.update(coco_ap(coco,predictions,evaluation["max_detections"]))
    if split == "val":
        metrics.update(f1_peak(truth,predictions,evaluation))
    metrics["inference_ms_per_image"] = statistics.mean(row["ms"] for row in times)
    save_json(directory/"predictions.json", predictions)
    save_json(directory/"latency_samples.json", times)
    save_json(directory/"metrics.json",metrics)
    return metrics


def execute_evaluation(cfg, name, run, eval_id):
    import torch
    from train import predictor
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    env = environment(torch)
    training = json.loads((run/"training/training_summary.json").read_text())
    checkpoint = run/"training"/training["checkpoint"]
    if digest(checkpoint) != training["checkpoint_sha256"]:
        raise ValueError("Training checkpoint changed")
    directory = run/"evaluation"/eval_id
    directory.mkdir(parents=True,exist_ok=False)
    save_json(directory/"environment.json",env)
    save_json(directory/"evaluation_config.json",cfg["evaluation"])
    save_json(directory/"status.json",dict(status="running"))
    try:
        predict = predictor(cfg,name,checkpoint,directory,torch)
        metrics = {}
        for split in ("val","test"):
            split_out = directory/split
            split_out.mkdir()
            metrics[split] = evaluate_split(cfg,split,predict,split_out,torch)
        frozen = json.loads((run/"dataset_snapshot.json").read_text())
        row = dict.fromkeys(FIELDS)
        row.update(schema_version=1,dataset=cfg["dataset"]["name"],dataset_manifest_sha256=frozen["manifest_sha256"],
                   model=name,run_id=run.name,eval_id=eval_id,checkpoint_sha256=training["checkpoint_sha256"],
                   gpu=env["gpu"],seed=cfg["common"]["seed"],input_size=cfg["common"]["input_size"],
                   batch_size=cfg["common"]["batch_size"],training_hyperparameters=training["hyperparameters"],
                   epochs_ending=training["epochs_ending"],best_epoch=training["best_epoch"],
                   total_training_seconds=training["total_training_seconds"],
                   model_size_bytes=training["model_size_bytes"],parameter_count=training["parameter_count"],
                   peak_vram_bytes=training["peak_vram_bytes"],evaluation_precision="fp32",
                   test_confidence_threshold=cfg["evaluation"]["confidence"],matching_iou_threshold=cfg["evaluation"]["match_iou"],
                   speed_protocol="batch=1; decoded RGB -> CPU detections; preprocess+transfer+forward+postprocess; CUDA synchronized; warmup excluded; arithmetic mean")
        for metric in ("map50","map50_95","precision","recall","f1_peak","f1_confidence","tp","fp","fn"):
            row["val_"+metric] = metrics["val"][metric]
        for metric in ("correct_predictions_percent","image_exact_match_percent","map50","map50_95","tp","fp","fn","inference_ms_per_image","average_confidence"):
            row["test_"+metric] = metrics["test"][metric]
        write_summary(directory,row)
        save_json(directory/"status.json",dict(status="complete"))
    except Exception as error:
        save_json(directory/"status.json",dict(status="failed",error=str(error)))
        raise
