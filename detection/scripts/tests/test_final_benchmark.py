"""Matching cases absent from the current final test predictions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from final_benchmark import image_matches


class ImageMatchingTests(unittest.TestCase):
    def test_duplicate_detection_is_fp_and_unmatched_gt_is_fn(self):
        truth = [
            {"bbox": [0, 0, 10, 10], "category_id": 0},
            {"bbox": [20, 20, 30, 30], "category_id": 0},
        ]
        predictions = [
            {"bbox": [0, 0, 10, 10], "category_id": 0, "score": 0.9},
            {"bbox": [0, 0, 10, 10], "category_id": 0, "score": 0.8},
            {"bbox": [20, 20, 30, 30], "category_id": 0, "score": 0.2},
        ]
        matched, missed = image_matches(truth, predictions, 0.25, 0.5)
        self.assertEqual([item["outcome"] for item in matched], ["TP", "FP"])
        self.assertEqual([item["gt_index"] for item in missed], [1])

    def test_negative_image_prediction_is_fp(self):
        predictions = [{"bbox": [0, 0, 10, 10], "category_id": 0, "score": 0.9}]
        matched, missed = image_matches([], predictions, 0.25, 0.5)
        self.assertEqual(matched[0]["outcome"], "FP")
        self.assertEqual(missed, [])


if __name__ == "__main__":
    unittest.main()
