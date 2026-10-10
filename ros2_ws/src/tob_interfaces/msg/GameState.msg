
# ============================================================
# GameState.msg
# 게임 전체 상태 스냅샷
# ============================================================

# [역할]
# 현재 회차의 게임 상태를 한 번에 전달한다.
# 웹 화면과 다른 ROS 노드가 동일한 게임 상태를
# 확인할 수 있도록 하는 대표 메시지이다.
#
# 게임 진행 상태의 최종 결정권은 game_manager_node.py에 있다.


# [포함할 정보]
# - stamp: 상태가 갱신된 시각
# - round_id: 현재 게임 회차의 고유 식별자
# - level: 현재 진행 중인 레벨
# - phase: 준비, 진행, 일시정지, 성공, 실패 상태
# - elapsed_s: 게임 시작 후 경과 시간(초)
# - remaining_s: 남은 시간(초)
# - hp: 현재 체력
# - max_hp: 최대 체력
# - candy_total: 현재 레벨에서 획득해야 하는 전체 사탕 수
# - collected_candy_ids: 지금까지 획득한 사탕 ID 목록
# - exit_enabled: 탈출 가능 조건 충족 여부
# - reason: 종료 또는 상태 변경 사유


# [사용 관계]
# 발행 노드:
#   tob_game/game_manager_node.py
#
# 발행 토픽:
#   /tob/game/state
#
# 구독하는 쪽:
#   1. backend/app/bridge/ros_bridge.py
#      - 게임 상태를 웹에 전달
#
#   2. 웹 게임 화면
#      - ROS Bridge를 통해 간접 수신
#      - 체력, 사탕, 타이머, 레벨, 결과 표시
#
#   3. tob_control의 게임 연동 제어 노드
#      - 게임 시작/정지/종료 상태 확인
#
# 예상 담당자:
#   은빈, 주은: ROS 게임 상태 관리 및 연동
#   주은, 희성: 웹 백엔드 연동
#   성은, 민서: 웹 화면 표시


# [범위]
# 현재 시점의 게임 상태만 전달한다.
#
# 새로운 구독자가 이 메시지 하나만 받아도
# 현재 진행 중인 회차의 상태를 이해할 수 있어야 한다.
#
# 과거의 모든 이벤트를 저장하거나
# 재생하는 시스템은 구현하지 않는다.
#
# 사탕을 모두 획득하면 exit_enabled = true가 된다.
#
# exit_enabled = true인 상태에서 Pumpkin이
# 탈출존에 진입하면 즉시 CLEARED로 변경된다.
#
# 탈출문 대기시간, 문 열림 애니메이션 완료,
# 별도 탈출 대기 상태는 포함하지 않는다.
#
# 실제 사탕 획득 및 탈출 판정은 rules.py와
# game_manager_node.py에서 처리한다.


# [완료 기준]
# - 웹에서 현재 레벨과 회차를 확인할 수 있다.
# - 진행 상태, 남은 시간, 체력을 표시할 수 있다.
# - 획득한 사탕 목록과 탈출 가능 여부를 확인할 수 있다.
# - 게임 성공과 실패를 명확하게 구분할 수 있다.
# - 새 구독자가 현재 메시지만으로 상태를 복원할 수 있다.


uint8 READY=0
uint8 RUNNING=1
uint8 PAUSED=2
uint8 CLEARED=3
uint8 FAILED=4

# 상태를 작성한 시각.
builtin_interfaces/Time stamp
string round_id
uint32 level
uint8 phase

# 일시정지를 제외한 진행시간과 남은 시간. 단위는 초.
float32 elapsed_s
float32 remaining_s

# 현재 하트와 최대 하트. 최대값은 레벨 설정에서 정한다.
uint16 hp
uint16 max_hp

# 전체 사탕 수와 획득한 사탕 식별자 목록.
uint32 candy_total
string[] collected_candy_ids

# 사탕을 모두 모아 탈출할 수 있는 상태인지 표시한다.
bool exit_enabled

# 실패 사유. 사유가 없으면 빈 문자열.
string reason
