# TrickOrBot 구현 지침 v2
# [공통 구현 원칙]
# - 아래 내용은 구현할 기능의 설명이며, 현재 기능이 구현되어 있다는 뜻은 아니다.
# - ROS 2 Jazzy와 현재 패키지 구조를 기준으로 최소한의 구현을 작성한다.
# - docs/interfaces.md와 관련 .msg/.srv 파일을 확인하고 공통 규격을 따른다.
# - 필수 규격이나 게임 규칙이 미정이면 필요한 결정 사항을 먼저 명시한다.
# - 미정인 값을 실제 장비에서 확인한 값처럼 사용하지 않는다.
# - 기존 ROS/Nav2 기능과 공통 모듈을 재사용하고 같은 기능을 중복 구현하지 않는다.
# - 요청하지 않은 패키지, 외부 서버, DB, 플러그인 구조는 추가하지 않는다.
# - 단순한 기능을 불필요한 클래스 계층이나 여러 보조 파일로 나누지 않는다.
# - 필요한 입력 검사와 안전 처리는 구현하되 자동 복구 기능을 임의로 확대하지 않는다.
# - 이 파일의 완료 기준을 만족하면 추가 기능 구현을 멈춘다.
#
# [역할]
# 부우 OAK-D의 RGB 영상에서 펌킨을 찾는 ROS 노드.
# [입출력]
# 입력: 부우 RGB 영상과 모델 설정. 출력: 촬영 시각을 유지한 탐지 결과.
# 출력 형식은 공통 명세의 tob_interfaces/TargetObservation 규격을 따른다.
# [구현]
# detector.py를 사용해 추론하고 대상 클래스와 신뢰도 기준으로 결과를 선택한다.
# 펌킨이 없는 처리 프레임은 빈 탐지 결과로 표현한다.
# [실패 처리]
# 모델 로딩 오류를 명확히 알리고 영상 처리 실패를 정상 탐지로 발행하지 않는다.
# 영상이 끊기면 이전 결과를 새 시각의 관측으로 반복 발행하지 않는다.
# [범위]
# 깊이 처리, 지도 좌표 계산, 추격·체포 판정은 담당하지 않는다.
# [완료 기준]
# 펌킨 있음·없음이 구분되고 탐지 결과에 원본 영상 시각이 유지된다.

"""Subscribe to compressed Boo RGB images and publish Pumpkin observations."""

import argparse
import math
from pathlib import Path
import sys

from ament_index_python.packages import (
    PackageNotFoundError,
    get_package_share_directory,
)
import cv2
import numpy as np
from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.utilities import remove_ros_args
from sensor_msgs.msg import CompressedImage
from tob_interfaces.msg import TargetObservation

from tob_perception.detector import Detector


class BooDetectorNode(Node):
    """Process new RGB frames using one GPU detector instance."""

    def __init__(self, debug: bool = False):
        """Read startup parameters and connect image input to observations."""
        super().__init__('boo_detector_node')
        try:
            self._debug_publisher = None
            try:
                package_dir = Path(get_package_share_directory('tob_perception'))
            except PackageNotFoundError:
                # Support direct source execution before package installation.
                package_dir = Path(__file__).resolve().parents[1]
            defaults = {
                'model_path': str(package_dir / 'models' / 'yolo11n_boo.pt'),
                'image_topic': '/robot1/oakd/rgb/image_raw/compressed',
                'detection_topic': '/tob/perception/pumpkin_detection',
                'source': 'boo_camera',
                'target_class_id': 0,
                'confidence_threshold': 0.5,
                'device': 0,
                'debug_image_topic': '/tob/perception/debug/image/compressed',
            }
            parameters = {}
            for name, default in defaults.items():
                parameters[name] = self.declare_parameter(
                    name, default, ParameterDescriptor(read_only=True)
                ).value
            for name in (
                'model_path', 'image_topic', 'detection_topic', 'source',
                'debug_image_topic',
            ):
                value = parameters[name]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'{name} must be a nonempty string')

            self._source = parameters['source']
            self._detector = Detector(
                model_path=parameters['model_path'],
                confidence_threshold=parameters['confidence_threshold'],
                device=parameters['device'],
                target_class_id=parameters['target_class_id'],
            )
            qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
            )
            self._publisher = self.create_publisher(
                TargetObservation, parameters['detection_topic'], qos
            )
            if debug:
                self._debug_class_name = str(
                    self._detector._model.names[parameters['target_class_id']]
                )
                self._debug_publisher = self.create_publisher(
                    CompressedImage, parameters['debug_image_topic'], qos
                )
            self._subscription = self.create_subscription(
                CompressedImage, parameters['image_topic'],
                self._image_callback, qos
            )
            self.get_logger().info(
                f"GPU {parameters['device']}: {parameters['image_topic']} -> "
                f"{parameters['detection_topic']}"
            )
        except Exception:
            self.destroy_node()
            raise

    def _image_callback(self, message: CompressedImage):
        """Publish one observation per successfully processed image."""
        try:
            encoded = np.frombuffer(message.data, dtype=np.uint8)
            if encoded.size == 0:
                raise ValueError('Compressed image data is empty')
            image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('Compressed image could not be decoded')

            detections = self._detector.detect(image)
            observation = TargetObservation()
            observation.header = message.header
            observation.source = self._source
            observation.map_valid = False
            if detections:
                best = max(detections, key=lambda item: item.confidence)
                height, width = image.shape[:2]
                if (
                    not all(math.isfinite(value) for value in best.bbox)
                    or not math.isfinite(best.confidence)
                    or not 0.0 <= best.confidence <= 1.0
                ):
                    raise ValueError('Detection contains invalid numeric values')
                x1, y1, x2, y2 = best.bbox
                x1, x2 = np.clip([x1, x2], 0, width).tolist()
                y1, y2 = np.clip([y1, y2], 0, height).tolist()
                if x2 <= x1 or y2 <= y1:
                    raise ValueError('Detection bounding box has no valid area')
                observation.detected = True
                observation.confidence = float(best.confidence)
                observation.bbox_center_x = (x1 + x2) / (2.0 * width)
                observation.bbox_center_y = (y1 + y2) / (2.0 * height)
                observation.bbox_width = (x2 - x1) / width
                observation.bbox_height = (y2 - y1) / height
            # No detection keeps the message's false/zero default values.
            self._publisher.publish(observation)
        except Exception as exc:
            self.get_logger().error(f'Image processing failed: {exc}')
            return

        if self._debug_publisher is not None:
            self._publish_debug_image(image, observation)

    def _publish_debug_image(self, image, observation: TargetObservation):
        """Publish an annotated JPEG image without affecting observations."""
        try:
            annotated = image.copy()
            if observation.detected:
                height, width = annotated.shape[:2]
                cx = observation.bbox_center_x * width
                cy = observation.bbox_center_y * height
                bw = observation.bbox_width * width
                bh = observation.bbox_height * height
                x1 = max(0, min(width - 1, round(cx - bw / 2)))
                y1 = max(0, min(height - 1, round(cy - bh / 2)))
                x2 = max(0, min(width - 1, round(cx + bw / 2)))
                y2 = max(0, min(height - 1, round(cy + bh / 2)))
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = (
                    f'{self._debug_class_name} {observation.confidence:.2f}'
                )
                cv2.putText(
                    annotated, label, (x1, max(15, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                    cv2.LINE_AA,
                )
            success, encoded = cv2.imencode('.jpg', annotated)
            if not success:
                raise RuntimeError('Debug image JPEG encoding failed')
            debug_message = CompressedImage()
            debug_message.header = observation.header
            debug_message.format = 'bgr8; jpeg compressed bgr8'
            debug_message.data = encoded.tobytes()
            self._debug_publisher.publish(debug_message)
        except Exception as exc:
            self.get_logger().error(f'Debug image publishing failed: {exc}')


def main(args=None):
    """Run the node; startup failures terminate without CPU fallback."""
    argv = sys.argv if args is None else ['boo_detector_node', *args]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--debug', action='store_true', help='publish annotated detection images'
    )
    options = parser.parse_args(remove_ros_args(args=argv)[1:])
    # rclpy consumes ROS arguments; argparse handles only non-ROS arguments.
    rclpy.init(args=argv)
    node = None
    try:
        node = BooDetectorNode(debug=options.debug)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception as exc:
        rclpy.logging.get_logger('boo_detector_node').warning(
            f'Detector stopped: {exc}'
        )
        return 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
