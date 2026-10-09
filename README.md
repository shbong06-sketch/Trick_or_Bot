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
source /opt/ros/jazzy/setup.bash
cd ~/cobot4_ws/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 **http://<서버 IP>:8000** → GAME START → Level 1 → 게임 시작 → **Enter**

조작: **W/S** 전진·후진, **A/D** 회전, **M** 소리, **G** 개발 정보

## 처음 연결할 때 확인

`backend/config/robot.yaml`의 토픽 값이 실제 로봇과 같아야 합니다.

```bash
ros2 topic info -v /robot2/cmd_vel                    # 타입(Twist/TwistStamped) → cmd_vel_type
ros2 topic list | grep -E '/robot[12]/(tf|oakd)'      # TF·영상 토픽 이름 → tf_topic, image_topic
```

## 설정

- `backend/config/level1.yaml`: 제한 시간, 사탕·시작 위치·탈출문 좌표
- 좌표 찍기: `cd backend && .venv/bin/python tools/pick_candies.py` (`--start`, `--gate`)
- 설정을 바꾸면 게임 서버를 재시작하세요.
