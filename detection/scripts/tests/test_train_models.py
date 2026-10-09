import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

SCRIPT = Path(__file__).resolve().parents[1]/"train_models.py"
spec = importlib.util.spec_from_file_location("train_models", SCRIPT)
train = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = train
spec.loader.exec_module(train)


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = yaml.safe_load((train.ROOT/"configs/phase1/common.yaml").read_text())

    def test_command_preview_for_all_models_never_imports_torch(self):
        for name in self.cfg["models"]:
            command = train.docker_command(self.cfg, name)
            self.assertIn("--inside-docker", command)
            self.assertIn("--no-deps", command)
            output = subprocess.check_output([sys.executable, str(SCRIPT), "--model", name], text=True)
            self.assertTrue(output.startswith("docker compose"))
        self.assertNotIn("torch", sys.modules)

    def test_patience_counts_only_consecutive_non_improvements(self):
        stop = train.EarlyStop(2)
        for value, expected in ((.1,(True,False)),(.1,(False,False)),(.2,(True,False)),(.2,(False,False)),(.19,(False,True))):
            self.assertEqual(stop.update(value), expected)
        with self.assertRaises(ValueError):
            stop.update(float("nan"))

    def test_yolo_uses_finetuning_and_common_conditions(self):
        captured = {}

        class YOLO:
            def __init__(self, weights):
                captured["weights"] = weights

            def add_callback(self, *args):
                pass

            def train(self, **options):
                captured.update(options)

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/"yolov8n"
            output.mkdir()
            with patch.dict(sys.modules, ultralytics=SimpleNamespace(YOLO=YOLO)):
                train.train_yolo(self.cfg, self.cfg["models"]["yolov8n"], output, {}, None)
            self.assertEqual(captured["weights"], "yolov8n.pt")
            self.assertEqual((captured["epochs"], captured["batch"], captured["imgsz"], captured["seed"], captured["patience"]), (100,16,704,42,20))
            self.assertEqual(captured["name"], "yolov8n")
            self.assertEqual(captured["project"], str(output.parent))
            self.assertTrue(captured["exist_ok"])

    def test_vendor_early_stop_saves_evaluated_weights_and_restores_function(self):
        class Config:
            def __init__(self, path):
                self.yaml_cfg = {"train_dataloader":dict(dataset=dict(transforms=dict(ops=[dict(type="Resize")]))),
                                 "val_dataloader":dict(dataset=dict(transforms=dict(ops=[dict(type="Resize")])))}

        class Solver:
            def __init__(self, cfg):
                self.model = SimpleNamespace(parameters=lambda: [])
                self.optimizer = SimpleNamespace(param_groups=[])
                self.lr_scheduler = None

            def fit(self):
                evaluated = SimpleNamespace(state_dict=lambda: {"ema_weight":"test"})
                for epoch in range(100):
                    module.evaluate(evaluated)

        original = lambda *args: ({"coco_eval_bbox":[.5,.7]}, None)
        module = SimpleNamespace(DetSolver=Solver, evaluate=original)
        saved = []
        torch = SimpleNamespace(save=lambda state, path: saved.append((state,path)))
        core = SimpleNamespace(YAMLConfig=Config)
        with tempfile.TemporaryDirectory() as temp:
            info = {}
            with patch("train_models.importlib.import_module", side_effect=[core,module]):
                train.train_vendor(self.cfg,self.cfg["models"]["dfine_n"],Path(temp),info,torch)
            self.assertEqual(info["epochs_ending"],21)
            self.assertEqual(info["best_epoch"],1)
            self.assertEqual(saved[0][0]["model"],{"ema_weight":"test"})
            self.assertEqual(len((Path(temp)/"metrics.jsonl").read_text().splitlines()),21)
            self.assertIs(module.evaluate,original)

    def test_rfdetr_uses_common_options_and_disables_test(self):
        captured = {}
        trainer = SimpleNamespace(callbacks=[], optimizers=[SimpleNamespace(param_groups=[])],
                                  lr_scheduler_configs=[], precision="16-mixed", current_epoch=2)
        original = lambda *args, **kwargs: trainer
        training = SimpleNamespace(build_trainer=original)

        class Nano:
            def __init__(self, **options):
                captured["init"] = options

            def train(self, **options):
                captured.update(options)
                config = SimpleNamespace(model_dump=lambda **kwargs:options)
                built = training.build_trainer(config,config)
                module = SimpleNamespace(parameters=lambda:[])
                for callback in built.callbacks:
                    callback.on_train_start(built,module)
                    callback.on_train_epoch_end(built,module)

        with tempfile.TemporaryDirectory() as temp:
            info = {}
            modules = {"pytorch_lightning":SimpleNamespace(Callback=object),
                       "rfdetr":SimpleNamespace(RFDETRNano=Nano,training=training), "rfdetr.training":training}
            with patch.dict(sys.modules,modules):
                train.train_rfdetr(self.cfg,self.cfg["models"]["rfdetr_n"],Path(temp),info,None)
            self.assertFalse(captured["run_test"])
            self.assertEqual(captured["init"]["resolution"],704)
            self.assertEqual((captured["epochs"],captured["batch_size"],captured["seed"],captured["early_stopping_patience"]),(100,16,42,20))
            self.assertEqual(info["epochs_ending"],3)
            self.assertIs(training.build_trainer,original)

    def test_launch_records_failure_and_reuses_model_directory(self):
        class Process:
            stdout = ["training error\n"]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def wait(self):
                return 2

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root/self.cfg["output_dir"]/"yolov8n"
            output.mkdir(parents=True)
            (output/"training.log").write_text("old log")
            with patch("train_models.ROOT",root), patch("train_models.subprocess.Popen",return_value=Process()):
                with self.assertRaises(SystemExit) as error:
                    train.launch(self.cfg,"yolov8n")
            self.assertEqual(error.exception.code,2)
            self.assertEqual((output/"training.log").read_text(),"training error\n")
            self.assertEqual(json.loads((output/"run_info.json").read_text())["status"],"failed")


if __name__ == "__main__":
    unittest.main()
