#!/usr/bin/env python3
"""점유 격자 맵(pgm + yaml)을 Gazebo 월드(SDF)로 바꾼다.

  python3 simulation/tools/map_to_world.py                    # 기본: backend/config/level1.yaml의 맵과 좌표
  python3 simulation/tools/map_to_world.py --level backend/config/level1.yaml --out simulation/worlds/holloween.sdf

- 벽(점유) 칸을 직사각형으로 합쳐 높이 WALL_H 박스로 세운다 (판자벽 SR-015, 모든 벽이 직선이라는 가정)
- 월드 좌표 = map 좌표 (맵 원점·해상도를 그대로 쓴다). 그래서 레벨 yaml의 사탕·탈출문·시작 좌표를 그대로 쓸 수 있다
- --markers: 사탕(초록)·탈출문(보라) 자리에 바닥 표시를 깐다. 충돌 없음, AR 위치가 맞는지 눈으로 보는 용도
"""
import argparse
import math
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WALL_H = 0.6          # 판자벽 높이 (m)
MARK_R = 0.10         # 바닥 표시 반지름 (m)


def read_pgm(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    tokens, pos = [], 0
    while len(tokens) < 4:
        end = data.index(b"\n", pos)
        tokens += data[pos:end].split(b"#", 1)[0].split()
        pos = end + 1
    if tokens[0] != b"P5":
        raise SystemExit(f"바이너리 PGM(P5)만 지원한다: {path}")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    return w, h, maxval, data[pos:pos + w * h]


def load_occupancy(map_yaml: Path):
    meta = yaml.safe_load(map_yaml.read_text(encoding="utf-8"))
    w, h, maxval, px = read_pgm(map_yaml.parent / meta["image"])
    negate = int(meta.get("negate", 0))
    occ_th = float(meta.get("occupied_thresh", 0.65))
    occ = [((p / maxval) if negate else 1.0 - p / maxval) > occ_th for p in px]
    return meta, w, h, occ


def merge_rectangles(w: int, h: int, occ: list[bool]) -> list[tuple[int, int, int, int]]:
    """벽 칸을 직사각형 (r0, r1, c0, c1)로 합친다 (끝은 포함 안 함). 행마다 연속 구간을 찾고, 아래 행과 같은 구간이면 이어 붙인다."""
    rects, open_runs = [], {}  # (c0, c1) → r0
    for r in range(h + 1):
        runs = set()
        if r < h:
            c = 0
            while c < w:
                if occ[r * w + c]:
                    c0 = c
                    while c < w and occ[r * w + c]:
                        c += 1
                    runs.add((c0, c))
                c += 1
        for run in list(open_runs):
            if run not in runs:
                rects.append((open_runs.pop(run), r, *run))
        for run in runs:
            open_runs.setdefault(run, r)
    return rects


def box(name: str, x: float, y: float, z: float, sx: float, sy: float, sz: float, rgba: str, collide: bool = True) -> str:
    geom = f"<geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>"
    col = f"<collision name='c'>{geom}</collision>" if collide else ""
    return (f"    <model name='{name}'><static>true</static><pose>{x:.3f} {y:.3f} {z:.3f} 0 0 0</pose>"
            f"<link name='l'>{col}<visual name='v'>{geom}"
            f"<material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse></material></visual></link></model>\n")


def disc(name: str, x: float, y: float, r: float, rgba: str) -> str:
    geom = f"<geometry><cylinder><radius>{r:.3f}</radius><length>0.004</length></cylinder></geometry>"
    return (f"    <model name='{name}'><static>true</static><pose>{x:.3f} {y:.3f} 0.002 0 0 0</pose>"
            f"<link name='l'><visual name='v'>{geom}"
            f"<material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse><emissive>{rgba}</emissive></material>"
            f"</visual></link></model>\n")


HEADER = """<?xml version="1.0"?>
<!-- map_to_world.py로 생성: {src}. 직접 고치지 말고 맵·레벨을 바꾼 뒤 다시 생성할 것 -->
<sdf version='1.8'>
  <world name='{name}'>
    <physics name='1ms' type='ignored'>
      <max_step_size>{step}</max_step_size>
      <real_time_factor>1</real_time_factor>
      <real_time_update_rate>{rate}</real_time_update_rate>
    </physics>
    <plugin name="gz::sim::systems::Physics" filename="gz-sim-physics-system" />
    <plugin name="gz::sim::systems::UserCommands" filename="gz-sim-user-commands-system" />
    <plugin name="gz::sim::systems::SceneBroadcaster" filename="gz-sim-scene-broadcaster-system" />
    <plugin name="gz::sim::systems::Contact" filename="gz-sim-contact-system" />
    <!-- 센서(카메라·라이다) 시스템은 월드에서 한 번만 불러온다. 로봇마다 불러오면 두 번째 로봇에서 Gazebo가 죽는다
         (Ogre ItemIdentityException). 그래서 런치가 로봇 모델에서 이 플러그인을 뺀 사본을 쓴다 -->
    <plugin name="gz::sim::systems::Sensors" filename="gz-sim-sensors-system">
      <render_engine>ogre2</render_engine>
    </plugin>
    <light name='sun' type='directional'>
      <cast_shadows>1</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <gravity>0 0 -9.8</gravity>
    <scene>
      <ambient>0.45 0.42 0.5 1</ambient>
      <background>0.08 0.06 0.12 1</background>
      <shadows>1</shadows>
    </scene>
    <model name='ground_plane'>
      <static>true</static>
      <link name='link'>
        <collision name='collision'><geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry></collision>
        <visual name='visual'>
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
          <material><ambient>0.22 0.2 0.26 1</ambient><diffuse>0.22 0.2 0.26 1</diffuse></material>
        </visual>
      </link>
    </model>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", default=str(REPO / "backend/config/level1.yaml"))
    ap.add_argument("--out", default=str(REPO / "simulation/worlds/holloween.sdf"))
    ap.add_argument("--no-markers", action="store_true", help="사탕·탈출문 바닥 표시를 넣지 않는다")
    ap.add_argument("--step", type=float, default=0.006,
                    help="물리 계산 간격(s). TB4 예제는 0.003인데 로봇 두 대면 실시간을 못 따라가서 기본 0.006")
    args = ap.parse_args()

    level_path = Path(args.level).resolve()
    level = yaml.safe_load(level_path.read_text(encoding="utf-8"))
    map_yaml = (level_path.parent / level["map_yaml"]).resolve()
    meta, w, h, occ = load_occupancy(map_yaml)
    res = float(meta["resolution"])
    ox, oy = float(meta["origin"][0]), float(meta["origin"][1])

    rects = merge_rectangles(w, h, occ)
    out = Path(args.out)
    name = out.stem
    parts = [HEADER.format(src=f"{map_yaml.name} + {level_path.name}", name=name,
                           step=args.step, rate=round(1 / args.step))]
    for i, (r0, r1, c0, c1) in enumerate(rects):
        x = ox + (c0 + c1) / 2 * res
        y = oy + (h - (r0 + r1) / 2) * res  # 0행 = 맵 위쪽
        parts.append(box(f"wall_{i}", x, y, WALL_H / 2, (c1 - c0) * res, (r1 - r0) * res, WALL_H, "0.45 0.3 0.2 1"))

    if not args.no_markers:
        for c in level.get("candies") or []:
            parts.append(disc(f"mark_{c['id']}", c["x"], c["y"], MARK_R, "0.1 0.9 0.45 1"))
        g = level.get("gate")
        if g:
            parts.append(disc("mark_gate", g["x"], g["y"], MARK_R, "0.65 0.3 1 1"))
            yaw, front = float(g.get("yaw", 0.0)), float(level.get("gate_front_m", 0.4))
            parts.append(disc("mark_gate_front", g["x"] + front * math.cos(yaw), g["y"] + front * math.sin(yaw),
                              float(level.get("gate_zone_r", 0.3)), "0.45 0.2 0.7 1"))

    parts.append("  </world>\n</sdf>\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    n_occ = sum(occ)
    print(f"{out}: 벽 칸 {n_occ}개 → 박스 {len(rects)}개, 맵 {w}×{h} @ {res} m, 원점 ({ox}, {oy})")


if __name__ == "__main__":
    main()
