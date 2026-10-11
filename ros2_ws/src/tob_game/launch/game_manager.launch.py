"""이동·Nav2·위치추정을 실행하지 않는 게임 관리자 단독 실행 설정."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """레벨 경로, 운영 설정, ROS 시계 선택을 실행 인자로 받는다."""
    share = Path(get_package_share_directory('tob_game'))
    return LaunchDescription([
        DeclareLaunchArgument('params_file',
                              default_value=str(share / 'config/game_manager.yaml')),
        DeclareLaunchArgument('level_path',
                              default_value=str(share / 'config/levels/level1.yaml')),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(package='tob_game', executable='game_manager', output='screen', parameters=[
            LaunchConfiguration('params_file'),
            {'level_path': LaunchConfiguration('level_path'),
             'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)},
        ]),
    ])
