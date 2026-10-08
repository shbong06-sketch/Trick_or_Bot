# ✏️ ROS 삭제

> 원본: https://indecisive-freedom-6e8.notion.site/9318e215779c826888cf81da2375b73e  
> 최종 수정: 2026-06-01 09:23 / 변환: 2026-10-08 14:07

### 💡 삭제

#### **ROS2 관련 패키지 삭제:**  

```bash
sudo apt remove --purge -y ros-*
sudo apt remove --purge -y python3-colcon* python3-rosdep* python3-vcstool* python3-setuptools*
sudo apt autoremove -y

```

#### **잔여 설정 파일 삭제:**  

```bash
sudo rm -rf /opt/ros
sudo rm -rf ~/.ros
sudo rm -rf ~/.rviz2
sudo rm -rf ~/ros2_ws #사용했던 워크스페이스
```

#### **설정된 저장소 삭제:**  

```bash
sudo rm /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt autoremove
# Consider upgrading for packages previously shadowed.
sudo apt upgrade
```
