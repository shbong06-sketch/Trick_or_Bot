#!/usr/bin/env python3
"""맵 이미지 위를 클릭해 사탕·펌킨 시작 위치·탈출문을 찍고 레벨 yaml에 저장한다.

  python3 tools/pick_candies.py                       # config/level1.yaml
  python3 tools/pick_candies.py config/level2.yaml -n 3
  python3 tools/pick_candies.py --start               # 시작 위치 모드로 열기
  python3 tools/pick_candies.py --gate                # 탈출문 모드로 열기

조작:
  Tab        = 사탕 → 시작 위치 → 탈출문 모드 순서로 전환
  사탕 모드   왼쪽 클릭 = 추가, 오른쪽 클릭 = 마지막 점 삭제, R = 모두 지우기
  시작 모드   왼쪽 버튼을 누른 곳 = 위치, 누른 채 끌면 = 바라보는 방향 (끌지 않으면 방향 유지)
  탈출문 모드 왼쪽 버튼을 누른 곳 = 문 위치, 누른 채 끌면 = 문이 바라보는 방향(문 앞 구역 쪽)
  S = 저장 (candies 블록, pumpkin_start 줄, gate 줄만 바뀐다), Q/Esc = 종료
"""
import argparse
import math
import re
import sys
import tkinter as tk
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
MAX_W, MAX_H = 900, 700
DRAG_MIN_PX = 6  # 이보다 짧게 끌면 방향은 바꾸지 않는다
MODES = ("candy", "start", "gate")


def read_pgm(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    tokens, pos = [], 0
    while len(tokens) < 4:
        end = data.index(b"\n", pos)
        tokens += data[pos:end].split(b"#", 1)[0].split()
        pos = end + 1
    if tokens[0] != b"P5":
        sys.exit(f"P5(바이너리) PGM만 지원한다: {path}")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    return w, h, maxval, data[pos:pos + w * h]


class Picker:
    def __init__(self, level_path: Path, count: int, mode: str = "candy"):
        self.level_path = level_path
        self.count = count
        self.mode = mode
        level = yaml.safe_load(level_path.read_text(encoding="utf-8"))
        map_yaml = (level_path.parent / level["map_yaml"]).resolve()
        meta = yaml.safe_load(map_yaml.read_text(encoding="utf-8"))
        self.res = float(meta["resolution"])
        self.ox, self.oy = float(meta["origin"][0]), float(meta["origin"][1])
        self.negate = int(meta.get("negate", 0))
        self.occ_th = float(meta.get("occupied_thresh", 0.65))
        self.free_th = float(meta.get("free_thresh", 0.196))
        self.pick_r = float(level.get("pick_radius_m", 0.3))
        pgm = map_yaml.parent / meta["image"]
        self.w, self.h, self.maxval, self.pixels = read_pgm(pgm)
        self.zoom = max(1, min(MAX_W // self.w, MAX_H // self.h))
        # 기존 값을 불러와 보여준다 (자리표시 값일 수 있음)
        self.points = [(float(c["x"]), float(c["y"])) for c in level.get("candies") or []][:count]
        s = level.get("pumpkin_start")
        self.start = (float(s["x"]), float(s["y"]), float(s.get("yaw", 0.0))) if s else None
        g = level.get("gate")
        self.gate = (float(g["x"]), float(g["y"]), float(g.get("yaw", 0.0))) if g else None
        self.gate_front = float(level.get("gate_front_m", 0.4))
        self.gate_zone_r = float(level.get("gate_zone_r", 0.3))
        self.gate_enter_r = float(level.get("gate_enter_r", 0.15))
        self.drag_from = None  # 시작·탈출문 모드에서 누른 캔버스 좌표

        self.root = tk.Tk()
        self.root.title(f"위치 찍기 — {level_path.name} / {map_yaml.name}")
        self.img = tk.PhotoImage(file=str(pgm)).zoom(self.zoom)
        self.canvas = tk.Canvas(self.root, width=self.w * self.zoom, height=self.h * self.zoom,
                                highlightthickness=0, cursor="crosshair")
        self.canvas.create_image(0, 0, anchor="nw", image=self.img)
        self.canvas.pack()
        self.mode_label = tk.Label(self.root, anchor="w", font=("sans", 11, "bold"))
        self.mode_label.pack(fill="x")
        self.status = tk.Label(self.root, anchor="w", font=("monospace", 10))
        self.status.pack(fill="x")
        self.info = tk.Label(self.root, anchor="w", justify="left", font=("monospace", 10))
        self.info.pack(fill="x")

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_undo)
        self.canvas.bind("<Motion>", self.on_move)
        self.root.bind("<Tab>", self.on_toggle)
        self.root.bind("<Key-s>", self.on_save)
        self.root.bind("<Key-r>", self.on_reset)
        self.root.bind("<Key-q>", lambda e: self.root.destroy())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.redraw()

    # 좌표 변환: PGM의 0행은 맵의 위쪽(y 최대), origin은 왼쪽 아래 모서리
    def canvas_to_map(self, cx: float, cy: float) -> tuple[float, float]:
        px, py = cx / self.zoom, cy / self.zoom
        return self.ox + px * self.res, self.oy + (self.h - py) * self.res

    def map_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        px = (x - self.ox) / self.res
        py = self.h - (y - self.oy) / self.res
        return px * self.zoom, py * self.zoom

    def cell_state(self, x: float, y: float) -> str:
        col = int((x - self.ox) / self.res)
        row = self.h - 1 - int((y - self.oy) / self.res)
        if not (0 <= col < self.w and 0 <= row < self.h):
            return "맵 밖"
        p = self.pixels[row * self.w + col] / self.maxval
        occ = p if self.negate else 1.0 - p
        if occ > self.occ_th:
            return "벽/장애물"
        if occ < self.free_th:
            return "빈 공간"
        return "미탐색"

    # ---- 입력 ----
    def on_toggle(self, e=None):
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        self.redraw()
        return "break"  # Tab 포커스 이동 막기

    def on_press(self, e):
        if self.mode == "candy":
            if len(self.points) >= self.count:
                self.status.config(text=f"이미 {self.count}개. 오른쪽 클릭으로 지운 뒤 다시 찍기")
                return
            self.points.append(self.canvas_to_map(e.x, e.y))
            self.redraw()
        elif self.mode == "gate":
            self.drag_from = (e.x, e.y)
            self.gate = (*self.canvas_to_map(e.x, e.y), self.gate[2] if self.gate else 0.0)
            self.redraw()
        else:
            self.drag_from = (e.x, e.y)
            x, y = self.canvas_to_map(e.x, e.y)
            yaw = self.start[2] if self.start else 0.0
            self.start = (x, y, yaw)
            self.redraw()

    def on_drag(self, e):
        if self.mode not in ("start", "gate") or not self.drag_from:
            return
        dx, dy = e.x - self.drag_from[0], e.y - self.drag_from[1]
        if math.hypot(dx, dy) >= DRAG_MIN_PX:
            # 캔버스 y는 아래로 증가, map y는 위로 증가
            yaw = math.atan2(-dy, dx)
            if self.mode == "start":
                self.start = (self.start[0], self.start[1], yaw)
            else:
                self.gate = (self.gate[0], self.gate[1], yaw)
            self.redraw()
        self.on_move(e)

    def on_release(self, e):
        self.drag_from = None

    def on_undo(self, e):
        if self.mode == "candy":
            self.points = self.points[:-1]
            self.redraw()

    def on_reset(self, e=None):
        if self.mode == "candy":
            self.points = []
            self.redraw()

    def on_move(self, e):
        x, y = self.canvas_to_map(e.x, e.y)
        self.status.config(text=f"커서 x={x:+.2f}  y={y:+.2f}  ({self.cell_state(x, y)})")

    # ---- 그리기 ----
    def redraw(self):
        self.canvas.delete("pt")
        if self.mode == "candy":
            self.mode_label.config(fg="#c60", text="[사탕 모드]  왼쪽 클릭: 추가   오른쪽 클릭: 마지막 삭제   "
                                                     "R: 모두 지우기   Tab: 다음 모드   S: 저장   Q: 종료")
        elif self.mode == "start":
            self.mode_label.config(fg="#07a", text="[시작 위치 모드]  누른 곳 = 위치, 누른 채 끌기 = 방향   "
                                                     "Tab: 다음 모드   S: 저장   Q: 종료")
        else:
            self.mode_label.config(fg="#a0a", text="[탈출문 모드]  누른 곳 = 문 위치, 누른 채 끌기 = 문 앞 방향   "
                                                     "Tab: 다음 모드   S: 저장   Q: 종료")
        # 맵 원점 (0,0)
        ox, oy = self.map_to_canvas(0.0, 0.0)
        self.canvas.create_line(ox - 8, oy, ox + 8, oy, fill="#3a7", tags="pt")
        self.canvas.create_line(ox, oy - 8, ox, oy + 8, fill="#3a7", tags="pt")

        r = self.pick_r / self.res * self.zoom
        lines = []
        for i, (x, y) in enumerate(self.points, 1):
            cx, cy = self.map_to_canvas(x, y)
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#f80", dash=(3, 2), tags="pt")
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#f80", outline="", tags="pt")
            self.canvas.create_text(cx + 8, cy - 8, text=f"c{i}", fill="#f40",
                                    font=("sans", 11, "bold"), anchor="sw", tags="pt")
            lines.append(f"c{i}: x={x:+.2f}  y={y:+.2f}{self._warn(x, y)}")
        lines.append(f"사탕 [{len(self.points)}/{self.count}]  점선 원 = 획득 반경 {self.pick_r} m")

        if self.start:
            x, y, yaw = self.start
            cx, cy = self.map_to_canvas(x, y)
            body = 0.17 / self.res * self.zoom  # TurtleBot4 반지름 약 0.17 m
            self.canvas.create_oval(cx - body, cy - body, cx + body, cy + body,
                                    outline="#29f", width=2, tags="pt")
            self.canvas.create_line(cx, cy, cx + 2 * body * math.cos(yaw), cy - 2 * body * math.sin(yaw),
                                    fill="#29f", width=3, arrow="last", tags="pt")
            self.canvas.create_text(cx + body + 4, cy + body, text="start", fill="#07a",
                                    font=("sans", 10, "bold"), anchor="nw", tags="pt")
            lines.append(f"시작: x={x:+.2f}  y={y:+.2f}  yaw={yaw:+.2f} rad "
                         f"({math.degrees(yaw):+.0f}°){self._warn(x, y)}")
        else:
            lines.append("시작: 없음")
        if self.gate:
            x, y, yaw = self.gate
            cx, cy = self.map_to_canvas(x, y)
            px = self.zoom / self.res  # m → 캔버스 px
            # 문 앞 구역 (사탕을 다 모은 뒤 여기서 머무르면 문이 열림)
            fx, fy = x + self.gate_front * math.cos(yaw), y + self.gate_front * math.sin(yaw)
            fcx, fcy = self.map_to_canvas(fx, fy)
            zr = self.gate_zone_r * px
            self.canvas.create_oval(fcx - zr, fcy - zr, fcx + zr, fcy + zr, outline="#a0a", dash=(4, 2), tags="pt")
            # 문 지점 (열린 뒤 여기 닿으면 클리어)
            er = self.gate_enter_r * px
            self.canvas.create_oval(cx - er, cy - er, cx + er, cy + er, fill="#c6c", outline="#a0a", width=2, tags="pt")
            self.canvas.create_line(cx, cy, fcx, fcy, fill="#a0a", width=3, arrow="last", tags="pt")
            self.canvas.create_text(cx - er - 4, cy - er, text="gate", fill="#a0a",
                                    font=("sans", 10, "bold"), anchor="se", tags="pt")
            lines.append(f"탈출문: x={x:+.2f}  y={y:+.2f}  yaw={yaw:+.2f} rad ({math.degrees(yaw):+.0f}°){self._warn(x, y)}"
                         f"   문 앞 구역 중심 ({fx:+.2f}, {fy:+.2f}){self._warn(fx, fy)}")
        else:
            lines.append("탈출문: 없음")
        lines.append("초록 + = map 원점 (0,0), 파란 원 = 로봇 크기(반지름 0.17 m)")
        self.info.config(text="\n".join(lines))

    def _warn(self, x: float, y: float) -> str:
        state = self.cell_state(x, y)
        return "" if state == "빈 공간" else f"   ⚠ {state}"

    # ---- 저장 ----
    def on_save(self, e=None):
        text = self.level_path.read_text(encoding="utf-8")
        saved = []
        if len(self.points) == self.count:
            block = ["candies:"] + [f"  - {{id: c{i}, x: {x:.2f}, y: {y:.2f}}}"
                                    for i, (x, y) in enumerate(self.points, 1)]
            # candies: 줄부터 들여쓰기된 줄이 끝날 때까지를 교체 (다른 키와 주석은 그대로 둔다)
            pattern = re.compile(r"^candies:.*\n(?:[ \t]+.*\n?|\n)*", re.M)
            if not pattern.search(text):
                sys.exit(f"{self.level_path}에 candies: 블록이 없다")
            text = pattern.sub(lambda m: "\n".join(block) + "\n\n", text, count=1)
            saved.append("사탕")
            print("\n".join(block))
        elif self.points:
            self.status.config(text=f"사탕은 {self.count}개를 모두 찍어야 저장된다 (현재 {len(self.points)}개)")
            return
        if self.start:
            x, y, yaw = self.start
            line = f"pumpkin_start: {{x: {x:.2f}, y: {y:.2f}, yaw: {yaw:.2f}}}"
            pattern = re.compile(r"^pumpkin_start:.*$", re.M)
            if pattern.search(text):
                text = pattern.sub(lambda m: line, text, count=1)
            else:
                text = text.replace("\ncandies:", f"\n{line}\n\ncandies:", 1)
            saved.append("시작 위치")
            print(line)
        if self.gate:
            x, y, yaw = self.gate
            line = f"gate: {{x: {x:.2f}, y: {y:.2f}, yaw: {yaw:.2f}}}"
            pattern = re.compile(r"^gate:.*$", re.M)
            text = pattern.sub(lambda m: line, text, count=1) if pattern.search(text) else text.rstrip("\n") + f"\n\n{line}\n"
            saved.append("탈출문")
            print(line)
        self.level_path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        self.status.config(text=f"저장함 ({', '.join(saved)}) → {self.level_path}")

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level", nargs="?", default=str(BACKEND_DIR / "config/level1.yaml"))
    ap.add_argument("-n", "--count", type=int, default=3, help="사탕 개수 (기본 3)")
    ap.add_argument("--start", action="store_true", help="시작 위치 모드로 연다")
    ap.add_argument("--gate", action="store_true", help="탈출문 모드로 연다")
    args = ap.parse_args()
    mode = "gate" if args.gate else "start" if args.start else "candy"
    Picker(Path(args.level).resolve(), args.count, mode).run()


if __name__ == "__main__":
    main()
