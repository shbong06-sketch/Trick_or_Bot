import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp05


class Experiment05Test(unittest.TestCase):
    def test_cosine_changes_only_scheduler_flag(self):
        with tempfile.TemporaryDirectory(dir=exp05.ROOT) as temporary, \
                patch.object(exp05, "EXPERIMENTS", Path(temporary)):
            for model, source, lr, decay in (("yolo11n", "004", 0.02, 0.0005),
                                             ("yolov8n", "007", 0.01, 0.001)):
                parent, _, inherited_from = exp05.reference(model)
                cfg = exp05.prepare(model)
                applied = yaml.safe_load((Path(temporary) / "008" / model / "exp05_config.yaml").read_text())
                native = applied["native"]
                self.assertIn(f"/{source}/{model}/", inherited_from)
                self.assertEqual({key for key in native if native[key] != parent["native"][key]}, {"cos_lr"})
                self.assertIs(native["cos_lr"], True)
                self.assertEqual(native["optimizer"], "SGD")
                self.assertEqual(native["lr0"], lr)
                self.assertEqual(native["momentum"], 0.937)
                self.assertEqual(native["weight_decay"], decay)
                self.assertEqual(cfg["training"], parent["training"])

    def test_run_all_only_trains_008(self):
        with patch.object(exp05, "prepare") as prepare, \
                patch.object(exp05.subprocess, "run") as run, \
                patch.object(exp05, "collect") as collect, patch("builtins.print"):
            exp05.run_all(True)
        self.assertEqual([call.args for call in prepare.call_args_list],
                         [("yolo11n",), ("yolo11n",), ("yolov8n",), ("yolov8n",)])
        self.assertEqual([(call.args[0][-4], call.args[0][-2]) for call in run.call_args_list],
                         [(task, model) for model in ("yolo11n", "yolov8n")
                          for task in ("train", "evaluate")])
        collect.assert_called_once_with()

    def test_collect_selects_and_writes_best_configs(self):
        references = {model: exp05.reference(model)[1] for model in ("yolo11n", "yolov8n")}

        def measured(model):
            delta = 0.01 if model == "yolo11n" else -0.01
            return {**references[model],
                    "validation_map50_95": references[model]["validation_map50_95"] + delta}

        with tempfile.TemporaryDirectory(dir=exp05.ROOT) as temporary, \
                patch.object(exp05, "EXPERIMENTS", Path(temporary) / "experiments"), \
                patch.object(exp05, "RESULTS", Path(temporary) / "results"), \
                patch.object(exp05, "measured", side_effect=measured):
            exp05.prepare("yolo11n")
            exp05.prepare("yolov8n")
            exp05.collect()
            selected = json.loads((Path(temporary) / "results/exp05_selection.json").read_text())
            self.assertEqual(selected["yolo11n"]["selected_experiment"], "008")
            self.assertEqual(selected["yolov8n"]["selected_experiment"], "007")
            best11 = yaml.safe_load((Path(temporary) / "results/yolo11n_best.yaml").read_text())
            best8 = yaml.safe_load((Path(temporary) / "results/yolov8n_best.yaml").read_text())
            self.assertIs(best11["native"]["cos_lr"], True)
            self.assertIs(best8["native"]["cos_lr"], False)
            with (Path(temporary) / "results/exp05_summary.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row["status"] == "reused_exp04" for row in rows), 2)


if __name__ == "__main__":
    unittest.main()
