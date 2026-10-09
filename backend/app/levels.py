import base64
from pathlib import Path

import yaml

from .settings import CONFIG_DIR


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_pgm(path: Path) -> tuple[int, int, int, bytes]:
    """바이너리 PGM(P5) → (width, height, maxval, 픽셀). 헤더의 주석(#)은 건너뛴다."""
    data = path.read_bytes()
    tokens: list[bytes] = []
    pos = 0
    while len(tokens) < 4:
        end = data.index(b"\n", pos)
        tokens += data[pos:end].split(b"#", 1)[0].split()
        pos = end + 1
    if tokens[0] != b"P5":
        raise ValueError(f"바이너리 PGM(P5)이 아니다: {path}")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    return w, h, maxval, data[pos:pos + w * h]


def load_map(map_yaml: Path) -> dict:
    """맵 메타 + 점유 격자. occ는 셀마다 1(벽)/0, PGM과 같은 순서(0행 = 맵 위쪽)."""
    meta = _read_yaml(map_yaml)
    w, h, maxval, pixels = _read_pgm(map_yaml.parent / meta["image"])
    negate = int(meta.get("negate", 0))
    occ_th = float(meta.get("occupied_thresh", 0.65))
    occ = bytes(1 if ((p / maxval) if negate else 1.0 - p / maxval) > occ_th else 0 for p in pixels)
    ox, oy, _yaw = meta["origin"]
    return {"res": meta["resolution"], "w": w, "h": h, "ox": ox, "oy": oy, "occ": occ}


def pack_occ(occ: bytes) -> str:
    """점유 격자를 비트로 묶어 base64로. 셀 i → 바이트 i>>3 의 비트 (i&7)."""
    packed = bytearray((len(occ) + 7) // 8)
    for i, v in enumerate(occ):
        if v:
            packed[i >> 3] |= 1 << (i & 7)
    return base64.b64encode(bytes(packed)).decode()


def list_levels() -> list[dict]:
    """설정 파일이 있는 레벨 목록 (레벨 선택 화면용)."""
    out = []
    for path in sorted(CONFIG_DIR.glob("level*.yaml")):
        cfg = _read_yaml(path)
        out.append({"id": int(cfg["lv"]), "name": cfg["name"], "time": cfg["time_limit_s"]})
    return sorted(out, key=lambda l: l["id"])


def load_level(lv: int) -> dict:
    path = CONFIG_DIR / f"level{lv}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    cfg = _read_yaml(path)
    cfg["map"] = load_map((path.parent / cfg["map_yaml"]).resolve())
    return cfg
