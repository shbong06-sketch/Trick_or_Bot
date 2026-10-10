"""Pumpkin Run Gazebo 시뮬레이션: holloween 월드 + TurtleBot4 두 대 + 각자 AMCL.

  ros2 launch ~/cobot4_ws/simulation/launch/pumpkin_run_sim.launch.py

- /robot1 = 부우, /robot2 = 펌킨. 시작 위치는 backend/config/level1.yaml의 boo_start, pumpkin_start
- 월드 좌표 = map 좌표 (simulation/tools/map_to_world.py로 생성). AMCL도 같은 holloween 맵을 쓴다
- 펌킨 카메라는 시뮬레이터가 raw만 내보내므로 compressed로 다시 내보낸다 (게임 서버는 CompressedImage만 구독)
"""
import os
import re
import shutil
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, SetEnvironmentVariable,
                            SetLaunchConfiguration, Shutdown, TimerAction)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

REPO = Path(__file__).resolve().parents[2]
WORLDS_DIR = REPO / 'simulation' / 'worlds'
WORLD = 'holloween'   # 경로가 아니라 이름이어야 한다 (TB4 브리지가 /world/<이름>/model/... 토픽을 만든다)
LEVEL = REPO / 'backend' / 'config' / 'level1.yaml'
ROBOTS = (('robot1', 'boo_start', 'boo_model'), ('robot2', 'pumpkin_start', 'model'))
SPAWN_GAP_S = 8.0   # 두 번째 로봇은 첫 로봇이 다 뜬 뒤에 스폰 (동시에 띄우면 브리지·컨트롤러가 꼬이기 쉽다)
LOCALIZATION_DELAY_S = 15.0  # 로봇 노드가 다 뜬 뒤 AMCL을 띄운다. 같이 띄우면 map_server가 Configuring에서 멈추는 일이 있다


OVERLAY = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'pumpkin_run_overlay'


# 시뮬레이터용으로 고친 사본을 쓸 패키지: {패키지: [(share 안 상대 경로, 찾을 정규식, 바꿀 문자열, 이유)]}
OVERLAY_PATCHES = {
    'irobot_create_description': [
        ('urdf/create3.urdf.xacro', r'<gazebo>\s*<plugin filename="libgz-sim-sensors-system\.so".*?</gazebo>', '',
         '센서 시스템은 월드에서 한 번만 (로봇마다 불러오면 두 번째 로봇에서 Gazebo가 죽는다)'),
        ('urdf/sensors/cliff_sensor.urdf.xacro', r'name="update_rate"(\s+)value="62"', r'name="update_rate"\1value="10"',
         '바닥 감지 4개 62 Hz → 10 Hz (렌더링 부담. 실시간 비율 0.42 → 0.70)'),
        ('urdf/sensors/ir_intensity.urdf.xacro', r'update_rate:=62\.0', 'update_rate:=10.0',
         '근접 IR 7개 62 Hz → 10 Hz (렌더링 부담)'),
    ],
    'irobot_create_common_bringup': [
        ('launch/create3_nodes.launch.py', r"'safety_override': 'backup_only'",
         "'safety_override': 'backup_only',\n            'reflexes_enabled': False",
         'Create3 반사 동작 끄기. 시뮬레이터가 실시간보다 느리면 "끼임" 반사가 계속 후진시켜 조작이 막힌다'),
    ],
    'turtlebot4_gz_bringup': [
        # 원본은 로봇이 도킹된 채(독이 로봇 앞)로 스폰한다. 실제 배치처럼 독을 로봇 뒤에 두고 독은 로봇 쪽을 보게 한다.
        # 독 충돌 벽이 로봇 중심에서 0.18~0.22 m라 로봇(반지름 약 0.17 m)과 겹치지 않는다
        ('launch/turtlebot4_spawn.launch.py', r'RotationalOffset([XY])\(0\.157, yaw\)', r'RotationalOffset\1(-0.157, yaw)',
         '독을 로봇 뒤로'),
        ('launch/turtlebot4_spawn.launch.py', r'OffsetParser\(yaw, 3\.1416\)', 'OffsetParser(yaw, 0.0)',
         '뒤에 놓인 독이 로봇 쪽을 보게'),
    ],
}


def _mirror(src: Path, dst: Path, patched: set[str], rel: str = '') -> None:
    """src를 dst에 링크로 복제한다. 고칠 파일이 들어 있는 폴더만 실제 폴더로 만든다."""
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        sub = f'{rel}{entry.name}'
        if entry.is_dir() and any(p.startswith(sub + '/') for p in patched):
            _mirror(entry, dst / entry.name, patched, sub + '/')
        elif sub not in patched:
            (dst / entry.name).symlink_to(entry)


def make_overlay() -> Path:
    """OVERLAY_PATCHES대로 고친 패키지 사본을 만든다 (나머지 파일은 원본을 가리키는 링크).

    AMENT_PREFIX_PATH 앞에 두면 xacro·TB4 런치가 이 사본을 먼저 찾는다. /opt 아래 원본은 건드리지 않는다.
    """
    if OVERLAY.exists():
        shutil.rmtree(OVERLAY)
    index = OVERLAY / 'share' / 'ament_index' / 'resource_index' / 'packages'
    index.mkdir(parents=True)
    for pkg, patches in OVERLAY_PATCHES.items():
        src = Path(get_package_share_directory(pkg))
        (index / pkg).touch()
        _mirror(src, OVERLAY / 'share' / pkg, {p[0] for p in patches})
        for rel, pattern, repl, why in patches:
            dst = OVERLAY / 'share' / pkg / rel   # 같은 파일을 여러 번 고치면 앞서 고친 사본에 이어서 고친다
            text, n = re.subn(pattern, repl, (dst if dst.exists() else src / rel).read_text(), flags=re.S)
            if n == 0:
                raise RuntimeError(f'{pkg}/{rel}: 고칠 곳을 찾지 못했다 ({why}). 패키지 버전 확인')
            dst.write_text(text)
    return OVERLAY


def amcl_params(ns: str, pose: dict) -> str:
    """TB4 기본 localization.yaml에 초기 위치만 넣은 파라미터 파일을 만든다."""
    base = Path(get_package_share_directory('turtlebot4_navigation')) / 'config' / 'localization.yaml'
    params = yaml.safe_load(base.read_text())
    amcl = params['amcl']['ros__parameters']
    amcl['set_initial_pose'] = True
    amcl['initial_pose'] = {'x': float(pose['x']), 'y': float(pose['y']), 'z': 0.0, 'yaw': float(pose.get('yaw', 0.0))}
    out = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'pumpkin_run_amcl_{ns}.yaml'
    out.write_text(yaml.safe_dump(params))
    return str(out)


def robots(context, *args, **kwargs):
    level = yaml.safe_load(LEVEL.read_text(encoding='utf-8'))
    map_yaml = str((LEVEL.parent / level['map_yaml']).resolve())
    actions = []
    for i, (ns, key, model_arg) in enumerate(ROBOTS):
        pose = level[key]
        model = LaunchConfiguration(model_arg).perform(context)
        # 로봇마다 별도 ros2 launch 프로세스로 띄운다. TB4 런치의 이벤트 핸들러가 나중에 'namespace' 설정을 다시 읽는데,
        # 한 런치 안에 두 번 include하면 그 시점에 설정이 사라져 런치 전체가 죽는다
        spawn_args = [f'namespace:={ns}', f'model:={model}', f'world:={WORLD}',
                      f"x:={pose['x']}", f"y:={pose['y']}", 'z:=0.0', f"yaw:={pose.get('yaw', 0.0)}"]
        localization = ExecuteProcess(
            cmd=['ros2', 'launch', 'turtlebot4_navigation', 'localization.launch.py',
                 f'namespace:={ns}', 'use_sim_time:=true', f'map:={map_yaml}', f'params:={amcl_params(ns, pose)}'],
            output='screen', name=f'localization_{ns}')
        group = [
            ExecuteProcess(cmd=['ros2', 'launch', 'turtlebot4_gz_bringup', 'turtlebot4_spawn.launch.py', *spawn_args],
                           output='screen', name=f'spawn_{ns}'),
            TimerAction(period=LOCALIZATION_DELAY_S, actions=[localization]),
        ]
        if ns == 'robot2':
            # raw → compressed (JPEG). /robot2/oakd/rgb/preview/image_raw/compressed 로 나온다
            group.append(Node(
                package='image_transport', executable='republish', name='oakd_compress', namespace=ns,
                parameters=[{'in_transport': 'raw', 'out_transport': 'compressed', 'use_sim_time': True}],
                # 'out'이 아니라 실제 이름 'out/compressed'를 리매핑해야 한다 (리매핑은 이름이 정확히 같을 때만 적용)
                remappings=[('in', f'/{ns}/oakd/rgb/preview/image_raw'),
                            ('out/compressed', f'/{ns}/oakd/rgb/preview/image_raw/compressed')]))
        actions.append(TimerAction(period=i * SPAWN_GAP_S, actions=group))
    return actions


def gazebo(context, *args, **kwargs):
    """turtlebot4_gz_bringup/sim.launch.py와 같지만, 리소스 경로에 우리 worlds 폴더를 더한다."""
    share = get_package_share_directory
    model = LaunchConfiguration('model').perform(context)
    resource = [str(WORLDS_DIR),
                os.path.join(share('turtlebot4_gz_bringup'), 'worlds'),
                os.path.join(share('irobot_create_gz_bringup'), 'worlds'),
                str(Path(share('turtlebot4_description')).parent),
                str(Path(share('irobot_create_description')).parent)]
    gui_plugins = [os.path.join(share('turtlebot4_gz_gui_plugins'), 'lib'),
                   os.path.join(share('irobot_create_gz_plugins'), 'lib')]
    gui_config = os.path.join(share('turtlebot4_gz_bringup'), 'gui', model, 'gui.config')
    headless = LaunchConfiguration('headless').perform(context) == 'true'
    gz_args = [f'{WORLD}.sdf', '-r', '-v', '3'] + (['-s'] if headless else ['--gui-config', gui_config])
    return [
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', ':'.join(resource)),
        SetEnvironmentVariable('GZ_GUI_PLUGIN_PATH', ':'.join(gui_plugins)),
        SetLaunchConfiguration('world', WORLD),   # TB4 브리지가 이 값을 읽는다
        # Gazebo가 죽거나 창을 닫으면 런치 전체를 끝낸다 (로봇 노드·브리지가 고아로 남지 않게)
        ExecuteProcess(cmd=['gz', 'sim', *gz_args], name='gazebo', output='screen', on_exit=Shutdown()),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='clock_bridge', output='screen',
             arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock']),
    ]


def generate_launch_description():
    # 이 런치와 자식 프로세스(로봇 스폰·xacro)가 고친 사본(OVERLAY_PATCHES)을 먼저 찾게 한다
    overlay = str(make_overlay())
    os.environ['AMENT_PREFIX_PATH'] = overlay + ':' + os.environ.get('AMENT_PREFIX_PATH', '')
    return LaunchDescription([
        SetEnvironmentVariable('AMENT_PREFIX_PATH', os.environ['AMENT_PREFIX_PATH']),
        DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite'],
                              description='standard = OAK-D 카메라 포함'),
        DeclareLaunchArgument('boo_model', default_value='standard', choices=['standard', 'lite'],
                              description='부우 모델. lite = 카메라 없음 (시뮬레이터가 느릴 때)'),
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false'],
                              description='true = Gazebo 창 없이 서버만'),
        OpaqueFunction(function=gazebo),
        OpaqueFunction(function=robots),
    ])
