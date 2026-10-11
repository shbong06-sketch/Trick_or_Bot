"""ROS와 실제 시계를 사용하지 않는 Level 1 판정 함수."""

from dataclasses import dataclass, field
import math


@dataclass
class RoundState:
    """한 회차의 규칙 상태. 시간 단위는 일시정지를 제외한 초이다."""

    hp: int
    elapsed_s: float = 0.0
    collected: list = field(default_factory=list)
    hold_s: float = 0.0
    cooldown_until_s: float = 0.0
    last_capture_elapsed: float | None = None
    last_capture_stamp: int | None = None
    observation_floor: int = 0
    awaiting_observation: bool = False
    outcome: str = ''
    reason: str = ''


@dataclass(frozen=True)
class Observation:
    """호출자가 시각·좌표·출처·감지를 검증한 관측."""

    stamp_ns: int
    distance_m: float


@dataclass(frozen=True)
class Event:
    """판정 순서에 따른 사건과 사건 당시의 하트."""

    kind: str
    hp: int
    candy_id: str = ''
    reason: str = ''


def distance(position, center):
    """지도 평면의 유클리드 거리를 계산한다."""
    return math.hypot(position[0] - center['x'], position[1] - center['y'])


def break_capture(state, preserve_hold=False):
    """연속성 기준을 지운다. 일시정지만 기존 누적을 보존한다."""
    if not preserve_hold:
        state.hold_s = 0.0
    state.last_capture_elapsed = None
    state.last_capture_stamp = None


def collect_candies(level, state, position):
    """반경 경계를 포함하여 아직 얻지 않은 사탕만 획득한다."""
    if position is None or not all(math.isfinite(v) for v in position):
        return []
    events = []
    for candy in level['layout']['candies']:
        if (candy['id'] not in state.collected
                and distance(position, candy['position'])
                <= level['rules']['candy']['pickup_radius_m']):
            state.collected.append(candy['id'])
            events.append(Event('CANDY_COLLECTED', state.hp, candy['id']))
    return events


def apply_capture(level, state, observation):
    """새 관측으로만 누적하고, 쿨다운 경계 이후 누적을 새로 시작한다."""
    capture = level['rules']['capture']
    if observation is None:
        if not state.awaiting_observation:
            break_capture(state)
        return []
    state.awaiting_observation = False
    if (not math.isfinite(observation.distance_m)
            or not 0 <= observation.distance_m <= capture['distance_m']):
        break_capture(state)
        return []
    if observation.stamp_ns <= state.observation_floor:
        return []
    state.observation_floor = observation.stamp_ns
    if state.elapsed_s < state.cooldown_until_s:
        break_capture(state)
        return []
    if state.last_capture_elapsed is not None:
        # ROS 게임 시간과 실제 새 관측 구간 중 작은 값만 인정한다.
        # RESUME 직후 첫 관측에는 일시정지 전후 간격을 더하지 않는다.
        # 나노초 정수로 누적해 0.1초 표본 20개가 2초보다 작아지는 오차를 막는다.
        delta_ns = min(round(state.elapsed_s * 1e9) - round(state.last_capture_elapsed * 1e9),
                       observation.stamp_ns - state.last_capture_stamp)
        state.hold_s = (round(state.hold_s * 1e9) + max(0, delta_ns)) / 1e9
    state.last_capture_elapsed = state.elapsed_s
    state.last_capture_stamp = observation.stamp_ns
    if state.hold_s >= capture['hold_s']:
        state.hp = max(0, state.hp - capture['damage_hp'])
        state.cooldown_until_s = state.elapsed_s + capture['cooldown_s']
        break_capture(state)
        return [Event('HIT', state.hp, reason='잡힘 조건 지속')]
    return []


def terminal_result(level, state, position):
    """하트 소진, 제한시간 경계, 탈출의 동시 성립 우선순위를 적용한다."""
    failure = ('하트 소진' if state.hp == 0 else
               '제한시간 초과' if state.elapsed_s >= level['rules']['time_limit_s'] else '')
    zone = level['layout']['exit_zone']
    cleared = (len(state.collected) == len(level['layout']['candies'])
               and position is not None
               and all(math.isfinite(v) for v in position)
               and distance(position, zone['position']) <= zone['radius_m'])
    if failure and (not cleared or level['rules']['simultaneous_result_priority'] == 'failed'):
        return 'FAILED', failure
    if cleared:
        return 'CLEARED', '모든 사탕 획득 후 탈출'
    return '', ''


def evaluate(level, state, elapsed_s, position=None, observation=None):
    """사탕 → 피격 → 최종 결과 순서로 한 주기를 판정한다."""
    if state.outcome:
        return []
    if not math.isfinite(elapsed_s) or elapsed_s < state.elapsed_s:
        raise ValueError('경과시간은 유한하고 이전 값보다 작지 않아야 합니다')
    state.elapsed_s = elapsed_s
    events = collect_candies(level, state, position)
    events.extend(apply_capture(level, state, observation))
    state.outcome, state.reason = terminal_result(level, state, position)
    if state.outcome:
        events.append(Event(state.outcome, state.hp, reason=state.reason))
    return events
