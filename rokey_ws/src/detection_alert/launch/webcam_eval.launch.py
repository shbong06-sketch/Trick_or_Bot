"""로봇 없이 웹캠 car 좌표를 맵 위에서 확인하는 launch.

한 번에 띄우는 것
  map_server + lifecycle_manager   맵(/map) publish
  rviz2 (rviz/webcam_eval.rviz)    맵 + 웹캠 car 좌표(빨간 점) + Publish Point
  webcam_detector                  웹캠 YOLO 검출
  car_locator                      bbox → map 좌표 (/webcam/car_point_raw, /webcam/car_point)

사용법:
  ros2 launch detection_alert webcam_eval.launch.py cam:=5 [map:=<yaml>] [rviz:=false]
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

SHARE = Path(get_package_share_directory('detection_alert'))
# install/detection_alert/share/detection_alert → workspace = 4단계 위, 맵은 workspace/maps/
DEFAULT_MAP = SHARE.parents[3] / 'maps' / 'map_auto_261006_1214.yaml'


def generate_launch_description():
    cam = LaunchConfiguration('cam')
    return LaunchDescription([
        DeclareLaunchArgument('cam', description='웹캠 번호 (v4l2-ctl --list-devices 의 USB 웹캠 첫 번째 /dev/videoN)'),
        DeclareLaunchArgument('map', default_value=str(DEFAULT_MAP), description='맵 yaml'),
        DeclareLaunchArgument('rviz', default_value='true', description='RViz를 띄울지'),
        Node(package='nav2_map_server', executable='map_server', name='map_server', output='screen',
             parameters=[{'yaml_filename': LaunchConfiguration('map')}]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_map',
             output='screen', parameters=[{'node_names': ['map_server'], 'autostart': True}]),
        Node(package='rviz2', executable='rviz2', name='rviz2', output='log',
             arguments=['-d', str(SHARE / 'rviz' / 'webcam_eval.rviz')],
             condition=IfCondition(LaunchConfiguration('rviz'))),
        Node(package='detection_alert', executable='webcam_detector', name='webcam_detector', output='screen',
             arguments=['--cam', cam]),
        Node(package='detection_alert', executable='car_locator', name='car_locator', output='screen'),
    ])
