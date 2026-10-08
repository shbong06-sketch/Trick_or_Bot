# guidance_10 — amr_goto_car 모듈 통합 재실행 (g9 실패 원인 2개 수정판)

- 작성: 2026-10-07_1613
- 목적: 가이던스 9차에서 Nav2가 안 올라와 `amr_goto_car`가 멈춘 문제를 고친 순서로 다시 실행해, 웹캠 car 좌표 → 로봇이 car 앞 1.2 m까지 가는 흐름을 끝까지 확인한다.
- 방침: **car와 dummy는 처음부터 끝까지 경기장에 그대로 둔다.** (두었다 치웠다 하는 수동 시험 없음)
- 맵: **오토 슬램 맵 `~/ROKEY_mP4_A1/rokey_ws/maps/map_auto_261006_1214.yaml`**
- 도크 초기 위치: `amr_goto_car` 코드 그대로 `[0.0, 0.0]` NORTH. 코드를 고치지 말 것.
- 기록: `~/ROKEY_mP4_A1/nav/result_nav/{log_nav, bag_nav}/`

## 0. g9에서 무엇이 틀렸나 (배경, 읽지 않아도 진행 가능)

| | g9에서 일어난 일 | 확인한 근거 | 이번 수정 |
|---|---|---|---|
| ① | Nav2 기동이 중단됨 (`Failed to change state … async_send_request failed` → `Aborting bringup`). `bt_navigator`가 active가 못 돼서 `amr_goto_car`가 `waitUntilNav2Active()`에서 5분간 멈춤 | 이 PC에서 같은 환경(`ROS_SUPER_CLIENT=True`)으로 서비스 호출 5회 시험 → **5/5 실패(10초 타임아웃)**. `ROS_SUPER_CLIENT=False`로 5회 → **5/5 성공** | 🔴 **노드를 띄우는 터미널은 `ROS_SUPER_CLIENT=False`** (아래 각 블록에 넣어 둠) |
| ② | (①을 고쳐도) Nav2가 초기 위치 없이 먼저 켜져서 global costmap이 `base_link→map` TF를 못 받아 기동 중단 | `ROS_SUPER_CLIENT=False`로 시험하니 `planner_server`가 `Timed out waiting for transform from base_link to map`로 실패 | 🔴 **localization → 초기 위치 발행 → Nav2** 순서 |
| ③ | (아직 안 일어났지만 곧 만났을 문제) 언도킹 1초 뒤 도킹 상태를 확인하는데 `dock_status`는 1초 간격이라 이미 내려왔어도 `Undock failed`로 끝날 수 있음 | g9 bag: `dock_status` 도착 간격의 **53%가 1.0초 초과** | `amr_goto_car`의 확인을 **최대 5초 대기**로 고침 (팀원 코드를 이 저장소에서 5줄 수정, 커밋 기록 있음) |

- **검증한 것** (Claude, 실제 로봇 환경, 2026-10-07 16:1x): `ROS_SUPER_CLIENT=False`로 localization → 초기 위치 `(0,0)` 발행 → `amcl_pose = (-0.04, 0.05)` → Nav2가 **`Managed nodes are active`까지 올라감**. 로봇을 움직이는 명령은 없었음.
- **검증 못 한 것**: `amr_goto_car`가 실제로 언도킹하고 car 앞 1.2 m까지 가는 구간 (이번 가이던스에서 처음 실행).

> ## 🔴 꼭 지킬 것 (8개) — 하나라도 놓치면 g9처럼 멈춤
> 1. 🔴 **모든 터미널 첫 두 줄은 `source ~/venvs/rokey_venv/bin/activate`, `source /etc/turtlebot4_discovery/setup.bash`.** `ros_local.sh`는 쓰지 말 것.
> 2. 🔴 **노드를 띄우는 터미널(localization, nav2, RViz, 웹캠, car_locator, amr_goto_car)은 세 번째 줄에 `export ROS_SUPER_CLIENT=False`.** 각 블록에 들어 있음. `ros2 topic/node` 확인용 터미널과 bag 터미널은 이 줄을 넣지 않는다 (기본값 True가 토픽을 보려면 필요).
> 3. 🔴 **순서를 지킬 것: localization → 초기 위치 → Nav2 → 나머지.** Nav2가 `Managed nodes are active`를 못 내면 **다음 단계로 가지 말 것.**
> 4. 🔴 **로봇은 도크 위, 사람이 컨트롤러 B(E-Stop)를 손에 듦.** car가 이미 보이므로 `amr_goto_car`를 켜면 **바로 언도킹하고 출발**한다.
> 5. 🔴 **`amr_goto_car`를 Ctrl+C로 꺼도 로봇은 목표로 계속 간다.** 멈추려면 RViz Nav2 패널 **Cancel** 또는 E-Stop.
> 6. 🔴 **시작 전 옛 `goto_car`/`amr_goto_car`가 0개** (T8 확인).
> 7. 🔴 **bag 터미널은 한 번만 실행.**
> 8. 🔴 **삼각대를 건드리지 말 것.** 시작 전·끝난 뒤 `check_camera`.

---

# [터미널 1] — 확인 + 준비 + localization

## 1-1. 🔴 필수: 환경과 옛 프로세스 확인

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
{
echo "도메인=$ROS_DOMAIN_ID  서버=$ROS_DISCOVERY_SERVER"
echo "--- 옛 노드 (0개여야 함)"; ps -eo pid,etimes,cmd | grep -E "goto_car|amr_goto|nav2_|amcl" | grep -v grep
echo "--- 로봇 노드"; ros2 daemon stop; sleep 1; ros2 node list
} 2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_precheck.txt
```

- ✅ 성공: `도메인=1`, `--- 옛 노드` 아래 **아무 줄도 없음**, `--- 로봇 노드`에 `/robot1/...`가 보임
- 🔴 옛 노드가 보이면 `kill -TERM <PID>` 후 다시. 로봇 노드가 안 보이면 다음 단계로 가지 말 것.

## 1-2. build

```bash
cd ~/ROKEY_mP4_A1/rokey_ws
colcon build --symlink-install --packages-select detection_alert amr_goto \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_build.txt
source install/setup.bash
```

- ✅ 성공: `Summary: 2 packages finished` (🔴 반드시 `rokey_ws` 안에서)

## 1-3. 웹캠 번호 확인

```bash
v4l2-ctl --list-devices
```

> ## ⚠️⚠️ 여기서 나온 웹캠 번호 N을 아래 **1-4, [터미널 4](웹캠 노드), 끝내기 check_after 커맨드 3곳**의 `5` 자리에 직접 써 넣을 것
> **`Web Camera` 아래 첫 번째 `/dev/videoN`의 N.** (`Integrated Camera`는 노트북 내장 → 쓰지 않음)

## 1-4. 🔴 필수: 카메라가 움직였는지 확인

```bash
ros2 run detection_alert check_camera --cam 5 \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_check_before.txt
# ⚠️ <<< 5를 1-3에서 확인한 번호로 바꿀 것
```

- ✅ 성공: `✅ 카메라 이동이 5cm 미만. 다음 단계로 진행`
- 🔴 `❌`면 다음 단계로 가지 말 것.

## 1-5. localization (이 터미널은 계속 켜 둠)

```bash
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널
ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot1 \
  map:=$HOME/ROKEY_mP4_A1/rokey_ws/maps/map_auto_261006_1214.yaml \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_loc.txt
# ⚠️ <<< map 이름이 map_auto_261006_1214.yaml 인지 확인
```

- ✅ 성공: `Received a 161 X 338 map`, `Managed nodes are active`
- `AMCL cannot publish a pose ... set the initial pose` 경고는 **정상** (다음 단계에서 해결)
- 🔴 `126 X 339`가 나오면 수동 맵. 멈추고 `map:=`를 다시 확인.

---

# [터미널 8] — 🔴 필수: 초기 위치 넣기 + 진단 (CLI 터미널, `ROS_SUPER_CLIENT` 건드리지 않음)

> 로봇은 **도크 위**여야 한다. 도크 위치 = 맵의 `(0, 0)`, 방향 NORTH(+x). `amr_goto_car` 코드와 같은 값이다.

## 8-1. 초기 위치 발행

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
{
ros2 topic pub -w 1 -t 3 -r 2 /robot1/initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.0685]}}"
echo "--- amcl_pose"; timeout 10 ros2 topic echo /robot1/amcl_pose --once | grep -A3 "position:"
} 2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_initpose.txt
```

- ✅ 성공: `amcl_pose`의 `x`, `y`가 **0에 가까움** (예: `x: -0.04`, `y: 0.05`)
- 🔴 **`amcl_pose`가 안 나오면 다음 단계(Nav2)로 가지 말 것.** [터미널 1]의 localization이 켜져 있는지 확인하고 8-1을 한 번 더.

## 8-2. dock_status 확인

```bash
{
echo "--- dock_status 1회"; timeout 10 ros2 topic echo /robot1/dock_status --once
echo "--- dock_status 주기 (8초)"; timeout 8 ros2 topic hz /robot1/dock_status
} 2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_dockstatus.txt
```

- ✅ 성공: `is_docked: true`, `average rate: 1` 안팎

---

# [터미널 2] — nav2 (🔴 8-1 성공 후에만)

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널
ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot1 \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_nav2.txt
```

- ✅ 성공: **`Managed nodes are active`** (약 20~40초 안에)
- 🔴 **`Aborting bringup`이 나오거나 1분 안에 `Managed nodes are active`가 안 나오면 다음 단계로 가지 말 것.** 그 터미널을 `Ctrl+C`로 끄지 말고 화면 그대로 Claude에게 알림.
- `Waiting for service controller_server/get_state...`이 한두 번 나오는 것은 정상.

---

# [터미널 3] — RViz (확인 + Cancel 버튼용)

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널 (Cancel 버튼이 이 값에서 안정적으로 동작)
ros2 launch turtlebot4_viz view_navigation.launch.py namespace:=/robot1
```

- ✅ 성공: 오토 맵이 보이고 로봇이 도크 (0,0) 근처에 보임. 🔴 **`2D Pose Estimate`는 누르지 말 것.**
- RViz **Nav2 패널의 `Cancel` 버튼 위치**를 미리 확인.
- ⚠️ 맵이나 로봇이 안 보이면 Claude에게 화면을 알림 (이 터미널만 `export ROS_SUPER_CLIENT=True`로 바꿔 재시도하는 대안이 있음).

---

# [터미널 4] — 웹캠 노드 (car·dummy는 경기장에 이미 있음)

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
ros2 run detection_alert webcam_detector --cam 5 --no-show \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_detector.txt
# ⚠️ <<< 5를 1-3에서 확인한 번호로 바꿀 것
```

- ✅ 성공: `rate=15.0Hz`, `fps=15.0`, `🚨 CAR ALERT ON`, `dets[car=…, dummy=…]`

---

# [터미널 5] — car_locator

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
ros2 run detection_alert car_locator \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_locator.txt
```

- ✅ 성공: `📍 car_point #1: x=… y=… (처음)` 줄 (car가 이미 보이므로 곧바로 나옴)
- 이 좌표가 **로봇이 향할 목표**다. 숫자를 적어 둘 것.

---

# [터미널 6] — rosbag 기록 (한 번만, `amr_goto_car` 실행 전에)

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
ros2 bag record -o ~/ROKEY_mP4_A1/nav/result_nav/bag_nav/bag_$(date +%y%m%d_%H%M%S)_g10 \
  /robot1/dock_status /robot1/amcl_pose /robot1/initialpose /robot1/cmd_vel /robot1/odom \
  /robot1/plan /robot1/tf /robot1/tf_static \
  /robot1/navigate_to_pose/_action/status /robot1/navigate_to_pose/_action/feedback \
  /robot1/undock/_action/status /robot1/goto_arrived /robot1/car_point \
  /webcam/car_point /webcam/car_point_raw /webcam/car_alert /webcam/detections \
  /webcam/image/compressed \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_bag.txt
```

- ✅ 성공: `Subscribed to topic '/robot1/dock_status'` 등. 🔴 한 번만 실행.

---

# [터미널 7] — 🔴 필수: amr_goto_car 실행 (로봇이 움직임)

> 시작 전 체크 (모두 ✅): [터미널 1] `Managed nodes are active` / [터미널 2] `Managed nodes are active` / [터미널 8] `amcl_pose ≈ (0,0)`, `is_docked: true` / [터미널 5] `car_point #1` / [터미널 6] 기록 중 / 로봇 도크 위 / **E-Stop을 손에 듦** / 로봇 앞 경로에 사람·물건 없음

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
export ROS_SUPER_CLIENT=False   # 🔴 노드를 띄우는 터미널
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
ros2 run amr_goto amr_goto_car --ros-args -r __ns:=/robot1 \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_amr_goto.txt
```

- ✅ 성공 (순서대로 나옴, 1~2분):
  1. `Publishing Initial Pose` 후 `Setting initial pose …` 가 짧게 여러 번 (소음, 정상)
  2. `Nav2 is ready for use!` ← 🔴 **이 줄이 20초 안에 안 나오면** 로봇이 움직이기 전이니 `Ctrl+C` 하고 [터미널 2]를 확인 후 Claude에게
  3. `Waiting for car point on /webcam/car_point` → 곧바로 `Car point received: (x, y)` (이미 car가 보이므로)
  4. 언도킹 (로봇이 도크에서 후진해 내려옴)
  5. `Goal (x, y), yaw …` (`No path from Nav2 -> use straight line`이 나오면 경로를 못 받은 것)
  6. 로봇이 car 쪽으로 이동 (RViz에서 확인)
  7. `Arrived 1.2 m before the car -> published goto_arrived`
- 🔴 위험하면 즉시 **E-Stop** 또는 RViz **Cancel**.
- ⚠️ `Undock failed`가 나오면 **로봇이 실제로 도크에서 내려왔는지 눈으로 확인**하고 Claude에게 알림 (이번에 5초 대기로 고쳤으므로 다시 나오면 다른 원인).
- ⚠️ `Move failed -> retry`가 나오면 그 화면과 RViz 화면(비용 지도)을 Claude에게.

## 도착 후 확인

| 확인 | 기대 |
|---|---|
| 로봇이 car에서 몇 m 앞에 멈췄나 (줄자·눈대중) | 약 **1.2 m** |
| `Goal (x, y)`의 car 좌표 | [터미널 5]의 `car_point` 좌표와 같음 |
| 로봇이 car를 바라보는 방향인가 | 예 (yaw가 car 쪽) |

---

# 끝내기 (🔴 순서대로)

1. 로봇이 움직이는 중이면 RViz **Cancel**, 완전히 멈춘 것을 확인
2. [터미널 7] `Ctrl+C` (🔴 이것만으로 로봇은 안 멈춤)
3. [터미널 6] `Ctrl+C` (bag 정지)
4. [터미널 5], [터미널 4] `Ctrl+C`
5. 로봇을 **손으로 도크에 올려 둔다.** (자동 도킹은 멀리서 하면 다른 팀 도크로 갈 수 있음)
6. [터미널 3], [터미널 2], [터미널 1] `Ctrl+C`
7. 🔴 카메라 이동 재확인:

```bash
source ~/venvs/rokey_venv/bin/activate
source /etc/turtlebot4_discovery/setup.bash   # ROS + 도메인 1 + discovery server
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
ros2 run detection_alert check_camera --cam 5 \
  2>&1 | tee -i ~/ROKEY_mP4_A1/nav/result_nav/log_nav/log_$(date +%y%m%d_%H%M%S)_g10_check_after.txt
# ⚠️ <<< 5를 1-3에서 확인한 번호로 바꿀 것
```

- ✅ `✅`면 측정 유효. 🔴 `❌`면 시험 중 카메라가 움직인 것 → 결과를 그대로 쓰지 말고 Claude에게.

---

## 자주 나는 문제

| 증상 | 원인 | 조치 |
|---|---|---|
| Nav2가 `Aborting bringup` | ① 노드 터미널에 `export ROS_SUPER_CLIENT=False`를 안 넣음 ② 초기 위치 전에 Nav2를 켬 | 두 가지 확인 후 [터미널 2]만 `Ctrl+C` → 8-1을 다시 → Nav2 재실행 |
| `amr_goto_car`가 `Nav2 is ready for use!` 전에 멈춤 | Nav2가 active가 아님 | [터미널 2]에 `Managed nodes are active`가 있는지. 없으면 Claude에게 |
| `amr_goto_car`가 아무 줄도 안 내고 멈춤 | `/robot1/dock_status`를 못 받음 | [터미널 8] 8-2 결과 확인. `export ROS_SUPER_CLIENT=False`가 맞게 들어갔는지 |
| `Not on the dock` | 로봇이 도크 위가 아님 | 손으로 도크에 올림 |
| `ros2: 명령을 찾을 수 없습니다` | 그 터미널에 ROS 환경이 없음 | 첫 두 줄 실행 (`which ros2`) |
| `ros2 topic list`에 `/robot1`이 안 보임 | 확인 터미널에 `ROS_SUPER_CLIENT=False`를 넣음 | CLI 확인 터미널은 그 줄을 넣지 말 것 (`unset ROS_SUPER_CLIENT` 후 `source /etc/turtlebot4_discovery/setup.bash`) |
| RViz에 맵·로봇이 안 보임 | super client 설정 차이 | Claude에게 화면. 대안: RViz 터미널만 `ROS_SUPER_CLIENT=True` |
| 로봇 위치가 RViz 맵과 안 맞음 | 도크 위치가 (0,0) NORTH가 아님 | 사진·RViz 화면을 Claude에게 (코드는 고치지 말 것) |

## 끝나면

- Claude에게 **"가이던스 10 실행했음"** → `*_g10_*` 로그와 bag(`*_g10`)을 읽고 정리한다. 이슈가 났다면 **어느 줄에서 멈췄는지**(T7 마지막 줄)를 함께 알릴 것.
- Claude가 볼 것: Nav2 기동 성공 여부, `amr_goto_car` 로그 순서, `dock_status` 변화(언도킹 시각), 목표 좌표와 `car_point` 일치, 로봇 실제 경로·정지 거리(1.2 m).
