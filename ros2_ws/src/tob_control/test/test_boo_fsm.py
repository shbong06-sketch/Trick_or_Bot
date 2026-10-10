"""boo_fsm 시나리오 시험(ROS 없이 실행)."""

from tob_control.boo_fsm import Behavior, BooFsm, CmdKind, FsmConfig

PATROL = [(1.0, 0.0), (2.0, 0.0)]
SEEN = (3.0, 1.0)


def make(**kw):
    fsm = BooFsm(FsmConfig(**kw), PATROL)
    fsm.set_enabled(True)
    return fsm


def run(fsm, seconds, seen, dt=0.1):
    cmd = None
    for _ in range(round(seconds / dt)):
        cmd = fsm.step(dt, seen)
    return cmd


def test_idle_until_enabled():
    fsm = BooFsm(FsmConfig(), PATROL)
    assert fsm.step(0.1, None).kind == CmdKind.NONE
    assert fsm.behavior == Behavior.IDLE


def test_patrol_goes_to_first_point_then_next_after_arrival():
    fsm = make()
    cmd = fsm.step(0.1, None)
    assert fsm.behavior == Behavior.PATROL
    assert (cmd.kind, cmd.target) == (CmdKind.GOTO, PATROL[0])
    fsm.on_nav_result(success=True)
    assert fsm.step(0.1, None).target == PATROL[1]
    fsm.on_nav_result(success=True)
    assert fsm.step(0.1, None).target == PATROL[0]


def test_seen_makes_suspect_and_stops():
    fsm = make()
    cmd = fsm.step(0.1, SEEN)
    assert fsm.behavior == Behavior.SUSPECT
    assert cmd.kind == CmdKind.STOP


def test_suspicion_fills_to_chase_in_fill_time():
    fsm = make(suspicion_fill_s=3.0)
    run(fsm, 2.5, SEEN)
    assert fsm.behavior == Behavior.SUSPECT
    assert 0.7 < fsm.suspicion < 0.95
    cmd = run(fsm, 0.7, SEEN)
    assert fsm.behavior == Behavior.CHASE
    assert cmd.kind == CmdKind.GOTO and cmd.target == SEEN


def test_suspicion_decays_back_to_patrol():
    fsm = make(suspicion_fill_s=3.0, suspicion_decay_s=2.0)
    run(fsm, 1.5, SEEN)
    assert fsm.behavior == Behavior.SUSPECT
    run(fsm, 2.5, None)
    assert fsm.behavior == Behavior.PATROL
    assert fsm.suspicion == 0.0


def test_chase_follows_latest_seen_position():
    fsm = make(suspicion_fill_s=0.5)
    run(fsm, 0.8, SEEN)
    assert fsm.behavior == Behavior.CHASE
    cmd = fsm.step(0.1, (4.0, 1.0))
    assert cmd.kind == CmdKind.GOTO and cmd.target == (4.0, 1.0)


def test_lost_goes_search_to_last_seen_then_patrol_lv1():
    fsm = make(suspicion_fill_s=0.5, lost_timeout_s=1.0, search_hold_s=0.0)
    run(fsm, 0.8, SEEN)
    cmd = run(fsm, 1.2, None)
    assert fsm.behavior == Behavior.SEARCH
    assert cmd.kind in (CmdKind.GOTO, CmdKind.NONE)
    fsm.on_nav_result(success=True)
    fsm.step(0.1, None)
    assert fsm.behavior == Behavior.PATROL
    assert fsm.last_seen == SEEN   # 기억은 남아도 새 관측으로 쓰지 않는다


def test_search_hold_waits_after_arrival():
    fsm = make(suspicion_fill_s=0.5, lost_timeout_s=0.5, search_hold_s=1.0)
    run(fsm, 0.8, SEEN)
    run(fsm, 0.8, None)
    assert fsm.behavior == Behavior.SEARCH
    fsm.on_nav_result(success=True)
    run(fsm, 0.5, None)
    assert fsm.behavior == Behavior.SEARCH
    run(fsm, 0.7, None)
    assert fsm.behavior == Behavior.PATROL


def test_search_reacquire_returns_to_chase():
    fsm = make(suspicion_fill_s=0.5, lost_timeout_s=0.5)
    run(fsm, 0.8, SEEN)
    run(fsm, 0.8, None)
    assert fsm.behavior == Behavior.SEARCH
    fsm.step(0.1, (5.0, 5.0))
    assert fsm.behavior == Behavior.CHASE


def test_search_timeout_returns_to_patrol():
    fsm = make(suspicion_fill_s=0.5, lost_timeout_s=0.5, search_timeout_s=3.0)
    run(fsm, 0.8, SEEN)
    run(fsm, 0.8, None)
    run(fsm, 3.5, None)
    assert fsm.behavior == Behavior.PATROL


def test_patrol_failure_is_not_arrival_and_stops_after_limit():
    fsm = make(max_goal_failures=2)
    fsm.step(0.1, None)
    fsm.on_nav_result(success=False)
    fsm.on_nav_result(success=False)
    cmd = fsm.step(0.1, None)
    assert cmd.kind == CmdKind.STOP


def test_patrol_success_resets_failures():
    fsm = make(max_goal_failures=2)
    fsm.step(0.1, None)
    fsm.on_nav_result(success=False)
    fsm.on_nav_result(success=True)
    fsm.on_nav_result(success=False)
    assert fsm.step(0.1, None).kind == CmdKind.GOTO


def test_disable_returns_idle_and_clears_memory():
    fsm = make(suspicion_fill_s=0.5)
    run(fsm, 0.8, SEEN)
    assert fsm.behavior == Behavior.CHASE
    fsm.set_enabled(False)
    assert fsm.behavior == Behavior.IDLE
    assert fsm.last_seen is None and fsm.suspicion == 0.0
    assert fsm.step(0.1, SEEN).kind == CmdKind.NONE


def test_canceled_result_is_ignored():
    fsm = make()
    fsm.step(0.1, None)
    fsm.on_nav_result(success=False, canceled=True)
    assert fsm.step(0.1, None).target == PATROL[0]
