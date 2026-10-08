#!/usr/bin/env python3
"""맵 이미지 위를 클릭해 사탕 위치를 찍고 레벨 yaml의 candies 블록에 저장한다.

  python3 tools/pick_candies.py                       # config/level1.yaml
  python3 tools/pick_candies.py config/level2.yaml -n 3

조작: 왼쪽 클릭 = 추가, 오른쪽 클릭 = 마지막 점 삭제, S = 저장, R = 모두 지우기, Q/Esc = 종료
"""
import argparse
import re
import sys
import tkinter as tk
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
MAX_W, MAX_H = 900, 700


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
    def __init__(self, level_path: Path, count: int):
        self.level_path = level_path
        self.count = count
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
        # 기존 좌표를 불러와 보여준다 (자리표시 값일 수 있음)
        self.points = [(float(c["x"]), float(c["y"])) for c in level.get("candies") or []][:count]

        self.root = tk.Tk()
        self.root.title(f"사탕 위치 찍기 — {level_path.name} / {map_yaml.name}")
        self.img = tk.PhotoImage(file=str(pgm)).zoom(self.zoom)
        self.canvas = tk.Canvas(self.root, width=self.w * self.zoom, height=self.h * self.zoom,
                                highlightthickness=0, cursor="crosshair")
        self.canvas.create_image(0, 0, anchor="nw", image=self.img)
        self.canvas.pack()
        self.status = tk.Label(self.root, anchor="w", font=("monospace", 10))
        self.status.pack(fill="x")
        self.info = tk.Label(self.root, anchor="w", justify="left", font=("monospace", 10))
        self.info.pack(fill="x")
        tk.Label(self.root, anchor="w", fg="#666",
                 text="왼쪽 클릭: 추가   오른쪽 클릭: 마지막 삭제   S: 저장   R: 모두 지우기   Q: 종료").pack(fill="x")

        self.canvas.bind("<Button-1>", self.on_add)
        self.canvas.bind("<Button-3>", self.on_undo)
        self.canvas.bind("<Motion>", self.on_move)
        self.root.bind("<Key-s>", self.on_save)
        self.root.bind("<Key-r>", lambda e: self.set_points([]))
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

    def set_points(self, pts):
        self.points = pts
        self.redraw()

    def on_add(self, e):
        if len(self.points) >= self.count:
            self.status.config(text=f"이미 {self.count}개. 오른쪽 클릭으로 지운 뒤 다시 찍기")
            return
        self.set_points(self.points + [self.canvas_to_map(e.x, e.y)])

    def on_undo(self, e):
        self.set_points(self.points[:-1])

    def on_move(self, e):
        x, y = self.canvas_to_map(e.x, e.y)
        self.status.config(text=f"커서 x={x:+.2f}  y={y:+.2f}  ({self.cell_state(x, y)})")

    def redraw(self):
        self.canvas.delete("pt")
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
            state = self.cell_state(x, y)
            warn = "" if state == "빈 공간" else f"   ⚠ {state}"
            lines.append(f"c{i}: x={x:+.2f}  y={y:+.2f}{warn}")
        lines.append(f"[{len(self.points)}/{self.count}]  점선 원 = 획득 반경 {self.pick_r} m   초록 + = map 원점")
        self.info.config(text="\n".join(lines))

    def on_save(self, e=None):
        if len(self.points) != self.count:
            self.status.config(text=f"{self.count}개를 모두 찍어야 저장된다 (현재 {len(self.points)}개)")
            return
        block = ["candies:"] + [f"  - {{id: c{i}, x: {x:.2f}, y: {y:.2f}}}"
                                for i, (x, y) in enumerate(self.points, 1)]
        text = self.level_path.read_text(encoding="utf-8")
        # candies: 줄부터 들여쓰기된 줄이 끝날 때까지를 교체 (다른 키와 주석은 그대로 둔다)
        pattern = re.compile(r"^candies:.*\n(?:[ \t]+.*\n?|\n)*", re.M)
        if not pattern.search(text):
            sys.exit(f"{self.level_path}에 candies: 블록이 없다")
        text = pattern.sub(lambda m: "\n".join(block) + "\n", text, count=1)
        self.level_path.write_text(text, encoding="utf-8")
        self.status.config(text=f"저장함 → {self.level_path}")
        print("\n".join(block))

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level", nargs="?", default=str(BACKEND_DIR / "config/level1.yaml"))
    ap.add_argument("-n", "--count", type=int, default=3, help="사탕 개수 (기본 3)")
    args = ap.parse_args()
    Picker(Path(args.level).resolve(), args.count).run()


if __name__ == "__main__":
    main()
