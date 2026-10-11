#!/bin/bash
# Boo Nav2 실물 TurtleBot4 시험용 ROS 환경 (모든 터미널에서 `source boo_nav/tools/env_real.sh`).
# 팀 네트워크(도메인 2, Discovery Server)에 붙는다. 서버 주소는 /etc/turtlebot4_discovery/setup.bash 값을 그대로 쓴다.
# 시뮬레이션에는 이 파일을 쓰지 않는다(시뮬레이션은 env_sim.sh, 도메인 77).
#   source boo_nav/tools/env_real.sh          일반 노드용(ROS_SUPER_CLIENT=False)
#   source boo_nav/tools/env_real.sh super    ros2 topic list 등 전체 그래프를 볼 확인용 터미널(ROS_SUPER_CLIENT=True)
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source /etc/turtlebot4_discovery/setup.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/ros2_ws/install/setup.bash"
if [ "$1" = "super" ]; then export ROS_SUPER_CLIENT=True; else export ROS_SUPER_CLIENT=False; fi
echo "[env_real] ROS_DOMAIN_ID=$ROS_DOMAIN_ID ROS_DISCOVERY_SERVER=$ROS_DISCOVERY_SERVER ROS_SUPER_CLIENT=$ROS_SUPER_CLIENT"
