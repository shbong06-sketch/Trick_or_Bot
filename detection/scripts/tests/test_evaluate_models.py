"""CPU-only checks; no checkpoint, dataset inference, or GPU is used."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1]/"evaluate_models.py"
spec = importlib.util.spec_from_file_location("evaluate_models", PATH)
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.images = [{"id": 1}, {"id": 2}]
        self.truth = {1: [{"bbox": [0, 0, 10, 10], "category_id": 0}], 2: []}
        self.pred = {1: [
            {"bbox": [0, 0, 10, 10], "score": 0.8, "category_id": 0},
            {"bbox": [0, 0, 10, 10], "score": 0.7, "category_id": 0}],
            2: [{"bbox": [0, 0, 10, 10], "score": 0.6, "category_id": 0}]}

    def test_config_and_command(self):
        cfg, ev = evaluate.settings()
        self.assertEqual((ev["confidence"], ev["matching_iou"]), (0.25, 0.5))
        self.assertEqual(len(cfg["models"]), 7)
        cmd = evaluate.docker_command(cfg, "dfine_n")
        self.assertIn("--inside-docker", cmd)
        self.assertIn("--execute", cmd)
        self.assertIn("/dfine/docker-compose.yaml", cmd[3])

    def test_one_to_one_duplicates_and_negative(self):
        self.assertEqual(evaluate.counts(self.images, self.truth, self.pred, .25, .5), (1, 2, 0))
        self.assertEqual(evaluate.prf(1, 2, 0), (1/3, 1.0, .5))
        self.assertEqual(evaluate.counts(self.images, self.truth, self.pred, .9, .5), (0, 0, 1))

    def test_empty_predictions_and_denominators(self):
        empty = {1: [], 2: []}
        self.assertEqual(evaluate.counts(self.images, self.truth, empty, .25, .5), (0, 0, 1))
        self.assertEqual(evaluate.prf(0, 0, 0), (0.0, 0.0, 0.0))
        self.assertEqual(evaluate.f1_peak(self.images, self.truth, empty, .5), (0.0, 1.0))

    def test_f1_observed_boundary(self):
        self.assertEqual(evaluate.f1_peak(self.images, self.truth, self.pred, .5), (1.0, .8))
        self.assertEqual(evaluate.counts(self.images, self.truth, self.pred, .8, .5), (1, 0, 0))

    def test_normalization_and_empty_test_mean(self):
        rows = [([-1, 0, 12, 11], .8, 0), ([0, 0, 10, 10], .9, 1)]
        self.assertEqual(evaluate.normalize(rows, 0, 10, 10, .001),
                         [{"bbox": [0.0, 0.0, 10.0, 10.0], "score": .8, "category_id": 0}])
        _, ev = evaluate.settings()
        with patch.object(evaluate, "coco_ap", return_value=(0.0, 0.0)):
            metrics = evaluate.split_metrics({}, self.images, self.truth, {1: [], 2: []}, ev)
        self.assertIsNone(metrics["average_confidence"])
        self.assertEqual(metrics["correct_predictions_percent"], 0.0)

    def test_common_schema_and_collect_without_inference(self):
        cfg, ev = evaluate.settings()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoint = root/"experiments/phase1/yolov8n/weights/best.pt"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"checkpoint")
            info = dict(optimizer="AdamW", optimizer_param_groups=[{"initial_lr": .002}],
                        scheduler="LambdaLR", epochs_ending=3, total_training_seconds=4,
                        parameter_count=5, training={"seed": 42}, status="complete",
                        best_checkpoint="weights/best.pt")
            (checkpoint.parents[1]/"run_info.json").write_text(json.dumps(info))
            (checkpoint.parents[1]/"config.yaml").write_text("training: {}\nsettings: {}\n")
            val = dict(map50=.7, map50_95=.4, precision=.5, recall=1, f1=2/3,
                       f1_peak=.8, f1_confidence=.3, tp=1, fp=1, fn=0)
            test = dict(map50=.6, map50_95=.3, tp=1, fp=0, fn=0,
                        correct_predictions_percent=100, inference_ms_per_image=5,
                        average_confidence=.8)
            with patch.object(evaluate, "ROOT", root):
                row = evaluate.summary("yolov8n", "yolo", info, checkpoint,
                                       {"training": {}, "settings": {}}, val, test, ev)
                self.assertEqual(set(row), set(evaluate.FIELDS))
                self.assertEqual(row["test_average_confidence"], .8)
                output = checkpoint.parents[1]/"evaluation"
                output.mkdir()
                (output/"model_screening_summary.json").write_text(json.dumps(row))
                with patch.object(evaluate, "load_model", side_effect=AssertionError("inference")):
                    evaluate.collect(cfg)
                result = (root/"records/phase1/model_comparison.csv").read_text()
                self.assertIn("yolov8n", result)


if __name__ == "__main__":
    unittest.main()
