#!/bin/bash
# boo_controller_node 모의 시험 실행기 (Gazebo, 실제 로봇 없음).
# 사용: bash boo_nav/tools/run_fake_test.sh   (저장소 최상위에서)
# 로그: boo_nav/result_boo_nav/log_boo_nav/ 에 컨트롤러·시험 출력이 저장된다.
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$REPO/boo_nav/result_boo_nav/log_boo_nav"
TS="$(date +%y%m%d_%H%M%S)"

source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source "$REPO/ros2_ws/install/setup.bash"
# 팀 네트워크와 섞이지 않게 이 시험만 따로 둔다
export ROS_DOMAIN_ID=77
unset ROS_AUTOMATIC_DISCOVERY_RANGE ROS_DISCOVERY_SERVER
unset ROS_DISCOVERY_SERVER

ros2 run tob_control boo_controller_node --ros-args -r __ns:=/robot1 \
  --params-file "$REPO/ros2_ws/src/tob_control/config/control.yaml" \
  -p suspicion_fill_s:=1.0 -p lost_timeout_s:=0.8 > "$LOG/ctrl_$TS.txt" 2>&1 &
CTRL=$!
sleep 2
timeout 120 python3 "$REPO/boo_nav/tools/fake_world.py" 2>&1 | tee -i "$LOG/fake_world_$TS.txt"
RESULT=${PIPESTATUS[0]}
pkill -P "$CTRL" 2>/dev/null; kill "$CTRL" 2>/dev/null
echo "컨트롤러 로그의 오류 줄:"; grep -i -E "error|traceback|exception" "$LOG/ctrl_$TS.txt" || echo "  (없음)"
exit "$RESULT"
