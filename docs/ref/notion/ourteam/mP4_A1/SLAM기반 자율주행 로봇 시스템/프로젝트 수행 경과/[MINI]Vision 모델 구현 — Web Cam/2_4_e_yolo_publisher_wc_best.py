"""best_v26s.pt(car / dummy)용 YOLO 웹캠 publisher.

2_4_e_yolo_publisher_wc.py 대비 변경점:
  - model 경로 / 카메라 / topic / conf 를 input() 대신 CLI 인자로 받음
  - 추론 전 프레임을 정사각형으로 center crop
    (학습 데이터의 Roboflow 전처리 "Fill (with center crop)"과 맞추기 위함)
  - annotated image를 원본 크기(2배 확대 없음)로 header stamp와 함께 publish
  - 시작 시 /dev/video* 목록 출력, --log-interval 초마다 상태 log 1줄
    (fps, 추론 ms, 프레임 밝기, 검출 수, subscriber 수), 검은 프레임이면 경고
    (privacy shutter가 닫혀 있거나 카메라 번호가 틀린 경우)
  - <topic>/compressed (JPEG)도 함께 publish → rosbag 용량 절약
  - annotated 프레임을 OpenCV 창으로 표시 ('q' 종료, --no-show 로 끄기)
  - class별로 bbox / 라벨 색을 다르게 그림 (car: 주황, dummy: 하늘색)

사용법:
  python3 2_4_e_yolo_publisher_wc_best.py [--model PATH] [--cam 0] [--conf 0.8]
                                          [--topic processed_image] [--no-crop]
                                          [--no-show] [--log-interval 2.0]
  --cam 에 이미지 폴더나 동영상 파일을 주면 웹캠 없이 반복 재생으로 테스트 가능
"""
import argparse
import json
import csv
import time
import math
import os
import shutil
import sys
import glob
from collections import Counter
from pathlib import Path
from ultralytics import YOLO
import cv2
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage

DEFAULT_MODEL = str(Path(__file__).resolve().parents[4] / 'm' / 'best_v26s.pt')
BLACK_FRAME_MEAN = 3.0  # 프레임 평균 밝기가 이 값보다 낮으면 카메라 영상이 안 들어오는 것으로 판단
# class별 bbox 색 (BGR). 표에 없는 class는 CLASS_COLORS_FALLBACK 에서 순서대로 사용
CLASS_COLORS = {'car': (0, 140, 255), 'dummy': (255, 200, 0)}
CLASS_COLORS_FALLBACK = [(0, 200, 0), (255, 0, 255), (0, 255, 255), (255, 0, 0)]


def class_color(cls_id, label):
    return CLASS_COLORS.get(label, CLASS_COLORS_FALLBACK[cls_id % len(CLASS_COLORS_FALLBACK)])


def draw_box(img, x1, y1, x2, y2, text, color):
    """bbox와, class 색으로 채운 라벨 배경 위에 글자를 그린다."""
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    ty = y1 - 6 if y1 - th - base - 6 > 0 else y2 + th + 6  # 위쪽 공간이 없으면 박스 아래에 표시
    cv2.rectangle(img, (x1, ty - th - base), (x1 + tw + 6, ty + base), color, -1)
    cv2.putText(img, text, (x1 + 3, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)


def list_video_devices():
    devs = []
    for d in sorted(glob.glob('/sys/class/video4linux/video*')):
        try:
            name = open(os.path.join(d, 'name')).read().strip()
        except OSError:
            name = '?'
        devs.append(f"/dev/{os.path.basename(d)} ({name})")
    return devs


class YOLOWebcamPublisher(Node):
    def __init__(self, model, output_dir, cam, topic, conf, crop, save, show, log_interval):
        super().__init__('yolo_webcam_publisher')
        self.model = model
        self.output_dir = output_dir
        self.conf = conf
        self.crop = crop
        self.save = save
        self.show = show
        self.should_shutdown = False
        # log 주기마다 집계하는 통계 (log_status()에서 초기화)
        self.n_frames = 0
        self.n_read_fail = 0
        self.infer_ms = 0.0
        self.brightness = 0.0
        self.cls_counter = Counter()
        self.last_dets = []
        self.total_frames = 0
        self.csv_output = []
        self.confidences = []
        self.max_object_count = 0
        self.classNames = model.names
        self.bridge = CvBridge()
        self.publisher = self.create_publisher(Image, topic, 10)
        # rosbag 기록용 JPEG 사본 (raw 1080x1080 bgr8은 약 30MB/s)
        self.comp_publisher = self.create_publisher(CompressedImage, topic + '/compressed', 10)

        self.get_logger().info("video devices: " + (", ".join(list_video_devices()) or "none"))
        self.status_timer = self.create_timer(log_interval, self.log_status)
        self.last_status = time.time()

        self.images = None
        if os.path.isdir(cam):
            self.images = sorted(glob.glob(os.path.join(cam, '*.jpg')) + glob.glob(os.path.join(cam, '*.png')))
            self.img_idx = 0
            self.cap = None
            self.get_logger().info(f"image folder {cam}: {len(self.images)} images, publishing on '{topic}', "
                                   f"conf={conf}, center_crop={crop}")
            self.timer = self.create_timer(0.1, self.process_frame)
            return

        self.cap = cv2.VideoCapture(int(cam), cv2.CAP_V4L2) if cam.isdigit() else cv2.VideoCapture(cam)
        if not self.cap.isOpened():
            self.get_logger().error(f"Failed to open webcam {cam}.")
            raise RuntimeError("Webcam not available")
        # 카메라가 지원하는 최대 해상도 요청 (학습 이미지는 1920x1080)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.get_logger().info(
            f"cam {cam}: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}, publishing on '{topic}', "
            f"conf={conf}, center_crop={crop}")

        self.timer = self.create_timer(0.1, self.process_frame)

    def read_frame(self):
        if self.images is not None:
            img = cv2.imread(self.images[self.img_idx])
            self.img_idx = (self.img_idx + 1) % len(self.images)
            return img is not None, img
        ret, img = self.cap.read()
        if not ret and self.cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0:  # 동영상 파일: 처음부터 반복
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, img = self.cap.read()
        return ret, img

    def process_frame(self):
        ret, img = self.read_frame()
        if not ret:
            self.n_read_fail += 1
            return
        self.n_frames += 1
        self.total_frames += 1
        self.brightness += float(img.mean())

        if self.crop:
            h, w = img.shape[:2]
            s = min(h, w)
            x0, y0 = (w - s) // 2, (h - s) // 2
            img = img[y0:y0 + s, x0:x0 + s].copy()

        t0 = time.time()
        results = self.model(img, stream=True, conf=self.conf, verbose=False)
        object_count = 0
        dets = []
        fontScale = 1

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = math.ceil((box.conf[0] * 100)) / 100
                cls = int(box.cls[0])
                label = self.classNames.get(cls, f"class_{cls}")
                self.confidences.append(confidence)
                draw_box(img, x1, y1, x2, y2, f"{label} {confidence}", class_color(cls, label))

                self.csv_output.append([x1, y1, x2, y2, confidence, label])
                self.cls_counter[label] += 1
                dets.append(f"{label}:{confidence}@({x1},{y1},{x2},{y2})")
                object_count += 1
        self.infer_ms += (time.time() - t0) * 1000
        self.last_dets = dets

        self.max_object_count = max(self.max_object_count, object_count)
        cv2.putText(img, f"Objects_count: {object_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, fontScale, (0, 255, 0), 2)

        if self.save and object_count > 0:
            filename = f'output_{int(time.time())}.jpg'
            cv2.imwrite(os.path.join(self.output_dir, filename), img)

        msg = self.bridge.cv2_to_imgmsg(img, encoding="bgr8")
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'webcam'
        self.publisher.publish(msg)

        comp = CompressedImage()
        comp.header = msg.header
        comp.format = 'jpeg'
        comp.data = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        self.comp_publisher.publish(comp)

        if self.show:
            if self.total_frames == 1:
                cv2.namedWindow("YOLO Detection (q: quit)", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("YOLO Detection (q: quit)", 720, 720)
            cv2.imshow("YOLO Detection (q: quit)", img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("'q' pressed, shutting down")
                self.should_shutdown = True

    def log_status(self):
        now = time.time()
        dt = now - self.last_status
        self.last_status = now
        n = self.n_frames
        if n == 0:
            self.get_logger().warn(f"no frames in last {dt:.1f}s (read failures: {self.n_read_fail})")
        else:
            bright = self.brightness / n
            dets = ", ".join(f"{k}={v}" for k, v in sorted(self.cls_counter.items())) or "none"
            self.get_logger().info(
                f"frames={self.total_frames} fps={n / dt:.1f} infer={self.infer_ms / n:.1f}ms "
                f"brightness={bright:.1f} dets[{dets}] last={self.last_dets} "
                f"subs={self.publisher.get_subscription_count()}")
            if bright < BLACK_FRAME_MEAN:
                self.get_logger().warn(
                    "frames are black: privacy shutter closed or wrong camera? "
                    "try another --cam (see 'video devices' above)")
        self.n_frames = self.n_read_fail = 0
        self.infer_ms = self.brightness = 0.0
        self.cls_counter.clear()

    def save_output(self):
        with open(os.path.join(self.output_dir, 'output.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['X1', 'Y1', 'X2', 'Y2', 'Confidence', 'Class'])
            writer.writerows(self.csv_output)

        with open(os.path.join(self.output_dir, 'output.json'), 'w') as f:
            json.dump(self.csv_output, f)

        with open(os.path.join(self.output_dir, 'statistics.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Max Object Count', 'Average Confidence'])
            avg_conf = sum(self.confidences) / len(self.confidences) if self.confidences else 0
            writer.writerow([self.max_object_count, avg_conf])

    def destroy_node(self):
        if self.cap is not None:
            self.cap.release()
        if self.show:
            cv2.destroyAllWindows()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=DEFAULT_MODEL, help='.pt / .onnx / .engine')
    parser.add_argument('--cam', default='0', help='카메라 번호, 이미지 폴더, 또는 동영상 파일')
    parser.add_argument('--topic', default='processed_image')
    parser.add_argument('--conf', type=float, default=0.8,
                        help='0.8이면 맵 벽 모서리 오검출(우리 이미지에서 최대 0.79)이 제거됨')
    parser.add_argument('--no-crop', dest='crop', action='store_false')
    parser.add_argument('--no-save', dest='save', action='store_false',
                        help='검출된 프레임 jpg를 ./output 에 저장하지 않음')
    parser.add_argument('--no-show', dest='show', action='store_false',
                        help='OpenCV 표시 창을 띄우지 않음')
    parser.add_argument('--log-interval', type=float, default=2.0,
                        help='상태 log 출력 주기(초)')
    args, ros_args = parser.parse_known_args()
    if args.show and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        print("⚠️  no DISPLAY, disabling the display window")
        args.show = False

    if not os.path.exists(args.model):
        print(f"❌ File not found: {args.model}")
        sys.exit(1)

    suffix = Path(args.model).suffix.lower()
    if suffix == '.pt':
        model = YOLO(args.model)
    elif suffix in ['.onnx', '.engine']:
        model = YOLO(args.model, task='detect')
    else:
        print(f"❌ Unsupported model format: {suffix}")
        sys.exit(1)

    output_dir = './output'
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)

    rclpy.init(args=ros_args)
    node = YOLOWebcamPublisher(model, output_dir, args.cam, args.topic,
                               args.conf, args.crop, args.save, args.show, args.log_interval)

    try:
        while rclpy.ok() and not node.should_shutdown:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        print("🔴 Shutdown requested. Exiting...")
    finally:
        node.save_output()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print("✅ Shutdown complete.")


if __name__ == '__main__':
    main()
