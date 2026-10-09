# Phase 3 execution structure

Each stage has one script. Only `exp01.py` is implemented now. After both optimizer runs finish and validation selects a winner **for each model**, `exp02.py` can be written using those two selected optimizer settings. The later stages follow the same pattern:

| Script | Comparison | Experiment numbers |
| --- | --- | --- |
| `exp01.py` | AdamW vs SGD | 001, 002 |
| `exp02.py` | selected optimizer; LR 0.5x, 1x, 2x | 003–005 |
| `exp03.py` | selected optimizer and LR; batch 8 vs 16 | 006, 007 |
| `exp04.py` | selected settings; weight decay 0.0001, 0.0005, 0.001 | 008–010 |
| `exp05.py` | selected settings; LambdaLR vs cosine | 011, 012 |

The same experiment number is used for both models. Training files, checkpoints, epoch logs, and validation details are stored at `experiments/phase3/<number>/<model>/`. Only summary CSVs and `exp01_selection.json` are stored in `results/phase3/`. Runs within a stage are independent; they can be dispatched on separate GPUs, or one at a time on the configured L4. `collect` selects each model independently after both candidates have validation results.

The completed exp01 runs were moved from `results/phase3/` to `experiments/phase3/`. Each moved run has `relocation.json`. Its original `args.yaml` and `config.yaml` retain the paths recorded at training time; the collector reads the current experiment directory.

From `detection/`, preview the commands:

```bash
python3 scripts/phase3/exp01.py list
python3 scripts/phase3/exp01.py run-all
```

To execute all four combinations sequentially on the configured GPU, training and then evaluating validation for each one, run:

```bash
python3 scripts/phase3/exp01.py run-all --execute
```

The order is YOLO11n 001, YOLO11n 002, YOLOv8n 001, YOLOv8n 002. A failed train or evaluation stops the sequence; selection is collected only after all four succeed. Individual `train`, `evaluate`, and `collect` commands remain available. The script trains from each model's original pretrained weights, uses the Phase 2 baseline augmentation and Phase 1 data, seed, and evaluation settings. The only compared variable is the optimizer with its appropriate starting LR and momentum. Evaluation reads validation only; Official Test is unused. `collect` writes the summary and baseline deltas with blank fields for unfinished runs, plus `exp01_selection.json`. GPU training occurs only with `--execute`.
