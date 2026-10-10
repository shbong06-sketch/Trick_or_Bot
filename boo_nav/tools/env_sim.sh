#!/bin/bash
# Boo Nav2 시험용 ROS 환경 (모든 터미널에서 `source boo_nav/tools/env_sim.sh`).
# 팀 네트워크(도메인 2, Discovery Server)와 섞이지 않도록 이 PC 안에서만 통신하는 도메인 77을 쓴다.
# 실제 로봇을 쓰는 시험에는 이 파일을 쓰지 않는다.
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER
echo "[env_sim] ROS_DOMAIN_ID=$ROS_DOMAIN_ID (이 PC 안에서만 통신)"
