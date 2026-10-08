import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.duration import Duration

from sensor_msgs.msg import Image, CameraInfo, CompressedImage

from tf2_geometry_msgs.tf2_geometry_msgs import do_transform_point
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener

from cv_bridge import CvBridge
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator, TurtleBot4Directions

import numpy as np
import cv2
import threading

from rclpy.time import Time


class DepthToMap(Node):
    def __init__(self):
        super().__init__('depth_to_map_node')

        self.bridge = CvBridge()
        self.K = None
        self.lock = threading.Lock()

        ns = self.get_namespace()
        self.depth_topic = f'{ns}/oakd/stereo/image_raw/compressedDepth'  # 원본(image_raw) 대신 압축 Depth
        self.rgb_topic = f'{ns}/oakd/rgb/image_raw/compressed'
        self.info_topic = f'{ns}/oakd/rgb/camera_info'

        self.depth_image = None
        self.rgb_image = None
        self.clicked_point = None
        self.shutdown_requested = False

        self.display_image = None
        self.gui_thread_stop = threading.Event()
        self.gui_thread = threading.Thread(target=self.gui_loop, daemon=True)
        self.gui_thread.start()

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.navigator = TurtleBot4Navigator()
        if not self.navigator.getDockedStatus():
            self.get_logger().info('Docking before initializing pose')
            self.navigator.dock()

        initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
        self.navigator.setInitialPose(initial_pose)
        self.navigator.waitUntilNav2Active()
        self.navigator.undock()

        self.logged_intrinsics = False
        self.logged_rgb_shape = False
        self.logged_depth_shape = False

        self.create_subscription(CameraInfo, self.info_topic, self.camera_info_callback, 1)
        self.create_subscription(CompressedImage, self.depth_topic, self.depth_callback, 1)
        self.create_subscription(CompressedImage, self.rgb_topic, self.rgb_callback, 1)

        self.get_logger().info("TF Tree 안정화 시작. 5초 후 변환 시작합니다.")
        self.start_timer = self.create_timer(5.0, self.start_transform)

    def start_transform(self):
        self.get_logger().info("TF Tree 안정화 완료. 변환 시작합니다.")
        self.timer = self.create_timer(0.2, self.display_images)
        self.start_timer.cancel()

    def camera_info_callback(self, msg):
        with self.lock:
            self.K = np.array(msg.k).reshape(3, 3)
            if not self.logged_intrinsics:
                self.get_logger().info(
                    f"Camera intrinsics received: fx={self.K[0,0]:.2f}, fy={self.K[1,1]:.2f}, cx={self.K[0,2]:.2f}, cy={self.K[1,2]:.2f}"
                )
                self.logged_intrinsics = True

    def depth_callback(self, msg):
        try:
            # compressedDepth 데이터 = 앞 12바이트(설정 정보) + PNG 이미지
            png_data = np.frombuffer(msg.data[12:], np.uint8)
            depth = cv2.imdecode(png_data, cv2.IMREAD_UNCHANGED)  # uint16, 단위 mm (image_raw와 같음)
            if depth is None:
                self.get_logger().warn(f"Depth decode failed. format: {msg.format}")
                return
            if depth is not None and depth.size > 0:
                if not self.logged_depth_shape:
                    self.get_logger().info(f"Depth image received: {depth.shape}")
                    self.logged_depth_shape = True
                with self.lock:
                    self.depth_image = depth
                    self.camera_frame = msg.header.frame_id
        except Exception as e:
            self.get_logger().error(f"Depth CV bridge conversion failed: {e}")

    def rgb_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            rgb = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if rgb is not None and rgb.size > 0:
                if not self.logged_rgb_shape:
                    self.get_logger().info(f"RGB image decoded: {rgb.shape}")
                    self.logged_rgb_shape = True
                with self.lock:
                    self.rgb_image = rgb
        except Exception as e:
            self.get_logger().error(f"Compressed RGB decode failed: {e}")

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            with self.lock:
                self.clicked_point = (x, y)
            self.get_logger().info(f"Clicked RGB pixel: ({x}, {y})")

    def display_images(self):
        with self.lock:
            rgb = self.rgb_image.copy() if self.rgb_image is not None else None
            depth = self.depth_image.copy() if self.depth_image is not None else None
            click = self.clicked_point
            frame_id = getattr(self, 'camera_frame', None)

        if rgb is not None and depth is not None and frame_id:
            try:
                rgb_display = rgb.copy()
                depth_display = depth.copy()

                depth_normalized = cv2.normalize(depth_display, None, 0, 255, cv2.NORM_MINMAX)
                depth_colored = cv2.applyColorMap(depth_normalized.astype(np.uint8), cv2.COLORMAP_JET)

                if click:
                    x, y = click
                    if x < rgb_display.shape[1] and y < rgb_display.shape[0] and y < depth_display.shape[0] and x < depth_display.shape[1]:
                        z = float(depth_display[y, x]) / 1000.0
                        if 0.2 < z < 5.0:
                            fx, fy = self.K[0, 0], self.K[1, 1]
                            cx, cy = self.K[0, 2], self.K[1, 2]

                            X = (x - cx) * z / fx
                            Y = (y - cy) * z / fy
                            Z = z

                            pt_camera = PointStamped()
                            # pt_camera.header.stamp = self.get_clock().now().to_msg()

                            pt_camera.header.stamp = Time().to_msg()

                            pt_camera.header.frame_id = frame_id
                            pt_camera.point.x = X
                            pt_camera.point.y = Y
                            pt_camera.point.z = Z

                            try:
                                pt_map = self.tf_buffer.transform(
                                    pt_camera,
                                    'map',
                                    timeout=Duration(seconds=1.0)
                                )
                                self.get_logger().info(
                                    f"Map coordinate: ({pt_map.point.x:.2f}, {pt_map.point.y:.2f}, {pt_map.point.z:.2f})"
                                )
                            except Exception as e:
                                self.get_logger().warn(f"TF transform failed: {e}")

                        text = f"{z:.2f} m" if 0.2 < z < 5.0 else "Invalid"
                        cv2.putText(rgb_display, '+', (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        cv2.circle(rgb_display, (x, y), 4, (0, 255, 0), -1)
                        cv2.putText(depth_colored, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        cv2.circle(depth_colored, (x, y), 4, (255, 255, 255), -1)

                combined = np.hstack((rgb_display, depth_colored))
                if combined is not None and combined.size > 0:
                    with self.lock:
                        self.display_image = combined.copy()
            except Exception as e:
                self.get_logger().warn(f"Image display error: {e}")

    def gui_loop(self):
        cv2.namedWindow('RGB (left) | Depth (right)', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('RGB (left) | Depth (right)', 1280, 480)
        cv2.moveWindow('RGB (left) | Depth (right)', 100, 100)
        cv2.setMouseCallback('RGB (left) | Depth (right)', self.mouse_callback)

        while not self.gui_thread_stop.is_set():
            img = None
            with self.lock:
                if self.display_image is not None:
                    img = self.display_image.copy()

            if img is not None:
                cv2.imshow('RGB (left) | Depth (right)', img)
                key = cv2.waitKey(1)
                if key == ord('q'):
                    self.get_logger().info("Shutdown requested by user (via GUI).")
                    self.navigator.dock()
                    self.shutdown_requested = True
                    self.gui_thread_stop.set()
                    rclpy.shutdown()
            else:
                cv2.waitKey(10)


def main():
    rclpy.init()
    node = DepthToMap()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    node.gui_thread_stop.set()
    node.gui_thread.join()
    node.destroy_node()
    cv2.destroyAllWindows()



# =====================================================================================================
#  여기부터 3_3_c 부분. 위의 3_3_b 코드(DepthToMap·main)는 팀원 파일 그대로이며 수정하지 않았다.
#  (바뀐 것은 b 파일 맨 끝 실행 진입부 2 줄뿐 — 한 파일에 진입부는 하나라 아래 main_bc() 로 대체)
#
#  동작 순서
#    1) b 노드 생성 = b 의 도킹 → 초기 위치 → Nav2 대기 → 언도킹 (b 코드 그대로)
#    2) 그 다음에 c 노드 생성 → c 는 항상 b 뒤에 동작
#    3) b 창에서 클릭 → b 가 map 좌표 출력 (b 기능 그대로)
#    4) 터미널에 g + Enter → 마지막 클릭 지점 앞 STANDOFF_M 까지 Nav2 이동, 지점을 바라보게
#       c + Enter → 이동 취소
#  c 는 창을 따로 띄우지 않고(b 창 하나), 영상·TF·클릭은 b 가 받은 것을 읽기만 한다.
#  Nav2 는 c 노드의 액션 클라이언트로 보낸다 (b 의 navigator 와 같은 전역 실행기를 쓰지 않아 b 의 도킹과 안 부딪힘).
#  b 의 q(도킹 + 종료) 로 도킹이 시작되면 c 의 목표는 자동 취소.
#
#  실행 (b 와 같은 인자):
#    python3 3_3_bc_depth_to_nav_goal.py --ros-args -r __ns:=/robot1 -r /tf:=/robot1/tf -r /tf_static:=/robot1/tf_static
# =====================================================================================================
import math
import sys
import time

from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus, GoalStatusArray
from irobot_create_msgs.msg import DockStatus

STANDOFF_M = 0.5                     # 목표 = 클릭 지점 앞 이 거리 (지점 자체는 장애물이라 Nav2 가 못 감)


class GoToClick(Node):
    """b 노드의 마지막 클릭을 읽어 Nav2 목표로 보낸다. 명령은 터미널(g / c)."""

    def __init__(self, b):
        super().__init__('c_go_to_click')          # b 는 depth_to_map_node — 이름이 겹치지 않게
        self.b = b
        self.request = None                        # 'g' / 'c' (터미널 스레드 → 타이머에서 처리)
        self.goal_handle = None
        self.docked = None
        self.action_busy = {'dock': False, 'undock': False}

        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.create_subscription(DockStatus, 'dock_status', self.dock_callback, qos_profile_sensor_data)
        status_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
        for name in self.action_busy:
            self.create_subscription(GoalStatusArray, f'{name}/_action/status',
                                     lambda msg, n=name: self.action_status_callback(n, msg), status_qos)
        self.create_timer(0.05, self.control)
        self.get_logger().info('c 준비: b 창에서 클릭 → 터미널에 g + Enter = 이동, c + Enter = 취소')

    # ---------------- 상태 ----------------
    def dock_callback(self, msg):
        self.docked = msg.is_docked

    def action_status_callback(self, name, msg):
        self.action_busy[name] = any(
            s.status in (GoalStatus.STATUS_ACCEPTED, GoalStatus.STATUS_EXECUTING, GoalStatus.STATUS_CANCELING)
            for s in msg.status_list)

    def docking(self):
        return bool(self.docked) or any(self.action_busy.values())

    # ---------------- 명령 처리 (타이머 하나에서만) ----------------
    def control(self):
        if self.goal_handle is not None and self.docking():
            self.cancel('도킹·언도킹 시작 (b 의 q 등)')
        req, self.request = self.request, None
        if req == 'c':
            self.cancel('사용자')
        elif req == 'g':
            self.go()

    def click_to_map(self):
        """b 의 마지막 클릭 → map 좌표. b 와 같은 계산 (camera_info fx, 픽셀 1 개 depth, 최신 TF)."""
        b = self.b
        with b.lock:
            click, depth, K = b.clicked_point, b.depth_image, b.K
            frame_id = getattr(b, 'camera_frame', None)
        if click is None:
            return None, 'b 창에서 먼저 클릭하세요'
        if depth is None or K is None or not frame_id:
            return None, '영상·camera_info 대기'
        x, y = click
        if not (y < depth.shape[0] and x < depth.shape[1]):
            return None, f'클릭 ({x},{y}) 이 depth 영상 밖'
        z = float(depth[y, x]) / 1000.0
        if not 0.2 < z < 5.0:
            return None, f'클릭 ({x},{y}) depth {z:.2f} m 무효 (b 화면 Invalid)'
        pt = PointStamped()
        pt.header.stamp = Time().to_msg()
        pt.header.frame_id = frame_id
        pt.point.x = (x - K[0, 2]) * z / K[0, 0]
        pt.point.y = (y - K[1, 2]) * z / K[1, 1]
        pt.point.z = z
        try:
            p = b.tf_buffer.transform(pt, 'map', timeout=Duration(seconds=1.0)).point
            return (p.x, p.y), None
        except Exception as e:
            return None, f'TF 실패: {e}'

    def go(self):
        if self.docking():
            self.get_logger().warn('도크 위 또는 도킹·언도킹 중 — 이동 안 함')
            return
        target, err = self.click_to_map()
        if err:
            self.get_logger().warn(err)
            return
        try:
            t = self.b.tf_buffer.lookup_transform('map', 'base_link', Time()).transform.translation
        except Exception as e:
            self.get_logger().warn(f'TF map -> base_link 실패: {e}')
            return
        dx, dy = target[0] - t.x, target[1] - t.y
        dist = math.hypot(dx, dy)
        if dist <= STANDOFF_M:
            self.get_logger().info(f'이미 {dist:.2f} m 안 — 이동 안 함')
            return
        if not self.nav_client.server_is_ready():
            self.get_logger().warn('Nav2 navigate_to_pose 서버 없음')
            return
        k = (dist - STANDOFF_M) / dist
        yaw = math.atan2(dy, dx)                                       # 지점을 바라보게
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = t.x + dx * k
        goal.pose.pose.position.y = t.y + dy * k
        goal.pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=math.sin(yaw / 2.0), w=math.cos(yaw / 2.0))
        self.get_logger().info(f'Goal: ({goal.pose.pose.position.x:.2f}, {goal.pose.pose.position.y:.2f}) '
                               f'= 클릭 지점 ({target[0]:.2f}, {target[1]:.2f}) 앞 {STANDOFF_M} m')
        self.nav_client.send_goal_async(goal).add_done_callback(self.goal_response)

    def goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().warn('Nav2 가 목표 거절')
            return
        self.goal_handle = handle
        handle.get_result_async().add_done_callback(lambda f, h=handle: self.goal_result(h, f))

    def goal_result(self, handle, future):
        status = future.result().status
        names = {GoalStatus.STATUS_SUCCEEDED: '도착', GoalStatus.STATUS_CANCELED: '취소됨',
                 GoalStatus.STATUS_ABORTED: '실패'}
        self.get_logger().info(f'이동 결과: {names.get(status, status)}')
        if self.goal_handle is handle:
            self.goal_handle = None

    def cancel(self, why):
        if self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()
            self.goal_handle = None
            self.get_logger().info(f'목표 취소: {why}')


def read_terminal(c_node):
    """터미널 입력 스레드: g / c 를 타이머에 넘긴다 (b 창의 키는 b 코드가 처리하므로 여기서 받음)."""
    for line in sys.stdin:
        cmd = line.strip().lower()
        if cmd in ('g', 'c'):
            c_node.request = cmd
        elif cmd:
            print('g = 마지막 클릭 지점으로 이동, c = 취소 (종료는 b 창에서 q 또는 Ctrl+C)', flush=True)


def main_bc():
    rclpy.init()
    b = DepthToMap()                     # b: 도킹 → 초기 위치 → Nav2 → 언도킹이 여기서 끝난다
    c = GoToClick(b)                     # c: 그 다음에 시작
    executor = MultiThreadedExecutor()
    executor.add_node(b)
    executor.add_node(c)
    threading.Thread(target=read_terminal, args=(c,), daemon=True).start()
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    if rclpy.ok():
        c.cancel('종료')
    b.gui_thread_stop.set()
    b.gui_thread.join(timeout=2.0)
    executor.shutdown()
    c.destroy_node()
    b.destroy_node()
    cv2.destroyAllWindows()     # b 의 main 과 같은 종료 순서 (종료 때 Qt 경고 2 줄은 b 창이 GUI 스레드에서 도는 구조 때문)
    rclpy.try_shutdown()


if __name__ == '__main__':
    main_bc()
