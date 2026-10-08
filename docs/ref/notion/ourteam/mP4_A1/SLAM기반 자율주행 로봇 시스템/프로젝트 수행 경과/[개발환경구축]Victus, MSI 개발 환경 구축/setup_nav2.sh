#   1) bond_timeout 4.0 -> 10.0
#   2) controller  MPPI -> DWB
#
#   실행:  bash setup_nav2.sh
set -euo pipefail

WS="${WS:-$HOME/turtlebot4_ws}"
PKG="$WS/src/turtlebot4/turtlebot4_navigation"
SRC="$(ros2 pkg prefix --share nav2_bringup)/launch/navigation_launch.py"
DWB="$(mktemp)"; trap 'rm -f "$DWB"' EXIT


# 공통 함수 replace: 파일에서 before -> after 로 한 번 치환
# 이미 적용돼 있으면 건너뛰고, before 가 없으면 에러 발생
replace() {
  python3 - "$@" <<'PY'
import sys
path, before, after = sys.argv[1:4]
s = open(path).read()
if after in s:
    print("이미 적용됨"); sys.exit()
if before not in s:
    sys.exit("치환 대상 없음: " + path)
open(path, 'w').write(s.replace(before, after, 1))
print("  ✓ 적용")
PY
}

# 1. navigation_launch.py를 pkg 안으로 복사 + configured_params 추가
# 이유: navigation_launch.py의 lifecycle_manager 에만 configured_params가 연결돼 있지 않아 nav2.yaml 의 bond_timeout 이 무시됨. 
echo "1. navigation_launch.py"
AFTER="parameters=[configured_params, {'autostart': autostart}, {'node_names': lifecycle_nodes}]"
[[ -f "$PKG/launch/navigation_launch.py" ]] || { cp "$SRC" "$PKG/launch/"; chmod u+w "$PKG/launch/navigation_launch.py"; }
replace "$PKG/launch/navigation_launch.py" \
        "parameters=[{'autostart': autostart}, {'node_names': lifecycle_nodes}]" "$AFTER"

# 2. 위 복사본을 바라보게 함
echo "2. nav2.launch.py"
replace "$PKG/launch/nav2.launch.py" \
        "pkg_nav2_bringup = get_package_share_directory('nav2_bringup')" \
        "pkg_nav2_bringup = get_package_share_directory('turtlebot4_navigation')"

# 3. FollowPath 블록 교체 + bond_timeout 추가
echo "3. nav2.yaml"
cat > "$DWB" <<'BLOCK'
    FollowPath:
      plugin: "dwb_core::DWBLocalPlanner"
      debug_trajectory_details: True
      min_vel_x: 0.0
      min_vel_y: 0.0
      max_vel_x: 0.26
      max_vel_y: 0.0
      max_vel_theta: 1.0
      min_speed_xy: 0.0
      max_speed_xy: 0.26
      min_speed_theta: 0.0
      acc_lim_x: 2.5
      acc_lim_y: 0.0
      acc_lim_theta: 3.2
      decel_lim_x: -2.5
      decel_lim_y: 0.0
      decel_lim_theta: -3.2
      vx_samples: 20
      vy_samples: 5
      vtheta_samples: 20
      sim_time: 1.7
      linear_granularity: 0.05
      angular_granularity: 0.025
      xy_goal_tolerance: 0.25
      path_length_tolerance: 1.0
      trans_stopped_velocity: 0.25
      short_circuit_trajectory_evaluation: True
      limit_vel_cmd_in_traj: False
      stateful: True
      critics: ["RotateToGoal", "Oscillation", "BaseObstacle", "GoalAlign", "PathAlign", "PathDist", "GoalDist"]
      BaseObstacle.scale: 0.02
      PathAlign.scale: 32.0
      GoalAlign.scale: 24.0
      PathAlign.forward_point_distance: 0.1
      GoalAlign.forward_point_distance: 0.1
      PathDist.scale: 32.0
      GoalDist.scale: 24.0
      RotateToGoal.scale: 32.0
      RotateToGoal.slowing_factor: 5.0
      RotateToGoal.lookahead_time: -1.0
BLOCK
python3 - "$PKG/config/nav2.yaml" "$DWB" <<'PY'
import re, sys, yaml
path, dwb = sys.argv[1], sys.argv[2]
s = open(path).read()

# FollowPath: 부터 다음 최상위 키(1열이 소문자인 줄) 직전까지를 새 블록으로 갈아끼움

if 'dwb_core::DWBLocalPlanner' in s:
    print("DWB 이미 적용됨")
else:
    m = re.search(r'^    FollowPath:\n(?:(?![a-z_]).*\n)*', s, re.M)
    if not m:
        sys.exit("FollowPath 블록을 찾지 못함")
    s = s[:m.start()] + open(dwb).read() + s[m.end():]
    print("  ✓ controller  MPPI → DWB")

if 'lifecycle_manager_navigation:' in s:
    print("bond_timeout 이미 설정됨")
else:
    s += "\nlifecycle_manager_navigation:\n  ros__parameters:\n    bond_timeout: 10.0\n"
    print("  ✓ bond_timeout: 10.0")

yaml.safe_load(s)
open(path, 'w').write(s)
PY

cat <<'MSG'

Successfully Completed.
MSG
