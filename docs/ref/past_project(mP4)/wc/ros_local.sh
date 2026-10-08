# 로봇 없이 이 PC 안에서만 ROS node끼리 통신하게 하는 설정 (터미널마다 source 할 것)
#   source ~/ROKEY_mP4_A1/wc/ros_local.sh
# ~/.bashrc가 불러오는 로봇 discovery server(192.168.107.101) 설정을 이 터미널에서만 끈다.
# AMR과 연동할 때는 쓰지 말 것 (새 터미널을 열면 원래 설정으로 돌아감)
unset ROS_DISCOVERY_SERVER ROS_SUPER_CLIENT
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 daemon stop > /dev/null 2>&1   # 예전 설정으로 떠 있던 daemon 정리
echo "✅ ROS 로컬 모드 (discovery server 끔, ROS_DOMAIN_ID=${ROS_DOMAIN_ID})"
