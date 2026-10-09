import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import evaluate
import results
import run
from train import EarlyStop, install_epoch_hook


def evaluate_stub():
    return {"coco_eval_bbox":[0.5,0.7]}, None


class FakeSolver:
    def __init__(self):
        self.events = []

    def fit(self):
        for epoch in range(10):
            test_stats, evaluator = evaluate_stub()
            self.events.append(("saved",epoch))
        self.events.append(("finished",epoch))


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.cfg = results.load_config(results.ROOT/"configs/phase1/screening.yaml")

    def test_all_models_command_preview_without_model_imports(self):
        for name in results.MODEL_NAMES:
            command = run.docker_command("train",self.cfg,name,"run01")
            self.assertIn("--execute",command)
            self.assertIn("--worker",command)
            self.assertIn(name,command)
            framework = self.cfg["models"][name]["framework"]
            self.assertIn(f"docker/{framework}/docker-compose.yaml",command[3])
            output = subprocess.check_output([sys.executable,str(SCRIPTS/"run.py"),"train","--model",name,"--run-name","preview_only"],text=True)
            self.assertTrue(output.startswith("docker compose"))
        self.assertNotIn("torch",sys.modules)
        self.assertNotIn("ultralytics",sys.modules)
        self.assertNotIn("rfdetr",sys.modules)

    def test_fixed_conditions_and_safe_names(self):
        for key,value in (("batch_size",8),("seed",0),("input_size",[640,640]),("patience",10)):
            cfg = copy.deepcopy(self.cfg)
            cfg["common"][key] = value
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/"config.yaml"
                import yaml
                path.write_text(yaml.safe_dump(cfg))
                with self.assertRaises(ValueError):
                    results.load_config(path)
        for unsafe in ("../escape","a/b","", "a b"):
            with self.assertRaises(ValueError):
                results.identifier(unsafe)

    def test_one_to_one_matching_negative_images_and_threshold(self):
        truth = {1:[dict(bbox=[0,0,10,10],category_id=0)],2:[],3:[dict(bbox=[0,0,10,10],category_id=0)]}
        predictions = {1:[dict(bbox=[0,0,10,10],score=.9,category_id=0),dict(bbox=[0,0,10,10],score=.8,category_id=0)],
                       2:[dict(bbox=[0,0,10,10],score=.2,category_id=0)],3:[]}
        metrics = evaluate.detection_metrics(truth,predictions,.25,.5)
        self.assertEqual((metrics["tp"],metrics["fp"],metrics["fn"]),(1,1,1))
        self.assertAlmostEqual(metrics["correct_predictions_percent"],100/3)
        self.assertAlmostEqual(metrics["image_exact_match_percent"],100/3)
        self.assertAlmostEqual(metrics["average_confidence"],.85)
        with self.assertRaises(ValueError):
            evaluate.detection_metrics(truth,{1:[]},.25,.5)
        empty = evaluate.detection_metrics({1:[]},{1:[]},.25,.5)
        self.assertIsNone(empty["average_confidence"])
        self.assertIsNone(empty["correct_predictions_percent"])
        self.assertEqual(empty["image_exact_match_percent"],100)

    def test_f1_peak_excludes_low_score_false_positive(self):
        truth = {1:[dict(bbox=[0,0,10,10],category_id=0)]}
        predictions = {1:[dict(bbox=[0,0,10,10],score=.9,category_id=0),dict(bbox=[20,20,30,30],score=.4,category_id=0)]}
        peak = evaluate.f1_peak(truth,predictions,self.cfg["evaluation"])
        self.assertEqual(peak["f1_peak"],1)
        self.assertAlmostEqual(peak["f1_confidence"],.41)
        predictions[1][0]["score"] = .405
        predictions[1][1]["score"] = .404
        narrow = evaluate.f1_peak(truth,predictions,self.cfg["evaluation"])
        self.assertEqual(narrow["f1_peak"],1)
        self.assertEqual(narrow["f1_confidence"],.405)

    def test_freeze_rejects_modified_and_added_files(self):
        import csv
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root/"dataset"
            (dataset/"annotations").mkdir(parents=True)
            (dataset/"data.yaml").write_text("names: {0: pumpkin}\n")
            for split in ("train","valid","test"):
                document = dict(categories=[dict(id=0,name="pumpkin")],images=[dict(id=0)],annotations=[])
                (dataset/"annotations"/f"instances_{split}.json").write_text(json.dumps(document))
            manifest = root/self.cfg["dataset"]["manifest"]
            manifest.parent.mkdir(parents=True)
            with manifest.open("w",newline="") as stream:
                writer = csv.DictWriter(stream,fieldnames=["path","bytes","sha256"])
                writer.writeheader()
                writer.writerows(dict(path=str(p.relative_to(dataset)),bytes=p.stat().st_size,sha256=results.digest(p)) for p in dataset.rglob("*") if p.is_file())
            cfg = copy.deepcopy(self.cfg)
            cfg["dataset"]["observed_images"] = 3
            with patch("results.ROOT",root):
                self.assertEqual(results.verify_dataset(cfg)["image_counts"],dict(train=1,val=1,test=1))
                (dataset/"labels").mkdir()
                extra = dataset/"labels/extra.txt"
                extra.write_text("")
                with self.assertRaisesRegex(ValueError,"added/removed"):
                    results.verify_dataset(cfg)
                extra.unlink()
                (dataset/"data.yaml").write_text("modified")
                with self.assertRaisesRegex(ValueError,"freeze mismatch"):
                    results.verify_dataset(cfg)

    def test_invalid_prediction_and_capping(self):
        with self.assertRaises(ValueError):
            evaluate.normalize_predictions([dict(bbox=[0,0,1,1],score=float("nan"),category_id=0)],self.cfg["evaluation"])
        with self.assertRaises(ValueError):
            evaluate.normalize_predictions([dict(bbox=[0,0,1,1],score=.9,category_id=1)],self.cfg["evaluation"])
        rows = [dict(bbox=[0,0,1,1],score=i/200,category_id=0) for i in range(150)]
        self.assertEqual(len(evaluate.normalize_predictions(rows,self.cfg["evaluation"])),100)

    def test_early_stop_and_epoch_hook_preserves_checkpoint_order(self):
        stop = EarlyStop(2)
        self.assertEqual(stop.update(.5,1),(True,False))
        self.assertEqual(stop.update(.5,2),(False,False))
        self.assertEqual(stop.update(.4,3),(False,True))
        controller = EarlyStop(2)
        solver = FakeSolver()

        def observe(instance, epoch, stats):
            instance.events.append(("observed",epoch))
            return controller.update(stats["coco_eval_bbox"][0],epoch+1)[1]

        # Vendor loop names the validation function evaluate.
        source = __import__("inspect").getsource(FakeSolver.fit).replace("evaluate_stub()","evaluate()")
        with patch("train.inspect.getsource",return_value=source):
            method = install_epoch_hook(FakeSolver.fit,observe)
        method.__globals__["evaluate"] = evaluate_stub
        method(solver)
        self.assertEqual(solver.events,[("observed",0),("saved",0),("observed",1),("saved",1),("observed",2),("saved",2),("finished",2)])

    def test_summary_schema_and_prepare_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            row = dict.fromkeys(results.FIELDS)
            row.update(schema_version=1,model="yolov8n",training_hyperparameters={"optimizer":"AdamW"})
            results.write_summary(output,row)
            self.assertEqual(set(json.loads((output/"model_screening_summary.json").read_text())),set(results.FIELDS))
            with patch("run.verify_dataset",return_value={"manifest_sha256":"test"}), patch("run.shutil.copyfile"):
                prepared = output/"run"
                run.prepare(self.cfg,"yolov8n",prepared)
                with self.assertRaises(FileExistsError):
                    run.prepare(self.cfg,"yolov8n",prepared)
            self.assertFalse((prepared/"training").exists())

    @unittest.skipUnless(importlib.util.find_spec("pycocotools"),"pycocotools not installed on host; no package installation needed")
    def test_common_ap_including_empty_predictions(self):
        coco = dict(images=[dict(id=1,width=20,height=20,file_name="synthetic.png")],categories=[dict(id=0,name="pumpkin")],
                    annotations=[dict(id=1,image_id=1,category_id=0,bbox=[0,0,10,10],area=100,iscrowd=0)])
        perfect = evaluate.coco_ap(coco,{1:[dict(bbox=[0,0,10,10],score=.9,category_id=0)]},100)
        self.assertAlmostEqual(perfect["map50"],1)
        self.assertEqual(evaluate.coco_ap(coco,{1:[]},100)["map50"],0)


if __name__ == "__main__":
    unittest.main()
