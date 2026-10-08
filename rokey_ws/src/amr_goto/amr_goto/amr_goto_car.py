#!/usr/bin/env python3
"""웹캠이 알려 준 car 좌표 앞 1.2 m까지 AMR을 보내는 노드.

흐름
  1. 도크 위에서 초기 위치 설정 → Nav2 준비 대기
  2. 웹캠 car 좌표(/webcam/car_point)가 오면 언도킹
  3. car 앞 1.2 m 지점으로 이동 (Nav2 경로 기준 → 벽 너머에 멈추지 않음, car를 바라보는 방향)
     - 웹캠 car 좌표가 0.5 m 넘게 바뀌면 → 목표를 다시 계산
     - AMR 카메라 노드가 car를 찾으면(/robot1/car_point) → 목표 보내기를 멈춤 (넘겨줌)
     - 도착하면 → /robot1/goto_arrived 발행
     - 실패하면 → 2번 다시 시도, 그래도 안 되면 새 car 좌표를 기다림

토픽
  받기  /webcam/car_point       PointStamped (map)  웹캠 PC의 car 좌표
  받기  /robot1/car_point       PointStamped (map)  AMR 카메라 노드의 car 좌표
  받기  /robot1/amcl_pose       로봇 현재 위치
  보내기 /robot1/goto_arrived    PointStamped (map)  1.2 m 지점 도착 (car 좌표)

실행
  ros2 run amr_goto amr_goto_car --ros-args -r __ns:=/robot1
"""

import math
import time

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import PointStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import TaskResult
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

# ======================
# 초기 설정
# ======================
INITIAL_POSE_POSITION = [0.0, 0.0]          # 도크 위치 (팀 지도 map_auto_261006_1214)
INITIAL_POSE_DIRECTION = TurtleBot4Directions.NORTH

# 맨 앞에 / 가 있으면 -r __ns:=/robot1 로 실행해도 이름이 그대로다.
WEBCAM_TOPIC = '/webcam/car_point'
# 맨 앞에 / 가 없으면 /robot1/ 이 앞에 붙는다.
AMR_TOPIC = 'car_point'                     # → /robot1/car_point (팀원 depth_to_car가 보냄)
ARRIVED_TOPIC = 'goto_arrived'              # → /robot1/goto_arrived

APPROACH_DIST = 1.2   # car 중심에서 이만큼 앞에 멈춤 (m)
REPLAN_DIST = 0.5     # 웹캠 car 좌표가 이만큼 바뀌면 목표 다시 계산 (m)
MAX_RETRIES = 2       # 이동 실패 시 다시 시도하는 횟수
# ======================

webcam_car = None     # 웹캠이 보낸 최신 car 좌표 (x, y)
robot = None          # 로봇 현재 위치 (x, y)
amr_found = False     # AMR 카메라 노드가 car를 찾았으면 True


def webcam_callback(msg):
    global webcam_car
    webcam_car = (msg.point.x, msg.point.y)


def robot_callback(msg):
    global robot
    robot = (msg.pose.pose.position.x, msg.pose.pose.position.y)


def amr_callback(msg):
    global amr_found
    amr_found = True


def distance(a, b):
    """두 점 a, b 사이의 거리 (m). a, b는 (x, y)."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy)     # = 루트(dx제곱 + dy제곱)


def point_on_path(navigator, car):
    """Nav2가 짜 준 로봇 → car 경로에서, car와 APPROACH_DIST 떨어진 지점. 실패하면 None.

    경로는 벽을 돌아서 car가 있는 쪽으로 들어가는 실제 길이다.
    그래서 경로의 car 쪽 끝부분에서 고른 지점은 car와 같은 쪽(벽 너머가 아님)이다.
    """
    car_pose = navigator.getPoseStamped([car[0], car[1]], 0.0)
    # getPath(시작, 목표): 시작 자리는 쓰이지 않고, 로봇 현재 위치에서 경로를 짠다. (로봇은 안 움직임)
    path = navigator.getPath(car_pose, car_pose)
    if path is None or len(path.poses) == 0:
        return None

    # 경로 점들을 car 쪽 끝(마지막)부터 로봇 쪽(처음)으로 하나씩 본다.
    # car와 APPROACH_DIST 이상 떨어진 첫 점이 멈출 지점이다.
    for pose_stamped in reversed(path.poses):
        p = pose_stamped.pose.position
        if distance((p.x, p.y), car) >= APPROACH_DIST:
            return [p.x, p.y]

    # 경로 전체가 car와 APPROACH_DIST 안쪽 = 로봇이 이미 충분히 가까움 → 경로 시작점(로봇 자리)
    p = path.poses[0].pose.position
    return [p.x, p.y]


def point_on_line(car):
    """로봇 → car 직선 위에서 car 앞 APPROACH_DIST 지점. (경로를 못 받았을 때 대신 사용)"""
    if robot is None:
        rx = INITIAL_POSE_POSITION[0]
        ry = INITIAL_POSE_POSITION[1]
    else:
        rx = robot[0]
        ry = robot[1]

    dx = car[0] - rx
    dy = car[1] - ry
    dist = math.hypot(dx, dy)                    # 로봇 ~ car 거리 = 루트(dx제곱 + dy제곱)

    if dist <= APPROACH_DIST:
        # 이미 충분히 가까움: 제자리
        return [rx, ry]

    # 로봇에서 car 쪽으로 (dist - 1.2) m 만큼 가면 car까지 1.2 m가 남는다.
    # 예) car가 3 m 떨어져 있으면 ratio = (3 - 1.2) / 3 = 0.6
    #     → 로봇~car 사이의 60% 지점 = 로봇에서 1.8 m, car까지 1.2 m
    ratio = (dist - APPROACH_DIST) / dist
    return [rx + dx * ratio, ry + dy * ratio]


def make_goal(navigator, car):
    """car 앞 APPROACH_DIST 지점을 목표로 만든다. 방향은 car를 바라보게."""
    position = point_on_path(navigator, car)
    if position is None:
        navigator.warn('No path from Nav2 -> use straight line')
        position = point_on_line(car)

    # 멈출 지점 → car 방향 각도. atan2(dy, dx)는 라디안으로 나오고(+x 방향이 0, 반시계가 +),
    # getPoseStamped()는 도(degree) 단위를 받으므로 degrees()로 바꾼다.
    dx = car[0] - position[0]
    dy = car[1] - position[1]
    yaw = math.degrees(math.atan2(dy, dx))

    navigator.info(f'Goal ({position[0]:.2f}, {position[1]:.2f}), yaw {yaw:.0f} deg '
                   f'/ car ({car[0]:.2f}, {car[1]:.2f})')
    return navigator.getPoseStamped(position, yaw)


def drive(navigator, target):
    """target 앞으로 이동하면서 지켜본다. 결과를 글자로 돌려준다.

    'HANDOVER'  AMR 카메라 노드가 car를 찾음
    'CAR_MOVED' 웹캠 car가 움직임
    'ARRIVED'   도착
    'FAILED'    이동 실패
    """
    navigator.goToPose(make_goal(navigator, target))

    # isTaskComplete() 안에서 콜백도 처리되므로 webcam_car, amr_found가 갱신된다.
    while not navigator.isTaskComplete():
        if amr_found:
            return 'HANDOVER'
        if distance(webcam_car, target) > REPLAN_DIST:
            return 'CAR_MOVED'

    if navigator.getResult() == TaskResult.SUCCEEDED:
        return 'ARRIVED'

    # 실패: AMR 카메라 노드가 새 목표를 보내서 내 목표가 밀려난 것일 수도 있다.
    # 0.5초 기다렸다가 확인한다. (0.1초씩 쉬면서 5번 → 0.5초 동안 들어온 메시지 처리)
    for i in range(5):
        time.sleep(0.1)
        rclpy.spin_once(navigator, timeout_sec=0.0)
    if amr_found:
        return 'HANDOVER'
    return 'FAILED'


def main():
    rclpy.init()
    navigator = TurtleBot4Navigator()

    # 웹캠 좌표는 웹캠 PC가 마지막 값을 남겨 두는 방식(transient_local)으로 보낸다.
    # 같은 방식으로 받아야, 이 노드보다 먼저 보낸 좌표도 받을 수 있다.
    latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
    navigator.create_subscription(PointStamped, WEBCAM_TOPIC, webcam_callback, latched)
    navigator.create_subscription(PoseWithCovarianceStamped, 'amcl_pose', robot_callback, 10)
    # AMR 좌표는 기본 방식으로 받는다 → 지난번 실행에서 남은 값은 안 받고 새 값만 받는다.
    navigator.create_subscription(PointStamped, AMR_TOPIC, amr_callback, 10)
    arrived_pub = navigator.create_publisher(PointStamped, ARRIVED_TOPIC, latched)

    # 1. 도크에서 시작해야 한다 (초기 위치가 도크 기준이므로)
    # 자동 도킹(dock)은 하지 않는다: 멀리서 하면 다른 팀 도크로 갈 수 있다.
    if not navigator.getDockedStatus():
        navigator.error('Not on the dock. Put the robot on the dock and run again.')
        navigator.destroy_node()
        rclpy.shutdown()
        return

    # 2. 초기 위치 설정 + Nav2 준비 대기
    initial_pose = navigator.getPoseStamped(INITIAL_POSE_POSITION, INITIAL_POSE_DIRECTION)
    navigator.setInitialPose(initial_pose)
    navigator.waitUntilNav2Active()

    # 3. 웹캠 car 좌표가 올 때까지 대기
    navigator.info('Waiting for car point on ' + WEBCAM_TOPIC)
    while webcam_car is None:
        rclpy.spin_once(navigator, timeout_sec=0.1)
    navigator.info(f'Car point received: ({webcam_car[0]:.2f}, {webcam_car[1]:.2f})')

    # 4. 언도킹
    navigator.undock()

    # 언도킹이 실패해서 아직 도크에 붙어 있으면 주행하지 않고 끝낸다.
    # 바로 확인하면 예전 상태(도크에 있음)가 나올 수 있다. dock_status는 약 1초 간격(실측 g9: 간격의 53%가 1.0초 초과)이라
    # 1초만 기다리면 이미 내려왔는데도 실패로 볼 수 있다 → 도킹이 풀렸다는 새 상태가 올 때까지 최대 5초 기다린다.
    for i in range(50):
        time.sleep(0.1)
        rclpy.spin_once(navigator, timeout_sec=0.0)
        if not navigator.is_docked:
            break
    if navigator.getDockedStatus():
        navigator.error('Undock failed. Check the robot and run again.')
        navigator.destroy_node()
        rclpy.shutdown()
        return

    # 5. car 앞 1.2 m로 이동
    retries = 0
    while True:
        target = webcam_car
        state = drive(navigator, target)

        if state == 'HANDOVER':
            navigator.info('AMR camera found the car -> stop sending goals (hand over)')
            break

        if state == 'ARRIVED':
            msg = PointStamped()
            msg.header.frame_id = 'map'
            msg.header.stamp = navigator.get_clock().now().to_msg()
            msg.point.x = target[0]
            msg.point.y = target[1]
            arrived_pub.publish(msg)
            navigator.info('Arrived 1.2 m before the car -> published ' + ARRIVED_TOPIC)
            break

        if state == 'CAR_MOVED':
            navigator.info('Car moved -> new goal')
            retries = 0
            continue

        # state == 'FAILED'
        retries += 1
        if retries <= MAX_RETRIES:
            navigator.warn(f'Move failed -> retry {retries}/{MAX_RETRIES}')
            continue

        # 다시 시도해도 실패: car가 벽 가까이 있을 수 있다 → car가 움직일 때까지 기다림
        navigator.error('Move failed: waiting for a new car point (car near a wall?)')
        while not amr_found and distance(webcam_car, target) <= REPLAN_DIST:
            rclpy.spin_once(navigator, timeout_sec=0.1)
        if amr_found:
            navigator.info('AMR camera found the car -> stop sending goals (hand over)')
            break
        retries = 0

    # 6. 끝난 뒤에도 Ctrl+C 전까지 켜 둔다 (goto_arrived 값을 남겨 두기 위함)
    # 주의: 이동 중에 Ctrl+C로 꺼도 로봇은 목표로 계속 간다 → RViz Nav2 패널의 Cancel로 멈출 것
    try:
        rclpy.spin(navigator)
    except KeyboardInterrupt:
        pass
    navigator.destroy_node()
    # Ctrl+C를 누르면 rclpy가 이미 꺼진 상태라 shutdown()을 또 부르면 오류가 난다.
    # try_shutdown()은 "아직 안 꺼졌으면 끄기"라서 오류가 안 난다.
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
