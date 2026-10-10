#!/bin/bash
# 시뮬레이션·Nav2·Boo 컨트롤러 관련 프로세스를 번호(PID)로 찾아 모두 종료하고 DDS 찌꺼기를 지운다.
# 사용: bash boo_nav/tools/stop_sim.sh   (시험 시작 전·끝난 뒤마다)
# `pkill -f`는 쓰지 않는다: 입력한 명령 자체와 이름이 겹치면 터미널이 같이 종료된다.
list() {
  ps -eo pid,args | awk '$2!~/^(\/bin\/bash|bash|grep|awk|ps)/' \
    | grep -E "/opt/ros/jazzy/(lib|bin)|turtlebot4_ws/install|ros2_ws/install|gz sim|ros_gz|joint_state_publisher|ros2 launch|obs_pub.py|fake_detector.py|pumpkin_scenario.py|boo_controller_node" \
    | grep -v grep | awk '{print $1}'
}
for i in 1 2 3; do P=$(list); [ -z "$P" ] && break; kill $P 2>/dev/null; sleep 3; done
P=$(list); [ -n "$P" ] && kill -9 $P 2>/dev/null; sleep 1
source /opt/ros/jazzy/setup.bash
ros2 daemon stop >/dev/null 2>&1
fastdds shm clean 2>&1 | tail -1
echo "남은 ROS/Gazebo 프로세스: $(list | wc -l)  (0이어야 한다)"
