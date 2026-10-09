import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp03


class Experiment03Test(unittest.TestCase):
    def test_batch_8_inherits_each_selected_optimizer_and_lr(self):
        with tempfile.TemporaryDirectory(dir=exp03.ROOT) as temporary, \
                patch.object(exp03, "EXPERIMENTS", Path(temporary)):
            for model, lr, source in (("yolo11n", 0.02, "004"), ("yolov8n", 0.01, "002")):
                parent, _, inherited_from = exp03.reference(model)
                cfg = exp03.prepare(model)
                applied = yaml.safe_load((Path(temporary) / "005" / model / "exp03_config.yaml").read_text())
                native = applied["native"]
                self.assertIn(f"/{source}/{model}/", inherited_from)
                self.assertEqual(cfg["training"]["batch_size"], 8)
                self.assertEqual(native["nbs"], 8)
                self.assertEqual(native["optimizer"], "SGD")
                self.assertEqual(native["lr0"], lr)
                self.assertEqual(native["momentum"], 0.937)
                self.assertEqual({key for key in native if native[key] != parent["native"][key]}, {"nbs"})
                self.assertEqual({key for key in cfg["training"] if cfg["training"][key] != parent["training"][key]},
                                 {"batch_size"})

    def test_run_all_only_trains_005(self):
        with patch.object(exp03, "prepare") as prepare, \
                patch.object(exp03.subprocess, "run") as run, \
                patch.object(exp03, "collect") as collect, patch("builtins.print"):
            exp03.run_all(True)
        self.assertEqual([call.args for call in prepare.call_args_list],
                         [("yolo11n",), ("yolo11n",), ("yolov8n",), ("yolov8n",)])
        self.assertEqual([(call.args[0][-4], call.args[0][-2]) for call in run.call_args_list],
                         [(task, model) for model in ("yolo11n", "yolov8n")
                          for task in ("train", "evaluate")])
        collect.assert_called_once_with()

    def test_collect_can_retain_reused_batch_16(self):
        references = {model: exp03.reference(model)[1] for model in ("yolo11n", "yolov8n")}

        def measured(model):
            delta = 0.01 if model == "yolo11n" else -0.01
            return {**references[model],
                    "validation_map50_95": references[model]["validation_map50_95"] + delta}

        with tempfile.TemporaryDirectory(dir=exp03.ROOT) as temporary, \
                patch.object(exp03, "EXPERIMENTS", Path(temporary) / "experiments"), \
                patch.object(exp03, "RESULTS", Path(temporary) / "results"), \
                patch.object(exp03, "measured", side_effect=measured):
            exp03.collect()
            selected = json.loads((Path(temporary) / "results/exp03_selection.json").read_text())
            self.assertEqual(selected["yolo11n"]["selected_experiment"], "005")
            self.assertEqual(selected["yolo11n"]["batch_size"], 8)
            self.assertEqual(selected["yolov8n"]["selected_experiment"], "002")
            self.assertEqual(selected["yolov8n"]["batch_size"], 16)
            with (Path(temporary) / "results/exp03_summary.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row["status"] == "reused_exp02" for row in rows), 2)


if __name__ == "__main__":
    unittest.main()
