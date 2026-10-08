import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, CompressedImage
from geometry_msgs.msg import PointStamped
import numpy as np
import tf2_ros
import tf2_geometry_msgs
import cv2
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator, TurtleBot4Directions


class PixelToMapTest(Node):
    def __init__(self):
        super().__init__('pixel_to_map_test_node')

        self.K = None
        self.depth_image = None
        self.camera_frame = None
        self.rgb_image = None
        self.box = None  # 테스트용 박스 (클릭 위치 주변). 통합 때는 YOLO 박스

        ns = self.get_namespace()
        self.depth_topic = f'{ns}/oakd/stereo/image_raw/compressedDepth'
        self.info_topic = f'{ns}/oakd/rgb/camera_info'
        self.rgb_topic = f'{ns}/oakd/rgb/image_raw/compressed'

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # 3_3_b와 같음: 도크에서 초기 위치 설정 -> Nav2 대기 -> 언도킹
        self.navigator = TurtleBot4Navigator()
        if not self.navigator.getDockedStatus():
            self.navigator.dock()
        initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
        self.navigator.setInitialPose(initial_pose)
        self.navigator.waitUntilNav2Active()
        self.navigator.undock()

        self.create_subscription(CameraInfo, self.info_topic, self.camera_info_callback, 10)
        self.create_subscription(CompressedImage, self.depth_topic, self.depth_callback, 10)
        self.create_subscription(CompressedImage, self.rgb_topic, self.rgb_callback, 10)

        cv2.namedWindow('RGB')
        cv2.setMouseCallback('RGB', self.mouse_callback)
        self.create_timer(0.1, self.show_image)

    def camera_info_callback(self, msg):
        self.K = np.array(msg.k).reshape(3, 3)

    def depth_callback(self, msg):
        # compressedDepth = 앞 12바이트 + PNG (uint16, 단위 mm)
        depth_mm = cv2.imdecode(np.frombuffer(msg.data[12:], np.uint8), cv2.IMREAD_UNCHANGED)
        if depth_mm is None:
            return
        self.depth_image = depth_mm / 1000.0  # m로 바꿔서 시뮬과 똑같이 사용
        self.camera_frame = msg.header.frame_id

    def rgb_callback(self, msg):
        self.rgb_image = cv2.imdecode(np.frombuffer(msg.data, np.uint8), cv2.IMREAD_COLOR)

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # 클릭 위치 주변 40x40 박스를 YOLO 박스 대신 사용
            self.box = (x - 20, y - 20, x + 20, y + 20)
            pt_map = self.pixel_to_map(self.box)
            if pt_map is not None:
                self.get_logger().info(f"box {self.box} -> map: ({pt_map.point.x:.2f}, {pt_map.point.y:.2f})")

    def pixel_to_map(self, box):
        """박스 (x1, y1, x2, y2) -> map 좌표 PointStamped. 실패하면 None"""
        if self.K is None or self.depth_image is None:
            self.get_logger().warn('No camera_info or depth yet')
            return None

        # 1. 박스 중심 픽셀
        x1, y1, x2, y2 = box
        u = int((x1 + x2) / 2)
        v = int((y1 + y2) / 2)

        # 2. 중심 주변 5x5 영역에서 거리 구하기 (한 점만 보면 0이나 nan일 수 있음)
        area = self.depth_image[max(v - 2, 0):v + 3, max(u - 2, 0):u + 3]
        valid = area[np.isfinite(area) & (area > 0.2) & (area < 5.0)]
        if len(valid) == 0:
            self.get_logger().warn(f'Invalid depth at ({u}, {v})')
            return None
        z = float(np.median(valid))

        # 3. 픽셀 -> 카메라 3D
        fx = self.K[0, 0]
        fy = self.K[1, 1]
        cx = self.K[0, 2]
        cy = self.K[1, 2]

        pt = PointStamped()
        pt.header.frame_id = self.camera_frame
        pt.header.stamp = rclpy.time.Time().to_msg()  # 가장 최근 TF 사용
        pt.point.x = (u - cx) * z / fx
        pt.point.y = (v - cy) * z / fy
        pt.point.z = z

        # 4. 카메라 -> map
        try:
            pt_map = self.tf_buffer.transform(pt, 'map', timeout=rclpy.duration.Duration(seconds=0.5))
        except Exception as e:
            self.get_logger().warn(f'TF to map failed: {e}')
            return None

        self.get_logger().info(f"pixel ({u}, {v}), depth {z:.2f} m")
        return pt_map

    def show_image(self):
        if self.rgb_image is None:
            cv2.waitKey(1)
            return
        img = self.rgb_image.copy()
        if self.box is not None:
            x1, y1, x2, y2 = self.box
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imshow('RGB', img)
        cv2.waitKey(1)


def main():
    rclpy.init()
    node = PixelToMapTest()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    cv2.destroyAllWindows()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
