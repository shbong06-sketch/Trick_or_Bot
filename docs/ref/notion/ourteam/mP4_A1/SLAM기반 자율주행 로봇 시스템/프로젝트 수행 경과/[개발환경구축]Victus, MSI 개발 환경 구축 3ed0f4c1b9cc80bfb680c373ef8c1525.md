# [개발환경구축]Victus, MSI 개발 환경 구축

관련 이슈·To-do: [개발환경구축]설정 및 장비 확인 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5D%EC%84%A4%EC%A0%95%20%EB%B0%8F%20%EC%9E%A5%EB%B9%84%20%ED%99%95%EC%9D%B8%203ec0f4c1b9cc8011a9b0de27fed4fdd7.md)
날짜: 2026년 10월 1일
기록일: 2026년 10월 1일
담당자: 09180_이원호, sj b
마지막 수정: 2026년 10월 5일 오후 8:48
분류: 구현
분야: HW, ROS2
생성일: 2026년 10월 2일 오전 9:26
작성 상태: 정리 완료

# PC 환경 설정

### 네트워크 SSID

| 조 | 와이파이 SSID  | 비밀번호 |
| --- | --- | --- |
| 기본 | Rokey_Guest | `rokey1234` |
| 1, 2 | turtle**07** | `rokey12345` |
| 3, 4 | turtle**08** | `rokey12345` |
| 5, 6 | turtle**09** | `rokey12345` |

### 노트북 비밀번호

rokey1234

### 시스템 기본 정보 확인

```bash
# === OS & GPU Driver Setup ===
# with ubuntu 24.04 installed
# Check Ubuntu version

lsb_release -a
```

### 패키지 리스트 업데이트

```bash
sudo apt update
```

```bash
sudo apt upgrade
```

### Nvidia GPU 드라이버 설치

```bash
# Add NVIDIA graphics drivers PPA
sudo add-apt-repository ppa:graphics-drivers/ppa -y
sudo apt-get update
```

아래 둘 중 하나만 수행

- Victus
    
    ```bash
    # For Victus
    sudo apt-get install -y nvidia-driver-570
    echo "Reboot required to apply NVIDIA driver changes."
    # nvidia driver 버전이 자동으로 맞춰지므로, 실제로는 570이 아닌 580 버전으로 설치된다. 
    ```
    
    ```bash
    sudo reboot #execute if gpu driver is newly installed by above
    ```
    
- MSI
    
    ```bash
    # For **MSI** Pulse 16 machine
    sudo apt install nvidia-driver-575
    #   while installing you will see a prompt for the MOK setup, select ok; setup password and select ok
    # nvidia driver 버전이 자동으로 맞춰지므로, 실제로는 575가 아닌 580 버전으로 설치된다.
    ```
    
    ```bash
    sudo reboot
    # while booting, when prompted select enroll MOK, press continue, press yes, enter password to complete the reboot
    
    # optional
    #   once rebooted, reboot again
    #   while booting, press DEL/F2/F12 to enter BIOS, goto security and set Secure Boot to Disabled 
    #   after successful boot then reboot again
    ```
    

### 시스템 확인

```bash
# View CPU details
cat /proc/cpuinfo
# Check NVIDIA GPU status (580 버전 확인)
nvidia-smi
```

### GPU 설정 (NVIDIA GPU만 해당)

1. NVIDIA XServer Setting GUI 를 클릭
    
    ![image (1).webp](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image_(1).webp)
    

1. PRIME Profiles > NVIDIA(Performance Mode) 선택
    
    Gazebo 실행시 그래픽 엔진 돌리는데 필요함 
    
    ![image.webp](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image.webp)
    
2. PC를 재부팅하여 Performance Mode가 적용되도록 한다. 
    
    ```python
    sudo reboot
    ```
    

## 💡 ROS2 Installation

### **Ubuntu Locale 설정 확인 및 UTF-8 지원:**

터미널을 열고 다음 명령어를 입력하여 Ubuntu Locale이 UTF-8을 지원하는지 확인하고 설정합니다.

```bash
#Check current locale
locale  # check for UTF-8

# Update package list
sudo apt update
```

```bash
sudo apt install locales
# Generate and configure locale
sudo locale-gen en_US en_US.UTF-8
# Generate and configure locale
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Verify locale settings
locale  # verify settings
```

![locale 설정 후 출력](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image%201.webp)

locale 설정 후 출력

### **ROS 2 apt 저장소 설정:**

시스템에 ROS 2 apt 저장소를 추가.

먼저 [Ubuntu Universe 저장소가](https://help.ubuntu.com/community/Repositories/Ubuntu) 활성화되어 있는지 확인하세요.

```bash
# === Development Tools Installation ===
# Install required software-properties-common package
sudo apt install software-properties-common
# Add 'universe' repository
sudo add-apt-repository universe
```

ROS2 apt 저장소를 등록하여, apt가 `ros-jazzy-*` 를 찾을 수 있게 합니다.

```bash
sudo apt update
```

```bash
sudo apt install curl -y
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
sudo apt install -y /tmp/ros2-apt-source.deb
```

### **ROS2 패키지 설치:**

```bash
sudo apt update
```

```bash
sudo apt upgrade
```

```python
# Install ROS2 Jazzy desktop version
sudo apt install -y ros-jazzy-desktop
```

```python
# Install ROS development tools
sudo apt install -y python3-rosdep python3-setuptools
```

```python
# install image compressed-transport plugins
sudo apt install -y ros-jazzy-image-transport-plugins
```

### **other package:**

필수 도구와 추가 패키지를 설치합니다.

```bash
# === Essential software installation ===
#Install Essential Software
# Install basic development tools
sudo apt install -y build-essential git wget cmake gpg neofetch vim htop

#For development:
# Install Python development tools
sudo apt install -y python3-pip python3-venv
```

```bash
#install vscode
# 1) 최신 .deb 다운로드
wget -O /tmp/vscode.deb "https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64"
# 2) 설치 (키 + 저장소 등록까지 자동)
sudo apt install -y /tmp/vscode.deb
```

![다음과 같은 화면이 뜨면 Yes 탭에서 ENTER를 치면 된다.](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode_install_apt_repo_prompt.png)

다음과 같은 화면이 뜨면 Yes 탭에서 ENTER를 치면 된다.

```bash
sudo apt install terminator
```

### Git 설치:

```bash
sudo apt update
```

```bash
sudo apt upgrade
sudo apt install git
```

GitHub에서 사용할 사용자 이름과 이메일을 설정한다.

```bash
git config --global user.name ***<내 GitHub 사용자 이름>***
git config --global user.email ***<내 이메일 주소>***

git config --list # check 
```

 버전 확인

```bash
git --version
```

### VSCode로 Git 강의록 다운받기:

[깃허브 공유 페이지](https://github.com/kimandreas/to_students/tree/main)에 접속해 아래의 방식으로 리포지토리 링크를 복사한다.

![vscode00_copy_repo_url.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode00_copy_repo_url.png)

VSCode에서 복사한 링크를 붙여 넣는다.

![vscode01_clone_repo.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode01_clone_repo.png)

![vscode02_paste_url.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode02_paste_url.png)

리포지토리 대상 폴더를 지정한다. 가급적 폴더 내에 설치하는 걸 권장.

![vscode03_select_folder.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode03_select_folder.png)

잠시 기다리면 강의록 파일 다운로드가 완료된다.

![vscode04_clone_done.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/vscode04_clone_done.png)

### 가상환경 생성:

- 앞으로의 모든 작업은 **venv 안에서** 이뤄진다. venv를 먼저 만든 후 **빌드 도구인 `colcon`을 venv 안에 설치**한다.
- ❗ **왜 colcon을 venv에 설치할까?**
    
    `colcon`이 파이썬 패키지를 빌드하면, **빌드에 사용된 python의 경로가 노드 실행파일 첫 줄(shebang)에 그대로 새겨진다.**
    
    ![shebang](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image_(1)%201.webp)
    
    shebang
    
    시스템 `colcon`은 항상 시스템 python으로 돌기 때문에, 시스템 colcon으로 빌드하면 노드가 시스템 python으로 실행되어 **venv에 설치한 torch를 찾지 못한다.**
    
    따라서, 시스템에 `colcon` 을 설치하지 않고, `venv` 내에만 `colcon` 을 설치해 두면, `colcon` 이 시스템 python이 아닌 venv python으로 빌드된다. 
    

```bash
# 1. venv 생성 (--system-site-packages 필수)
python3 -m venv --system-site-packages ~/venvs/rokey_venv
touch ~/venvs/rokey_venv/COLCON_IGNORE

# --system-site-packages : venv 안에서도 시스템에 깔린 ROS2 패키지(rclpy 등)를 그대로 import 하기 위함
# COLCON_IGNORE          : colcon이 이 폴더를 빌드 대상으로 스캔하지 않게 하는 안전장치
```

- venv를 활성화한 후에는 pip로 설치하는 **패키지들이 모두 venv 환경 내에 설치**된다.

```bash
# 2. venv 활성화 후 colcon 설치
source ~/venvs/rokey_venv/bin/activate
pip install colcon-common-extensions
```

### **환경설정*:***

ROS setup 스크립트를 .bashrc에 추가합니다.

```bash
# ~/.bashrc 끝에 추가
# 순서 중요: venv 활성화 → ROS2(underlay)
echo 'source ~/venvs/rokey_venv/bin/activate' >> ~/.bashrc
echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc

# colcon 탭 자동완성 편의 기능
echo 'source ~/venvs/rokey_venv/share/colcon_argcomplete/hook/colcon-argcomplete.bash' >> ~/.bashrc

```

```bash
# Confirm ROS 2 CLI is installed
source ~/.bashrc
```

### System Monitor 도구 설치:

```bash
# tools for system monitor
pip install flask
sudo apt install sqlite3
sudo apt install sqlitebrowser
```

---

## 💡 설치 확인

### 설치된 패키지 확인:

```bash
### 1. 설치된 패키지 확인:
ros2 pkg list
```

![ros2_pkg_list.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/ros2_pkg_list.png)

### ROS2 버전 확인

```bash
printenv | grep ROS          #ROS_DISTRO=jazzy
```

### Python 버전 확인

```bash
python3 -V         #Python 3.12.XX
```

### VScode 확인

```bash
code --version
```

### venv / colcon 배치 확인

새 터미널을 열면 프롬프트 앞에 `(rokey_venv)`이 보여야 하고, 아래 경로가 맞아야 한다.

```bash
which python3   # → ~/venvs/rokey_venv/bin/python3   (venv)
which colcon    # → ~/venvs/rokey_venv/bin/colcon    (venv)
which rosdep    # → /usr/bin/rosdep               (시스템)
```

## 💡 Restart

```bash
#restart with clean reboot
sudo reboot
```

### 시스템은 현재 날짜 시간일 것!

```bash
date
```

---

### (선택) ROS 삭제

[ROS 삭제 (1)](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/ROS%20%EC%82%AD%EC%A0%9C%20(1)%203ed0f4c1b9cc807a827fc961aa790f3c.md)

---

# Turtlebot4 SW Setup

TurtleBot4의 SLAM 및 Navigation을 실행하기 위해 필요한 패키지를 설치하고, 시뮬레이션 환경을 구성한다.

## 🔑Turtlebot4

## 💡 로봇 환경 구성 및 설치

## 1. 패키지 업데이트 및 기본 패키지 설치

### TurtleBot4 소스코드 설치

- PC 터미널:

```bash
# === Create the TurtleBot4 workspace ===
mkdir -p ~/turtlebot4_ws/src
cd ~/turtlebot4_ws

# === Build the empty workspace once (optional at this stage, can be deferred) ===
colcon build

# Source the environment (can be skipped here since nothing is built yet)
source install/setup.bash
```

```bash
# === Clone TurtleBot4 and related packages ===
cd ~/turtlebot4_ws/src
git clone https://github.com/turtlebot/turtlebot4.git -b jazzy
git clone https://github.com/turtlebot/turtlebot4_simulator.git -b jazzy
git clone https://github.com/turtlebot/turtlebot4_desktop.git -b jazzy
git clone https://github.com/turtlebot/turtlebot4_tutorials.git -b jazzy
git clone https://github.com/robo-friends/m-explore-ros2.git
```

### 의존성 관리도구(rosdep) 초기화

**초기 한 번만 실행**하면 됨

```bash
# === Install dependencies with rosdep ===
cd ~/turtlebot4_ws

# Initialize rosdep if not already initialized
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init
fi

# Update rosdep and install dependencies
rosdep update
```

### 종속성 패키지 설치

```bash
cd ~/turtlebot4_ws
rosdep install --from-path src -yi --rosdistro jazzy
```

- 옵션별 의미
    
    
    | 옵션 | 의미 |
    | --- | --- |
    | `--from-path src` | `src` 폴더 내의 **모든 패키지의 의존성을 확인하고 설치** |
    | `-y` | 설치 시 **사용자 확인(`yes/no`)을 자동으로 `yes` 처리** |
    | `-i` | 이미 설치된 패키지는 **건너뛰고, 누락된 패키지만 설치** |
    | `--rosdistro jazzy` | **Jazzy 버전에 맞는 의존성을 설치** |

### 패키지 보완

- 아래 **bash 파일을 다운로드 후, 명령어 실행**
    
    <aside>
    
    [setup_nav2.sh](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/setup_nav2.sh)
    
    </aside>
    

```python
bash ~/Downloads/setup_nav2.sh
```

### 패키지 빌드

```bash
cd ~/turtlebot4_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install

# 출력: 다음 stderr output 라인은 테스트 지도(.pgm) 다운로드용 wget 진행률 출력 관련이므로 무시한다.
# Summary: 17 packages finished [33.5s]
#  1 package had stderr output: multirobot_map_merge
```

## 2. Gazebo(시뮬레이터) 설치 (필수 X)

ROS2 Jazzy는 modern Gazebo(gz-harmonic)을 쓴다.

```bash
# osrfoundation 저장소 등록
sudo curl https://packages.osrfoundation.org/gazebo.gpg \
  --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
```

```python
# apt로 modern Gazebo 설치
sudo apt-get update
sudo apt-get install -y gz-harmonic
```

```python
# 설치 확인
gz sim --version     # 8.11.xx
```

### 종속성 패키지 설치

```bash
cd ~/turtlebot4_ws
rosdep update
rosdep install --from-path src -yi --rosdistro jazzy
# #All required rosdeps installed successfully
```

```bash
cd ~/turtlebot4_ws/src
```

```bash
#Corrects the known Harmonic/Jazzy issue 
git clone --branch jazzy --depth 1 [https://github.com/iRobotEducation/create3_sim.git](https://github.com/iRobotEducation/create3_sim.git)
```

```bash
grep -n "render_engine" ~/turtlebot4_ws/src/create3_sim/irobot_create_common/irobot_create_description/urdf/create3.urdf.xacro
sed -i 's#<render_engine>ogre</render_engine>#<render_engine>ogre2</render_engine>#' ~/turtlebot4_ws/src/create3_sim/irobot_create_common/irobot_create_description/urdf/create3.urdf.xacro
grep -n "render_engine" ~/turtlebot4_ws/src/create3_sim/irobot_create_common/irobot_create_description/urdf/create3.urdf.xacro
```

### 패키지 빌드

```bash
cd ~/turtlebot4_ws
```

```python
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### .bashrc 수정

```bash
# .bashrc 등록
echo 'source ~/turtlebot4_ws/install/setup.bash' >> ~/.bashrc
source ~/.bashrc
```

## 3. 실행 확인

### ROS2 및 TurtleBot4 환경 확인

```bash
cd ~/turtlebot4_ws
source install/setup.bash
ros2 pkg list | grep turtlebot4
```

- 설치된 `turtlebot4` 관련 패키지가 정상적으로 출력되면 성공

```bash
(rokey_venv) hv-07@hv-07-Victus-by-HP-Laptop-16-d1xxx:~/turtlebot4_ws$ ros2 pkg list | grep turtlebot4
turtlebot4_cpp_tutorials
turtlebot4_description
turtlebot4_desktop
turtlebot4_gz_bringup
turtlebot4_gz_gui_plugins
turtlebot4_gz_toolbox
turtlebot4_msgs
turtlebot4_navigation
turtlebot4_node
turtlebot4_openai_tutorials
turtlebot4_python_tutorials
turtlebot4_simulator
turtlebot4_tutorials
turtlebot4_viz
```

```bash
#verifiy again the setup for Harmonic GZ Simulation
source ~/turtlebot4_ws/install/setup.bash
ros2 pkg prefix irobot_create_description
grep -n "render_engine" $(ros2 pkg prefix irobot_create_description)/share/irobot_create_description/urdf/create3.urdf.xacro
```

---

# YOLO Setup

## YOLO / Torch 설치

1. venv 활성화 상태 확인
    
    ```bash
    cd ~
    which python3
    
    # → ~/venvs/rokey_venv/bin/python3 이어야 함
    # 아니라면: source ~/venvs/rokey_venv/bin/activate
    ```
    
2. 설치
    
    ```bash
    pip install --upgrade pip
    ```
    
    ```python
    nvidia-smi # Cheak if the GPU is available
    # If you have a GPU, install the CUDA version of PyTorch
    
    ```
    
    ```bash
    pip install torch torchvision
    ```
    
    ```bash
    pip install "setuptools<80"
    ```
    
    Ultralytics 설치 시 자동으로 다운로드되는 OpenCV 버전에 호환성 오류가 발생할 수 있다. 아래 스텝을 진행해 OpenCV 버전을 다운그레이드한다. 
    

```python
pip install ultralytics
```

```python
pip install "opencv-python==4.9.0.80" "numpy==1.26.4"
```

## 설치 확인

```bash
python3 -c "
import torch; print('PyTorch:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('GPU:', torch.cuda.get_device_name(0))
from ultralytics import YOLO; print('Ultralytics OK')
import rclpy; print('rclpy OK')
import numpy; print('numpy:', numpy.__version__)
from cv_bridge import CvBridge; print('cv_bridge OK')
"
```

```python
# 출력

PyTorch: 2.13.0+cu130
CUDA available: True
GPU: NVIDIA GeForce RTX 3060 Laptop GPU
Creating new Ultralytics Settings v0.0.6 file ✅ 
View Ultralytics Settings with 'yolo settings' or at '/home/hv-07/.config/Ultralytics/settings.json'
Update Settings with 'yolo settings key=value', i.e. 'yolo settings runs_dir=path/to/dir'. For help see https://docs.ultralytics.com/quickstart/#ultralytics-settings.
Ultralytics OK
rclpy OK
numpy: 1.26.4
cv_bridge OK

```

---

# PC와 Single Robot Network Setup

반드시 PC에서 실행 !! (Turtlebot에 접속하여 실행하면 절대 안됨)

## 🔑 개발 환경 구성

### **ROS2 기반 로봇 시스템의 네트워크 구성**

| 구성 요소 | 역할 |
| --- | --- |
| 무선 공유기 | 독립적인 로컬 ROS 네트워크 구성의 중심 허브 |
| 노트북들 | 실습자 ROS 클라이언트 (RViz, CLI, rqt 등 실d행) |
| Raspberry Pi | 로봇 제어용 ROS2 노드 구동 (publisher, service server 등) |
| Create3 | 하드웨어 모빌리티 제공 (모터 제어, 센서 통합) |

**이 구성의 장점**

- 외부 인터넷과 분리되어 있어 **통신 충돌 위험이 낮고**, **학습용 네트워크로 안정적**입니다.
- 모든 장비가 동일한 로컬 네트워크 대역 안에 있어 **ROS2 DDS 통신이 원활**합니다.

**공식 문서 참고**

[Networking · User Manual](https://turtlebot.github.io/turtlebot4-user-manual/setup/networking.html)

## 💡 Networking

### Robot Connection setup

Connect the robots to same wifi router and obtain the ip addresses

### PC setup

[https://turtlebot.github.io/turtlebot4-user-manual/setup/discovery_server.html](https://turtlebot.github.io/turtlebot4-user-manual/setup/discovery_server.html)

1. Turtlebot을 도킹 스테이션에 밀어넣어 전원을 킨다. (Power ON)
    
    ![image.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image.png)
    
    - TurtleBot4를 도킹 스테이션에 정확히 올려놓으면
    - **자동으로 전원이 켜진다** (별도의 버튼 조작 불필요)
    - 터틀봇의 HMI Display에서 터틀봇의 IP address를 확인할 수 있다.
2. 공유기에 PC를 연결한다.
    
    
    | 조 | 와이파이 SSID  | 비밀번호 |
    | --- | --- | --- |
    | 1, 2 | turtle**07** | `rokey12345` |
    | 3, 4 | turtle**08** | `rokey12345` |
    | 5, 6 | turtle**09** | `rokey12345` |
    | 7, 8 | turtle**01** | `rokey12345` |
    
    ```bash
    # Turtlebot과 같은 공유기에 속해 있는지 확인하기 위해 터미널 창에 아래 코드를 입력한다.
    # 돌아오는 메세지가 없다면 본인 노트북의 Wifi 이름 확인.
    # You can find the Turtlebot IP address on the top line of Turtlebot HMI LED screen 
    ping ***<각 팀의 Turtlebot IP>***
    ```
    
3. 아래의 명령을 실행시킨다.
    
    ```bash
    #make sure pc is connected to the same wifi router as the robot
    wget -qO - https://raw.githubusercontent.com/turtlebot/turtlebot4_setup/jazzy/turtlebot4_discovery/configure_discovery.sh | bash <(cat) </dev/tty
    ```
    
    ![image.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image%201.png)
    
    ![Screenshot from 2025-05-20 14-59-35.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/Screenshot_from_2025-05-20_14-59-35.png)
    
    Enter your team # as ROS_DOMAIN_ID (1 or 2 or …~6)
    Enter ***<각 팀의 Turtlebot IP> as Discovery Server IP***
    Leave the Discovery Server Port as [11811]
    
    **ROS 2 TurtleBot4 Discovery Server 설정 입력표**
    
    | 항목 | 입력 예시 값 | 설명 |
    | --- | --- | --- |
    | **ROS_DOMAIN_ID** | `1,2,3,4,5,or 6` | 로봇 및 PC가 공유할 ROS 도메인 번호 (기본값: 0) **팀 별로 부여된 번호** |
    | **Discovery Server ID** | `1,2,3,4,5,or 6` | 고유한 서버 ID (로봇마다 다르게 설정해야 함), **팀 별로 부여된 번호** |
    | **Discovery Server IP** | `192.168.10.16` | 로봇(Raspberry Pi)의 IP 주소 |
    | **Discovery Server Port** | *(엔터)* 또는 `11811` | 기본 포트 11811 사용 시 엔터 입력 |
    | **Server 입력 선택** | `r`, `a`, `d` | `r`: 재입력, `a`: 다른 서버 추가, `d`: 완료 |
4. 설정 내용 source해서 반영
    
    ```bash
    source .bashrc
    ```
    
5. ROS2 daemon restart
    
    ```bash
    ros2 daemon stop
    ros2 daemon start
    ```
    
6. 연결 확인
    - 아래 명령어를 두 번정도 시도 해야한다.
    - 처음 command 명령을 실행하면 daemon이 가능한 토픽 리스트를 취합하느라 바로 토픽리스트를 반환하지 못한다.
    
    ```bash
    ros2 topic list
    ```
    
7. 설정 내용 확인
    
    위의 설정 내용이 어떤 파일에 저장되어 있고 어떤 내용으로 설정되었는지 확인한다. (**경로 기억할 것!**)
    
    ```bash
    cat /etc/turtlebot4_discovery/setup.bash
    ```
    

---

**여러 로봇의 ROS 2 Discovery Server 설정 (robot1 ~ robot4) : ROS_DOMAIN_ID 같음** 

| 로봇 이름 | Discovery Server ID | Ros Domain ID | 사용 포트 | 설명 |
| --- | --- | --- | --- | --- |
| robot0 | 0 | 0 | 11811 |  |
| robot1 | 1 | 1 | 11811 | 첫 번째 로봇 |
| robot2 | 2 | 2 | 11811 | 두 번째 로봇 |
| robot3 | 3 | 3 | 11811 | 세 번째 로봇 |
| robot4 | 4 | 4 | 11811 | 네 번째 로봇 |

## 💡 테스트

키보드로 turtlebot4를 움직여 봅시다. (**반드시 undock 해야함.**)

- undock & move robot
    
    ```python
    
    #Undock the robot if not undocked; enter your robot namespace
    ros2 action send_goal /robot***<n>***/undock irobot_create_msgs/action/Undock "{}"
    
    ```
    
    ```bash
    
    #make sure update the <n> to match your robot namespace
    ros2 run teleop_twist_keyboard teleop_twist_keyboard \
      --ros-args -p stamped:=true -r /cmd_vel:=/robot**<n>**/cmd_vel
    
    ```
    
    - `-ros-args` : ROS 2 런타임 인자 설정을 시작함을 의미
    - `-r /cmd_vel:=/robot<n>/cmd_vel` : 토픽 리매핑: `/cmd_vel` → `/robot<n>/cmd_vel` 으로 변경
        
        ![Screenshot from 2026-08-11 15-26-41.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/Screenshot_from_2026-08-11_15-26-41.png)
        
- view robot camera:
    
    ```python
    rqt --clear-config
    #goto plugins and select visualization --> image view
    #refresh and select the image topic
    ```
    
    ![image.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image%202.png)
    
    ![image.png](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/image%203.png)
    
- dock robot
    
    ```python
    #Dock your robot
    ros2 action send_goal /robot***<n>***/dock irobot_create_msgs/action/Dock "{}"
    ```
    

---

# bashrc 설정

<aside>
📎

[bashrc.md](%5B%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD%EA%B5%AC%EC%B6%95%5DVictus,%20MSI%20%EA%B0%9C%EB%B0%9C%20%ED%99%98%EA%B2%BD%20%EA%B5%AC%EC%B6%95/bashrc.md)

</aside>