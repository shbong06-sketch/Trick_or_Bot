# tob_game — Level 1 게임 관리자

게임 규칙의 최종 판정자는 `game_manager`이다. 웹은 `GameState`로 상태를 표시하고
`GameCommand`로 명령을 요청한다. 이 패키지는 Nav2·속도 명령·위치추정·자동 복귀를
실행하지 않는다. 작업 기준 브랜치는 `development`이며 작업 시작 시 변경 사항은 없었다.
적용되는 `AGENTS.md`, 루트의 `PROJECT_CONTEXT.md`, `GAME_RULES.md`,
`LEVEL1_INTERFACES.md`는 없었다. `docs/interfaces.md`와 실제 `.msg`/`.srv`,
사용자의 최신 Level 1 범위를 적용했다.

**구현 파일과 역할**

| 파일 | 구현 내용 |
|---|---|
| `tob_game/level_loader.py` | `yaml.safe_load`, 필수·null·자료형·유한값·양수·uint16/uint32·중복 ID·레벨·우선순위 검증. 오류에 파일·키 포함 |
| `tob_game/rules.py` | ROS와 실제 시계 없이 거리, 사탕, 관측 기반 잡힘, 쿨다운, 탈출·실패 판정 |
| `tob_game/game_manager_node.py` | 입력 검증, 명령 전환, 시간 관리, 상태·이벤트 발행, 종료 기록 |
| `tob_game/round_logger.py` | 회차 ID별 한 번의 JSONL 기록 시도. 실패를 보고하고 결과 유지 |
| `config/levels/level1.yaml` | 기존 규칙과 사용자 승인으로 복사한 백엔드 배치 |
| `config/game_manager.yaml` | 난이도와 분리한 ROS 운영 파라미터 |
| `launch/game_manager.launch.py` | 게임 관리자 하나만 실행 |
| `setup.py`, `package.xml` | 실행 진입점·설정·launch 설치와 실제 의존성 |
| `test/` | 별도 가상 레벨, 순수 Python 규칙, 노드 콜백, 실제 DDS 서비스·토픽 시험 |

**백엔드에서 복사한 데이터**

2026-10-11 사용자가 `backend/config` 값을 복사하도록 지시했다.
`backend/config/level1.yaml` 원본은 수정하지 않고 아래 값을
`config/levels/level1.yaml`의 구조에 맞춰 복사했다. 데이터 이전과 단일 원본 연결은 후속 작업이다.
테스트용 좌표로 운영 레벨을 덮어쓰지 않았다.

| 원본 → 대상 | 현재 값 |
|---|---|
| `lv`, `name` → `level`, `name` | 1, 첫 번째 밤 |
| `time_limit_s`, `hearts` → `rules.time_limit_s`, `rules.initial_hp` | 240초, 3 |
| `pick_radius_m` → `rules.candy.pickup_radius_m` | 0.3m |
| `pumpkin_start` → `layout.start_poses.pumpkin` | x=-0.7, y=3.0, yaw_rad=1.57 |
| `boo_start` → `layout.start_poses.boo` | x=-3.5, y=-1.85, yaw_rad=0.0 |
| `candies` → `layout.candies` | c1=(-3.55, 3.22), c2=(-1.0, 0.0), c3=(-2.47, -1.75) |
| `gate.x/y` → `layout.exit_zone.position` | (-4.5, -1.8) |
| `gate_enter_r` → `layout.exit_zone.radius_m` | 0.3m. 기존 null을 사용자 지시에 따라 교체 |

`gate_dwell_s`, `gate_front_m`, `gate_zone_r`, 문 방향, 영상·카메라·순찰 설정은
게임 규칙으로 복사하지 않았다. 잡힘 거리 0.5m·지속 2초·피해 1·쿨다운 3초와
동시 판정 시 `failed` 우선은 백엔드에 없는 기존 ROS 레벨의 제안값이었으며,
2026-10-11 사용자가 운영 규칙으로 확정했다. 현재 레벨의 필수 미정·null 값은 없다.
실제 Boo 영상 frame_id와 지연·유효기간 등 노드 운영 설정은 현장에서 확인해야 한다.
좌표 복사는 실물에서 위치나 지도 정렬을 확인했다는 뜻이 아니다.

**적용 규칙과 경계**

- 판정 순서는 사탕 획득 → 피격 → 최종 결과이다. 반경과 잡힘 거리의 경계는 `<=`,
  잡힘 지속시간과 제한시간의 경계는 `>=`이다. 하트 소진과 시간 초과가 함께이면
  실패 사유는 `하트 소진`이다. 성공·실패 동시 성립에는 레벨의 `failed`/`cleared` 우선순위를 적용한다.
- 사탕 ID당 회차에서 한 번 획득한다. 마지막 사탕을 얻은 주기에 탈출존 안이면 즉시 성공한다.
  문 열림·대기·재진입 조건은 없다.
- 잡힘은 허용 출처의 새 관측, `detected`, `map_valid`, 유효한 원본·결합 위치 시각,
  지도 좌표와 거리로 판정한다. Boo의 CHASE·suspicion이나 실제 두 위치만으로 잡힘을 추가하지 않는다.
- 새 관측의 원본 시간 간격과 실제 RUNNING 시간 간격 중 작은 값만 누적한다.
  같은 관측의 타이머 재사용은 누적과 반복 피격을 만들지 않는다. 나노초로 합산한다.
  관측 단절·만료·무효·거리 초과는 잡힘 누적을 지운다.
- 피해 이후 하트는 0 이상으로 제한한다. 누적을 지우고 쿨다운이 끝난 뒤 새 관측부터
  `hold_s`를 다시 채운다. 쿨다운 중 들어온 관측은 이후 누적의 시작점으로 재사용하지 않는다.
- PAUSED에서는 게임 시간·잡힘 누적·쿨다운을 동결하고 모든 게임 판정을 중단한다.
  재개 전후 시간 간격은 잡힘에 더하지 않는다. 재개 후 새 관측을 기다리는 동안 보존하되,
  아래 관측·수신 만료시간을 넘기면 이전 누적을 지운다.
- 종료 이후 하트·사탕·경과시간·최종 결과는 동결한다. 종료 사건과 JSONL 기록은 한 번이다.
  RESET은 결과 사건이나 결과 로그를 만들지 않는다.

**명령 계약**

| 요청 | 조건 및 처리 |
|---|---|
| START=0 | READY·CLEARED·FAILED, `level=1`, `round_id=''`. 설정 재로딩과 두 로봇 위치·안전 허가 검증 후 UUID 생성. 이전 관측·누적·쿨다운·결과 초기화 |
| PAUSE=1 | RUNNING, 현재 round_id 일치. 명령 시각까지 게임 시간만 반영하고 PAUSED. 서비스에서는 사탕·피격·승패를 새로 판정하지 않음 |
| RESUME=2 | PAUSED, 현재 round_id 일치. 두 위치·안전 허가 재검사. 새 관측과 결합 위치 모두 재개 시각 이후여야 함 |
| RESET=3 | 회차가 남아 있으면 종료 상태를 포함해 현재 round_id 일치. READY·빈 ID·빈 회차 데이터로 초기화. 회차가 없으면 빈 ID |

서비스 주석의 `level`은 START에만 사용하므로 나머지 요청에서는 무시한다.
최초 및 종료 후 새 START 모두 빈 `round_id`를 요구하는 것으로 해석했다.
RUNNING·PAUSED의 START는 회차를 덮어쓰지 않는다. 거절 응답은 회차를 변경하지 않으며
현재 phase·round_id와 구체적인 이유를 반환한다. 수락·거절 모두 상태를 즉시 발행한다.
PAUSE 직전에 제한시간에 도달해도 명령 자체는 판정하지 않으므로 재개 후 첫 판정에서 처리한다.

`accepted=true`는 실제 로봇 정지 완료를 뜻하지 않는다. PAUSE·RESET·종료 상태를 받은
제어 계층이 Nav2 취소·속도 차단·오래된 명령 폐기를 수행해야 한다.

**추가한 운영 정책과 초기 파라미터**

아래 값은 실측값이 아닌 초기 구현값이다. 실행할 때 ROS 파라미터로 지정하며,
노드 실행 중에는 읽기 전용이다. 레벨은 START마다 다시 읽고 진행 회차는 스냅샷을 유지한다.

| 파라미터 | 기본값 | 용도 |
|---|---|---|
| `tick_period_s` | 0.05초 | 판정 주기 |
| `state_period_s` | 0.1초 | 모든 phase의 GameState 주기 발행 |
| `pose_timeout_s` | 0.5초 | 위치 및 결합 목표 위치의 원본 시각 최신성 |
| `observation_timeout_s` | 0.5초 | 관측 원본 시각 최신성·재개 관측 대기 상한 |
| `receive_timeout_s` | 0.5초 | 단조 시계로 검사하는 수신 중단 |
| `future_tolerance_s` | 0.05초 | 원본 미래 시각 허용 범위 |
| `observation_position_skew_s` | 0.2초 | 관측과 결합 위치의 원본 시각 차이 |
| `safety_max_valid_for_s` | 1.0초 | 안전 허가 기간 상한 |
| `max_clock_step_s` | 1.0초 | 연속 콜백에서 허용하는 ROS 시계 도약 |
| `observation_sources` | `[boo_camera]` | 허용된 출처 |
| `observation_frame_ids` | `[camera_optical_frame]` | 원본 영상 좌표계의 초기 자리표시 값. 실제 Boo 영상 frame_id로 지정 필요 |
| `level_path` | `levels/level1.yaml` | 설치된 `share/tob_game/config/game_manager.yaml`의 부모 기준 |
| `result_log_path` | `~/.local/state/tob_game/rounds.jsonl` | 운영 JSONL. 확장 후 절대 경로 필요 |

- 게임 시간은 ROS clock을 사용한다. `use_sim_time`을 지원한다. 원본 메시지 stamp를
  현재 시각으로 바꾸지 않는다. 영 시각, 과도한 미래 시각, 빈·다른 좌표계,
  NaN/무한 좌표·음수/비유한 거리를 판정에서 제외한다.
- 수신 중단 검사는 `time.monotonic()`이다. 판정·상태 타이머는 STEADY_TIME이므로
  `/clock`이 멈춰도 상태 발행·입력 만료 검사를 계속한다. 게임 시간은 진행하지 않는다.
- 채택한 원본 stamp의 최댓값을 토픽별로 보존한다. 중복·역순 입력은 수신 시간을 갱신하지 않는다.
  더 새로운 무효 관측을 받으면 타이머 사이에서도 잡힘 연속성을 끊는다.
- SafetyState는 토픽과 `robot_id` 일치, 이동 허가, 유한한 양수·상한 이하 `valid_for_s`,
  원본 시각과 단조 수신 경과시간을 모두 확인한다. 안전 header에 좌표계는 요구하지 않는다.
- START·RESUME에는 두 로봇의 위치와 안전 허가를 요구한다. BooState로 확인할 준비 조건은
  정의되어 있지 않아 구독하지 않는다. 설정 시작점과 실제 로봇 위치의 일치·Nav2 준비 여부는
  이 메시지들로 보장하지 않으며, 로봇 이동·AMCL 초기화를 실행하지 않는다.
- RUNNING 중 위치·관측이 무효이면 그 입력을 쓰는 판정만 중단한다. 게임 시간은 계속 간다.
  안전 차단만으로 자동 PAUSED·FAILED를 만들거나 자동 재개하지 않는다.
- ROS 시계 역행 또는 상한을 넘는 도약은 그 구간을 게임 시간에 더하지 않는다.
  입력·원본 시각 기준·잡힘 누적을 지우고 새 시간축의 새 입력을 기다린다.
  기존 게임 시간과 남은 쿨다운은 보존한다. 자동 상태 전환은 없다.
  이 정책은 실제 장시간 executor 중단도 제외할 수 있으므로 운영 시 부하와 상한을 검토해야 한다.
- `load_level(relative_path, config_file=absolute_path)`는 전달한 설정 파일의 부모를 사용한다.
  ROS가 원본 파라미터 YAML 경로를 노드에 제공하지 않으므로, 노드의 상대 경로 기준은 위의
  설치된 기본 설정 파일로 고정했다. 외부 YAML/launch에서는 절대 `level_path`를 사용한다.
  현재 레벨 스키마에는 지도 파일 경로가 없으며 게임 매니저는 지도 파일을 열거나 변환하지 않는다.
- 결과는 `round_id`, `level`, `ended_at_ros_ns`, 최종 phase·reason·elapsed_s·hp·획득 ID만 기록한다.
  종료 시각은 ROS 시간축의 나노초이며 벽시계 날짜로 꾸미지 않는다. 동일 프로세스에서 회차별
  한 번만 기록을 시도한다. 새 회차는 새 UUID를 사용한다. 실패 시 로그를 남기며 재시도·종료 사건
  반복·결과 변경을 하지 않는다. 프로세스 재시작 후 진행 회차 복구 기능은 없다.
  기본 경로는 소스 밖이고 알려진 패키지 소스·설치 경로에는 저장을 거절한다.

**현재 코드와 문서의 충돌, 담당자 연결 작업**

보호 영역은 수정하지 않았다. 아래 작업이 끝나기 전에는 패키지 테스트 통과를 실물 운용 완료로
해석하지 않는다.

| 파일·담당 | 현재 상태·충돌 | 필요한 연결과 이유 |
|---|---|---|
| `docs/interfaces.md` 담당 표 및 기존 메시지 주석 | 이전 담당 구분 | 최신 담당은 주은: Pumpkin 제어, 원호: Boo FSM·Nav2, 게임 매니저 담당: 규칙·결과 |
| `tob_localization/.../robot_pose_node.py` | 실제 발행 코드 없이 지침 주석만 있음 | 두 `/tob/{pumpkin,boo}/pose`에 유효한 원본 stamp·지도 위치 발행. 실패 시 원점/새 시각으로 위장하지 않기 |
| `tob_localization/.../target_localizer_node.py` | 깊이 영상 기반 위치 계산 지침이며 Level 1 문서의 두 지도 위치 기반 거리와 충돌 | 인식·위치 담당자가 Level 1 방식으로 출처·감지·map_valid·목표 원본 시각·거리를 연결 |
| `tob_control/.../boo_controller_node.py`, `boo_fsm.py`, `config/control.yaml` — 원호 | 주석만 있으며 GameState 구독, 만료시간, 회차 초기화, 실제 QoS 없음 | GameState RUNNING에서만 허용, PAUSE·RESET·종료·만료 시 Nav2 취소. 새 round_id와 READY에서 이전 관측·FSM/목표 상태 정리. 0.1초 발행 주기보다 여유 있는 만료시간 합의 |
| `tob_control/.../pumpkin_controller_node.py` — 주은 | 게임 상태와 실제 정지의 연결 검증이 필요 | PAUSE·READY·종료·상태 만료 및 안전 차단에서 속도 요청 중지·오래된 키 입력 폐기 |
| `tob_safety` | 안전·속도 차단 기능은 이 작업 범위 밖 | 두 SafetyState를 지정한 ID·기간·원본 시각으로 발행. 실제 차단·안전 메시지 만료·종료 연동 검증 |
| `backend/app/levels.py`, `backend/config/level1.yaml` — 웹 | 여전히 `lv`, `hearts`, 평면 candies, gate 등의 별도 파일을 사용 | 공통 레벨 경로를 읽고 위 키 대응표로 웹 형식 변환. 복사본이 서로 달라지지 않게 이후 단일 원본으로 이전 |
| `backend/app/bridge/ros_bridge.py` — 웹 | TF·영상·속도 기능은 있으나 GameState/GameEvent 구독·GameCommand 클라이언트 없음 | 세 게임 인터페이스 연결. 명령 응답의 거절 이유·round_id·phase를 UI에 전달 |
| `backend/app/game.py` — 웹 | 자체 사탕·하트·시간·문 대기·성공 판정 | 실제 로봇 모드에서는 ROS 상태로 대체. `gate_dwell_s`/문 열림 규칙 제거. mock 게임이 실제 회차를 덮어쓰지 않게 구분 |
| `backend/tools/pick_candies.py` — 배치 도구 담당 | 기존 백엔드 레벨 구조를 대상으로 함 | 향후 공통 레벨의 `layout.candies`·`layout.exit_zone`을 갱신하도록 변경 |
| `tob_bringup/launch/game.launch.py` | 실행 구현 없이 지침 주석만 있음 | 이 패키지의 단독 launch 재사용 여부를 통합 담당자가 결정 |

상태·위치·관측·안전 QoS는 RELIABLE / VOLATILE / KEEP_LAST / depth=1,
사건은 같은 정책의 depth=10이다. 문서 권장값을 적용했으며 기존 실물 발행·구독 노드가
미구현이라 실제 상대와 호환되었다고 보고할 수 없다. DDS 시험에서는 같은 계약의 별도 노드와 연결했다.

Boo 지도는 `backend/maps/holloween_boo.yaml`(origin `[-4.859, -4.126, 0]`),
Pumpkin 지도는 `backend/maps/holloween_pumpkin.yaml`(origin `[-5.015, -2.364, 0]`)이며
서로 다른 파일을 유지했다. 두 `frame_id=map`이나 YAML origin 차이만으로 물리적 정렬을
판정하거나 좌표 변환을 생성하지 않았다. 공통 기준점·방향·로봇 위치 기준 프레임과 시계 동기화는
운영 전에 확인해야 한다. 이 확인 전에는 관측의 로봇 간 거리 정확성을 보장하지 않는다.

**빌드·실행·명령 확인**

```bash
cd /home/may/trick_or_bot/Trick_or_Bot/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select tob_interfaces tob_game
source install/setup.bash

# 게임 매니저만 실행한다. 기본 레벨은 설치된 share의 파일이다.
ros2 run tob_game game_manager

# 위 실행 대신 launch를 사용할 수도 있다. 다른 제어 노드는 시작하지 않는다.
ros2 launch tob_game game_manager.launch.py use_sim_time:=false

# 별도 레벨은 절대 경로로 지정한다.
# ros2 launch tob_game game_manager.launch.py level_path:=/절대경로/level1.yaml
# ros2 run tob_game game_manager --ros-args -p level_path:=/절대경로/level1.yaml
```

설정이 유효해도 두 로봇 위치·안전 입력이 없으면 START를 거절한다.
게임 테스트만 할 때는 아래 pytest의 가상 발행자를 사용한다. 실제 로봇용 안전 허가를 임의로 만들지 않는다.
다른 터미널에서 동일한 workspace 환경을 읽은 뒤 확인한다.

```bash
ros2 topic echo /tob/game/state
ros2 topic echo /tob/game/event
ros2 topic info -v /tob/game/state
ros2 service call /tob/game/command tob_interfaces/srv/GameCommand \
  "{command: 0, level: 1, round_id: ''}"

# START 응답 또는 GameState에서 받은 실제 ID로 교체한다.
TOB_ROUND_ID='응답의-round_id'
ros2 service call /tob/game/command tob_interfaces/srv/GameCommand \
  "{command: 1, level: 0, round_id: '${TOB_ROUND_ID}'}"
ros2 service call /tob/game/command tob_interfaces/srv/GameCommand \
  "{command: 2, level: 0, round_id: '${TOB_ROUND_ID}'}"
ros2 service call /tob/game/command tob_interfaces/srv/GameCommand \
  "{command: 3, level: 0, round_id: '${TOB_ROUND_ID}'}"
```

**검증 명령과 범위**

ROS 없는 순수 Python 시험은 Python 3.10 이상, PyYAML, pytest만 필요하다.

```bash
cd /home/may/trick_or_bot/Trick_or_Bot
PYTHONPATH=ros2_ws/src/tob_game python3 -m pytest -q \
  ros2_ws/src/tob_game/test/test_level_loader.py \
  ros2_ws/src/tob_game/test/test_rules.py \
  ros2_ws/src/tob_game/test/test_round_logger.py
```

전체 ROS 시험은 인터페이스와 패키지를 빌드한 뒤 실행한다. 실제 로봇과 분리된 ROS 도메인을 쓴다.

```bash
cd /home/may/trick_or_bot/Trick_or_Bot/ros2_ws
source install/setup.bash
export ROS_DOMAIN_ID=173
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_LOG_DIR=/tmp/tob-game-ros-log
unset ROS_DISCOVERY_SERVER ROS_SUPER_CLIENT
colcon test --packages-select tob_game --event-handlers console_direct+
colcon test-result --verbose
```

이번 작업에서는 기존 build/install과 분리한 `/tmp/tob-game-build`, `/tmp/tob-game-install`,
`/tmp/tob-game-colcon-log`에서 빌드했다. `colcon test` 결과는 **97개 통과, 기존 저작권 검사
1개 생략, 오류·실패 0개**이다. 린터 실행의 fork 관련 환경 경고 16개는 있었으나 검사는 통과했다.
실제 Jazzy 생성 메시지를 사용한 명령·입력 검증과,
별도 노드의 DDS 서비스·토픽 및 `/clock` 시험을 수행했다.
추가로 설치된 launch를 별도 프로세스로 실행하고 로컬 도메인 174에서
START·PAUSE·시간 동결·RESUME·두 사탕 획득·CLEARED·결과 한 번 기록·RESET 및
정상 종료를 확인했다. 이 시험은 샌드박스 UDP 제한 밖에서, 기존 외부 discovery 서버 설정을
제거하고 LOCALHOST 범위로 수행했다. 실제 로봇 제어 노드는 실행하지 않았다.
기존 저작권 템플릿 검사는
원래의 skip을 유지했다. 실제 로봇·Nav2 취소·Velocity Gate 정지·지도 정렬·현장 지연 및
안전 입력 실측, 웹 화면 연결은 수행하지 않았다.
