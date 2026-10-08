# =============================================================================
# Int01-bashrc setting
# ============================================================================
source ~/venvs/rokey_venv/bin/activate
source /opt/ros/jazzy/setup.bash
source ~/venvs/rokey_venv/share/colcon_argcomplete/hook/colcon-argcomplete.bash
source ~/turtlebot4_ws/install/setup.bash
source /etc/turtlebot4_discovery/setup.bash

alias sb='source ~/.bashrc'
alias eb='nano ~/.bashrc'
alias vb='cat ~/.bashrc'

alias sd='source /etc/turtlebot4_discovery/setup.bash'
alias ed='nano /etc/turtlebot4_discovery/setup.bash'
alias vd='cat /etc/turtlebot4_discovery/setup.bash'


alias ros-restart='ros2 daemon stop; ros2 daemon start'
alias ssh-robot='ssh ubuntu@192.168.107.101'
alias robot-loc='ros2 launch turtlebot4_navigation localization.launch.py namespace:=robot1 map:=$HOME/Documents/student_maps/map.yaml'
alias robot-nav='ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot1'
alias robot-view='ros2 launch turtlebot4_viz view_navigation.launch.py namespace:=/robot1'
alias robot-dock='ros2 action send_goal /robot1/dock irobot_create_msgs/action/Dock "{}"'
alias robot-undock='ros2 action send_goal /robot1/undock irobot_create_msgs/action/Undock "{}"'
alias robot-keyboard='ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true -r /cmd_vel:=/robot1/cmd_vel'

undock() {
  if [ -z "$1" ]; then
    echo "Usage: undock robot1"
    return 1
  fi
  ros2 action send_goal /robot$1/undock irobot_create_msgs/action/Undock "{}"
}

dock() {
  if [ -z "$1" ]; then
    echo "Usage: dock robot1"
    return 1
  fi
  ros2 action send_goal /robot$1/dock irobot_create_msgs/action/Dock "{}"
}

loc() {
  if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: loc <robot#> <map_path>"
    return 1
  fi

  ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot$1 map:=$2
}


nav() {
  if [ -z "$1" ]; then
    echo "Usage: ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot1"
    return 1
  fi
  ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot$1
}

rv() {
  if [ -z "$1" ]; then
    echo "Usage: ros2 launch turtlebot4_viz view_navigation.launch.py namespace:=/robot1"
    return 1
  fi
  ros2 launch turtlebot4_viz view_navigation.launch.py namespace:=/robot$1
}

export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=1
# =============================================================================
# Int01-bashrc setting end-point
# ============================================================================
