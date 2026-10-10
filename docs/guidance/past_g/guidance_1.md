# guidance_1 — 멀티 로봇 Discovery Server 설정 (서버 PC 1대 + 나머지 클라이언트)

- 작성: 2026-10-08_1655
- 기준 문서: 튜터님 DAY5 **Multi Robot Client Setup** (`docs/ref/notion/tutors/day5-SystemMonitor_MultiRobot/02__Multi Robot Client Setup_.md`)
- 구조: **빅터스 노트북 = 서버 PC**, 나머지 고성능 PC = 클라이언트, TB4 2대 = 클라이언트. **ROS_DOMAIN_ID = 2 (전원 통일)**
- 기록 폴더: `mr/result_mr/{log_mr, bag_mr}` (테마 `mr` = multi robot)

---

## 🔴 꼭 지킬 것 (하나라도 어기면 로봇이 안 보인다)

1. 🔴 **튜터님 문서의 `ROS_DOMAIN_ID=0`을 전부 `2`로 바꿔서 입력한다.** 서버 PC, 클라이언트 PC, **로봇 2대** 모두 2.
2. 🔴 **이 PC(및 같은 `.bashrc` 템플릿을 쓴 PC)는 `~/.bashrc` 195번째 줄 `export ROS_DOMAIN_ID=1`이 `/etc/turtlebot4_discovery/setup.bash`를 덮어쓴다.** 그 줄도 `2`로 고치거나 지워야 한다. (3-3 단계)
3. 🔴 **서버 PC의 Discovery Server 터미널은 로봇을 쓰는 내내 켜 둔다.** 닫으면 모든 ROS 통신이 끊긴다.
4. 🔴 **순서: 서버 PC → 로봇 2대 → 클라이언트 PC → 전체 확인.** 로봇 확인(`nc`)은 서버가 켜져 있어야 성공한다.
5. 🔴 **`ROS_DISCOVERY_SERVER` 앞에 세미콜론(`;`)을 붙이지 않는다.** `;`의 위치가 server ID다. 우리는 서버 ID 0이므로 `<IP>:11811` 그대로 쓴다. (이 PC의 기존 값 `;192.168.107.101:11811;`은 ID 1이라 틀린 값이다.)
6. 🔴 **IP는 점(`.`)으로 입력한다.** 튜터님 로봇 화면 예시에 `172,30.1.60`처럼 쉼표가 찍혀 있다. 따라 하지 말 것.
7. 🔴 **튜터님 DAY5의 나머지 두 문서(Standard Setup, Custom Discovery Setup)는 이 방식의 대안이다. 이 가이드를 따를 때는 실행하지 않는다.** 특히 `configure_discovery.sh`를 실행하면 설정이 덮어써진다.
8. 🔴 **로봇 터미널에서는 `turtlebot4-setup` 메뉴와 확인 명령만 쓴다.** 로봇의 설정 파일을 직접 고치지 않는다. (튜터님 문서: Create 3 설정까지 함께 맞춰 주는 건 이 메뉴뿐)

---

## ⚠️ 먼저 정해서 아래 단계에 직접 써 넣을 값

| 값 | 내용 | 어느 단계에 넣는가 |
|---|---|---|
| ⚠️ **`<서버IP>`** | **빅터스 노트북의 IP** (Wi-Fi 인터페이스 주소). 1-1에서 나온 값 | **1-3, 1-6, 2-4, 2-7, 3-2, 3-6** 코드 블록 전부 (2-6, 1-7, 3-5는 이 값과 같은지 대조) |
| `ROS_DOMAIN_ID` | **2** | 1-3, 2-3, 3-2, 3-3 (확인: 1-7, 2-6, 3-5) |
| 서버 ID / 포트 | **0 / 11811** | 1-6, 2-4 (고정, 바꾸지 않는다) |

> 서버 IP는 **공유기가 바꾸지 못하게** 고정(DHCP 예약 또는 고정 IP)하는 것을 권한다. IP가 바뀌면 서버·로봇·클라이언트를 전부 다시 설정해야 한다. (튜터님 문서에는 없는 우리 쪽 권고)

---

## 0. 준비 (이 PC)

### 0-1. 🔴 로그 폴더 확인 (이미 만들어 두었음)

```bash
ls ~/Trick_or_Bot/mr/result_mr/log_mr
```

- ✅ 에러 없이 실행되면 됨(비어 있어도 정상).
- 다른 PC·로봇에서는 `mkdir -p ~/mr_log` 후 같은 형식으로 `~/mr_log/`에 저장한다. 끝나면 파일을 이 PC의 `mr/result_mr/log_mr/`로 복사하거나 내용을 붙여 넣어 달라고 하면 된다.

---

## 1. 서버 PC (빅터스 노트북)에서

> 🔴 이 PC에서만 실행한다. 로봇 터미널이 아니다.

### 1-1. 서버 IP 확인

```bash
ip -4 -br addr | grep -v '^lo'
```

- ✅ Wi-Fi 인터페이스(`wlo1`, `wlp…`) 줄의 `192.168.x.x`가 **`<서버IP>`**다. 메모해 둔다. `tailscale0`의 `100.x.x.x`는 쓰지 않는다.

### 1-2. 설정 파일 열기

```bash
sudo nano /etc/turtlebot4_discovery/setup.bash
```

- 파일이 없으면 `ls /etc/turtlebot4_discovery/`로 확인하고 멈춘 뒤 알려 준다.

### 1-3. 🔴 필수: 내용을 아래로 바꾸고 저장 (Ctrl+O, Enter, Ctrl+X)

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=2                                  # 🔴 0이 아니라 2
export ROS_DISCOVERY_SERVER=<서버IP>:11811              # ⚠️ <<< 1-1의 빅터스 IP로 바꿀 것. 앞에 ; 붙이지 말 것
export ROS_LOCALHOST_ONLY=0
export ROS_SUPER_CLIENT=True
```

### 1-4. 🔴 필수: `~/.bashrc`에 `ROS_DOMAIN_ID`를 덮어쓰는 줄이 없는지 확인

```bash
grep -n "ROS_DOMAIN_ID\|ROS_DISCOVERY_SERVER" ~/.bashrc
```

- ✅ `~/.bashrc`에 `export ROS_DOMAIN_ID=…` 줄이 **나오지 않아야** 한다.
- ⚠️ 나온다면 그 줄을 `export ROS_DOMAIN_ID=2`로 고치거나 지운다. (이 PC는 195번째 줄이 해당. 3-3 참고)

### 1-5. fastdds 도구 확인

```bash
source ~/.bashrc
which -a fastdds
```

- ✅ 경로가 한 줄 이상 나오면 된다. 튜터님 문서는 `sudo apt install -y fastdds-tools`로 설치하라고 한다.
- 우리 쪽 PC는 `/opt/ros/jazzy/bin/fastdds`가 이미 있고 `fastdds-tools` 패키지는 없다. **아무것도 안 나올 때만** 설치한다.

```bash
sudo apt update && sudo apt install -y fastdds-tools   # which -a fastdds 결과가 비어 있을 때만 실행
```

### 1-6. 🔴 필수: Discovery Server 실행 (이 터미널은 닫지 않는다)

```bash
mkdir -p ~/mr_log
fastdds discovery --server-id 0 --ip-address <서버IP> --port 11811 2>&1 | tee -i ~/mr_log/log_$(date +%y%m%d_%H%M%S)_server.txt
# ⚠️ <<< <서버IP>를 1-1의 빅터스 IP로 바꿀 것
```

- ✅ 서버가 뜬 채로 터미널이 멈춰 있으면 정상이다.
- 튜터님 문서는 `/usr/bin/fastdds`로 적혀 있다. 1-5에서 나온 경로가 다르면 그 경로로 실행해도 된다.

---

**(새 터미널을 연다 — 서버 PC)**

### 1-7. 서버 환경 확인

```bash
source ~/.bashrc
env | grep -E 'RMW_IMPLEMENTATION|ROS_DOMAIN_ID|ROS_DISCOVERY_SERVER|ROS_LOCALHOST_ONLY|ROS_SUPER_CLIENT' 2>&1 | tee -i ~/mr_log/log_$(date +%y%m%d_%H%M%S)_server_env.txt
```

- ✅ 다섯 줄이 모두 나와야 한다: `ROS_SUPER_CLIENT=True`, **`ROS_DOMAIN_ID=2`**, `ROS_LOCALHOST_ONLY=0`, `ROS_DISCOVERY_SERVER=<서버IP>:11811`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`
- ⚠️ **`ROS_DOMAIN_ID`가 2가 아니거나, `ROS_DISCOVERY_SERVER` 앞에 `;`가 있으면 다음 단계로 가지 말 것.** 1-3, 1-4로 돌아간다.

### 1-8. 서버가 포트를 열었는지 확인

```bash
ss -lunp | grep 11811 2>&1 | tee -i ~/mr_log/log_$(date +%y%m%d_%H%M%S)_server_port.txt
```

- ✅ `0.0.0.0:11811` 줄에 `fast-discovery-…`가 나와야 한다.
- ⚠️ 아무것도 안 나오면 다음 단계로 가지 말 것. 1-6의 터미널이 켜져 있는지 확인한다.

### 1-9. ROS 데몬 재시작

```bash
ros2 daemon stop
ros2 daemon start
```

- ✅ 에러 없이 끝나면 된다.

---

## 2. 로봇 TB4 2대 — **각 로봇마다 2-1부터 2-9를 따로 한다**

> 🔴 로봇에 SSH로 접속한 터미널에서 실행한다. 로봇 1대를 끝까지 한 뒤 다음 로봇으로 간다.
> 🔴 두 로봇이 같은 공유기(서버 PC와 같은 네트워크)에 붙어 있어야 한다. 아니라면 2-1 전에 튜터님 **Multi Robot Standard Setup**의 "Robot Connection setup"(1~6번)만 따라 Wi-Fi를 바꾼다. 이 문서의 `configure_discovery.sh`는 실행하지 않는다.

### 2-1. 로봇에 SSH 접속

```bash
ssh ubuntu@<로봇IP>
# ⚠️ <<< <로봇IP>는 로봇 LED 화면에서 확인한 주소. 로봇 1을 먼저, 끝나면 로봇 2
```

- ✅ `ubuntu@turtlebot4:~$` 프롬프트가 나온다.

### 2-2. 설정 메뉴 열기

```bash
turtlebot4-setup
```

- ✅ `ROS Setup / Wi-Fi Setup / … / Apply Settings` 메뉴가 나온다.

### 2-3. 🔴 필수: `ROS Setup`에서 `ROS_DOMAIN_ID`를 2로 바꾼다

- `ROS Setup`(Enter) → **ROS Domain ID 항목을 `2`로 변경** → Save
- 튜터님 문서에는 이 단계가 적혀 있지 않다(예시가 0이라 기본값 그대로 쓴 것으로 보인다). **우리는 2로 통일하므로 반드시 바꾼다.**
- 같은 `ROS Setup` 화면에서 **namespace가 로봇마다 다른지** 본다(로봇 1 = `/robot1`, 로봇 2 = `/robot2`). 같으면 토픽이 섞인다. (SRD SR-005)

### 2-4. 🔴 필수: `Discovery Server`를 아래 값으로 바꾼다

- `ROS Setup` → `Discovery Server`(Enter)

| 항목 | 값 |
|---|---|
| Enabled | **True** |
| Onboard Server (Port / Server ID) | **바꾸지 않는다** (로봇마다 ID가 자동으로 다르게 들어 있다) |
| Offboard Server – IP | ⚠️ **`<서버IP>`** (빅터스 IP, **점으로**, 포트 없이 IP만) <<< 직접 써 넣을 것 |
| Offboard Server – Port | **11811** |
| Offboard Server – Server ID | **0** |

- `Save` Enter → ESC 두 번 → 메인 메뉴의 **`Apply Settings`** Enter

### 2-5. 로봇이 다시 준비될 때까지 기다린다

- ✅ 로봇 LED가 **모두 밝혀질 때까지** 기다린다. (그 전에 다음 단계로 가지 말 것)

### 2-6. 설정 파일 내용 확인

```bash
cat /etc/turtlebot4/setup.bash
```

- ✅ 아래 두 줄이 맞아야 한다 (나머지 줄은 로봇마다 다르다).
  - `export ROS_DOMAIN_ID="2"`
  - `export ROS_DISCOVERY_SERVER="<서버IP>:11811;…;127.0.0.1:11811;"` ← **맨 앞이 서버(ID 0)**
- ⚠️ 맞지 않으면 다음 단계로 가지 말 것. 2-3, 2-4로 돌아간다.

### 2-7. 로봇에서 서버로 통신되는지 확인

```bash
mkdir -p ~/mr_log
nc -vzu <서버IP> 11811 2>&1 | tee -i ~/mr_log/log_$(date +%y%m%d_%H%M%S)_robot_nc.txt
# ⚠️ <<< <서버IP>를 1-1의 빅터스 IP로 바꿀 것
```

- ✅ `succeeded`가 나와야 한다.
- ⚠️ 안 나오면 다음 단계로 가지 말 것. 서버 PC에서 1-8(포트 열림)을 확인하고, 서버 PC의 방화벽이 UDP 11811을 막는지(`sudo ufw status`)도 본다.

### 2-8. onboard server가 꺼져 있는지 확인

```bash
systemctl status discovery.service --no-pager 2>&1 | tee -i ~/mr_log/log_$(date +%y%m%d_%H%M%S)_robot_discovery.txt
ps aux | grep -E "fastdds.*discovery|fastdds.py discovery|fast-discovery-server" | grep -v grep
```

- ✅ 튜터님 문서의 확인 항목이다. 서비스가 `inactive`이거나 해당 프로세스가 보이지 않으면 정상으로 본다.
- ⚠️ 서비스가 `active (running)`이면 다음 단계로 가지 말고 그 출력을 그대로 알려 준다.

### 2-9. 서비스 재시작

```bash
turtlebot4-service-restart
turtlebot4-daemon-restart
```

- ✅ 에러 없이 끝나면 된다. 이제 **로봇 2로 이동**해 2-1부터 반복한다.

---

## 3. 클라이언트 PC (이 PC와 나머지 고성능 PC마다 3-1부터 3-6)

> 🔴 **로봇이 아닌 PC**에서 실행한다. PC마다 같은 작업을 한다. (술래 제어 PC, 도망자 제어 PC, CCTV PC)

### 3-1. 기존 설정 백업

```bash
sudo cp /etc/turtlebot4_discovery/setup.bash /etc/turtlebot4_discovery/setup.bash.bak_$(date +%y%m%d_%H%M)
```

- ✅ 에러 없이 끝나면 된다. (이 PC의 현재 값: 도메인 1, `;192.168.107.101:11811;`)

### 3-2. 🔴 필수: 설정 파일 수정

```bash
sudo nano /etc/turtlebot4_discovery/setup.bash
```

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
[ -t 0 ] && export ROS_SUPER_CLIENT=True || export ROS_SUPER_CLIENT=False   # 이 줄은 이미 있으면 그대로 둔다
export ROS_DOMAIN_ID=2                                  # 🔴 0이 아니라 2
export ROS_DISCOVERY_SERVER=<서버IP>:11811              # ⚠️ <<< 1-1의 빅터스 IP로 바꿀 것. 앞에 ; 붙이지 말 것
export ROS_LOCALHOST_ONLY=0
```

- 이 PC의 파일에는 `ROS_SUPER_CLIENT`가 "터미널에서만 True"인 줄이 이미 있다. 튜터님 예시(항상 True)와 달라도 **그대로 둔다.** 터미널에서 `ros2 topic list`를 쓰는 데는 True가 적용된다.

### 3-3. 🔴 필수: `~/.bashrc`의 `ROS_DOMAIN_ID` 덮어쓰기 줄 수정

```bash
sed -n 128,140p ~/.bashrc
sed -n 193,196p ~/.bashrc
```

- ✅ 131번째 줄 근처에 `source /etc/turtlebot4_discovery/setup.bash`가 있고, **195번째 줄 근처에 `export ROS_DOMAIN_ID=1`이 있으면 그 줄이 위 파일을 덮어쓴다.**
- 195번째 줄을 아래로 고친다. (줄 번호가 다르면 `grep -n "ROS_DOMAIN_ID" ~/.bashrc`로 찾는다)

```bash
sed -i 's/^export ROS_DOMAIN_ID=1$/export ROS_DOMAIN_ID=2/' ~/.bashrc
grep -n "ROS_DOMAIN_ID" ~/.bashrc
```

- ✅ 마지막 줄에 `export ROS_DOMAIN_ID=2`만 나오고 `=1`은 나오지 않아야 한다.

### 3-4. 🔴 필수: 열려 있는 **모든 터미널**에 적용

```bash
source ~/.bashrc
ros2 daemon stop
ros2 daemon start
```

- ✅ 에러 없이 끝나면 된다. **새로 연 터미널은 자동 적용되지만 이미 켜져 있던 터미널과 이미 실행 중이던 노드(Nav2, launch 등)는 종료 후 다시 실행해야 한다.**

### 3-5. 환경 확인 (로그 기록)

```bash
env | grep -E 'RMW_IMPLEMENTATION|ROS_DOMAIN_ID|ROS_DISCOVERY_SERVER|ROS_LOCALHOST_ONLY|ROS_SUPER_CLIENT' 2>&1 | tee -i ~/Trick_or_Bot/mr/result_mr/log_mr/log_$(date +%y%m%d_%H%M%S)_client_env.txt
```

- ✅ 다섯 줄이 나와야 한다: `ROS_SUPER_CLIENT=True`, **`ROS_DOMAIN_ID=2`**, `ROS_LOCALHOST_ONLY=0`, `ROS_DISCOVERY_SERVER=<서버IP>:11811`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`
- ⚠️ **`ROS_DOMAIN_ID`가 2가 아니거나 `ROS_DISCOVERY_SERVER` 앞에 `;`가 있으면 다음 단계로 가지 말 것.** 3-2, 3-3으로 돌아간다.
- (튜터님 문서의 같은 명령에는 `-E'RMW…`처럼 `-E` 뒤에 공백이 없는 오타가 있다. 위 명령을 쓴다.)

### 3-6. 서버 연결 확인

```bash
nc -vzu <서버IP> 11811 2>&1 | tee -i ~/Trick_or_Bot/mr/result_mr/log_mr/log_$(date +%y%m%d_%H%M%S)_client_nc.txt
# ⚠️ <<< <서버IP>를 1-1의 빅터스 IP로 바꿀 것
```

- ✅ `succeeded`가 나와야 한다.

---

## 4. 전체 확인 (서버 PC와 모든 클라이언트 PC에서)

### 4-1. 🔴 필수: 두 로봇의 토픽이 모두 보이는지 확인

```bash
ros2 topic list 2>&1 | tee -i ~/Trick_or_Bot/mr/result_mr/log_mr/log_$(date +%y%m%d_%H%M%S)_topics_1.txt
ros2 topic list 2>&1 | tee -i ~/Trick_or_Bot/mr/result_mr/log_mr/log_$(date +%y%m%d_%H%M%S)_topics_2.txt
```

- 🔴 **같은 명령을 두 번 실행한다.** 처음에는 데몬이 토픽을 모으는 중이라 바로 안 나올 수 있다. (튜터님 문서)
- ✅ 두 번째 결과에 **`/robot1/…`과 `/robot2/…` 토픽이 둘 다** 있어야 한다.
- ⚠️ 한 로봇만 보이거나 둘 다 안 보이면 **통합 단계로 가지 말 것.** 서버 PC의 1-6 터미널이 켜져 있는지, 모든 곳의 `ROS_DOMAIN_ID`가 2인지(1-7, 2-6, 3-5)부터 확인한다.

### 4-2. 로봇 움직임 확인 (튜터님 Standard Setup "테스트")

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r /cmd_vel:=/robot1/cmd_vel
```

- ✅ 로봇 1이 움직인다. Ctrl+C로 끄고 `/robot2/cmd_vel`로 바꿔 로봇 2도 확인한다.
- ⚠️ 움직일 공간을 먼저 확보한다. 안 움직이면 `ros2 topic list | grep cmd_vel`로 토픽 이름을 확인한다.

---

## 5. 끝난 뒤 알려 줄 것

아래만 알려 주면 로그를 읽고 다음 단계(SRD/SDD의 환경 값 확정, `dev_env.md` 갱신)를 진행한다.

- 어느 단계까지 성공했는지(예: "4-1까지 성공, 로봇 2만 안 보임")
- 로그 파일 위치: 이 PC `~/Trick_or_Bot/mr/result_mr/log_mr/`, 다른 PC·로봇 `~/mr_log/` (복사하거나 내용을 붙여 넣기)
- `<서버IP>`와 로봇 IP 2개 (확정되면 `dev_env.md`에 기록)

---

## 참고: 튜터님 문서와 달라진 점 (한눈에)

| 튜터님 문서 | 우리 설정 |
|---|---|
| `ROS_DOMAIN_ID=0` | **2** |
| 서버 PC = PC3(모니터 PC) | **빅터스 노트북** |
| 클라이언트 = PC1, PC2 | 나머지 고성능 PC 전부(술래 제어, 도망자 제어, CCTV) |
| 로봇의 도메인 ID 변경 단계 없음 | **2-3에서 로봇 2대도 2로 변경** |
| `ROS_SUPER_CLIENT=True` 고정 | 이 PC는 터미널에서만 True(기존 줄 유지) |
| 확인 명령 `grep -E'…` (공백 없음) | `grep -E '…'` |
| 서버 실행 `/usr/bin/fastdds …` | `which -a fastdds`로 나온 경로 (`/opt/ros/jazzy/bin/fastdds` 가능) |
