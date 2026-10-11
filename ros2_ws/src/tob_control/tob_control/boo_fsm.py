"""Boo 행동 상태 전환(순찰·의심·추격·수색).

[역할]
유효한 관측과 이동 결과를 받아 Boo의 다음 행동을 결정하는 일반 Python 모듈이다.
ROS, Nav2에 의존하지 않아 로봇 없이 시험할 수 있다.
[입출력]
입력: 관측(보이면 지도 좌표, 아니면 None), 경과 시간, 이동 결과, 활성 여부.
출력: 현재 상태(Behavior), 의심 게이지(0~1), 지금 필요한 행동(Command).
[규칙(Lv1)]
- PATROL: 순찰 지점을 차례로 돈다. 관측되면 SUSPECT.
  관측이 되는 순간 곧바로 의심하며, 이 모듈에는 거리 기준이 없다. 지도 어디에서든 "보인다"는 관측이면 된다
  (개발팀장 구두 지시 2026-10-11: 거리와 상관없이 펌킨이 인지되면 의심 모드. 몇 m까지 인지되는지는 탐지 노드의 몫).
- SUSPECT: 멈추고 본다. 보이는 동안 게이지가 suspicion_fill_s(3초)에 걸쳐 0에서 1까지 차오르고,
  1이 되면 CHASE. 안 보이면 suspicion_decay_s에 걸쳐 줄어 0이 되면 PATROL.
  계속 보이면 SUSPECT에 머무는 시간은 정확히 suspicion_fill_s(3초)이다.
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
    """Boo의 행동 상태. 숫자는 tob_interfaces/BooState.msg의 behavior 값과 같아야 한다."""

    IDLE = 0
    PATROL = 1
    SUSPECT = 2
    CHASE = 3
    SEARCH = 4


class CmdKind(IntEnum):
    """step()이 호출자(컨트롤러 노드)에게 요청하는 행동의 종류."""

    NONE = 0   # 하던 대로 둔다
    GOTO = 1   # target으로 이동 (이미 같은 목표면 호출자가 다시 보내지 않는다)
    STOP = 2   # 진행 중인 이동을 취소하고 서 있는다


@dataclass
class Command:
    """step()의 결과. 무엇을(kind) 어디로(target) 왜(reason) 하라는 요청이다."""

    kind: CmdKind = CmdKind.NONE
    target: Optional[Point] = None
    reason: str = ''


@dataclass
class FsmConfig:
    """상태 전환에 쓰는 시간·횟수 설정. 값은 control.yaml에서 오며, 항목별 설명은 그 파일을 본다."""

    # 계속 보일 때 의심 게이지가 0 → 1이 되는 시간 [s]. 이 시간이 곧 SUSPECT에 머무는 시간(Lv1은 3초).
    suspicion_fill_s: float = 3.0
    # 안 보일 때 게이지가 1 → 0이 되는 시간 [s]. 0이 되면 의심을 거두고 PATROL로 돌아간다.
    suspicion_decay_s: float = 3.0
    # 추격 중 이 시간[s] 동안 관측이 없으면 놓친 것으로 보고 SEARCH로 간다.
    lost_timeout_s: float = 1.0
    # SEARCH 지점에 도착한 뒤 머무는 시간 [s]. Lv1은 수색 연출이 없으므로 0(도착하면 바로 순찰).
    search_hold_s: float = 0.0
    # SEARCH 지점까지 가는 데 쓸 최대 시간 [s]. 넘으면 못 간 채로 수색을 끝낸다.
    search_timeout_s: float = 15.0
    # 순찰 목표가 연속으로 이만큼 실패하면 멈추고 사유를 남긴다 [회].
    max_goal_failures: int = 3
    # 연속 실패로 멈춘 뒤 이 시간[s]이 지나면 실패 횟수를 지우고 순찰을 다시 시도한다.
    failure_hold_s: float = 5.0
    # True이면 의심 중 이동을 멈추고 서서 관찰한다. False이면 하던 순찰을 계속한다.
    suspect_hold: bool = True


class BooFsm:
    """Boo 행동 상태기계. step()을 주기적으로 부르고, 이동이 끝나면 on_nav_result()를 부른다."""

    def __init__(self, config: FsmConfig, patrol_points: List[Point]):
        self.cfg = config
        self.patrol_points = list(patrol_points)
        self.behavior = Behavior.IDLE
        self.suspicion = 0.0                          # 의심 게이지 0~1 (1이 되면 추격)
        self.last_seen: Optional[Point] = None        # 마지막으로 본 펌킨의 지도 좌표 (SEARCH 목표)
        self.reason = '대기'
        self._enabled = False        # 게임 진행 + 이동 허용일 때만 True
        self._patrol_index = 0       # 다음에 갈 순찰 지점 번호
        self._unseen_s = 0.0         # 연속으로 못 본 시간
        self._state_s = 0.0          # 현재 상태에 머문 시간
        self._arrived = False        # SEARCH의 목표에 도착했는지
        self._since_arrival = 0.0    # 도착한 뒤 흐른 시간
        self._failures = 0           # 순찰 목표 연속 실패 횟수
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
        """진행 중이던 목표가 끝났을 때 알린다. canceled는 우리가 취소한 경우다.

        PATROL: 성공하면 실패 횟수를 지우고, 성공·실패와 상관없이 다음 순찰 지점으로 넘어간다.
        CHASE/SEARCH: 성공은 "도착"이다. 실패는 도착으로 치지 않지만, SEARCH에서는 못 가는 곳이므로 수색을 마무리한다.
        """
        if canceled:
            return   # 우리가 일부러 취소한 것(상태 전환·정지 거리)은 성공도 실패도 아니다
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
        """dt초가 지났고 지금 seen(지도 좌표)이 보이면 그 좌표, 아니면 None.

        한 번 부를 때마다 시간을 갱신하고 현재 상태의 처리를 한 번 수행해, 호출자가 할 일(Command)을 돌려준다.
        """
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
            # 거리와 상관없이 보이면 곧바로 의심한다. 멈춰서 관찰하는 설정이면 진행 중인 순찰 이동을 취소한다.
            self._go(Behavior.SUSPECT, '펌킨 발견')
            return Command(CmdKind.STOP if self.cfg.suspect_hold else CmdKind.NONE,
                           reason=self.reason)
        if not self.patrol_points:
            return Command(CmdKind.STOP, reason='순찰 지점 없음')
        if self._failures >= self.cfg.max_goal_failures:
            # 목표가 계속 실패하면 새 목표를 보내지 않고 정지한다. failure_hold_s가 지나면 횟수를 지우고 재시도한다.
            self.reason = '순찰 목표 연속 실패'
            if self._fail_stop_s >= self.cfg.failure_hold_s:
                self._failures = 0    # 잠시 쉬었다가 처음부터 다시 시도한다(무한 재시도는 아님)
                self._fail_stop_s = 0.0
            return Command(CmdKind.STOP, reason=self.reason)
        return Command(CmdKind.GOTO, self.patrol_points[self._patrol_index], '순찰')

    def _suspect(self, dt: float, seen: Optional[Point]) -> Command:
        if seen is not None:
            # 보이는 동안 dt/suspicion_fill_s씩 올라 3초(기본)면 1이 된다. 1이 되는 순간 추격을 시작한다.
            self.suspicion = min(1.0, self.suspicion + dt / self.cfg.suspicion_fill_s)
            if self.suspicion >= 1.0:
                self._go(Behavior.CHASE, '의심 게이지 가득')
                return Command(CmdKind.GOTO, seen, self.reason)
        else:
            # 안 보이면 같은 방식으로 줄고, 0이 되면 의심을 거둔다.
            self.suspicion = max(0.0, self.suspicion - dt / self.cfg.suspicion_decay_s)
            if self.suspicion <= 0.0:
                self._go(Behavior.PATROL, '의심 해소')
                return Command(CmdKind.NONE, reason=self.reason)
        return Command(CmdKind.NONE)

    def _chase(self, seen: Optional[Point]) -> Command:
        if seen is not None:
            self._arrived = False   # 목표를 계속 새 위치로 갱신한다(너무 자주 보내지 않는 것은 컨트롤러가 거른다)
            return Command(CmdKind.GOTO, seen, '추격')
        # 잠깐 안 보이는 것은 참고 계속 가고, lost_timeout_s 이상 못 보면 마지막으로 본 곳을 수색한다.
        if self._unseen_s >= self.cfg.lost_timeout_s and self.last_seen is not None:
            self._go(Behavior.SEARCH, '펌킨을 놓침')
            return Command(CmdKind.GOTO, self.last_seen, self.reason)
        return Command(CmdKind.NONE)

    def _search(self, seen: Optional[Point]) -> Command:
        if seen is not None:
            self._go(Behavior.CHASE, '수색 중 재발견')
            return Command(CmdKind.GOTO, seen, self.reason)
        # 도착한 뒤 search_hold_s가 지났거나, 가는 데 search_timeout_s를 넘기면 수색을 끝낸다.
        done_waiting = self._arrived and self._since_arrival >= self.cfg.search_hold_s
        if done_waiting or self._state_s >= self.cfg.search_timeout_s:
            self.suspicion = 0.0
            self._go(Behavior.PATROL, '수색 종료')
            return Command(CmdKind.NONE, reason=self.reason)
        return Command(CmdKind.NONE)

    # ---- 내부 ----
    def _go(self, behavior: Behavior, reason: str) -> None:
        """상태를 바꾸고 상태별 타이머를 0으로 되돌린다. reason은 BooState.reason으로 나간다."""
        self.behavior = behavior
        self.reason = reason
        self._state_s = 0.0
        self._since_arrival = 0.0
        self._arrived = False
