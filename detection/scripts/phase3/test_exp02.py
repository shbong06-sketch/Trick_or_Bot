import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp02


class Experiment02Test(unittest.TestCase):
    def test_new_runs_change_only_lr(self):
        parent, _ = exp02.reference("yolo11n")
        with tempfile.TemporaryDirectory(dir=exp02.ROOT) as temporary, \
                patch.object(exp02, "EXPERIMENTS", Path(temporary)):
            cfg003 = exp02.prepare("yolo11n", "003")
            cfg004 = exp02.prepare("yolo11n", "004")
            for number, lr in (("003", 0.005), ("004", 0.02)):
                native = yaml.safe_load((Path(temporary) / number / "yolo11n/native.yaml").read_text())
                self.assertEqual({key for key in native if native[key] != parent["native"][key]}, {"lr0"})
                self.assertEqual(native["lr0"], lr)
            self.assertEqual(cfg003["training"], cfg004["training"])
            self.assertEqual(cfg003["models"]["yolo11n"]["weights"], "yolo11n.pt")

    def test_run_all_skips_reused_002(self):
        with patch.object(exp02, "prepare"), patch.object(exp02.subprocess, "run") as run, \
                patch.object(exp02, "collect") as collect, patch("builtins.print"):
            exp02.run_all(True)
        self.assertEqual([(call.args[0][-6], call.args[0][-4], call.args[0][-2])
                          for call in run.call_args_list],
                         [(task, model, number) for model in ("yolo11n", "yolov8n")
                          for number in ("003", "004") for task in ("train", "evaluate")])
        collect.assert_called_once_with()

    def test_collect_can_keep_reused_lr_as_winner(self):
        references = {model: exp02.reference(model)[1] for model in ("yolo11n", "yolov8n")}

        def measured(model, number):
            delta = {("yolo11n", "003"): 0.01, ("yolo11n", "004"): -0.01,
                     ("yolov8n", "003"): -0.01, ("yolov8n", "004"): -0.02}[model, number]
            return {**references[model], "validation_map50_95": references[model]["validation_map50_95"] + delta}

        with tempfile.TemporaryDirectory(dir=exp02.ROOT) as temporary, \
                patch.object(exp02, "EXPERIMENTS", Path(temporary) / "experiments"), \
                patch.object(exp02, "RESULTS", Path(temporary) / "results"), \
                patch.object(exp02, "measured", side_effect=measured):
            exp02.collect()
            result = json.loads((Path(temporary) / "results/exp02_selection.json").read_text())
            self.assertEqual(result["yolo11n"]["selected_experiment"], "003")
            self.assertEqual(result["yolov8n"]["selected_experiment"], "002")
            with (Path(temporary) / "results/exp02_summary.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(row["status"] == "reused_exp01" for row in rows), 2)


if __name__ == "__main__":
    unittest.main()
