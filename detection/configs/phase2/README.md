# Phase 2 augmentation comparison

`scripts/phase2.py` reads the four selected models from
`records/phase1/model_comparison.csv` and checks each Phase 1 detailed JSON.
`baseline.yaml` points to the original Phase 1 checkpoint and metrics; it never
starts a new training run. The three other conditions start from the same
pretrained weights and use the Phase 1 training schedule and evaluation schema.

The train split alone receives these transforms. Validation and test use the
original Phase 1 split and evaluation settings. Native Mosaic, MixUp, CutMix,
vertical flip, and YOLO copy-paste are off for A/B/C. Phase 1 baseline settings
remain untouched.

| Condition | Spatial | Color |
| --- | --- | --- |
| spatial (A) | horizontal flip 0.5, ±5° rotation, ±20% translation, 0.7–1.3 scale | none |
| photometric (B) | none | ±0.005 hue, ±20% saturation, ±25% brightness, ±18% contrast where supported |
| combined (C) | horizontal flip 0.5, ±5° rotation, ±15% translation, 0.8–1.2 scale | ±0.005 hue, ±15% saturation, ±20% brightness, ±15% contrast where supported |

YOLO's native training interface exposes HSV augmentation but no independent
contrast parameter. Its Phase 2 runner adds a contrast-only Albumentations
transform for B/C and removes the default blur/gray transforms for A/B/C.
D-FINE uses registered
torchvision v2 `RandomAffine` and `ColorJitter`; RF-DETR uses its Albumentations
backend, installed via the RF-DETR Docker `augment` extra. The frameworks sample
these transforms differently, so matching the experimental intent takes priority
over forcing identical distributions.

## Commands

From `detection/`, build the RF-DETR image after the Dockerfile change, then run
all conditions sequentially. Without `--execute`, `run-all` prints the 12 train
and evaluation commands in execution order without starting training.

```bash
docker compose -f docker/rfdetr/docker-compose.yaml build trainer
python3 scripts/phase2.py run-all
python3 scripts/phase2.py run-all --execute
```

The order is YOLO11n, YOLOv8n, RF-DETR-N, D-FINE-N; each model runs spatial,
photometric, then combined. Every training run is followed by its evaluation.
Baseline is reused without training. The command stops on the first failure and
collects the results after all 12 runs succeed. To run only one model, pass
`--model yolo11n` to `run-all`.

Individual runs remain available:

```bash
python3 scripts/phase2.py train --model yolo11n --condition spatial --execute
python3 scripts/phase2.py evaluate --model yolo11n --condition spatial --execute
python3 scripts/phase2.py collect
```

Use `yolo11n`, `yolov8n`, `rfdetr_n`, or `dfine_n` with `spatial`,
`photometric`, or `combined`. `collect` writes
`results/phase2/augmentation_summary.csv`, `augmentation_delta.csv`, and one
`<model>/details.json` per model. Before training and evaluation, A/B/C rows are
marked `pending` and their metrics and deltas are blank. This avoids presenting
unmeasured numbers as results. Deltas use validation mAP50, precision, recall,
and F1; correct prediction rate and inference time use the test split. A positive
inference speed percentage means the new condition is faster. The millisecond
delta is new minus baseline, so a negative value means lower latency.
