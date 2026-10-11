# Trick_or_Bot — Pumpkin Run

웹에서 펌킨 로봇(/robot2)을 WASD로 조작해 부우 로봇(/robot1)을 피해 사탕 3개를 모으고 탈출하는 게임.

## 설치 (처음 한 번)

```bash
cd ~/cobot4_ws/backend
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

cd ~/cobot4_ws/frontend
npm ci
npm run build
```

## 실행

로봇 두 대가 켜져 있고, 같은 ROS 네트워크에서 토픽이 보이는 상태에서:

```bash
# 처음 한 번 + ros2_ws 코드를 바꿨을 때
source /opt/ros/jazzy/setup.bash
cd ~/cobot4_ws/ros2_ws && colcon build --packages-select tob_interfaces tob_game tob_control tob_safety

# ROS 노드 (터미널마다 source /opt/ros/jazzy/setup.bash && source ~/cobot4_ws/ros2_ws/install/setup.bash)
ros2 run tob_game game_manager                                  # 게임 상태 /tob/game/state
ros2 run tob_control pumpkin_controller --ros-args \
  --params-file ~/cobot4_ws/ros2_ws/install/tob_control/share/tob_control/config/control.yaml
ros2 run tob_safety velocity_gate --ros-args -r __node:=pumpkin_velocity_gate \
  --params-file ~/cobot4_ws/ros2_ws/install/tob_safety/share/tob_safety/config/safety.yaml

# 게임 서버
cd ~/cobot4_ws/backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

게임 서버는 `/robot2/cmd_vel`에 직접 발행하지 않는다. 키보드 입력은 `/tob/pumpkin/cmd_request` → `pumpkin_controller`(game_manager가 RUNNING일 때만) → `velocity_gate` → `/robot2/cmd_vel`을 거친다.
통합 launch는 이후에 만든다.

브라우저에서 **http://<서버 IP>:8000** → GAME START → Level 1 → 게임 시작 → **Enter**

조작: **W/S** 전진·후진, **A/D** 회전, **M** 소리, **G** 개발 정보

## 처음 연결할 때 확인

`backend/config/robot.yaml`과 `ros2_ws/src/tob_safety/config/safety.yaml`(`output_*`)의 토픽 값이 실제 로봇과 같아야 합니다.

```bash
ros2 topic info -v /robot2/cmd_vel                    # 타입(Twist/TwistStamped) → safety.yaml output_stamped
ros2 topic list | grep -E '/robot[12]/(tf|oakd)'      # TF·영상 토픽 이름 → tf_topic, image_topic
```

## 설정

- `backend/config/level1.yaml`: 제한 시간, 사탕·시작 위치·탈출문 좌표
- 좌표 찍기: `cd backend && .venv/bin/python tools/pick_candies.py` (`--start`, `--gate`)
- 설정을 바꾸면 게임 서버를 재시작하세요.
