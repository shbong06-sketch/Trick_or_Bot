"""Boo 행동 상태 전환(순찰·의심·추격·수색).

[역할]
유효한 관측과 이동 결과를 받아 Boo의 다음 행동을 결정하는 일반 Python 모듈이다.
ROS, Nav2에 의존하지 않아 로봇 없이 시험할 수 있다.
[입출력]
입력: 관측(보이면 지도 좌표, 아니면 None), 경과 시간, 이동 결과, 활성 여부.
출력: 현재 상태(Behavior), 의심 게이지(0~1), 지금 필요한 행동(Command).
[규칙(Lv1)]
- PATROL: 순찰 지점을 차례로 돈다. 관측되면 SUSPECT.
- SUSPECT: 멈추고 본다. 보이는 동안 게이지가 suspicion_fill_s에 걸쳐 차오르고,
  가득 차면 CHASE. 안 보이면 suspicion_decay_s에 걸쳐 줄어 0이 되면 PATROL.
- CHASE: 마지막 관측 위치로 계속 이동한다. lost_timeout_s 동안 못 보면 SEARCH.
- SEARCH: 마지막 관측 위치로 가서 search_hold_s만큼 머문 뒤 PATROL.
  (Lv1은 수색이 없으므로 search_hold_s=0.) 도중에 보이면 곧바로 CHASE.
[실패 처리]
오래된 관측은 호출자가 걸러서 None으로 넘긴다. 이동 실패는 도착으로 취급하지 않는다.
순찰 목표가 연달아 max_goal_failures번 실패하면 멈추고 사유를 남긴다.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple

Point = Tuple[float, float]


class Behavior(IntEnum):
    """BooState.msg의 behavior 값과 같다."""

    IDLE = 0
    PATROL = 1
    SUSPECT = 2
    CHASE = 3
    SEARCH = 4


class CmdKind(IntEnum):
    NONE = 0   # 하던 대로 둔다
    GOTO = 1   # target으로 이동 (이미 같은 목표면 호출자가 다시 보내지 않는다)
    STOP = 2   # 진행 중인 이동을 취소하고 서 있는다


@dataclass
class Command:
    kind: CmdKind = CmdKind.NONE
    target: Optional[Point] = None
    reason: str = ''


@dataclass
class FsmConfig:
    suspicion_fill_s: float = 3.0     # 계속 보일 때 게이지가 0 → 1이 되는 시간
    suspicion_decay_s: float = 3.0    # 안 보일 때 게이지가 1 → 0이 되는 시간
    lost_timeout_s: float = 1.0       # 추격 중 이 시간 못 보면 수색
    search_hold_s: float = 0.0        # 수색 지점에 도착해 머무는 시간
    search_timeout_s: float = 15.0    # 수색 지점까지 가는 데 쓸 최대 시간
    max_goal_failures: int = 3        # 순찰 목표가 연속 실패하면 멈추는 횟수
    failure_hold_s: float = 5.0       # 연속 실패로 멈춘 뒤 이 시간이 지나면 실패 횟수를 지우고 다시 시도
    suspect_hold: bool = True         # 의심 중에 멈춰 서서 관찰할지


class BooFsm:
    """Boo 행동 상태기계. step()을 주기적으로 부르고, 이동이 끝나면 on_nav_result()를 부른다."""

    def __init__(self, config: FsmConfig, patrol_points: List[Point]):
        self.cfg = config
        self.patrol_points = list(patrol_points)
        self.behavior = Behavior.IDLE
        self.suspicion = 0.0
        self.last_seen: Optional[Point] = None
        self.reason = '대기'
        self._enabled = False
        self._patrol_index = 0
        self._unseen_s = 0.0
        self._state_s = 0.0          # 현재 상태에 머문 시간
        self._arrived = False        # SEARCH의 목표에 도착했는지
        self._since_arrival = 0.0    # 도착한 뒤 흐른 시간
        self._failures = 0
        self._fail_stop_s = 0.0      # 연속 실패로 멈춘 뒤 흐른 시간

    # ---- 외부 입력 ----
    def set_enabled(self, enabled: bool) -> None:
        """게임이 진행 중이고 이동이 허용되면 True. False이면 IDLE로 돌아가고 기억을 지운다."""
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if not enabled:
            self._go(Behavior.IDLE, '이동 금지 또는 게임 중단')
            self.suspicion = 0.0
            self.last_seen = None
            self._failures = 0

    def on_nav_result(self, success: bool, canceled: bool = False) -> None:
        """진행 중이던 목표가 끝났을 때 알린다. canceled는 우리가 취소한 경우다."""
        if canceled:
            return
        if self.behavior == Behavior.PATROL:
            if success:
                self._failures = 0
            else:
                self._failures += 1
            self._patrol_index = (self._patrol_index + 1) % max(len(self.patrol_points), 1)
        elif self.behavior in (Behavior.CHASE, Behavior.SEARCH):
            if success:
                self._arrived = True
            elif self.behavior == Behavior.SEARCH:
                self._arrived = True   # 못 가는 곳이면 더 시도하지 않고 마무리
                self.reason = '수색 지점 도달 실패'

    # ---- 주기 호출 ----
    def step(self, dt: float, seen: Optional[Point]) -> Command:
        """dt초가 지났고 지금 seen(지도 좌표)이 보이면 그 좌표, 아니면 None."""
        if not self._enabled:
            return Command(CmdKind.NONE)
        self._state_s += dt
        if self._arrived:
            self._since_arrival += dt
        if self._failures >= self.cfg.max_goal_failures:
            self._fail_stop_s += dt
        if seen is not None:
            self.last_seen = seen
            self._unseen_s = 0.0
        else:
            self._unseen_s += dt

        if self.behavior == Behavior.IDLE:
            self._go(Behavior.PATROL, '게임 진행')
        if self.behavior == Behavior.PATROL:
            return self._patrol(seen)
        if self.behavior == Behavior.SUSPECT:
            return self._suspect(dt, seen)
        if self.behavior == Behavior.CHASE:
            return self._chase(seen)
        return self._search(seen)

    # ---- 상태별 처리 ----
    def _patrol(self, seen: Optional[Point]) -> Command:
        if seen is not None:
            self._go(Behavior.SUSPECT, '펌킨 발견')
            return Command(CmdKind.STOP if self.cfg.suspect_hold else CmdKind.NONE,
                           reason=self.reason)
        if not self.patrol_points:
            return Command(CmdKind.STOP, reason='순찰 지점 없음')
        if self._failures >= self.cfg.max_goal_failures:
            self.reason = '순찰 목표 연속 실패'
            if self._fail_stop_s >= self.cfg.failure_hold_s:
                self._failures = 0    # 잠시 쉬었다가 처음부터 다시 시도한다(무한 재시도는 아님)
                self._fail_stop_s = 0.0
            return Command(CmdKind.STOP, reason=self.reason)
        return Command(CmdKind.GOTO, self.patrol_points[self._patrol_index], '순찰')

    def _suspect(self, dt: float, seen: Optional[Point]) -> Command:
        if seen is not None:
            self.suspicion = min(1.0, self.suspicion + dt / self.cfg.suspicion_fill_s)
            if self.suspicion >= 1.0:
                self._go(Behavior.CHASE, '의심 게이지 가득')
                return Command(CmdKind.GOTO, seen, self.reason)
        else:
            self.suspicion = max(0.0, self.suspicion - dt / self.cfg.suspicion_decay_s)
            if self.suspicion <= 0.0:
                self._go(Behavior.PATROL, '의심 해소')
                return Command(CmdKind.NONE, reason=self.reason)
        return Command(CmdKind.NONE)

    def _chase(self, seen: Optional[Point]) -> Command:
        if seen is not None:
            self._arrived = False
            return Command(CmdKind.GOTO, seen, '추격')
        if self._unseen_s >= self.cfg.lost_timeout_s and self.last_seen is not None:
            self._go(Behavior.SEARCH, '펌킨을 놓침')
            return Command(CmdKind.GOTO, self.last_seen, self.reason)
        return Command(CmdKind.NONE)

    def _search(self, seen: Optional[Point]) -> Command:
        if seen is not None:
            self._go(Behavior.CHASE, '수색 중 재발견')
            return Command(CmdKind.GOTO, seen, self.reason)
        done_waiting = self._arrived and self._since_arrival >= self.cfg.search_hold_s
        if done_waiting or self._state_s >= self.cfg.search_timeout_s:
            self.suspicion = 0.0
            self._go(Behavior.PATROL, '수색 종료')
            return Command(CmdKind.NONE, reason=self.reason)
        return Command(CmdKind.NONE)

    # ---- 내부 ----
    def _go(self, behavior: Behavior, reason: str) -> None:
        self.behavior = behavior
        self.reason = reason
        self._state_s = 0.0
        self._since_arrival = 0.0
        self._arrived = False
