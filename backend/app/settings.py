import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_DIR / "config"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MOCK = os.environ.get("MOCK", "0") == "1"
