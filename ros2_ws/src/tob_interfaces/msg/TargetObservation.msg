# ============================================================
# TargetObservation.msg
# Pumpkin 감지 및 목표 위치 정보
# ============================================================

# [역할]
# 카메라에서 감지한 Pumpkin의 정보를
# Boo 추격 제어 노드에 전달한다.
#
# YOLO 감지 결과와 지도 좌표 변환 결과를 포함한다.
#
# Boo FSM이 추격 여부와 추격 목표를 결정할 때
# 사용할 수 있는 공통 관측 메시지이다.


# [포함할 정보]
# - header: 관측 시각 및 좌표계 정보
# - source: 관측 정보를 생성한 카메라 또는 소스
# - detected: Pumpkin 감지 여부
# - confidence: 감지 신뢰도
#
# - bbox_center_x: 바운딩 박스 중심 X
# - bbox_center_y: 바운딩 박스 중심 Y
# - bbox_width: 바운딩 박스 너비
# - bbox_height: 바운딩 박스 높이
#
# 바운딩 박스 값은 이미지 크기로 정규화한
# 0~1 범위의 좌표를 사용한다.
#
# - map_valid: 지도 좌표 추정 성공 여부
# - target_position: 지도 좌표계에서의 Pumpkin 위치
# - distance_m: 추정된 목표까지의 거리(m)


# [사용 관계]
# 입력 측:
#   tob_perception/boo_detector_node.py
#   tob_perception/detector.py
#
# 입력 토픽:
#   /tob/perception/pumpkin_detection
#
# 최종 발행 노드:
#   tob_localization/target_localizer_node.py
#
# 발행 토픽:
#   /tob/target/observation
#
# 구독하는 쪽:
#   1. tob_control/boo_fsm.py
#      - Pumpkin 감지 여부 확인
#      - 추격 또는 탐색 상태 결정
#
#   2. tob_game/game_manager_node.py
#      - 게임 판정에 필요한 관측 정보 사용
#
#   3. 디버깅 및 시각화 노드
#      - 감지 결과와 지도 위치 확인
#
# 예상 담당자:
#   승현, 원호: YOLO 감지 및 위치 추정
#   은빈, 주은: Boo FSM과 관측 정보 연동


# [범위]
# Pumpkin의 관측 결과만 전달한다.
#
# Boo의 추격 여부나 Nav2 이동 명령을
# 이 메시지에서 결정하지 않는다.
#
# detected = false이면 현재 감지된 대상이 없다는 뜻이다.
#
# map_valid = false이면 target_position을
# 유효한 지도 좌표로 사용해서는 안 된다.
#
# map_valid = true일 때 target_position의
# frame_id는 map으로 설정한다.
#
# 감지가 실패했다고 해서 과거 목표 위치를
# 현재 위치로 새롭게 발행해서는 안 된다.
#
# 마지막 위치 보관 및 감지 상실 후 행동 결정은
# boo_fsm.py에서 담당한다.
#
# 원본 이미지의 촬영 시각을 유지하여
# 오래된 관측 정보를 구분할 수 있도록 한다.


# [완료 기준]
# - Pumpkin 감지 여부를 전달할 수 있다.
# - 감지 신뢰도와 바운딩 박스 정보를 전달할 수 있다.
# - 지도 좌표가 유효한지 구분할 수 있다.
# - Boo FSM이 지도 좌표를 받아 추격 판단에 사용할 수 있다.
# - 감지 실패 시 잘못된 목표를 추격하지 않는다.
# - 관측 정보의 시각을 확인할 수 있다.


# ------------------------------------------------------------
# 실제 메시지 필드
# ------------------------------------------------------------

std_msgs/Header header
string source

# 감지되지 않았으면 신뢰도와 박스 값을 사용하지 않는다.
bool detected
float32 confidence

# 원본 영상 기준으로 정규화한 박스. 값의 범위는 0부터 1까지.
float32 bbox_center_x
float32 bbox_center_y
float32 bbox_width
float32 bbox_height

# 감지와 두 로봇 위치가 모두 유효할 때만 참으로 설정한다.
# 거짓이면 아래 위치와 거리를 사용하지 않는다.
bool map_valid

# 지도 기준 펌킨 위치. 사용한 위치 샘플의 시각을 유지한다.
geometry_msgs/PointStamped target_position

# 두 로봇 위치 기준점 사이의 평면 거리. 단위는 미터.
float32 distance_m
