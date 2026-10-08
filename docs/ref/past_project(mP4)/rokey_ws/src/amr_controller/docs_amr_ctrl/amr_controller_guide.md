# amr_controller 패키지 가이드 (웹캠 좌표로 AMR 이동)

- 작성: 2026-10-07_0925
- 위치: `rokey_ws/src/amr_controller/`
- 한 줄 설명: **웹캠(detection_alert)이 보낸 car의 지도 좌표를 받아, TurtleBot4를 도크에서 출발시켜 car 앞까지 Nav2로 이동시키는 패키지**
- 관련: `rokey_ws/src/detection_alert/docs_wc_det/detection_alert_guide.md` (좌표를 만드는 쪽),
  `docs/guidance/guidance_6.md` C (실행 절차), 튜터님 자료 `docs/ref/notion/tutors/day3-SLAM_navigation/06_Robot_Navigation/`

> ⚠️ **현재 상태**: 로봇 없이 할 수 있는 시험(목표 계산, 시작 흐름, 종료)만 통과. **실제 로봇·Nav2로는 아직 시험하지 않음.**
> 팀원 `rccar_follow`(feature/real-trial-261003)가 같은 역할(웹캠 좌표로 목표 이동)을 자체 구현해 두었으므로,
> 통합 때 둘 중 무엇을 쓸지 정해야 한다 (8절).

---

## 0. 1분 요약 (설명할 때 이 순서로)

1. **무엇을**: 교안 시나리오의 "start AMR → move AMR → Arrived at Target?" 부분.
2. **출발 조건**: 웹캠이 `/webcam/car_point`(car 지도 좌표)를 보내면 undock 후 출발. 그 전에는 도크에서 대기.
3. **목표**: car 좌표 그 자체가 아니라 **car 앞 0.5 m 지점, car를 바라보는 방향**.
   car 자리는 장애물이라 Nav2가 갈 수 없고, 도착 후 카메라로 car를 바로 보게 하기 위함.
4. **car가 움직이면**: 이동 중 car 좌표가 0.5 m 넘게 바뀌면 목표를 새 위치로 바꾼다.
5. **도착하면**: `/robot1/arrived_near_car`를 발행 → 이후 탐색·접근은 AMR 카메라 쪽(팀원) node가 맡는다.
6. **기반 코드**: 튜터님 `Robot_TB4_nav_to_pose` 예제(`3_1_a1`)의 순서를 그대로 따른다.

---

## 1. 시나리오에서의 위치

```
[detection_alert]                [amr_controller: goto_car]                         [AMR 카메라 쪽 (팀원)]
웹캠 car 검출 → car 지도 좌표 ──▶ 도크 대기 → undock → car 앞 0.5m로 Nav2 이동 → 도착 알림 ──▶ Detect Car(OAK-D) → Approach
                /webcam/car_point                                    /robot1/arrived_near_car
```

| DAY3 과제 항목 | goto_car에서 하는 곳 |
|---|---|
| AMR receives an event and undocks | `/webcam/car_point` 수신 → `undock()` |
| Init Pose is set | 시작할 때 `setInitialPose(initial_pose)` (도크 좌표) |
| AMR moves to a goal position | car 앞 0.5 m로 `goToPose` |

---

## 2. 동작 순서

```
 시작
  │
  ├─ ① 도크 위인지 확인 (아니면 dock)                   ← 튜터님 예제와 같음
  ├─ ② initial pose 설정 (도크의 지도 좌표, 파라미터)     ← 도크 위에서 설정해야 정확
  ├─ ③ Nav2 준비 대기 (waitUntilNav2Active)
  ├─ ④ 🔸 웹캠 car 좌표 대기  ────── /webcam/car_point 올 때까지 도크에서 대기
  ├─ ⑤ undock
  └─ ⑥ 이동 반복
        ├─ 목표 = 로봇→car 방향으로 car 앞 0.5 m, car를 바라봄
        ├─ goToPose(목표) 후, 도착할 때까지:
        │     · 주기적으로 남은 거리 log
        │     · car 좌표가 0.5 m 넘게 바뀌면 → 목표 갱신 (⑥ 처음으로)
        ├─ 성공 → /robot1/arrived_near_car 발행, 종료 대기 (Ctrl+C)
        └─ 실패 → 같은 목표로 2번 더 시도 → 그래도 실패면 새 car 좌표를 기다림
```

---

## 3. 핵심 원리

### 3-1. 목표 계산 (car 앞 0.5 m)

```
   로봇 R ●────────────────────▶ ● 목표 G ─ 0.5 m ─ ◆ car C
          (amcl_pose, 없으면 initial pose)
   방향 yaw = atan2(C - R)  → 도착하면 car를 정면으로 바라봄
   이미 0.5 m 안이면: 제자리에서 방향만 돌림
```

- 팀원 `3_3_bc`의 `STANDOFF_M = 0.5`와 같은 계산이다.

### 3-2. 왜 `startToPose`가 아니라 `goToPose` + `isTaskComplete` 반복인가

- `startToPose`(튜터님 TB4 예제)는 도착할 때까지 함수 안에서 기다린다 → 그동안 car가 움직여도 목표를 바꿀 수 없다.
- `goToPose`는 목표만 보내고 바로 돌아온다. `isTaskComplete()`를 반복 확인하면서 새 car 좌표를 볼 수 있다.
  (튜터님 `Robot_SC_nav_to_pose` 예제와 같은 방식)

### 3-3. namespace는 코드에 넣지 않는다

- 튜터님 방식대로 실행할 때 `--ros-args -r __ns:=/robot1`로 붙인다.
  → `amcl_pose`, `navigate_to_pose`, `dock_status` 등이 자동으로 `/robot1/...`이 된다.
- 웹캠 topic은 `/webcam/car_point`(절대 이름)라 namespace의 영향을 받지 않는다.

### 3-4. Ctrl+C로 끄면 Nav2 이동도 취소

- node만 꺼지면 Nav2는 받은 목표로 **계속 주행**한다.
- 그래서 Ctrl+C를 rclpy가 아닌 코드에서 받아, 진행 중인 목표를 `cancelTask()`로 취소한 뒤 끝낸다.

### 3-5. 도착 알림을 남겨 두는 이유

- `/robot1/arrived_near_car`는 transient_local로 발행하고, 도착 후에도 node를 끄지 않는다.
  → AMR 카메라 쪽 node를 나중에 켜도 도착 알림과 car 좌표를 받을 수 있다.

---

## 4. 패키지 구성

```
amr_controller/
├── package.xml, setup.py, setup.cfg, resource/
├── docs_amr_ctrl/                  이 문서
└── amr_controller/
    └── goto_car_node.py            실행 파일 goto_car (3_1_a1_nav_clicked_points.py 기반)
```

- 원래 `rokey_ws/src/nav_to_pose/`에 있던 튜터님 예제 파일들(`3_1_a`, `3_1_a1`)을 패키지로 정리한 것.
  예제 원본은 `nav/rokey_pjt/rokey_pjt/`에 그대로 있다.

---

## 5. 사용법

준비 (로봇 연결, 터미널마다):

```bash
source ~/venvs/rokey_venv/bin/activate
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
```

먼저 켜 둘 것: localization(맵), nav2, (확인용) RViz, 웹캠 쪽 `webcam_detector` + `car_locator` → 가이던스 6의 C

```bash
ros2 run amr_controller goto_car --ros-args -r __ns:=/robot1 -p "initial_pose:=[0.0, 0.0, 0.0]"
# 🔴 initial_pose = [도크의 x, y, 방향(도)]. 방향은 지도 +x가 0, 반시계 +
```

🔴 **도크 좌표 구하는 법** (guidance_5 3번): 로봇을 도크에 두고 RViz `2D Pose Estimate`로 맞춘 뒤
`ros2 topic echo /robot1/amcl_pose --once`의 `position.x, y`.

정상 log 순서:

```
Publishing Initial Pose → (Nav2 준비) → 웹캠 car 좌표 대기 중 → car 좌표 수신: x=… y=…
→ Undocking... → goal x=… (car x=…) → 남은 거리 … m → car 근처 도착 → arrived_near_car publish
```

---

## 6. topic

| 방향 | topic (`__ns:=/robot1` 기준) | 타입 | 내용 |
|---|---|---|---|
| 받음 | `/webcam/car_point` | geometry_msgs/PointStamped | 웹캠 car 지도 좌표 (detection_alert/car_locator) |
| 받음 | `/robot1/amcl_pose` | PoseWithCovarianceStamped | 로봇 현재 위치 (목표 방향 계산) |
| 받음 | `/robot1/dock_status` | irobot_create_msgs/DockStatus | 도크 위인지 |
| 보냄 | `/robot1/initialpose` | PoseWithCovarianceStamped | 시작 위치 (도크 좌표) |
| action | `/robot1/navigate_to_pose` | nav2_msgs/NavigateToPose | Nav2 이동 |
| action | `/robot1/undock`, `/robot1/dock` | irobot_create_msgs | 도킹 |
| 보냄 | `/robot1/arrived_near_car` | geometry_msgs/PointStamped | 도착 알림 + 그때의 car 좌표 (transient_local) |

---

## 7. 설정값 (`--ros-args -p 이름:=값`)

| 이름 | 기본 | 뜻 |
|---|---|---|
| `initial_pose` | `[0.0, 0.0, 0.0]` | 🔴 도크의 지도 좌표 `[x, y, 방향(도)]` |
| `approach_dist` | 0.5 | car 중심에서 이만큼 앞에서 멈춤 (m). 벽 근처 car면 0.7 등으로 |
| `replan_dist` | 0.5 | 이동 중 car 좌표가 이만큼 바뀌면 목표 갱신 (m) |
| `max_retries` | 2 | 이동 실패 시 같은 목표 재시도 횟수 |
| `car_topic` | `/webcam/car_point` | car 좌표 topic |

---

## 8. 통합 현황 (2026-10-07 기준)

| | goto_car (이 패키지) | 팀원 rccar_follow (feature/real-trial-261003) |
|---|---|---|
| 출발 신호 | `/webcam/car_point` 수신 | `/webcam/car_alert` = true |
| car 좌표 | detection_alert `car_locator`가 계산해 보냄 | `/webcam/detections`를 받아 **자체 homography**로 계산 |
| 목표 | car 앞 0.5 m | car 앞 1.0 m (멈춘 car 0.6 m) |
| 도착 후 | 알림만 내고 팀원 node에 넘김 | 탐색·추종·접근까지 한 패키지에서 |
| 시험 | 로봇 없이 시험만 | Gazebo·단위 시험 44개 |

- 지금 통합 흐름에서는 팀원 `rccar_follow`가 웹캠 출력(`/webcam/car_alert`, `/webcam/detections`)을 직접 쓴다.
- goto_car는 **웹캠 → Nav2 이동 구간만 따로 시험**할 때(모듈 테스트) 쓰기 좋다.

---

## 9. 예상 질문과 답

**Q. 왜 car 좌표로 바로 안 가고 0.5 m 앞으로 가나?**
A. car 자리는 장애물이라 Nav2가 목표로 받아도 갈 수 없다. 또 도착했을 때 로봇 카메라가 car를 바로 보도록, car를 바라보는 방향으로 멈춘다.

**Q. car가 움직이면?**
A. 이동 중 웹캠 좌표가 0.5 m 넘게 바뀌면 목표를 새 위치로 다시 보낸다 (Nav2가 이전 목표를 대체).

**Q. initial pose는 왜 도크에서 설정하나?**
A. 도크 위치는 매번 같아서 지도 좌표를 미리 알 수 있다. 출발 전에 정확한 위치를 줘야 AMCL이 처음부터 맞게 위치를 추정한다.

**Q. 튜터님 예제와 뭐가 다른가?**
A. 순서(도크 확인 → initial pose → Nav2 대기 → undock → 이동)는 같다.
다른 점: ① 목표가 고정 좌표가 아니라 웹캠이 보낸 좌표 ② `startToPose` 대신 `goToPose` 반복으로 목표 갱신 가능
③ 웹캠 신호가 올 때까지 도크에서 대기 ④ Ctrl+C 시 이동 취소.

**Q. 실제로 돌려 봤나?**
A. 아직 로봇으로는 안 했다. 목표 계산, namespace 적용, initial pose 발행, Nav2 대기, 종료는 로봇 없이 확인했다.

---

## 10. 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `amcl/get_state service not available` 반복 | localization이 안 켜짐, 또는 `-r __ns:=/robot1` 빠짐 |
| 처음에 아무 log 없이 멈춤 | `dock_status`를 못 받음 → 로봇 연결·namespace 확인 |
| `웹캠 car 좌표 대기 중`에서 안 넘어감 | car_locator가 좌표를 안 보냄 → car_locator log에 `📍 car_point`, webcam_detector log에 `CAR ALERT ON` 있는지 |
| 출발하자마자 엉뚱한 방향 | `initial_pose`가 실제 도크 좌표와 다름 |
| `이동 실패` 반복 | car 앞 0.5 m 지점이 벽·장애물 안 → `-p approach_dist:=0.7` 또는 car를 벽에서 떼기 |
| Ctrl+C 후에도 로봇이 움직임 | 정상이라면 `Ctrl+C → Nav2 이동 취소` log가 나옴. 안 나오면 RViz에서 Nav2 취소 |
