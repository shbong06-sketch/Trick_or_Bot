import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

spec = importlib.util.spec_from_file_location("analyze_dataset", Path(__file__).resolve().parents[1]/"analyze_dataset.py")
eda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eda)


class DatasetAnalysisTest(unittest.TestCase):
    def test_bbox_validation_and_pixel_aspect(self):
        make = lambda box, cid=0: eda.bbox_record("YOLO", "train", "a.jpg", 1, box, cid, {0}, 200, 100, 1e-6)
        good = make([0, 0, 100, 50])
        self.assertTrue(good["edge_touch"])
        self.assertEqual(good["aspect_ratio"], 2)
        self.assertEqual(good["area"], .25)
        self.assertEqual(good["center_x"], .25)
        for box, reason in (([0,0,0,1], "nonpositive_size"), ([-1,0,2,2], "outside_image"), ([0,0,float("nan"),2], "malformed_or_nonfinite_bbox"), ([1,2], "malformed_or_nonfinite_bbox")):
            self.assertIn(reason, make(box)["errors"])
        self.assertIn("invalid_category_id", make([0,0,1,1], 9)["errors"])

    def test_end_to_end_negative_unknown_mismatch_and_leakage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"dataset"
            root.mkdir()
            (root/"annotations").mkdir()
            (root/"data.yaml").write_text("train: images/train\nval: images/valid\ntest: images/test\nnames: {0: pumpkin}\n")
            for split in ("train", "valid", "test"):
                (root/"images"/split).mkdir(parents=True)
                (root/"labels"/split).mkdir(parents=True)
                Image.new("RGB", (20,10), "green").save(root/"images"/split/"same.png")
                if split != "test":
                    (root/"labels"/split/"same.txt").write_text("0 0.5 0.5 0.5 0.5\n" if split == "train" else "")
                coco = dict(categories=[dict(id=1,name="pumpkin")], images=[dict(id=1,file_name="same.png",width=20,height=10)], annotations=[])
                if split == "train":
                    coco["annotations"] = [dict(id=1,image_id=1,category_id=1,bbox=[5,2.5,10,5])]
                if split == "test":
                    coco["images"] = []
                (root/"annotations"/f"instances_{split}.json").write_text(json.dumps(coco))
            before = {p:eda.sha256(p) for p in root.rglob("*") if p.is_file()}
            out = Path(temp)/"output"
            rows = eda.analyze(root,out,expected_images=3)
            lookup = {(r["format"],r["split"]):r for r in rows}
            self.assertEqual(lookup["YOLO","val"]["negative_images"],1)
            self.assertEqual(lookup["YOLO","test"]["unknown_images"],1)
            self.assertEqual(lookup["YOLO","test"]["negative_images"],0)
            self.assertEqual(lookup["COCO","train"]["invalid_annotations"],0)
            self.assertEqual(before, {p:eda.sha256(p) for p in before})
            self.assertIn("identical_pixels", (out/"leakage_candidates.csv").read_text())
            self.assertIn("False", (out/"split_comparison.csv").read_text())
            for file in ("dataset_summary.csv","split_summary.csv","negative_image_summary.csv","bbox_center_distribution.png","bbox_size_distribution.png","bbox_area_distribution.png","dataset_eda.md"):
                self.assertGreater((out/file).stat().st_size,0)
            with self.assertRaises(ValueError):
                eda.analyze(root,root/"output")


if __name__ == "__main__":
    unittest.main()
