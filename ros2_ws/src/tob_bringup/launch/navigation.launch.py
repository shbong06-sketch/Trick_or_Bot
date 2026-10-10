"""Boo의 자율 이동에 필요한 Nav2와 이동 관리 노드를 함께 실행한다.

[입력]
namespace(기본 robot1), use_sim_time, nav2_params(tob_control/config/nav2.yaml),
control_params(tob_control/config/control.yaml).
[구성]
- turtlebot4_navigation의 nav2.launch.py (플래너·컨트롤러·속도 평활기·충돌 감시)
- boo_controller_node (FSM 결정을 Nav2 목표로 실행)
[범위]
위치추정(AMCL, map_server)은 localization.launch.py가 맡으므로 여기서 실행하지 않는다.
"""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    control_share = get_package_share_directory('tob_control')
    nav_share = get_package_share_directory('turtlebot4_navigation')

    namespace = LaunchConfiguration('namespace')
    use_sim_time = LaunchConfiguration('use_sim_time')

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([nav_share, 'launch', 'nav2.launch.py'])),
        launch_arguments={
            'namespace': namespace,
            'use_sim_time': use_sim_time,
            'params_file': LaunchConfiguration('nav2_params'),
        }.items())

    controller = Node(
        package='tob_control',
        executable='boo_controller_node',
        namespace=namespace,
        parameters=[LaunchConfiguration('control_params'),
                    {'use_sim_time': use_sim_time}],
        output='screen')

    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value='robot1',
                              description='Boo 로봇 네임스페이스'),
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              choices=['true', 'false']),
        DeclareLaunchArgument('nav2_params',
                              default_value=PathJoinSubstitution(
                                  [control_share, 'config', 'nav2.yaml'])),
        DeclareLaunchArgument('control_params',
                              default_value=PathJoinSubstitution(
                                  [control_share, 'config', 'control.yaml'])),
        nav2,
        controller,
    ])
