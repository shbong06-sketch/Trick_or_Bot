# [역할]
# 부 제어 노드가 결정한 현재 행동 상태를 전달한다.
#
# [포함할 정보]
# 회차 식별자, 행동 상태, 대상 가시 여부, 의심 정도,
# 이동 목표 진행 여부, 마지막 관측 위치와 사유를 포함한다.
#
# [사용 관계]
# 부 제어 노드가 발행하고 게임 관리 노드와 웹 연결부가 사용한다.
# 행동 상태의 전환은 부의 상태 관리 코드가 담당한다.
#
# [범위]
# 순찰·의심·추격·탐색·대기 상태를 표현한다.
# 의심 기능을 사용하지 않으면 의심 정도는 0으로 둔다.
# 감지 상실 후 마지막 관측 위치를 숨은 대상의 현재 위치로 갱신하지 않는다.
# 최종 잡힘 판정이나 안전 이동 허용을 대신하지 않는다.
# 레벨 1의 자동 복귀 기능은 포함하지 않는다.
#
# [완료 기준]
# 화면과 게임 관리 노드가 부의 현재 행동을 구분할 수 있다.
# 마지막 관측 위치의 유효 여부를 구분할 수 있다.

# 부 제어 노드가 결정한 행동 상태.
uint8 IDLE=0
uint8 PATROL=1
uint8 SUSPECT=2
uint8 CHASE=3
uint8 SEARCH=4

# 상태 작성 시각. 좌표계 이름은 비운다.
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
