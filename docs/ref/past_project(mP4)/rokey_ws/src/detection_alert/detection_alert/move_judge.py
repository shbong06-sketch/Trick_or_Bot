"""시간 기준 판정 로직 (ROS 없이 단독 테스트 가능). 처리 주기(Hz)와 무관하게 초 단위로 판단한다.

CarAlert   car 알림 ON/OFF 안정화
             ON  : 최근 on_sec 동안 내 차가 보인 프레임 비율 >= on_ratio
             OFF : off_sec 동안 내 차가 한 번도 안 보임
MoveJudge  내 차의 map 좌표로 '멈춤'과 '이동'을 판단 (플로우차트 '이동 판단')
             기준 위치 : stop_sec 동안 흔들림 <= stop_tol 로 멈춘 위치
             이동      : 최근 avg_sec 평균이 기준에서 >= move_dist 인 상태가 hold_sec 이상 계속
             hold_sec 미만의 튐은 노이즈로 무시. 다시 stop_sec 동안 멈추면 새 기준.
"""
import math
from collections import deque


class CarAlert:
    def __init__(self, on_sec=0.3, on_ratio=0.6, off_sec=0.7):
        self.on_sec, self.on_ratio, self.off_sec = on_sec, on_ratio, off_sec
        self.history = deque()   # (t, 내 차가 보였는가)
        self.last_seen = None
        self.last_t = None
        self.dt = None           # 프레임 간격 이동평균(초). 처리 주기가 달라져도 ON 기준이 따라감
        self.active = False

    def update(self, t, seen):
        """프레임 시각 t(초)와 내 차 검출 여부를 넣고, 상태가 바뀌었으면 True를 돌려준다."""
        if self.last_t is not None and t > self.last_t:
            gap = t - self.last_t
            self.dt = gap if self.dt is None else 0.9 * self.dt + 0.1 * gap
        self.last_t = t
        self.history.append((t, seen))
        if seen:
            self.last_seen = t
        while self.history and t - self.history[0][0] > self.on_sec:
            self.history.popleft()
        prev = self.active
        if not self.active:
            n_seen = sum(s for _, s in self.history)
            # 구간 안에 들어올 프레임 수(on_sec/dt)의 on_ratio 만큼은 봐야 함. 단발(1프레임)로는 켜지지 않게 최소 2
            need = 2 if self.dt is None else max(2, math.ceil(self.on_ratio * self.on_sec / self.dt - 1e-9))
            if n_seen >= need and n_seen / len(self.history) >= self.on_ratio:
                self.active = True
        elif self.last_seen is None or t - self.last_seen >= self.off_sec:
            self.active = False
            self.history.clear()
        return self.active != prev


class MoveJudge:
    def __init__(self, stop_sec=1.0, stop_tol=0.05, avg_sec=0.5, move_dist=0.3, hold_sec=0.2):
        self.stop_sec, self.stop_tol = stop_sec, stop_tol
        self.avg_sec, self.move_dist, self.hold_sec = avg_sec, move_dist, hold_sec
        self.reset()

    def reset(self):
        self.samples = deque()   # (t, x, y), 최근 stop_sec 동안
        self.ref = None          # 기준 위치 (x, y)
        self.move_since = None
        self.moving = False
        self.stopped = False
        self.pos = None          # 판단에 쓰는 대표 위치: 멈춤=stop_sec 평균, 이동=avg_sec 평균

    def update(self, t, x, y):
        """샘플 1개를 넣는다. 결과는 self.stopped / self.moving / self.pos / self.ref 로 읽는다."""
        self.samples.append((t, x, y))
        while self.samples and t - self.samples[0][0] > self.stop_sec:
            self.samples.popleft()
        n = len(self.samples)
        mx = sum(s[1] for s in self.samples) / n
        my = sum(s[2] for s in self.samples) / n
        full = t - self.samples[0][0] >= self.stop_sec * 0.8
        self.stopped = full and max(math.dist((s[1], s[2]), (mx, my)) for s in self.samples) <= self.stop_tol
        if self.ref is None:
            self.ref = (x, y)    # 처음 보인 위치를 임시 기준으로 (첫 멈춤에서 갱신됨)

        if self.stopped:
            self.ref, self.pos = (mx, my), (mx, my)
            self.moving, self.move_since = False, None
            return
        recent = [s for s in self.samples if t - s[0] <= self.avg_sec]
        rx = sum(s[1] for s in recent) / len(recent)
        ry = sum(s[2] for s in recent) / len(recent)
        self.pos = (rx, ry)
        if math.dist(self.pos, self.ref) >= self.move_dist:
            if self.move_since is None:
                self.move_since = t
            self.moving = t - self.move_since >= self.hold_sec
        else:
            self.move_since, self.moving = None, False   # 기준 근처로 돌아오면 이동이 아님 (튐)
