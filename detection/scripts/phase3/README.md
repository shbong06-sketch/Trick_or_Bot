# Phase 3 execution structure

Each stage has one script. Experiments 01 and 02 are implemented. Each model makes its own selection using validation; later stages inherit that model's selected settings.

| Script | Comparison | Experiment numbers |
| --- | --- | --- |
| `exp01.py` | AdamW vs SGD | 001, 002 |
| `exp02.py` | SGD LR 0.005 and 0.02 vs reused exp01 LR 0.01 | 003, 004; reuse 002 |
| `exp03.py` | selected optimizer and LR; batch 8 vs 16 | assigned after exp02 |
| `exp04.py` | selected settings; weight decay 0.0001, 0.0005, 0.001 | assigned later |
| `exp05.py` | selected settings; LambdaLR vs cosine | assigned later |

The same experiment number is used for both models. Training files, checkpoints, epoch logs, and validation details are stored at `experiments/phase3/<number>/<model>/`. Only summary CSVs and selection JSONs are stored in `results/phase3/`. Runs within a stage are independent; they can be dispatched on separate GPUs, or one at a time on the configured L4. `collect` selects each model independently after the required new runs have validation results.

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

## Experiment 02

`exp02.py` checks that both models selected SGD at `lr0=0.01` in exp01 and reads each model's completed 002 validation result. It creates only two new LR conditions per model: 003 uses 0.005 and 004 uses 0.02. The new runs inherit 002's training and native YOLO settings, changing only `lr0`; they start again from the original pretrained weights.

```bash
python3 scripts/phase3/exp02.py list
python3 scripts/phase3/exp02.py run-all            # print the four new train/evaluate pairs
python3 scripts/phase3/exp02.py run-all --execute  # run sequentially on the configured GPU
python3 scripts/phase3/exp02.py collect            # CPU-only summary refresh
```

The exp02 summary contains 002 as `reused_exp01` alongside 003 and 004. `exp02_delta.csv` compares every LR with 002. The cumulative `hyperparameter_summary.csv` and `hyperparameter_delta.csv` keep the exp01 rows and add the two new runs per model; their deltas remain relative to the Phase 2 baseline. Official Test is never read for selection.
