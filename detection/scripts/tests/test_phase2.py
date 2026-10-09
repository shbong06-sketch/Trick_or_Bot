import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phase2
import evaluate_models


class Phase2CollectionTests(unittest.TestCase):
    def test_run_all_trains_and_evaluates_in_order_then_collects(self):
        calls = []
        with patch.object(phase2, "selected_phase1", return_value={}), \
             patch.object(phase2, "condition_config", return_value={}), \
             patch.object(phase2, "run_train", side_effect=lambda model, condition, inside: calls.append(("train", model, condition))), \
             patch.object(phase2, "run_evaluate", side_effect=lambda model, condition, inside: calls.append(("evaluate", model, condition))), \
             patch.object(phase2, "collect", side_effect=lambda: calls.append(("collect",))), \
             patch("sys.stdout", new_callable=io.StringIO):
            phase2.run_all(("yolo11n", "dfine_n"), execute=True)
        expected = []
        for model in ("yolo11n", "dfine_n"):
            for condition in phase2.CONDITIONS[1:]:
                expected.extend((("train", model, condition), ("evaluate", model, condition)))
        self.assertEqual(calls, expected + [("collect",)])

    def test_run_all_stops_when_training_fails(self):
        with patch.object(phase2, "selected_phase1", return_value={}), \
             patch.object(phase2, "condition_config", return_value={}), \
             patch.object(phase2, "run_train", side_effect=RuntimeError("training failed")) as train, \
             patch.object(phase2, "run_evaluate") as evaluate, \
             patch.object(phase2, "collect") as collect, \
             patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaisesRegex(RuntimeError, "training failed"):
                phase2.run_all(("yolo11n",), execute=True)
        train.assert_called_once()
        evaluate.assert_not_called()
        collect.assert_not_called()

    def test_baseline_reuse_pending_and_measured_deltas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = {name: {"model": name, "validation_map50": 0.8,
                               "validation_precision": 0.7, "validation_recall": 0.6,
                               "validation_f1": 0.65, "test_correct_predictions_percent": 75.0,
                               "test_inference_ms_per_image": 20.0} for name in phase2.MODELS}
            measured = dict.fromkeys(evaluate_models.FIELDS)
            measured.update(baseline["yolo11n"])
            measured.update(validation_map50=0.85,
                            test_correct_predictions_percent=80.0,
                            test_inference_ms_per_image=10.0)
            checkpoint = root / "experiments/phase2/spatial/yolo11n/weights/best.pt"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"checkpoint")
            measured["checkpoint"] = str(checkpoint.relative_to(root))
            measured["model_size_bytes"] = checkpoint.stat().st_size
            path = root / "experiments/phase2/spatial/yolo11n/evaluation/model_screening_summary.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(measured))
            with patch.object(phase2, "ROOT", root), patch.object(phase2, "RESULTS", root / "results/phase2"), \
                 patch.object(phase2, "selected_phase1", return_value=baseline), \
                 patch.object(phase2, "condition_config", return_value={}), \
                 patch.object(phase2, "prepare", return_value={}), \
                 patch.object(evaluate_models, "training_record", return_value=(checkpoint.parent.parent, {}, checkpoint)):
                phase2.collect()
            with (root / "results/phase2/augmentation_delta.csv").open(newline="") as stream:
                rows = {(r["model"], r["condition"]): r for r in csv.DictReader(stream)}
            self.assertEqual(len(rows), 16)
            self.assertEqual(float(rows["yolo11n", "baseline"]["delta_map50"]), 0.0)
            self.assertAlmostEqual(float(rows["yolo11n", "spatial"]["delta_map50"]), 0.05)
            self.assertEqual(float(rows["yolo11n", "spatial"]["delta_correct_prediction_rate"]), 5.0)
            self.assertEqual(float(rows["yolo11n", "spatial"]["delta_inference_ms_per_image"]), -10.0)
            self.assertEqual(float(rows["yolo11n", "spatial"]["delta_inference_speed_percent"]), 100.0)
            self.assertEqual(rows["dfine_n", "combined"]["status"], "pending")
            self.assertEqual(rows["dfine_n", "combined"]["delta_map50"], "")


if __name__ == "__main__":
    unittest.main()
