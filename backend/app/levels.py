from pathlib import Path

import yaml

from .settings import CONFIG_DIR


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pgm_size(path: Path) -> tuple[int, int]:
    """PGM 헤더에서 (width, height)만 읽는다. 주석(#) 줄은 건너뛴다."""
    tokens: list[bytes] = []
    with open(path, "rb") as f:
        while len(tokens) < 3:
            line = f.readline()
            if not line:
                raise ValueError(f"PGM 헤더가 잘렸다: {path}")
            tokens += line.split(b"#", 1)[0].split()
    if tokens[0] not in (b"P2", b"P5"):
        raise ValueError(f"PGM이 아니다: {path}")
    return int(tokens[1]), int(tokens[2])


def load_map_meta(map_yaml: Path) -> dict:
    meta = _read_yaml(map_yaml)
    w, h = _pgm_size(map_yaml.parent / meta["image"])
    ox, oy, _yaw = meta["origin"]
    return {"res": meta["resolution"], "w": w, "h": h, "ox": ox, "oy": oy}


def load_level(lv: int) -> dict:
    path = CONFIG_DIR / f"level{lv}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    cfg = _read_yaml(path)
    cfg["map"] = load_map_meta((path.parent / cfg["map_yaml"]).resolve())
    return cfg
