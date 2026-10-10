import os
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_DIR / "config"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MOCK = os.environ.get("MOCK", "0") == "1"

# 로봇 설정 파일: 실물 robot.yaml(기본), Gazebo는 ROBOT_CONFIG=robot_sim.yaml
ROBOT_CONFIG = os.environ.get("ROBOT_CONFIG", "robot.yaml")
with open(CONFIG_DIR / ROBOT_CONFIG, encoding="utf-8") as f:
    ROBOT = yaml.safe_load(f)
