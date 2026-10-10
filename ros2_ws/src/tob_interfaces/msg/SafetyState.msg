
# ============================================================
# SafetyState.msg
# 로봇 이동 안전 상태 전달
# ============================================================

# [역할]
# 각 로봇의 이동 허용 여부를 전달한다.
#
# 안전 감시 노드가 판단한 결과를
# 실제 속도 명령을 처리하는 노드에 전달한다.
#
# 게임 로직과 독립적으로 이동 안전 조건을 관리한다.


# [포함할 정보]
# - header: 안전 상태가 판단된 시각
# - robot_id: 안전 상태의 대상 로봇
# - motion_allowed: 이동 허용 여부
# - reason: 이동 허용 또는 차단 사유
# - valid_for_s: 해당 안전 판단의 유효 시간(초)


# [사용 관계]
# 발행 노드:
#   tob_safety/safety_supervisor_node.py
#
# 발행 토픽:
#   /tob/pumpkin/safety
#   /tob/boo/safety
#
# 구독하는 쪽:
#   1. tob_safety/velocity_gate_node.py
#      - 실제 속도 명령의 통과/차단 결정
#
#   2. tob_control/pumpkin_controller_node.py
#      - Pumpkin 제어 상태 확인
#
#   3. tob_control/boo_controller_node.py
#      - Boo 이동 제어 상태 확인
#
#   4. tob_game/game_manager_node.py
#      - 필요시 안전 상태를 게임 진행에 반영
#
# 예상 담당자:
#   은빈, 주은: 안전 감시 및 로봇 제어 연동


# [범위]
# 게임 규칙과 별도로 로봇의 이동 안전을 판단한다.
#
# Pumpkin과 Boo는 각각 독립적인 안전 상태를 가진다.
#
# motion_allowed = true이면
# 해당 안전 판단에 따라 이동을 허용할 수 있다.
#
# motion_allowed = false이면
# velocity_gate_node.py에서 이동 명령을 차단한다.
#
# 안전 상태 메시지가 오래되어 valid_for_s를
# 초과했다면 유효한 이동 허가로 취급하지 않는다.
#
# ROS 통신 오류나 안전 감시 노드 중단 시에도
# 이전에 받은 이동 허가를 무기한 유지하지 않는다.
#
# 이 메시지는 안전 판단 결과를 전달하는 용도이며,
# 실제 이동 명령 차단 로직은 별도로 구현한다.


# [완료 기준]
# - Pumpkin과 Boo의 안전 상태를 구분할 수 있다.
# - 이동 허용/차단 결과를 전달할 수 있다.
# - 이동 차단 사유를 확인할 수 있다.
# - 오래된 안전 상태를 무효 처리할 수 있다.
# - velocity_gate가 안전하지 않은 이동을 차단할 수 있다.


# ------------------------------------------------------------
# 실제 메시지 필드
# ------------------------------------------------------------

std_msgs/Header header
string robot_id
bool motion_allowed
string reason

# 작성 시각부터 허용되는 기간. 단위는 초.
# 수신자는 자체 설정의 최대 허용기간도 적용한다.
float32 valid_for_s
