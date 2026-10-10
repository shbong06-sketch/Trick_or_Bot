import io
import math
import threading
import time
from datetime import datetime

from ..protocol import Pose7
from ..settings import ROBOT
from .base import Bridge, VideoSink

CAMERA_FPS = 30          # OAK-D처럼 서버 목표 fps보다 빠르게 내보낸다
JPEG_QUALITY = 70
CAM_OFFSET = (0.08, 0.0, 0.25)  # base_link 기준 카메라 위치 (m), mock 전용 대략값
# base_link → 광학 프레임 회전 (광학: x 오른쪽, y 아래, z 앞)
Q_BASE_OPTICAL = (-0.5, 0.5, -0.5, 0.5)
GRID_STEP = 0.5          # 바닥 격자 간격 (m)
MARK_R = 0.10            # 사탕 자리 바닥 표시 반지름 (m). 실제 아레나의 바닥 테이프 역할
NEAR = 0.05              # 이보다 가까운 점은 잘라 낸다 (m)
WALL_H = 0.6             # 판자벽 높이 (m), SR-015


def _wall_segments(m: dict) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """점유 격자에서 벽 면(점유/비점유 셀 경계)을 뽑아 일직선으로 이어 붙인다."""
    w, h, res, ox, oy, occ = m["w"], m["h"], m["res"], m["ox"], m["oy"], m["occ"]

    def o(r, c):
        return 0 <= r < h and 0 <= c < w and occ[r * w + c] == 1

    segs = []
    for r in range(h + 1):          # 가로 경계: r행 위쪽 변, y는 고정
        y = oy + (h - r) * res
        c = 0
        while c < w:
            if o(r, c) != o(r - 1, c):
                c0 = c
                while c < w and o(r, c) != o(r - 1, c):
                    c += 1
                segs.append(((ox + c0 * res, y), (ox + c * res, y)))
            c += 1
    for c in range(w + 1):          # 세로 경계: c열 왼쪽 변, x는 고정
        x = ox + c * res
        r = 0
        while r < h:
            if o(r, c) != o(r, c - 1):
                r0 = r
                while r < h and o(r, c) != o(r, c - 1):
                    r += 1
                segs.append(((x, oy + (h - r) * res), (x, oy + (h - r0) * res)))
            r += 1
    return segs


def _quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


class MockBridge(Bridge):
    """가짜 펌킨: 마지막 cmd_vel을 시간에 대해 적분해 움직이고, 가짜 카메라 JPEG를 만든다. 벽 충돌은 없다.

    가짜 카메라는 바닥 격자와 사탕 자리 표시(원)를 브라우저와 별개의 코드로 투영해 그린다.
    브라우저 AR 아이콘이 이 원 위에 붙어 있으면 투영이 맞는 것이다.
    """

    def __init__(self, level: dict):
        start = level["pumpkin_start"]
        self._lock = threading.Lock()
        self._x, self._y, self._yaw = start["x"], start["y"], start["yaw"]
        self._lin = self._ang = 0.0
        self._t = time.monotonic()
        self._candies = [(c["x"], c["y"]) for c in level["candies"]]
        self._patrol = [(p["x"], p["y"]) for p in level.get("boo_patrol") or []]
        self._boo_speed = float(ROBOT["boo"]["mock_speed"])
        self._t_start = time.monotonic()
        m = level["map"]
        self._walls = _wall_segments(m)
        self._bounds = (m["ox"], m["oy"], m["ox"] + m["w"] * m["res"], m["oy"] + m["h"] * m["res"])
        self._sink: VideoSink | None = None
        self._running = False
        self._cam_thread = threading.Thread(target=self._camera_loop, daemon=True)

    def start(self) -> None:
        self._running = True
        self._cam_thread.start()

    def stop(self) -> None:
        self._running = False

    def set_video_sink(self, sink: VideoSink) -> None:
        self._sink = sink

    def camera_info(self) -> dict:
        return dict(ROBOT["camera_placeholder"])

    def _integrate(self) -> None:
        now = time.monotonic()
        dt, self._t = now - self._t, now
        lin, ang = self._lin, self._ang
        if ang:
            # 원호 적분 (차동 구동)
            yaw2 = self._yaw + ang * dt
            r = lin / ang
            self._x += r * (math.sin(yaw2) - math.sin(self._yaw))
            self._y -= r * (math.cos(yaw2) - math.cos(self._yaw))
            self._yaw = math.atan2(math.sin(yaw2), math.cos(yaw2))
        else:
            self._x += lin * math.cos(self._yaw) * dt
            self._y += lin * math.sin(self._yaw) * dt

    def send_cmd(self, lin: float, ang: float) -> None:
        with self._lock:
            self._integrate()
            self._lin, self._ang = lin, ang

    def pumpkin_pose(self):
        with self._lock:
            self._integrate()
            return self._x, self._y, self._yaw

    def boo_pose(self):
        """mock 부우: 순찰선 두 점을 일정 속도로 왕복한다."""
        if len(self._patrol) < 2:
            return None
        (ax, ay), (bx, by) = self._patrol[:2]
        length = math.hypot(bx - ax, by - ay)
        s = (time.monotonic() - self._t_start) * self._boo_speed % (2 * length)
        forward = s <= length
        f = (s if forward else 2 * length - s) / length
        yaw = math.atan2(by - ay, bx - ax) + (0.0 if forward else math.pi)
        return ax + f * (bx - ax), ay + f * (by - ay), math.atan2(math.sin(yaw), math.cos(yaw))

    # ---- 가짜 카메라 ----
    def _camera_pose(self, x: float, y: float, yaw: float) -> Pose7:
        c, s = math.cos(yaw), math.sin(yaw)
        ox, oy, oz = CAM_OFFSET
        q = _quat_mul((0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)), Q_BASE_OPTICAL)
        return (x + c * ox - s * oy, y + s * ox + c * oy, oz, *q)

    def _camera_loop(self) -> None:
        from PIL import Image, ImageDraw, ImageFont  # mock에서만 필요

        cam = ROBOT["camera_placeholder"]
        w, h = int(cam["w"]), int(cam["h"])
        fx, fy, cx, cy = float(cam["fx"]), float(cam["fy"]), float(cam["cx"]), float(cam["cy"])
        try:
            big = ImageFont.truetype("DejaVuSansMono.ttf", 44)
            small = ImageFont.truetype("DejaVuSansMono.ttf", 20)
        except OSError:
            big = small = ImageFont.load_default()
        x0, y0, x1, y1 = self._bounds
        gx = [x0 + i * GRID_STEP for i in range(int((x1 - x0) / GRID_STEP) + 1)]
        gy = [y0 + i * GRID_STEP for i in range(int((y1 - y0) / GRID_STEP) + 1)]
        period = 1.0 / CAMERA_FPS
        seq = 0
        while self._running:
            t0 = time.monotonic()
            seq += 1
            if self._sink and self._sink.want_frame():
                stamp = time.time()
                x, y, yaw = self.pumpkin_pose()
                pose = self._camera_pose(x, y, yaw)
                cam_x, cam_y, cam_z = pose[:3]
                c, s = math.cos(yaw), math.sin(yaw)

                def to_cam(px, py, pz=0.0):
                    # 로봇 yaw로 직접 풀기: 앞 = (c, s), 왼쪽 = (-s, c), 위 = z
                    dx, dy, dz = px - cam_x, py - cam_y, pz - cam_z
                    fwd, left = c * dx + s * dy, -s * dx + c * dy
                    return -left, -dz, fwd  # 광학 (x 오른쪽, y 아래, z 앞)

                def proj(p):
                    return fx * p[0] / p[2] + cx, fy * p[1] / p[2] + cy

                def seg(a, b):
                    """카메라 앞쪽(z ≥ NEAR)으로 자른 선분을 투영한다."""
                    pa, pb = to_cam(*a), to_cam(*b)
                    if pa[2] < NEAR and pb[2] < NEAR:
                        return None
                    if pa[2] < NEAR or pb[2] < NEAR:
                        t = (NEAR - pa[2]) / (pb[2] - pa[2])
                        cut = tuple(pa[i] + t * (pb[i] - pa[i]) for i in range(3))
                        pa, pb = (cut, pb) if pa[2] < NEAR else (pa, cut)
                    return proj(pa) + proj(pb)

                def poly(pts3):
                    """광학 프레임 다각형을 z ≥ NEAR로 잘라 투영한다."""
                    out = []
                    for i, p in enumerate(pts3):
                        q = pts3[(i + 1) % len(pts3)]
                        if p[2] >= NEAR:
                            out.append(p)
                        if (p[2] >= NEAR) != (q[2] >= NEAR):
                            t = (NEAR - p[2]) / (q[2] - p[2])
                            out.append(tuple(p[k] + t * (q[k] - p[k]) for k in range(3)))
                    return [proj(p) for p in out] if len(out) >= 3 else None

                img = Image.new("RGB", (w, h), (18, 14, 28))
                d = ImageDraw.Draw(img)
                d.rectangle([0, cy, w, h], fill=(30, 25, 42))  # 카메라가 수평이라 지평선 = cy
                for gxv in gx:
                    if (l := seg((gxv, y0), (gxv, y1))):
                        d.line(l, fill=(70, 62, 110), width=1)
                for gyv in gy:
                    if (l := seg((x0, gyv), (x1, gyv))):
                        d.line(l, fill=(70, 62, 110), width=1)
                # 사탕 자리 바닥 표시: 실제 아레나에 붙인 테이프 원과 같은 역할
                for (px, py) in self._candies:
                    ring = [(px + MARK_R * math.cos(a), py + MARK_R * math.sin(a))
                            for a in (2 * math.pi * k / 24 for k in range(25))]
                    for a, b in zip(ring, ring[1:]):
                        if (l := seg(a, b)):
                            d.line(l, fill=(0, 230, 120), width=2)
                    if (l := seg((px - MARK_R, py), (px + MARK_R, py))):
                        d.line(l, fill=(0, 230, 120), width=1)
                    if (l := seg((px, py - MARK_R), (px, py + MARK_R))):
                        d.line(l, fill=(0, 230, 120), width=1)
                # 벽: 먼 면부터 그려 가까운 면이 앞을 가리게 한다 (사탕 자리 표시도 가려진다)
                faces = []
                for (a, b) in self._walls:
                    ca, cb = to_cam(*a), to_cam(*b)
                    if ca[2] < NEAR and cb[2] < NEAR:
                        continue
                    mid = ((a[0] + b[0]) / 2 - cam_x, (a[1] + b[1]) / 2 - cam_y)
                    faces.append((mid[0] ** 2 + mid[1] ** 2, a, b))
                for _, a, b in sorted(faces, key=lambda f: f[0], reverse=True):
                    pts = poly([to_cam(a[0], a[1], 0), to_cam(b[0], b[1], 0),
                                to_cam(b[0], b[1], WALL_H), to_cam(a[0], a[1], WALL_H)])
                    if pts:
                        shade = (92, 70, 58) if a[1] == b[1] else (120, 92, 72)  # 가로·세로 면 밝기 차이
                        d.polygon(pts, fill=shade, outline=(60, 44, 36))
                clock = datetime.fromtimestamp(stamp).strftime("%H:%M:%S.%f")[:-3]
                d.text((20, 20), clock, font=big, fill=(255, 255, 255))
                d.text((20, 76), f"MOCK cam #{seq}  {w}x{h}",
                       font=small, fill=(180, 180, 200))
                d.text((20, h - 40), f"x {x:+.2f}  y {y:+.2f}  yaw {math.degrees(yaw):+.0f}°",
                       font=small, fill=(180, 180, 200))
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=JPEG_QUALITY)
                self._sink.push(stamp, pose, buf.getvalue())
            time.sleep(max(0.0, period - (time.monotonic() - t0)))
