# Gazebo 시뮬레이션

holloween 맵을 Gazebo 월드로 만들고 TurtleBot4 두 대(/robot1 부우, /robot2 펌킨)를 띄워 실제 로봇 없이 게임을 테스트한다.

## 설치 (처음 한 번)

```bash
sudo apt install ros-jazzy-turtlebot4-simulator ros-jazzy-turtlebot4-navigation
```

## 실행

```bash
# 터미널 1: 시뮬레이터 (Gazebo + 로봇 2대 + 각자 AMCL). 다 뜨는 데 약 40초
source /opt/ros/jazzy/setup.bash
ros2 launch ~/cobot4_ws/simulation/launch/pumpkin_run_sim.launch.py      # 창 없이: headless:=true

# 터미널 2~4: game_manager, pumpkin_controller, velocity_gate (README.md의 ros2 run 명령에 아래 인자 추가)
#   모두: -p use_sim_time:=true      velocity_gate만: -p output_stamped:=true

# 터미널 5: 게임 서버 (시뮬레이터용 설정)
source /opt/ros/jazzy/setup.bash
cd ~/cobot4_ws/backend
ROBOT_CONFIG=robot_sim.yaml .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저: `http://localhost:8000` (frontend를 `npm run build` 해 둔 경우) 또는 `npm run dev` 후 `http://localhost:5173`.

- 시작 위치는 `backend/config/level1.yaml`의 `pumpkin_start`, `boo_start`
- 맵·좌표를 바꾸면 월드를 다시 만든다: `backend/.venv/bin/python simulation/tools/map_to_world.py`
- 월드 바닥의 초록 원 = 사탕 자리, 보라 원 = 탈출문·문 앞 구역 (AR이 맞는지 보는 용도, 충돌 없음)
- 종료는 터미널 1에서 Ctrl+C (Gazebo 창을 닫아도 전체가 같이 꺼짐)

## 실물과 다른 점 (`backend/config/robot_sim.yaml`, cmd_vel 형식은 velocity_gate의 `output_stamped:=true`)

| 항목 | 시뮬레이터 |
| --- | --- |
| cmd_vel | TwistStamped |
| 카메라 | `oakd/rgb/preview` 320×240 (런치가 raw → compressed로 변환), 내부 파라미터는 camera_info에서 |
| 시간 | 시뮬레이션 시간 (`use_sim_time`). 웹의 "영상 지연" 수치는 의미 없음 |

## 런치가 TurtleBot4 패키지를 고쳐 쓰는 곳

`/opt` 원본은 그대로 두고, 고친 사본을 `$XDG_RUNTIME_DIR/pumpkin_run_overlay`에 만들어 먼저 찾게 한다 (`OVERLAY_PATCHES`).

- 센서 시스템을 로봇이 아니라 월드에서 한 번만 불러옴 → 로봇 두 대에서 Gazebo가 죽던 문제 (Ogre ItemIdentityException)
- 바닥·근접 IR 센서 62 Hz → 10 Hz → 실시간 비율 0.42 → 약 0.7
- Create3 반사 동작 끔 → 실시간보다 느린 시뮬레이터에서 "끼임" 반사가 계속 후진시켜 조작이 막히던 문제 (실물 로봇은 그대로)
- 도킹 스테이션을 로봇 앞이 아니라 뒤에 둠 (원본은 로봇이 독을 바라보는 도킹 상태로 스폰). 두 로봇 모두 독을 등지고 출발

## 실행이 이상할 때

로봇이 안 움직이고 로그에 `Failed to acquire lock`이 보이면, 이전 실행의 노드가 남아 컨트롤러 등록을 막고 있는 것이다.

```bash
pkill -f /opt/ros/jazzy/lib/ ; pkill -f "gz sim"   # 남은 노드 정리
ros2 daemon stop && fastdds shm clean
```

## 알려진 한계

- 이 PC 기준 실시간의 약 0.7배 속도 → 로봇이 실제보다 느리게 움직인다
- AR 위치: 2.7 m에서는 맞고, 1.2 m에서 약 9 cm 어긋남 (AMCL 위치 추정 오차로 추정, 기준 15 cm 이내)
- 부우는 아직 자율 주행하지 않는다 (부우 파트 노드가 붙어야 함)
