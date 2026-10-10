3-3. msg/BooState.msg
목적: Boo가 현재 순찰 중인지, Pumpkin을 의심하는지, 추격 중인지 웹과 게임 관리자가 확인하도록 하는 메시지.

# ============================================================
# BooState.msg
# Boo 행동 상태 전달
# ============================================================

# [역할]
# Boo 로봇의 현재 행동 상태를 전달한다.
#
# Boo는 Nav2를 이용해 이동하는 AI 추격 로봇이다.
# 순찰, 의심, 추격, 탐색 등의 행동 상태를 가진다.
#
# BooState는 Boo의 행동을 외부에 알려주기 위한
# 메시지이며, 행동 전환의 판단은 boo_fsm.py가 담당한다.


# [포함할 정보]
# - header: 상태 시각 및 좌표계 정보
# - round_id: 현재 게임 회차 ID
# - behavior: Boo의 현재 행동 상태
# - target_visible: Pumpkin을 현재 감지하고 있는지
# - suspicion: 현재 의심도
# - goal_active: Nav2 이동 목표 활성화 여부
# - last_seen_valid: 마지막 감지 위치가 유효한지
# - last_seen_target: Pumpkin을 마지막으로 감지한 위치
# - reason: 현재 행동 상태의 이유


# [사용 관계]
# 발행 노드:
#   tob_control/boo_fsm.py
#
# 발행 토픽:
#   /tob/boo/state
#
# 구독하는 쪽:
#   1. backend/app/bridge/ros_bridge.py
#      - Boo 행동 상태를 웹으로 전달
#
#   2. tob_game/game_manager_node.py
#      - 필요한 경우 게임 진행과 연동
#
#   3. 웹 게임 화면
#      - 순찰/추격/탐색 상태 표시
#      - Boo 행동에 따른 시각적 효과
#
# 관련 노드:
#   tob_control/boo_controller_node.py
#   tob_control/nav2_client.py
#
# 예상 담당자:
#   은빈, 주은: Boo FSM 및 Nav2 연동
#   성은, 민서: Boo 행동 상태의 화면 표시


# [범위]
# Boo의 행동 상태를 전달한다.
#
# 실제 Nav2 경로 계산이나 이동 명령 자체는
# BooState에서 수행하지 않는다.
#
# Boo의 상태 전환은 boo_fsm.py에서 처리한다.
#
# Pumpkin 감지를 잃었다면 target_visible = false이다.
#
# 감지를 잃었더라도 마지막 위치가 유효하면
# last_seen_valid = true로 유지할 수 있다.
#
# 단, 감지가 끊긴 상태에서 마지막 감지 위치를
# 새로운 관측 위치인 것처럼 갱신하지 않는다.
#
# 탐색 실패 이후 순찰 복귀 등의 동작도
# FSM 내부에서 결정한다.


# [완료 기준]
# - 현재 Boo의 행동 상태를 구분할 수 있다.
# - Pumpkin 감지 여부를 확인할 수 있다.
# - Nav2 목표 활성 상태를 확인할 수 있다.
# - 마지막으로 감지한 목표 위치의 유효성을 확인할 수 있다.
# - 웹에서 Boo의 현재 행동을 표시할 수 있다.


# ------------------------------------------------------------
# Boo 행동 상태
# ------------------------------------------------------------

uint8 IDLE=0
uint8 PATROL=1
uint8 SUSPECT=2
uint8 CHASE=3
uint8 SEARCH=4

# ------------------------------------------------------------
# 실제 메시지 필드
# ------------------------------------------------------------

std_msgs/Header header
string round_id
uint8 behavior

# 최신 관측 기준으로 대상이 보이는지 표시한다.
bool target_visible

# 의심 정도는 0부터 1까지. 사용하지 않으면 0.
float32 suspicion
bool goal_active

# 마지막으로 본 위치. 유효하지 않으면 좌표를 사용하지 않는다.
bool last_seen_valid
geometry_msgs/PointStamped last_seen_target

string reason
