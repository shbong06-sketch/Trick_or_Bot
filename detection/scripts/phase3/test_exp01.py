import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp01


class Experiment01Test(unittest.TestCase):
    def test_run_all_trains_then_validates_each_combination(self):
        with patch.object(exp01, "prepare") as prepare, \
                patch.object(exp01.subprocess, "run") as run, \
                patch.object(exp01, "collect") as collect, \
                patch("builtins.print"):
            exp01.run_all(True)
        expected = [(model, number) for model in ("yolo11n", "yolov8n")
                    for number in ("001", "002")]
        self.assertEqual([call.args for call in prepare.call_args_list],
                         [pair for pair in expected for _ in range(2)])
        self.assertEqual([(call.args[0][-6], call.args[0][-4], call.args[0][-2])
                          for call in run.call_args_list],
                         [(task, model, number) for model, number in expected
                          for task in ("train", "evaluate")])
        collect.assert_called_once_with()

    def test_prepare_changes_only_optimizer_settings(self):
        with tempfile.TemporaryDirectory(dir=exp01.ROOT) as temporary, patch.object(exp01, "EXPERIMENTS", Path(temporary)):
            adamw = exp01.prepare("yolo11n", "001")
            sgd = exp01.prepare("yolo11n", "002")
            adamw_options = (Path(temporary) / "001/yolo11n/native.yaml").read_text()
            sgd_options = (Path(temporary) / "002/yolo11n/native.yaml").read_text()
            import yaml
            a, b = yaml.safe_load(adamw_options), yaml.safe_load(sgd_options)
            self.assertEqual({key for key in a if a[key] != b[key]}, {"optimizer", "lr0", "momentum"})
            self.assertEqual(adamw["training"], sgd["training"])
            self.assertEqual(adamw["dataset"], sgd["dataset"])
            self.assertEqual(adamw["models"]["yolo11n"]["weights"], "yolo11n.pt")

    def test_collect_selects_models_independently_after_both_runs(self):
        base = dict(validation_recall=0.9, validation_f1=0.9, validation_map50_95=0.9,
                    validation_map50=0.9, best_epoch=10, time_to_best_seconds=20,
                    ending_epoch=30, total_training_seconds=60)
        results = {("yolo11n", "001"): {**base, "validation_map50_95": 0.92},
                   ("yolo11n", "002"): {**base, "validation_map50_95": 0.91},
                   ("yolov8n", "001"): {**base, "validation_map50_95": 0.90},
                   ("yolov8n", "002"): {**base, "validation_map50_95": 0.93}}
        with tempfile.TemporaryDirectory(dir=exp01.ROOT) as temporary, \
                patch.object(exp01, "EXPERIMENTS", Path(temporary) / "experiments"), \
                patch.object(exp01, "RESULTS", Path(temporary) / "results"), \
                patch.object(exp01, "measured", side_effect=lambda model, number: results[model, number]), \
                patch.object(exp01, "baseline_metrics", return_value=base):
            exp01.collect()
            selected = json.loads((Path(temporary) / "results/exp01_selection.json").read_text())
            self.assertEqual(selected["yolo11n"]["selected_experiment"], "001")
            self.assertEqual(selected["yolov8n"]["selected_experiment"], "002")
            with (Path(temporary) / "results/hyperparameter_summary.csv").open(newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 4)


if __name__ == "__main__":
    unittest.main()
