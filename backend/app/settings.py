import os
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_DIR / "config"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MOCK = os.environ.get("MOCK", "0") == "1"

with open(CONFIG_DIR / "robot.yaml", encoding="utf-8") as f:
    ROBOT = yaml.safe_load(f)
