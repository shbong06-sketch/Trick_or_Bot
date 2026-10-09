#!/usr/bin/env python3
"""Read-only YOLO/COCO freeze and EDA. See detection/records/dataset_analysis/dataset_eda.md."""
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import yaml

SPLITS = ("train", "val", "test")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
METRICS = ("center_x", "center_y", "width", "height", "area", "aspect_ratio")


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filename_key(name):
    # Roboflow export suffix is not part of the original image identity.
    return re.sub(r"\.rf\.[^.]+$", "", Path(name).stem).casefold()


def bbox_record(fmt, split, name, reference, box, category, allowed, width, height, epsilon):
    errors = []
    if category not in allowed:
        errors.append("invalid_category_id")
    try:
        x, y, w, h = map(float, box)
        finite = all(math.isfinite(v) for v in (x, y, w, h))
    except (ValueError, TypeError):
        x = y = w = h = float("nan")
        finite = False
    if not finite:
        errors.append("malformed_or_nonfinite_bbox")
    else:
        if w <= 0 or h <= 0:
            errors.append("nonpositive_size")
        if x < -epsilon or y < -epsilon or x + w > width + epsilon or y + h > height + epsilon:
            errors.append("outside_image")
    edge = finite and w > 0 and h > 0 and any((
        abs(x) <= epsilon, abs(y) <= epsilon,
        abs(x + w - width) <= epsilon, abs(y + h - height) <= epsilon,
    ))
    result = dict(format=fmt, split=split, image=name, reference=reference,
                  category_id=category, x=x, y=y, pixel_width=w, pixel_height=h,
                  valid=not errors, errors=";".join(errors), edge_touch=edge,
                  outside_image="outside_image" in errors, explicit_truncated=None)
    if not errors:
        result.update(center_x=(x + w / 2) / width, center_y=(y + h / 2) / height,
                      width=w / width, height=h / height, area=w * h / (width * height),
                      aspect_ratio=w / h)
    return result


def analyze(root, output, expected_images=416, epsilon=1e-6, hash_threshold=5):
    root, output = root.resolve(), output.resolve()
    if output == root or root in output.parents:
        raise ValueError("Output must be outside the original dataset")
    config_path = root / "data.yaml"
    config = yaml.safe_load(config_path.read_text())
    names = config["names"]
    classes = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    issues, boxes, images, manifest, comparison = [], [], [], [], []
    frozen = set()

    def issue(fmt, split, name, message):
        issues.append(dict(format=fmt, split=split, image=name, issue=message))

    def freeze(path):
        if path not in frozen:
            frozen.add(path)
            manifest.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=sha256(path)))

    freeze(config_path)
    if sorted(classes.values()) != ["pumpkin"]:
        issue("YOLO", "all", "data.yaml", "expected_single_pumpkin_category")
    base = Path(config.get("path", "."))
    base = base if base.is_absolute() else root / base
    for split in SPLITS:
        directory = base / config[split]
        if not directory.is_dir():
            raise ValueError(f"Expected image directory: {directory}")
        paths = sorted(p for p in directory.rglob("*") if p.suffix.lower() in EXTENSIONS)
        image_map = {}
        for path in paths:
            freeze(path)
            relative = str(path.relative_to(directory))
            if relative in image_map:
                issue("YOLO", split, relative, "duplicate_image_name")
            try:
                with Image.open(path) as im:
                    im.load()
                    width, height = im.size
                    thumbnail = np.asarray(im.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
                    bits = (thumbnail[:, 1:] > thumbnail[:, :-1]).ravel()
                    dhash = sum(int(bit) << i for i, bit in enumerate(bits))
                    pixels = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
            except (OSError, ValueError) as exc:
                issue("YOLO", split, relative, f"unreadable_image:{exc}")
                continue
            item = dict(split=split, image=relative, width=width, height=height,
                        dhash=dhash, pixel_hash=pixels, file_hash=sha256(path), key=filename_key(relative))
            images.append(item)
            image_map[relative] = item
            image_relative = path.relative_to(base)
            if image_relative.parts[0] != "images":
                raise ValueError("YOLO layout must be images/<split> and labels/<split>")
            label = base / "labels" / Path(*image_relative.parts[1:]).with_suffix(".txt")
            if not label.exists():
                issue("YOLO", split, relative, "missing_label_unknown_not_negative")
                item["yolo_known"] = False
                continue
            item["yolo_known"] = True
            freeze(label)
            for line_number, line in enumerate(label.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                parts = line.split()
                try:
                    category = int(parts[0])
                    cx, cy, w, h = map(float, parts[1:])
                    box = ((cx - w / 2) * width, (cy - h / 2) * height, w * width, h * height)
                except (ValueError, IndexError):
                    category, box = None, []
                boxes.append(bbox_record("YOLO", split, relative, line_number, box, category,
                                         classes, width, height, epsilon))
        label_dir = base / "labels" / directory.relative_to(base / "images")
        expected_labels = {Path(name).with_suffix(".txt") for name in image_map}
        for label in sorted(label_dir.rglob("*.txt")):
            freeze(label)
            if label.relative_to(label_dir) not in expected_labels:
                issue("YOLO", split, str(label.relative_to(label_dir)), "orphan_label")

        ann_path = root / "annotations" / f"instances_{directory.name}.json"
        freeze(ann_path)
        coco = json.loads(ann_path.read_text())
        categories = {c["id"]: c["name"] for c in coco["categories"]}
        allowed = {cid for cid, name in categories.items() if name == "pumpkin"}
        if sorted(categories.values()) != ["pumpkin"]:
            issue("COCO", split, "", "expected_single_pumpkin_category")
        ids, coco_names, ann_ids = {}, Counter(), set()
        for im in coco["images"]:
            name = im["file_name"]
            coco_names[name] += 1
            if im["id"] in ids:
                issue("COCO", split, name, "duplicate_image_id")
            ids[im["id"]] = im
            if name in image_map:
                image_map[name]["coco_known"] = True
                if (im.get("width"), im.get("height")) != (image_map[name]["width"], image_map[name]["height"]):
                    issue("COCO", split, name, "resolution_metadata_mismatch")
        for name, count in coco_names.items():
            if count > 1:
                issue("COCO", split, name, "duplicate_image_name")
        for name in sorted(set(image_map) | set(coco_names)):
            comparison.append(dict(split=split, image=name, in_yolo=name in image_map,
                                   in_coco=name in coco_names, match=name in image_map and name in coco_names))
        for ann in coco["annotations"]:
            if ann.get("id") in ann_ids:
                issue("COCO", split, "", "duplicate_annotation_id")
            ann_ids.add(ann.get("id"))
            im = ids.get(ann.get("image_id"))
            if im is None:
                issue("COCO", split, "", f"orphan_annotation:{ann.get('id')}")
                continue
            actual = image_map.get(im["file_name"], im)
            if actual["width"] <= 0 or actual["height"] <= 0:
                issue("COCO", split, im["file_name"], "invalid_image_resolution")
                continue
            record = bbox_record("COCO", split, im["file_name"], ann.get("id"), ann.get("bbox"),
                                 ann.get("category_id"), allowed, actual["width"], actual["height"], epsilon)
            if "truncated" in ann and ann["truncated"] in (0, 1, False, True):
                record["explicit_truncated"] = bool(ann["truncated"])
            boxes.append(record)

    output.mkdir(parents=True, exist_ok=True)
    summaries, negatives, distributions = [], [], []
    for fmt, split in itertools.product(("YOLO", "COCO"), SPLITS):
        ims = [im for im in images if im["split"] == split]
        bs = [b for b in boxes if b["format"] == fmt and b["split"] == split]
        known = [im for im in ims if im.get(fmt.lower() + "_known", False)]
        counts = Counter(b["image"] for b in bs)
        positive = sum(counts[im["image"]] > 0 for im in known)
        negative = len(known) - positive
        valid = [b for b in bs if b["valid"]]
        edge = sum(b["edge_touch"] for b in valid)
        explicit = [b for b in bs if b["explicit_truncated"] is not None]
        row = dict(format=fmt, split=split, images=len(ims), annotations=len(bs),
                   valid_annotations=len(valid), invalid_annotations=len(bs)-len(valid),
                   positive_images=positive, negative_images=negative, unknown_images=len(ims)-len(known),
                   positive_ratio=positive/len(ims) if ims else 0,
                   negative_ratio=negative/len(ims) if ims else 0,
                   image_ratio=len(ims)/len(images) if images else 0,
                   target_ratio={"train": .7, "val": .2, "test": .1}[split],
                   edge_touch_annotations=edge, edge_touch_ratio=edge/len(valid) if valid else 0,
                   outside_annotations=sum(b["outside_image"] for b in bs),
                   explicit_truncated_annotations=sum(b["explicit_truncated"] for b in explicit),
                   explicit_truncated_ratio=sum(b["explicit_truncated"] for b in explicit)/len(explicit) if explicit else "",
                   truncated_metadata_annotations=len(explicit))
        summaries.append(row)
        negatives.append({k: row[k] for k in ("format", "split", "images", "positive_images", "negative_images", "unknown_images", "positive_ratio", "negative_ratio")})
        for metric in METRICS:
            values = np.array([b[metric] for b in valid])
            stats = dict(format=fmt, split=split, metric=metric, count=len(values))
            for key, value in zip(("min", "p25", "median", "p75", "max"), np.percentile(values, [0,25,50,75,100]) if len(values) else [""]*5):
                stats[key] = value
            stats["mean"] = float(values.mean()) if len(values) else ""
            stats["std"] = float(values.std()) if len(values) else ""
            distributions.append(stats)

    leakage = []
    for a, b in itertools.combinations(images, 2):
        if a["split"] == b["split"]:
            continue
        distance = (a["dhash"] ^ b["dhash"]).bit_count()
        reasons = []
        if a["key"] == b["key"]:
            reasons.append("filename_identity")
        if a["file_hash"] == b["file_hash"]:
            reasons.append("identical_file")
        if (a["width"], a["height"], a["pixel_hash"]) == (b["width"], b["height"], b["pixel_hash"]):
            reasons.append("identical_pixels")
        if distance <= hash_threshold:
            reasons.append("similar_dhash")
        if reasons:
            leakage.append(dict(split_a=a["split"], image_a=a["image"], split_b=b["split"], image_b=b["image"], dhash_distance=distance, reasons=";".join(reasons)))
    dataset_rows = []
    for fmt in ("YOLO", "COCO"):
        rows = [r for r in summaries if r["format"] == fmt]
        dataset_rows.append(dict(dataset="trick_or_bot_v01", format=fmt, expected_images=expected_images,
                                 images=len(images), image_count_matches=len(images)==expected_images,
                                 classes=json.dumps(classes if fmt == "YOLO" else "pumpkin", ensure_ascii=False),
                                 annotations=sum(r["annotations"] for r in rows),
                                 invalid_annotations=sum(r["invalid_annotations"] for r in rows),
                                 split_mismatches=sum(not r["match"] for r in comparison),
                                 leakage_candidate_pairs=len(leakage), structural_issues=sum(i["format"]==fmt for i in issues)))
    tables = {
        "dataset_summary.csv": (dataset_rows, list(dataset_rows[0])),
        "split_summary.csv": (summaries, list(summaries[0])),
        "negative_image_summary.csv": (negatives, list(negatives[0])),
        "bbox_distribution_summary.csv": (distributions, list(distributions[0])),
        "split_comparison.csv": (comparison, ["split","image","in_yolo","in_coco","match"]),
        "leakage_candidates.csv": (leakage, ["split_a","image_a","split_b","image_b","dhash_distance","reasons"]),
        "validation_issues.csv": (issues, ["format","split","image","issue"]),
        "freeze_manifest.csv": (sorted(manifest, key=lambda r:r["path"]), ["path","bytes","sha256"]),
        "invalid_bboxes.csv": ([{k:b[k] for k in ("format","split","image","reference","category_id","x","y","pixel_width","pixel_height","errors")} for b in boxes if not b["valid"]], ["format","split","image","reference","category_id","x","y","pixel_width","pixel_height","errors"]),
    }
    resolutions = Counter((im["split"], im["width"], im["height"]) for im in images)
    tables["image_resolution_summary.csv"] = ([dict(split=s,width=w,height=h,images=n,ratio=n/sum(im["split"]==s for im in images)) for (s,w,h),n in sorted(resolutions.items())], ["split","width","height","images","ratio"])
    for name, (rows, fields) in tables.items():
        write_csv(output/name, rows, fields)
    for filename, metrics in (("bbox_center_distribution.png", ("center_x", "center_y")),
                              ("bbox_size_distribution.png", ("width", "height", "aspect_ratio")),
                              ("bbox_area_distribution.png", ("area",))):
        fig, axes = plt.subplots(2, len(metrics), figsize=(5*len(metrics), 7), squeeze=False)
        for row, fmt in enumerate(("YOLO", "COCO")):
            for col, metric in enumerate(metrics):
                ax = axes[row, col]
                all_values = [b[metric] for b in boxes if b["valid"] and b["format"]==fmt]
                bins = np.linspace(0, max(all_values, default=1) or 1, 31) if metric=="aspect_ratio" else np.linspace(0,1,31)
                for split in SPLITS:
                    values = [b[metric] for b in boxes if b["valid"] and b["format"]==fmt and b["split"]==split]
                    if values:
                        ax.hist(values, bins=bins, weights=np.ones(len(values))/len(values), histtype="step", linewidth=1.8, label=f"{split} (n={len(values)})")
                ax.set(title=f"{fmt}: {metric}", xlabel=metric, ylabel="Fraction of valid boxes")
                if ax.get_legend_handles_labels()[0]:
                    ax.legend()
                ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(output/filename, dpi=160)
        plt.close(fig)
    digest = hashlib.sha256((output/"freeze_manifest.csv").read_bytes()).hexdigest()
    report = ["# Phase 0 Dataset Freeze & EDA", "", f"Dataset: trick_or_bot_v01 · root: `{root}`", "",
              f"Expected images: **{expected_images}**; observed readable images: **{len(images)}**. Count matches: **{len(images)==expected_images}**.",
              f"Manifest SHA-256: `{digest}`. Original dataset is read only; no split changes or clipping performed.", "",
              "## Split comparison", "", "| Format | Split | Images | Annotations | Positive | Negative | Unknown | Invalid | Edge touch |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in summaries:
        report.append(f"| {r['format']} | {r['split']} | {r['images']} | {r['annotations']} | {r['positive_images']} ({r['positive_ratio']:.1%}) | {r['negative_images']} ({r['negative_ratio']:.1%}) | {r['unknown_images']} | {r['invalid_annotations']} | {r['edge_touch_ratio']:.1%} |")
    report += ["", "## Freeze checks", "",
               f"- YOLO/COCO split membership mismatches: {sum(not r['match'] for r in comparison)}. See split_comparison.csv.",
               f"- Structural issues: {len(issues)}; invalid boxes: {sum(not b['valid'] for b in boxes)}. See validation_issues.csv and invalid_bboxes.csv.",
               f"- Cross-split leakage candidates: {len(leakage)}. See leakage_candidates.csv; manual review required.",
               f"- Candidate evidence: filename identity {sum('filename_identity' in r['reasons'] for r in leakage)}, identical files {sum('identical_file' in r['reasons'] for r in leakage)}, identical decoded pixels {sum('identical_pixels' in r['reasons'] for r in leakage)}, dHash similarity {sum('similar_dhash' in r['reasons'] for r in leakage)} pairs (evidence can overlap).",
               f"- Actual split: " + ", ".join(f"{s}={sum(im['split']==s for im in images)}/{len(images)}" for s in SPLITS) + "; target 70/20/10%.",
               "- A count mismatch, invalid annotations, structural errors or unresolved leakage candidates prevents an unconditional freeze approval.",
               "", "## Definitions and formulas", "",
               "- YOLO: class_id cx cy w h, normalized. Convert to pixels: x=(cx-w/2)W, y=(cy-h/2)H, bw=wW, bh=hH. COCO: [x,y,bw,bh] in pixels. Categories are checked independently: YOLO data.yaml IDs; COCO category IDs named pumpkin (no assumed 0/1 mapping).",
               "- Center: ((x+bw/2)/W, (y+bh/2)/H); normalized width=bw/W, height=bh/H; normalized area=bw*bh/(W*H); aspect ratio=bw/bh in pixel coordinates.",
               "- All parsed annotation rows, including invalid rows, count as annotations. Positive means at least one annotation row, not necessarily a valid box. Negative means a present empty YOLO label or a COCO image with zero annotations. Missing YOLO labels/COCO records are unknown, never silently negative. Ratios use readable physical images per split as denominator. Orphan COCO annotations are listed as structural issues and excluded from bbox counts.",
               "- Distribution statistics and charts include only finite, positive-size, in-boundary, valid-category boxes. Percentiles use numpy linear interpolation; std is population standard deviation (ddof=0). Histogram heights are per-split bin counts / valid bbox count, with common bins across splits. Aspect ratio uses the full observed range; other axes use [0,1].",
               f"- Boundary tolerance: {epsilon} pixels (floating-point tolerance, not a visual margin). Invalid outside: x < -eps, y < -eps, x+bw > W+eps, or y+bh > H+eps. Edge touch: any boundary distance <= eps among valid boxes; denominator = valid boxes.",
               "- Truncation cannot be established from a bbox alone. Edge contact is a truncation candidate proxy, outside-image counts indicate geometric overflow. Explicit truncated ratio = true flags / annotations carrying a recognized truncated flag; blank CSV ratio means no metadata. iscrowd is not a truncation flag.",
               "- Resolution comes from Pillow-decoded image dimensions, compared with COCO metadata. Resolution ratio = images with that resolution / readable images in split.",
               "- Split matching compares exact relative image filenames in YOLO physical directories and COCO image records, retaining negative images. val maps to the configured valid directory. No filename identity heuristic is used for this equality check.",
               f"- Leakage compares every pair from different splits. Filename identity strips Roboflow .rf.<hash> and case-folds; exact file SHA-256 and decoded RGB SHA-256 detect exact duplicates. dHash uses grayscale 9x8 LANCZOS pixels and 64 horizontal comparisons; Hamming distance <= {hash_threshold} is a near-duplicate candidate. Similar backgrounds can yield false positives; crops/rotations can evade detection. Filenames alone do not establish capture-session independence.",
               "- freeze_manifest.csv hashes all analyzed images, labels, COCO JSON and data.yaml, ordered by dataset-relative path. It records byte counts and file SHA-256. Unrelated raw_data is excluded. Compare manifests between runs to detect changes; source files must remain stable during analysis.",
               "", "## Distribution and resolution tables", "", "See bbox_distribution_summary.csv (min/p25/median/p75/max/mean/std), image_resolution_summary.csv, and split_summary.csv for machine-readable comparisons.",
               "", "| Split | Resolution | Images |", "|---|---|---:|",
               *[f"| {s} | {w} x {h} | {n} |" for (s,w,h),n in sorted(resolutions.items())],
               "", "![Centers](bbox_center_distribution.png)", "![Sizes](bbox_size_distribution.png)", "![Areas](bbox_area_distribution.png)",
               "", "## Reproduce", "", "From repository root:", "", "```bash", "python3 -m pip install -r detection/scripts/requirements-analysis.txt",
               f"python3 detection/scripts/analyze_dataset.py --dataset-root {root} --output-dir {output} --expected-images {expected_images} --edge-epsilon {epsilon} --dhash-threshold {hash_threshold}", "```", "", "Dependencies: numpy, matplotlib (Agg backend), Pillow, PyYAML. Tests: python3 -m unittest discover -s detection/scripts/tests."]
    (output/"dataset_eda.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(f"Analyzed {len(images)} images, {len(boxes)} YOLO+COCO boxes; {len(leakage)} leakage candidates -> {output}")
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path(__file__).resolve().parents[1]/"dataset")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1]/"records"/"dataset_analysis")
    parser.add_argument("--expected-images", type=int, default=416)
    parser.add_argument("--edge-epsilon", type=float, default=1e-6)
    parser.add_argument("--dhash-threshold", type=int, default=5)
    args = parser.parse_args()
    if args.edge_epsilon < 0 or not math.isfinite(args.edge_epsilon) or not 0 <= args.dhash_threshold <= 64:
        parser.error("edge-epsilon must be finite and nonnegative; dhash-threshold must be 0..64")
    analyze(args.dataset_root, args.output_dir, args.expected_images, args.edge_epsilon, args.dhash_threshold)


if __name__ == "__main__":
    main()
