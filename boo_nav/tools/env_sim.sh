#!/bin/bash
# Boo Nav2 시험용 ROS 환경 (모든 터미널에서 `source boo_nav/tools/env_sim.sh`).
# 팀 네트워크(도메인 2, Discovery Server)와 섞이지 않도록 도메인 77을 쓴다. Discovery Server는 쓰지 않는다.
# 🔴 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST는 쓰지 않는다: 이 PC에서 Gazebo 시뮬레이션과 함께 쓰면
#    노드끼리 서비스 연결이 안 돼 localization이 멈췄다(map_server/get_state 대기 반복). 기본값(SUBNET)이 정상이다.
# 실제 로봇을 쓰는 시험에는 이 파일을 쓰지 않는다.
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID=77
unset ROS_DISCOVERY_SERVER ROS_AUTOMATIC_DISCOVERY_RANGE FASTRTPS_DEFAULT_PROFILES_FILE
echo "[env_sim] ROS_DOMAIN_ID=$ROS_DOMAIN_ID (팀 도메인 2와 분리, Discovery Server 없음)"
