import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp04


class Experiment04Test(unittest.TestCase):
    def test_new_runs_change_only_weight_decay(self):
        with tempfile.TemporaryDirectory(dir=exp04.ROOT) as temporary, \
                patch.object(exp04, "EXPERIMENTS", Path(temporary)):
            for model, lr, source in (("yolo11n", 0.02, "004"), ("yolov8n", 0.01, "002")):
                parent, _, inherited_from = exp04.reference(model)
                self.assertIn(f"/{source}/{model}/", inherited_from)
                for number, decay in (("006", 0.0001), ("007", 0.001)):
                    cfg = exp04.prepare(model, number)
                    applied = yaml.safe_load((Path(temporary) / number / model / "exp04_config.yaml").read_text())
                    native = applied["native"]
                    self.assertEqual({key for key in native if native[key] != parent["native"][key]},
                                     {"weight_decay"})
                    self.assertEqual(native["weight_decay"], decay)
                    self.assertEqual(native["optimizer"], "SGD")
                    self.assertEqual(native["lr0"], lr)
                    self.assertEqual(native["momentum"], 0.937)
                    self.assertEqual(cfg["training"], parent["training"])
                    self.assertEqual(cfg["training"]["batch_size"], 16)

    def test_run_all_only_trains_006_and_007(self):
        with patch.object(exp04, "prepare") as prepare, \
                patch.object(exp04.subprocess, "run") as run, \
                patch.object(exp04, "collect") as collect, patch("builtins.print"):
            exp04.run_all(True)
        expected = [(model, number) for model in ("yolo11n", "yolov8n")
                    for number in ("006", "007")]
        self.assertEqual([call.args for call in prepare.call_args_list],
                         [pair for pair in expected for _ in range(2)])
        self.assertEqual([(call.args[0][-6], call.args[0][-4], call.args[0][-2])
                          for call in run.call_args_list],
                         [(task, model, number) for model, number in expected
                          for task in ("train", "evaluate")])
        collect.assert_called_once_with()

    def test_collect_can_retain_reused_weight_decay(self):
        references = {model: exp04.reference(model)[1] for model in ("yolo11n", "yolov8n")}

        def measured(model, number):
            delta = {("yolo11n", "006"): 0.01, ("yolo11n", "007"): -0.01,
                     ("yolov8n", "006"): -0.01, ("yolov8n", "007"): -0.02}[model, number]
            return {**references[model],
                    "validation_map50_95": references[model]["validation_map50_95"] + delta}

        with tempfile.TemporaryDirectory(dir=exp04.ROOT) as temporary, \
                patch.object(exp04, "EXPERIMENTS", Path(temporary) / "experiments"), \
                patch.object(exp04, "RESULTS", Path(temporary) / "results"), \
                patch.object(exp04, "measured", side_effect=measured):
            exp04.collect()
            selected = json.loads((Path(temporary) / "results/exp04_selection.json").read_text())
            self.assertEqual(selected["yolo11n"]["selected_experiment"], "006")
            self.assertEqual(selected["yolo11n"]["weight_decay"], 0.0001)
            self.assertEqual(selected["yolov8n"]["selected_experiment"], "002")
            self.assertEqual(selected["yolov8n"]["weight_decay"], 0.0005)
            with (Path(temporary) / "results/exp04_summary.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(row["status"] == "reused_exp03" for row in rows), 2)


if __name__ == "__main__":
    unittest.main()
