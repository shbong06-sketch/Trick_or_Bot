# [기술검증] 가즈보 시험 월드 v1.0 — 심투리얼(sim-to-real) 세팅 규격

관련 이슈·To-do: [기술검증]AMR 제어 기술 탐색 및 검증 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DAMR%20%EC%A0%9C%EC%96%B4%20%EA%B8%B0%EC%88%A0%20%ED%83%90%EC%83%89%20%EB%B0%8F%20%EA%B2%80%EC%A6%9D%203ed0f4c1b9cc809e8cabec53f31cb31b.md)
기록일: 2026년 10월 5일
담당자: sj b
마지막 수정: 2026년 10월 6일 오전 9:31
분류: 실험
분야: ROS2, Robot
생성일: 2026년 10월 5일 오후 9:38
작성 상태: 정리 완료

<aside>
📌

**한 줄 요약**: 실물 TurtleBot4·RC카에서 잰 값(카메라 화각, 지연, 차 크기, depth 오차)을 가즈보에 넣고, SLAM과 YOLO·ArUco 검출을 같은 조건으로 반복 시험하는 월드를 만들었다.

저장소: `TGS10218/ROKEY_mP4_A1` 브랜치 **`feature/gazebo-world-final`** (기반: `feature/real-trial-261003`), 규격서 원본 `tb4_follow_sim/docs/FINAL_WORLD.md`

</aside>

<aside>
⚠️

**기억할 것**

- 로봇 카메라 YOLO 검출은 **1.6 m부터 거의 없다** (실측 크기 차 + 화각 42.4°).
- **ArUco 판을 붙이면 YOLO가 차를 못 찾는다** (0 %). 판이 차 면을 대부분 가린다.
- 웹캠 모델은 시뮬의 실측 크기 차를 `dummy`로 분류하고, 장애물 기둥을 `car`로 오검출한다.
- 실측값 반영 전 시뮬(화각 64°, 큰 차)의 숫자와 직접 비교하지 않는다.
</aside>

## 왜 심투리얼 시험 환경이 필요했나

### 이 프로젝트에서 실제로 한 시험

| 시험 | 확인한 것 | 시뮬이 필요한 이유 |
| --- | --- | --- |
| **1. 추종 코드 시험** | 터틀봇4가 RC카를 따라갈 때 돌발 움직임(급회전·급가속·충돌)이 없는지. 추종 노드(1안 `follow_object_node_v3_safe`)를 실물에 올리기 전에 같은 코드로 돌려 봄 | 실물에서 돌발 움직임을 처음 발견하면 로봇·차·사람이 다칠 수 있음. 속도·파라미터를 바꿀 때마다 실물 시험장을 잡기 어려움 |
| **2. 검출 데이터 시험** | YOLO·ArUco가 거리·방향별로 차를 찾는지 (이 문서 10장) | 같은 자세를 반복해서 놓고 버전(마커 유무, 모델)만 바꿔 비교하려면 위치를 정확히 재현해야 함. 실물로는 32 자세를 같은 조건으로 반복하기 어려움 |

### 왜 이상 조건이 아니라 실측 조건 시뮬이어야 했나

- 같은 추종 노드를 실물 SLAM 지도 월드에서 돌렸다(square 코스 60 s, 최대 0.3 m/s, 각 1회).
    - **이상 조건** (10/4): RC카와 충돌 0회.
    - **실측 조건** (10/5): 지연 0.6 s, 화각 42.4°, 실측 크기 차를 넣자 **RC카와 충돌 3회**, 최소 전방 여유 0.157 m.
    - 이상 조건 시뮬만 봤다면 못 봤을 문제다.
    - 단, 두 실행 사이에 화각·지연·차 크기가 한꺼번에 바뀌었고 점수 계산 버그도 함께 고쳤다. 변수 하나만 바꾼 비교가 아니다.
- 충돌의 원인 후보는 두 가지다(각 1회 실행이라 원인은 아직 분리하지 못했다).
    - 실측 지연.
    - 차 높이 8.5 cm: 라이다 평면 0.19 m보다 낮아 라이다로 차가 안 보인다.
- 그래서 실물은 0.1 m/s(`run_real.sh`)로 시작한다. 속도를 올리기 전에 실측 조건 시뮬에서 먼저 확인한다.
- 검출도 같다. 화각 64°·큰 차인 이상 조건 시뮬의 검출률은 실물 예측에 쓸 수 없다. 실측 조건에서는 1.6 m부터 검출이 거의 없다는 것이 드러났다(10장).

### 근거 등급 규칙: 시뮬은 결정·절차에, 성능은 실물로

<aside>
⚖️

**(S) 시뮬** 결과는 설계 결정과 시험 절차를 정하는 데에만 쓴다.

- 예: 속도 상한을 정한다.
- 예: 루프 클로저를 끈다.
- 예: 마커 배치 후보를 고른다.

**(R) 실물**: 검출률·위치 오차 같은 성능 수치는 실물로 다시 잰 값만 쓴다.

시뮬과 실물의 차이는 가정하지 않고 항목별로 재서 아래 표에 남긴다. (R-S4, R-I2, R-I5)

</aside>

### 외부 근거

- **같은 로봇·같은 라이다의 시뮬→실물 선례 (R-S1)**: TB4 Lite와 RPLIDAR A1에서 Isaac→가즈보→실물로 주행 정책을 옮긴 연구가 있다. 주제는 강화학습 주행이고, 검출 전이의 증거는 아니다.
- **로봇별 센서 기하를 맞춰야 한다 (R-S18)**: 카메라 높이·pitch·내부 파라미터를 로봇 프로필로 두고 같은 정책을 배포한다. 우리가 실측 fx 909로 화각을 맞춘 것과 같은 방향이다.
- **가즈보는 센서 잡음을 직접 넣을 수 있다 (R-S8, 공식 문서, URL 미기록)**: 잡음 σ·bias를 SDF에서 지정한다. 우리 라이다 σ 0.01 m, depth 오차식을 넣은 근거다.
- **시뮬 영상으로 YOLO를 다룰 때는 센서 열화 단계가 필요하다 (R-S5)**: 우리 시뮬 영상은 깨끗하다. 그래서 시뮬 검출률은 버전 간 비교에만 쓴다.
- **같은 저가 센서 구성도 환경에 따라 성능이 크게 달라진다 (R-S11, R-S12, R-S13)**: 통제된 실내에서는 물체 위치 오차가 수 cm다. 산업 실환경에서는 수 m까지 보고된다. 그래서 실물 합격 기준을 따로 정해야 한다.
- **TB4 가즈보 프로젝트의 실패는 지각에 몰려 있었다 (R-S16)**: 실패 17건이 모두 지각 실패였다. 우리가 추종 코드와 함께 검출 시험을 따로 둔 근거다.
- **시뮬이 근거가 되지 않는 영역도 있다 (R-S6)**: VIO처럼 드라이버 시간 동기에 좌우되는 센서 문제는 실물에서만 드러난다.

### 시뮬–실물 차이표 (잰 것만)

| 항목 | 시뮬 (S) | 실물 (R) | 판단 |
| --- | --- | --- | --- |
| 카메라 fx (화각) | 907 (42.4°) | 909 (10/3 회전 시험) | 맞음 |
| depth, 차 뒷면 2.1 m | 2.285 m | 2.248 m (10/2) | 3.7 cm 차이 |
| 라이다 ↔ 실물 SLAM 지도 벽 | 10 cm 이내 99.5 % | — | 좌표가 맞다는 확인일 뿐, 실물 라이다 잡음 재현은 아님 |
| 루프 클로저 위치 튀 (R-I2) | 켬 1.66 m (2/2), 끔 0.10 m | 재현 안 함 | 설계 결정(루프 클로저 끔)에만 사용 |
| YOLO 검출률 (R-I5) | v1.0 38.1 % (32 자세, 0.8–2.0 m) | 97 % (10/3 실물 bag, 로봇 카메라 모델 기준) | 조건이 달라 비교하지 않음. 시뮬 숫자는 버전 간 비교용 |
| 추종 중 충돌 | 실측 조건 0.3 m/s에서 3회 (1회 실행) | 실물은 0.1 m/s로 시작 | 실물 속도 상향 전 시뮬 재확인 필요 |

| 버전 | 월드 파일 | 내용 |
| --- | --- | --- |
| `v1.0` | `worlds/follow_arena_final.sdf` | 마커 없음. **YOLO 시험 기준판** |
| `v1.0-aruco` | `worlds/follow_arena_final_aruco.sdf` | RC카 뒷면·양옆 ArUco (DICT_4X4_50 ID 1, 6 cm) |

![천장 카메라 탑뷰: 펜스 8 × 6 m, 장애물 A~D](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20%EA%B0%80%EC%A6%88%EB%B3%B4%20%EC%8B%9C%ED%97%98%20%EC%9B%94%EB%93%9C%20v1%200%20%E2%80%94%20%EC%8B%AC%ED%88%AC%EB%A6%AC%EC%96%BC(sim-to-real)%20%EC%84%B8%ED%8C%85%20%EA%B7%9C%EA%B2%A9/overhead.png)

천장 카메라 탑뷰: 펜스 8 × 6 m, 장애물 A~D

## 0. 심투리얼: 시뮬에 넣은 실측값

기본 월드(`follow_arena.sdf`)에 실측값을 넣은 것은 팀 브랜치 `feature/real-trial-261003`의 커밋 `c40104b`(`docs/SIM_REAL_SPECS.md`)다. 최종 월드는 그 위에 만들었다. `ideal:=true`로 실측 재현을 모두 끌 수 있다.

| 항목 | 이전 시뮬 | 실측 → 지금 시뮬 | 출처 |
| --- | --- | --- | --- |
| RC카 외곽 (L × W × H) | 0.28 × 0.15 × 0.14 m | **0.25 × 0.08 × 0.085 m** | 10/4 줄자 |
| 로봇 카메라 수평 화각 | 64° (camera_info fx 564.65) | **42.4°** (fx 909) | 10/3 회전 시험 |
| 영상 지연 | 0 | **0.4 s** | 10/3 |
| 명령 → 바퀴 지연 | 0 | **0.2 s** | 10/3 |
| 제자리 회전 최소 속도 | 없음 | **0.26 rad/s** | 10/3 |
| depth 거리 오차 | 없음 | **+0.0595·(d² − 1) m**, 잡음 σ 0.008·d | 10/2 (0.9→0.861, 2.1→2.248, 3.76→4.542 m) |
| TB4 높이·반지름 | 0.351 m · 0.171 m | **0.355 m · 0.170 m** | 10/4 줄자 |

시뮬에서 다시 확인한 값: camera_info fx **907** (실측 909), 2.1 m depth 시뮬 2.285 m ↔ 실물 2.248 m.

## 1. 실행 환경

| 항목 | 버전 |
| --- | --- |
| OS | Ubuntu 24.04 (WSL2에서 검증) |
| ROS 2 | Jazzy |
| Gazebo | Harmonic 계열, `gz-sim-vendor` 0.0.13 |
| `ros_gz_sim` | 1.0.24 |
| `turtlebot4_description` | 2.1.1 (`setup.sh` overlay: 카메라 704 × 704, 화각 42.4°, 10 Hz, gz 라이다 끔) |
| `irobot_create_description` | 3.0.4 |
| YOLO | ultralytics 8.4 (`~/yolo_venv`) |
| 가중치 | 로봇 카메라 `weights/yolo12n_amr_best.pt` (저장소에 있음), 웹캠 `weights/webcam_yolo26s_best.pt` (저장소에 없음, 팀 공유 폴더에서 복사) |

## 2. 빠른 시작

```bash
git fetch && git checkout feature/gazebo-world-final
cd tb4_follow_sim
bash setup.sh                                   # 처음 한 번: overlay (화각 42.4°)
python3 scripts/make_final_world.py             # v1.0 월드
python3 scripts/make_final_world.py --markers   # v1.0-aruco 월드

# 터미널 1: 시뮬 (헤드리스, 실측 지연·depth 오차 켬)
bash run_final_sim.sh                                   # v1.0
WORLD=follow_arena_final_aruco bash run_final_sim.sh    # v1.0-aruco
GUI=true bash run_final_sim.sh                          # 화면 보기
bash run_final_sim.sh ideal:=true                       # 이상 조건
DOMAIN=31 PART=myname bash run_final_sim.sh             # 같은 PC에서 다른 시뮬과 같이

# 터미널 2: SLAM
source env.sh
ros2 launch turtlebot4_navigation slam.launch.py namespace:=/robot1 use_sim_time:=true params:=$PWD/config/slam_final.yaml
ros2 run nav2_map_server map_saver_cli -f my_map -t /robot1/map --ros-args -p use_sim_time:=true

# 터미널 2: YOLO 버전 시험
source env.sh && source ~/yolo_venv/bin/activate
python3 tools/yolo_world_test.py --tag v1.0 --webcam-model weights/webcam_yolo26s_best.pt
```

## 3. 월드 배치도

좌표는 월드 원점 기준(m), 펜스 안쪽 x −4 ~ 4, y −3 ~ 3.

```
y=+3 ┌──────────────────────────────────────────────────────────┐
     │                                                 dummy □  │ (3.5, 2.6)
     │      D ■ (-1.6,0.9)    A ┃ (0, 0.5~1.4)                   │
     │                          ┃                               │
y= 0 │ ◀R (-3.2,0)        W◎(-0.5,0) 웹캠 1.29 m → 시야 x -0.06~2.3│
     │                  B ┃(-1.1,-0.6)                          │
     │      ━━━━━━━━━━━━ B (-1.6,-0.9)       C ■ (1.5,-0.9)       │
     │                                                 RC카 ▭   │ (3.5, -2.6)
y=-3 └──────────────────────────────────────────────────────────┘
    x=-4                         x=0                          x=4
R = 로봇 시작 (yaw 180°)    천장 카메라 (0, 0, 7 m)
pole·pillar(안전 시험용)는 펜스 밖 (6, ∓5)
```

## 4. 물리 엔진

| 항목 | 값 |
| --- | --- |
| 월드 이름 | `follow_arena` (기존 실험 스크립트·`set_pose` 서비스 호환) |
| 물리 시스템 | `gz-sim-physics-system` (Gazebo Harmonic 기본 엔진 DART) |
| 스텝 크기 | 0.003 s (333 Hz) |
| 실시간 배율 목표 | 1.0 |
| 중력 | 기본값 0 0 −9.8 m/s² |
| 월드 플러그인 | physics, user-commands, scene-broadcaster, contact |
| 조명 | sun (directional, 확산 0.65), 주변광 0.35 |
| 마찰 | 바닥 μ 1.0, RC카 μ 0 (`velocity-control`로 미끄러지듯 이동) |

## 5. 모델 규격

`python3 tools/world_spec.py worlds/follow_arena_final.sdf`로 월드 파일에서 뽑은 값. 크기는 충돌 상자 기준.

| 모델 | 용도 | 위치 x, y (m) | 크기 L×W×H (m) | 부피 (L) | 질량 (kg) | 밀도 (kg/m³) | 정적 | 플러그인 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `floor` | 바닥 | 0, 0 | 20 × 20 평면 | — | 정적 | — | 예 | — |
| `fence` | 아레나 경계 | 0, 0 | 8 × 6 둘레, 두께 0.03, 높이 0.5 | 420.0 | 정적 | — | 예 | — |
| `rc_car` | 추종 대상 RC카 | 3.5, −2.6 | 0.2317 × 0.0653 × 0.0734 (차체) | 1.11 | 1.5 | 1351 | 아니오 | velocity-control, pose-publisher |
| `dummy_box` | 오검출 유도용 상자 | 3.5, 2.6 | 0.15 × 0.12 × 0.1 | 1.80 | 3.0 | 1667 | 아니오 | pose-publisher |
| `obs_A_wall` | SLAM 특징용 장애물 | 0, 0.95 | 0.1 × 0.9 × 0.5 | 45.00 | 정적 | — | 예 | — |
| `obs_B_wall_h` | SLAM 특징용 장애물 | −1.6, −0.9 | 1 × 0.1 × 0.5 | 50.00 | 정적 | — | 예 | — |
| `obs_B_wall_v` | SLAM 특징용 장애물 | −1.1, −0.6 | 0.1 × 0.6 × 0.5 | 30.00 | 정적 | — | 예 | — |
| `obs_C_pillar` | SLAM 특징용 장애물 | 1.5, −0.9 | 0.3 × 0.3 × 0.5 | 45.00 | 정적 | — | 예 | — |
| `obs_D_pillar` | SLAM 특징용 장애물 | −1.6, 0.9 | 0.3 × 0.3 × 0.5 | 45.00 | 정적 | — | 예 | — |
| `overhead_cam` | 천장 카메라 | 0, 0 | — | — | 정적 | — | 예 | — |
| `webcam_cam` | 실습장 웹캠 재현 | −0.5, 0 | — | — | 정적 | — | 예 | — |
| `pole` | 안전 시험용 폴 | 6, −5 | 0.05 × 0.05 × 0.6 | 1.50 | 40.0 | 26667 | 아니오 | pose-publisher |
| `pillar` | 안전 시험용 기둥 | 6, 5 | 0.25 × 0.25 × 0.6 | 37.50 | 40.0 | 1067 | 아니오 | pose-publisher |
- RC카 외곽(바퀴·램프 포함)은 실측 **0.25 × 0.08 × 0.085 m**. 위 표는 차체 충돌 상자다. 뒷면 스페어타이어는 차 중심 뒤 0.134 m까지 나온다.
- 장애물 높이 0.5 m는 라이다 평면(0.19 m)을 지나도록 정한 값이라 시뮬 라이다와 SLAM 지도에 잡힌다.
- `pole`·`pillar`의 40 kg은 로봇이 부딪혀도 밀리지 않게 넣은 값이다(실제 무게 아님).
- **ArUco 판 (`v1.0-aruco`만)**: 6 cm 마커 + 흰 여백 = 판 8 × 8 cm, 바닥에서 5 mm.
    - 뒷면 판: 차 중심 뒤 0.15 m (스페어타이어 바깥).
    - 양옆 판: 차 옆면 바깥 8 mm.
    - 판은 visual만 있다(충돌 없음).

![로봇 카메라 (v1.0-aruco): 1.5 m 앞 차 옆모습의 ArUco](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20%EA%B0%80%EC%A6%88%EB%B3%B4%20%EC%8B%9C%ED%97%98%20%EC%9B%94%EB%93%9C%20v1%200%20%E2%80%94%20%EC%8B%AC%ED%88%AC%EB%A6%AC%EC%96%BC(sim-to-real)%20%EC%84%B8%ED%8C%85%20%EA%B7%9C%EA%B2%A9/robot_cam_aruco.png)

로봇 카메라 (v1.0-aruco): 1.5 m 앞 차 옆모습의 ArUco

## 6. 로봇

| 항목 | 값 |
| --- | --- |
| 모델 | TurtleBot4 standard (`/robot1`) |
| 외곽 크기 | 341.8 × 339.1 × 351.2 mm (URDF). 실측 높이 0.355 m, 반지름 0.170 m |
| 질량 | 5.39 kg (URDF 링크 41개 질량 합) |
| 시작 자세 | (−3.2, 0), yaw 180° |
| 구동 | `/robot1/cmd_vel_unstamped` (Twist) → 어댑터(지연 0.2 s) → `/robot1/cmd_vel` (TwistStamped) |

## 7. 센서

| 센서 | 규격 | 비고 |
| --- | --- | --- |
| 로봇 카메라 (OAK-D) | 704 × 704, 화각 0.7403 rad (**42.4°**, fx 907), 10 Hz, 지연 0.4 s | 실측 fx 909 |
| 로봇 depth | +0.0595·(d² − 1) m 오차, 잡음 σ 0.008·d | `ideal:=true`로 끔 |
| 라이다 (`sim_rplidar.py`) | 640 점, 0.164 – 12 m, 10 Hz, 잡음 σ 0.01 m, 높이 0.19 m | WSL에서 gz gpu_lidar가 동작하지 않아 충돌 상자 레이캐스트로 대체 |
| 실습장 웹캠 | (−0.5, 0, 1.29 m), 아래로 48.1°, 640 × 640, 화각 46.1°, 10 Hz | 바닥 시야 대략 x −0.06 ~ 2.3 m |
| 천장 카메라 | (0, 0, 7 m) 수직 아래, 960 × 720, 화각 68.8°, 10 Hz | 녹화·확인용 |

## 8. 토픽

| 토픽 | 형식 | 내용 |
| --- | --- | --- |
| `/robot1/oakd/rgb/image_raw` | Image | 로봇 카메라 (지연 적용 후) |
| `/robot1/oakd/rgb/camera_info` | CameraInfo | fx 907 |
| `/robot1/oakd/stereo/image_raw` | Image | depth (오차 적용 후) |
| `/robot1/scan` | LaserScan | 시뮬 라이다 |
| `/robot1/cmd_vel_unstamped` | Twist | 로봇 명령 |
| `/robot1/map` | OccupancyGrid | SLAM 지도 |
| `/sim/webcam`, `/sim/overhead` | Image | 웹캠, 천장 카메라 |
| `/rc_car/cmd_vel` | Twist | RC카 움직이기 |
| `/rc_car/pose` 외 | TFMessage | 정답 위치 (dummy_box, pole, pillar 포함) |
| gz `/world/follow_arena/set_pose` | 서비스 | 시험 때 로봇·RC카 배치 |

## 9. SLAM 설정

- `config/slam_final.yaml` = `turtlebot4_navigation`의 `slam.yaml`에서 **`do_loop_closing: false`만 바꿈**.
- 이유: 장애물 아레나에서 루프 클로저가 잘못 걸려 위치가 1.66 m 튐(2회 중 2회). 끈 뒤 최대 0.10 m.
- 검증 (10/5): 제자리 회전 + 직진 1.5 m + 회전 + 직진 1.5 m로 만든 지도에 펜스와 장애물 모서리가 나온다(한 바퀴라 일부만 채워짐). 지도: `config/maps/map_final.{pgm,yaml}` (0.05 m).
- 시뮬 라이다가 최종 월드의 장애물을 읽는 것은 로그로 확인했다 (`sim rplidar: 10 models … obs_A_wall … obs_D_pillar`).

![시뮬 SLAM 지도 (루프 클로저 끔)](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20%EA%B0%80%EC%A6%88%EB%B3%B4%20%EC%8B%9C%ED%97%98%20%EC%9B%94%EB%93%9C%20v1%200%20%E2%80%94%20%EC%8B%AC%ED%88%AC%EB%A6%AC%EC%96%BC(sim-to-real)%20%EC%84%B8%ED%8C%85%20%EA%B7%9C%EA%B2%A9/slam_map_final.png)

시뮬 SLAM 지도 (루프 클로저 끔)

## 9-1. 지도의 한계

이 문서의 지도는 두 가지다.

- 최종 월드에서 만든 시뮬 SLAM 지도 `map_final`.
- 10/4 실물 SLAM 지도 `arena_1004_run1`로 만든 월드 `follow_arena_slam1004`.

둘 다 2D 점유 격자 지도라서 아래 한계가 있다.

| 한계 | 내용 | 영향 |
| --- | --- | --- |
| **높이 정보가 없음** | 라이다 평면(0.19 m) 하나의 단면만 남는다. 실물 지도로 월드를 만들 때 모든 벽·물체를 높이 0.5 m 상자로 세웠다 | 카메라에 보이는 벽·물체의 모양·높이·색은 실물과 다르다. 검출 시험의 배경은 실물 재현이 아니다 |
| **라이다 아래 물체가 안 남음** | 0.19 m보다 낮은 물체는 지도에 없다. RC카(8.5 cm), 턴이 낮은 장애물, 케이블 등이다 | 지도·라이다만으로는 차와 부딪히는 것을 막지 못한다. 추종 충돌 3회의 원인 후보다 |
| **미탐색 영역** | 회색 칸은 비워 두었다. `map_final`은 한 바퀴만 돌아 일부만 채워졌다. `slam1004` 월드에는 벽이 빠진 곳이 있다(방 아래쪽 통로 끝) | 로봇·차가 지도 밖으로 나갈 수 있다. 내비게이션에 쓰려면 전체를 다시 돌아 채워야 한다 |
| **정적 지도** | 만든 시점의 배치만 담긴다 | 움직이는 사람·차·옮긴 물체는 지도에 없다. AMCL이 지도와 다른 장면을 만나면 위치를 잘못 잡을 수 있다 |
| **루프 클로저 끔** | 장애물 아레나의 위치 튀(1.66 m)을 막으려고 끔 | 긴 경로를 돌면 오차가 쌓여도 바로잡지 못한다. 지도는 짧게 만들고 이후에는 고정 지도+AMCL로 쓴다 |
| **해상도 0.05 m** | 칸 하나가 5 cm다 | 5 cm보다 작은 틈·모서리는 뛰러진다. 실물 지도에서 1칸짜리 잡음을 지우면서 작은 물체도 같이 지워졌을 수 있다 |
| **시뮬 지도는 실물 라이다 현상을 안 담음** | 시뮬 라이다는 충돌 상자 기하 계산이다 | 유리·검은 면·반사면의 누락과 허상은 시뮬 지도에 없다. 시뮬 라이다와 지도의 99.5 % 일치는 좌표 확인일 뿐 실물 성능이 아니다 |
| **물체의 의미가 없음** | 점유 격자는 막힘/빈칸만 안다 | 어느 칸이 차·벽·사람인지는 검출(YOLO 등)을 따로 붙여야 한다. 2D 라이다 단독 의미 분할은 별도 연구 주제다 (R-S14) |

## 10. 버전별 YOLO 시험 방법과 기준값

**방법** (`tools/yolo_world_test.py`)

- **로봇 카메라**: 로봇 (−2.5, 0), RC카를 앞 0.8 / 1.2 / 1.6 / 2.0 m × 방향 8개 = 32 자세에 둔다. 자세마다 5 프레임, 신뢰도 0.4 이상(추종 노드 기준) `car`의 비율.
- **웹캠**: 로봇 카메라 시험 위치는 웹캠 시야 밖이라 따로 잰다. 차를 웹캠 시야 안 9곳 × 2방향에 둔다.
    - 차가 없는 빈 화면에서 잡히는 박스(배경 오검출)는 빼고 센다.
    - 차를 다른 클래스로 본 경우도 센다.
- 결과: `results/yolo_<tag>_<시각>.csv`, `_webcam.csv`, `_summary.json`, 예시 사진 `results/img_<tag>/`

**기준값** (10/5, 실측 조건, 로봇 카메라 `yolo12n_amr_best`, 웹캠 `webcam_yolo26s_best`)

| 버전 | 로봇 카메라 프레임 검출률 | 1번이라도 검출된 자세 | 거리별 0.8 / 1.2 / 1.6 / 2.0 m | 웹캠 `car` | 웹캠이 다른 클래스로 봄 |
| --- | --- | --- | --- | --- | --- |
| `v1.0` | **38.1 %** | 56.2 % | 72.5 / 72.5 / 7.5 / 0 % | 16.7 % | 100 % (`dummy`) |
| `v1.0-aruco` | **0 %** | 0 % | 0 / 0 / 0 / 0 % | 27.8 % | 100 % (`dummy`) |

**ArUco 검출** (`v1.0-aruco`, OpenCV `ArucoDetector`, 로봇 카메라). 뒷면은 거리마다 1장, 옆면은 5장씩 확인.

| 거리 | 뒷면 | 옆면 |
| --- | --- | --- |
| 0.6 m | 검출 안 됨 (원인 미확인) | 5 / 5 |
| 0.8 m | 검출 | — |
| 1.0 m | 검출 | 4 / 5 |
| 1.5 m | 검출 | 5 / 5 |
| 2.0 m | 검출 | — |

![v1.0 로봇 카메라, 0.8 m 뒷모습](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20%EA%B0%80%EC%A6%88%EB%B3%B4%20%EC%8B%9C%ED%97%98%20%EC%9B%94%EB%93%9C%20v1%200%20%E2%80%94%20%EC%8B%AC%ED%88%AC%EB%A6%AC%EC%96%BC(sim-to-real)%20%EC%84%B8%ED%8C%85%20%EA%B7%9C%EA%B2%A9/robot_v1.0_0.8m_rear.jpg)

v1.0 로봇 카메라, 0.8 m 뒷모습

![v1.0 웹캠: 차를 dummy로, 기둥 C를 car로 봄](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20%EA%B0%80%EC%A6%88%EB%B3%B4%20%EC%8B%9C%ED%97%98%20%EC%9B%94%EB%93%9C%20v1%200%20%E2%80%94%20%EC%8B%AC%ED%88%AC%EB%A6%AC%EC%96%BC(sim-to-real)%20%EC%84%B8%ED%8C%85%20%EA%B7%9C%EA%B2%A9/webcam_v1.0_dummy.jpg)

v1.0 웹캠: 차를 dummy로, 기둥 C를 car로 봄

**읽는 법**

- **1.6 m부터 로봇 카메라 검출이 거의 없다.** 실측 크기 차(높이 8.5 cm)가 화각 42.4°에서 작게 보인다.
- **마커를 붙이면 YOLO가 차를 못 찾는다.** YOLO와 ArUco를 같이 쓰려면 마커를 작게 하거나 한 면에만 붙이는 버전을 시험해야 한다.
- **웹캠 모델은 시뮬의 실측 크기 차를 주로 `dummy`로 분류한다.** 기둥 C도 빈 화면에서 `car` 0.54로 잡힌다(표에서는 뺐다). 실물 웹캠 영상에서도 같은지 먼저 확인할 것.

**새 버전 시험 순서**

1. `make_final_world.py`를 고치거나 새 월드를 만든다 (월드 이름 `follow_arena` 유지).
2. `WORLD=<새 월드> bash run_final_sim.sh`
3. `python3 tools/yolo_world_test.py --tag v1.1 --webcam-model weights/webcam_yolo26s_best.pt`
4. 위 기준값 표에 한 줄 더한다.
5. 월드 구성이 바뀌었으면 `python3 tools/world_spec.py worlds/<새 월드>.sdf`로 5장 표를 갱신한다.

## 11. 알려진 한계

- 라이다는 충돌 상자 기하 계산이라 실물 라이다의 반사·누락은 재현하지 않는다.
- 차 높이(8.5 cm)가 라이다 평면(0.19 m)보다 낮아 라이다에 차가 안 보인다(실물과 같음).
- 바닥·벽은 단색, 조명 한 가지. 실물 시험장의 질감·반사·조명 변화는 없다.
- RC카는 `velocity-control`로 미끄러져 움직인다(바퀴 굴림·조향 없음).
- 웹캠 위치·각도는 실습장 웹캠을 재현한 값이고, 실물 캘리브레이션 결과와 맞춘 것은 아니다.
- YOLO 기준값은 버전별 1회 실행 결과다. v1.0을 3번 돌렸을 때 프레임 검출률은 38.1 ~ 41.9 %였다.
- 마커 텍스처가 월드 파일에 절대경로로 들어간다. 다른 PC에서는 `make_final_world.py --markers`를 다시 실행한다.

## 12. 파일 구성

```
tb4_follow_sim/
├── scripts/make_final_world.py      # 최종 월드 생성 (기본 월드 + 장애물 [+ ArUco])
├── run_final_sim.sh                 # 최종 월드 실행 (WORLD, GUI, DOMAIN, PART)
├── config/slam_final.yaml           # slam_toolbox (루프 클로저 끔)
├── config/maps/map_final.{pgm,yaml} # 검증한 SLAM 지도
├── tools/yolo_world_test.py         # 버전별 YOLO 시험
├── tools/world_spec.py              # 월드 파일 → 규격 표
├── docs/FINAL_WORLD.md              # 규격서 (이 페이지 원본)
├── docs/img_final_world/            # 탑뷰, 로봇 카메라, SLAM 지도
├── results/yolo_v1.0*_*             # 기준값 (csv, summary.json)
└── results/img_v1.0*/               # 예시 사진
# 생성물 (커밋 안 함): worlds/follow_arena_final*.sdf, worlds/final_tex/
```

## 13. 근거 출처

- 각 출처는 "이 문서에서 뒷받침하는 주장"에만 쓴다.
- 포럼·2차 자료와 미열람 자료는 표시를 그대로 둔다.
- 출처의 수치는 출처의 조건에서 나온 값이다. 우리 결과와 직접 비교하지 않는다.

| ID | 출처 | 유형 | 이 문서에서 뒷받침하는 주장 | 주의 |
| --- | --- | --- | --- | --- |
| R-S1 | [Salimpour 외 2025, Isaac Sim → Gazebo → Real ROS 2](https://arxiv.org/abs/2501.02902) · [코드](https://github.com/sahars93/RL-Navigation) | 학술·코드 | 같은 TB4·RPLIDAR A1에서 시뮬→실물 전이 선례 | RL 주행 주제. 검출 전이 증거 아님 |
| R-S4 | [FERBIN12/isaac-sim-robot-workspace](https://github.com/FERBIN12/isaac-sim-robot-workspace) | 코드 | 시뮬–실물 차이는 가정하지 않고 항목별로 잰다 | 미열람 (설명문 기준) |
| R-S5 | [IGL5/Sim-to-Real-Isaac-Sim](https://github.com/IGL5/Sim-to-Real-Isaac-Sim) | 코드 | 시뮬 영상으로 YOLO를 다룰 때 센서 열화 단계가 필요 | 성능 수치 없음 |
| R-S6 | [Open Navigation, Integrating VIO into Nav2](https://navigation.ros.org/tutorials/docs/integrating_vio.html) | 공식문서 | 드라이버 시간 동기 같은 센서 문제는 시뮬로 근거가 안 됨 | VIO 한정 |
| R-S8 | Gazebo SDF 센서 잡음 파라미터 (공식 SDF 스펙) | 공식문서 | 잡음 σ·bias를 SDF에서 지정해 실측 잡음을 넣을 수 있음 | URL 미기록 |
| R-S11 | [Patrol and Security Robot with Semantic Mapping, CMC 2026](https://www.techscience.com/cmc/v87n1/66098/html) | 학술 | 통제된 실내에서 저가 센서 구성의 물체 위치 오차가 수 cm 수준 | 통제된 실내 |
| R-S12 | [Semantic Mapping in Desalination, Machines 2025](https://doi.org/10.3390/machines13121129) | 학술 | 산업 실환경에서는 위치 오차가 m 단위로 커짐 | — |
| R-S13 | [Real-Time Semantic Map Production System, Sensors 2024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11511299/) | 학술 | 실환경 의미 지도 위치 오차가 m 단위 | — |
| R-S14 | [Semantic2D](https://arxiv.org/pdf/2409.09899) | 학술 | 2D 라이다 단독 의미 분할은 별도 데이터셋·도구가 필요한 주제 (지도의 한계) | — |
| R-S16 | [MHVVD/Semantic-object-finding-robot](https://github.com/MHVVD/Semantic-object-finding-robot) | 코드 | TB4 가즈보 프로젝트의 실패가 모두 지각 실패 | 실물은 future work |
| R-S18 | [Matthew-K-Chua/rpv-sim2real-policy](https://github.com/Matthew-K-Chua/rpv-sim2real-policy) | 코드 | 로봇별 카메라 높이·pitch·내부 파라미터 프로필로 배포 | — |
| R-I2 | 내부: 가즈보 장애물 아레나 SLAM | 내부 (S) | 루프 클로저 켬 1.66 m 튐(2/2), 끔 0.10 m → 루프 클로저 끔 | 실물 재현 안 함 |
| R-I5 | 내부: 10/3 실물 bag | 내부 (R) | 실물 검출 97 %, 모델 9/11이 로봇을 오검출 | 로봇 카메라 모델 기준 |

이 문서에서 쓰지 않은 출처(R-S2·S3·S7·S9·S10·S15·S19·S20)는 원본 목록 `SIM2REAL_REFS.md`에 있다.