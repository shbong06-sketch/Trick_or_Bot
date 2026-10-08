"""웹캠 Detection Alert node (실적용판, 팀 공유용). 실행 파일: webcam_detector

고정 웹캠으로 car / dummy를 검출하고, AMR 쪽이 바로 받아 쓸 수 있는 메시지를 publish한다.

모델: best_v26n.pt (패키지 models/ 에 포함, colcon build 시 함께 설치)
  - 24개 run 비교(docs/notion_draft/vision_compare_wc.md)에서 선정한 YOLO26n (Ultralytics 기본 증강)
  - Test 오류(FP/FN) 0, Validation·Test mAP50-95 모두 1위, 맞힌 예측의 최저 confidence 0.936

wc/04_Inference/past_inf/2_4_e_yolo_publisher_wc_best.py 대비 변경점:
  - 기본 모델을 best_v26s.pt → best_v26n.pt 로 변경
  - 검출 결과를 다른 node가 받을 수 있게 publish (영상만 보내던 것 → 메시지 추가)
      webcam/detections  std_msgs/String (JSON)  매 프레임 검출 목록
      webcam/car_alert   std_msgs/Bool           car 알림 상태 (매 프레임)
  - 'car'가 아니라 '내 차'를 기준으로 알림 (class == car + bbox 안 검정 픽셀 >= --black-min)
      YOLO Tracking(ByteTrack)으로 car에 ID를 붙이고, 같은 ID를 계속 내 차로 본다.
  - car 알림은 시간 기준으로 안정화 (처리 주기와 무관, move_judge.CarAlert)
      최근 --on-sec 초 중 --on-ratio 이상 내 차 검출 → 알림 ON
      --off-sec 초 동안 내 차 미검출 → 알림 OFF
      (708초 실측에서 car 미검출은 대부분 1~2프레임짜리 순간 미검출이었음)
  - 가운데 정사각형 crop을 곧바로 640x640으로 줄여 쓴다 (학습 데이터와 같은 640x640).
      YOLO 내부 resize·bbox 되돌림 단계가 없어지고, 영상·bbox·JSON 모두 640 기준 하나로 통일
  - 카메라 버퍼를 1프레임으로 줄여 오래된 프레임을 처리하지 않게 함 (알림 지연 감소)
  - 영상 topic은 subscriber가 있을 때만 변환·publish (Wi-Fi 대역폭, CPU 절약)
  - 검출 프레임 jpg 저장은 기본 꺼짐(--save로 켬), ./output 을 지우지 않고 실행 시각별 폴더에 저장
  - 처리 주기를 15Hz로 고정 (PROCESS_HZ). 이유는 아래 "처리 주기 15Hz" 참고
  - torch·OpenCV 스레드를 1개로 제한 (기본 설정은 CPU를 코어 7개 넘게 쓰고, 제한하면 약 0.3개. 추론 시간은 같음)
  - 내 차 판정에서 bbox가 crop 경계(640x640의 가장자리)에 닿은 검출은 제외 (--edge-margin)
    사람 다리·팔이 화면 가장자리에서 car로 잡히는 오검출이 대부분 경계에 닿아 있었음 (guidance_7 S8 실측)
  - 촬영 해상도를 1920x1080 → 1280x720 으로 변경 (--width / --height), 30 FPS (--fps)
  - detections JSON에 원본 해상도(src_w, src_h), center crop 위치(crop_offset),
    crop 한 변 → 640 축소 비율(crop_scale), 640 영상 위 bbox(bbox_img) 추가
    (car_locator가 bbox를 원본 영상 pixel로 되돌려 map 좌표로 바꿀 때 사용)

처리 주기 15Hz (고정) — 이유
  1. 카메라는 30fps지만 이 node는 30Hz를 못 지킨다. 30Hz를 요청해도 실측은 14.8Hz였다 (guidance_7 Part B, 검출 간격 67ms).
     15Hz는 한 프레임 처리 약 20ms에 비해 주기 67ms로 3배 여유가 있어 안정적으로 지킨다 (실측 fps 14.9).
  2. 이 시스템의 판단은 모두 시간 기준이다 (알림 ON 0.3초 창, OFF 0.7초, 이동 확정 0.2초).
     15Hz면 0.3초 창에 4~5프레임, 0.2초에 3프레임이 들어와 한두 프레임 순간 미검출(708초 실측의 대부분)을 견딘다.
     10Hz 이하는 0.2초 안에 2프레임뿐이라 노이즈 억제가 약해지고, 5Hz는 알림 ON이 어렵다.
  3. 30Hz로 올려도 downstream이 얻는 정보가 없다. car_point는 0.3 m 움직일 때만 나가고, AMR(Nav2) 목표는 초당 1~2회 갱신이면 충분하다.
     반면 CPU는 약 2배 (스레드 1개 기준 15Hz 29% → 30Hz 56%).
  4. 튜터님도 30Hz 순간 정확도 유지를 권장하지 않았다.

publish하는 topic (기본 이름, --ns 로 앞부분 변경 가능):
  webcam/detections          std_msgs/String  JSON 예시:
    {"stamp": 1759555555.123, "frame_id": "webcam", "image_w": 640, "image_h": 640,
     "src_w": 1280, "src_h": 720, "crop_offset": [280, 0], "crop_scale": 1.125,
     "car_alert": true, "my_id": 3,
     "detections": [{"class": "car", "conf": 0.95, "bbox": [x1, y1, x2, y2], "bbox_img": [..],
                     "center": [cx, cy], "center_norm": [u, v],
                     "track_id": 3, "black": 0.62, "edge": false, "mine": true}]}
    - bbox·center는 기존 규약 그대로: crop한 정사각형(720x720) 기준 pixel → 원본 영상 pixel = bbox + crop_offset
      (팀원 rccar_follow가 이 규약으로 계산하므로 바꾸지 않음. 내부는 640으로 처리하고 내보낼 때만 crop_scale을 곱함)
    - bbox_img: /webcam/image(640x640) 위의 bbox, image_w/h = 640, center_norm은 0~1
    - detections 순서: 내 차가 맨 앞, 그 안에서 confidence 높은 순
    - track_id: ByteTrack ID (없으면 null), black: bbox 안 검정 픽셀 비율, edge: 가장자리에 닿음, mine: 내 차 여부
    - my_id: 지금 내 차로 보는 ID (내 차가 없으면 null)
  webcam/car_alert           std_msgs/Bool    car 알림 상태
  webcam/image               sensor_msgs/Image (bbox를 그린 영상)
  webcam/image/compressed    sensor_msgs/CompressedImage (JPEG, rosbag 기록용)

사용법 (colcon build 후):
  ros2 run detection_alert webcam_detector [--model PATH] [--cam 0] [--conf 0.8]
                                           [--width 1280] [--height 720]
                                           [--ns webcam] [--no-crop] [--no-show] [--save]
                                           [--on-sec 0.3] [--on-ratio 0.6] [--off-sec 0.7]
                                           [--black-v 110] [--black-min 0.4] [--edge-margin 3] [--fps 30]
  --cam 에 이미지 폴더나 동영상 파일을 주면 웹캠 없이 반복 재생으로 테스트 가능
  AMR 쪽에서 확인:  ros2 topic echo /webcam/car_alert
                    ros2 topic echo /webcam/detections
"""
import os

# 🔴 torch·OpenCV를 import하기 전에 스레드를 1개로 제한 (대기 중인 스레드가 CPU를 코어 7개 넘게 쓰는 것을 막음)
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import glob
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy._rclpy_pybind11 import RCLError
from rclpy.node import Node
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Bool, String
from ultralytics import YOLO

from detection_alert.move_judge import CarAlert


def default_model():
    """패키지와 함께 설치된 가중치 경로 (install/detection_alert/share/detection_alert/models/)."""
    try:
        from ament_index_python.packages import get_package_share_directory
        return str(Path(get_package_share_directory('detection_alert')) / 'models' / 'best_v26n.pt')
    except Exception:  # colcon build 없이 소스 파일을 직접 실행한 경우
        return str(Path(__file__).resolve().parents[1] / 'models' / 'best_v26n.pt')


PROCESS_HZ = 15.0       # 처리 주기 (고정). 이유는 위 docstring 참고
IMGSZ = 640             # 학습 해상도
BLACK_FRAME_MEAN = 3.0  # 프레임 평균 밝기가 이 값보다 낮으면 카메라 영상이 안 들어오는 것으로 판단
ALERT_CLASS = 'car'
# class별 bbox 색 (BGR). 표에 없는 class는 CLASS_COLORS_FALLBACK 에서 순서대로 사용
CLASS_COLORS = {'car': (0, 140, 255), 'dummy': (255, 200, 0)}
CLASS_COLORS_FALLBACK = [(0, 200, 0), (255, 0, 255), (0, 255, 255), (255, 0, 0)]
WINDOW = "Detection Alert (q: quit)"


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


def touches_edge(bbox, size, margin):
    """bbox가 영상 가장자리에 닿았는지 (margin pixel 이내). 잘린 물체라 아래 가운데 좌표도 믿기 어렵다."""
    x1, y1, x2, y2 = bbox
    return margin > 0 and (x1 <= margin or y1 <= margin or x2 >= size - margin or y2 >= size - margin)


def black_ratio(img, bbox, v_max):
    """bbox 안에서 밝기(HSV V)가 v_max 미만인 픽셀 비율 (검정 장난감 car 판별용)."""
    x1, y1, x2, y2 = bbox
    roi = img[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]
    if roi.size == 0:
        return 0.0
    return float((cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 2] < v_max).mean())


class DetectionAlertNode(Node):
    def __init__(self, model, args):
        super().__init__('webcam_detector')
        self.model = model
        self.conf = args.conf
        self.crop = args.crop
        self.show = args.show
        self.save_dir = None
        if args.save:
            self.save_dir = Path('./output') / datetime.now().strftime('%y%m%d_%H%M%S')
            self.save_dir.mkdir(parents=True, exist_ok=True)
        self.should_shutdown = False
        self.class_names = model.names
        self.bridge = CvBridge()
        self.alert = CarAlert(args.on_sec, args.on_ratio, args.off_sec)
        self.black_v = args.black_v
        self.black_min = args.black_min
        self.edge_margin = args.edge_margin
        self.my_id = None  # 지금 내 차로 보는 track ID

        ns = args.ns.strip('/')
        self.det_pub = self.create_publisher(String, f'{ns}/detections', 10)
        self.alert_pub = self.create_publisher(Bool, f'{ns}/car_alert', 10)
        self.img_pub = self.create_publisher(Image, f'{ns}/image', 10)
        # rosbag 기록용 JPEG 사본 (raw 640x640 bgr8은 프레임당 약 1.2MB)
        self.comp_pub = self.create_publisher(CompressedImage, f'{ns}/image/compressed', 10)

        # log 주기마다 집계하는 통계 (log_status()에서 초기화)
        self.n_frames = 0
        self.n_read_fail = 0
        self.infer_ms = 0.0
        self.brightness = 0.0
        self.cls_counter = Counter()
        self.last_dets = []
        self.total_frames = 0

        self.get_logger().info("video devices: " + (", ".join(list_video_devices()) or "none"))
        ds = os.environ.get('ROS_DISCOVERY_SERVER', '').strip(';')
        if ds:
            # 로봇에 연결되지 않았으면 이 PC의 다른 터미널(rosbag, topic echo)도 이 node를 못 찾는다
            self.get_logger().warn(
                f"discovery server {ds} 사용 중: 로봇 미연결이면 다른 터미널에서 topic이 안 보이고 "
                f"rosbag이 0개 기록됨 → 모든 터미널에서 source ~/ROKEY_mP4_A1/wc/ros_local.sh")

        self.images = None
        self.cap = None
        cam = args.cam
        if os.path.isdir(cam):
            self.images = sorted(glob.glob(os.path.join(cam, '*.jpg')) + glob.glob(os.path.join(cam, '*.png')))
            if not self.images:
                raise RuntimeError(f"no images in {cam}")
            self.img_idx = 0
            src = f"image folder {cam} ({len(self.images)} images)"
        else:
            self.cap = cv2.VideoCapture(int(cam), cv2.CAP_V4L2) if cam.isdigit() else cv2.VideoCapture(cam)
            if not self.cap.isOpened():
                self.get_logger().error(f"Failed to open webcam {cam}.")
                raise RuntimeError("Webcam not available")
            if cam.isdigit():
                # 촬영 해상도 고정 (기본 1280x720, 팀 기준). center crop 후 640x640으로 줄여 YOLO에 넣음
                self.cap.set(cv2.CAP_PROP_FPS, args.fps)
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
                # 버퍼에 쌓인 오래된 프레임 대신 최신 프레임을 읽기 위함
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            src = (f"cam {cam}: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                   f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        self.get_logger().info(
            f"{src}, model={Path(args.model).name}, conf={self.conf}, center_crop={self.crop}, "
            f"rate={PROCESS_HZ}Hz, alert ON={args.on_ratio:.0%}/{args.on_sec}s, OFF={args.off_sec}s, "
            f"내 차=car+검정(V<{self.black_v})>={self.black_min:.0%}+가장자리 {self.edge_margin}px 밖, topics: /{ns}/{{detections, car_alert, image, image/compressed}}")

        self.status_timer = self.create_timer(args.log_interval, self.log_status)
        self.last_status = time.time()
        self.timer = self.create_timer(1.0 / PROCESS_HZ, self.process_frame)

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

    @staticmethod
    def to_json(d, scale):
        """검출 1개를 JSON으로. bbox·center는 기존 규약(crop한 정사각형 기준 → 원본 = bbox + crop_offset)으로
        되돌려 보낸다 (팀원 rccar_follow가 이 규약으로 계산). 640 영상 위 좌표는 bbox_img."""
        out = {k: v for k, v in d.items() if k != 'cls_id'}
        out['bbox_img'] = d['bbox']
        out['bbox'] = [round(v * scale) for v in d['bbox']]
        out['center'] = [round(v * scale) for v in d['center']]
        return out

    def process_frame(self):
        if not self.context.ok():  # 종료 신호(SIGTERM 등) 직후에는 publish하지 않음
            return
        ret, img = self.read_frame()
        if not ret:
            self.n_read_fail += 1
            return
        stamp = self.get_clock().now()
        t_now = time.monotonic()
        self.n_frames += 1
        self.total_frames += 1
        self.brightness += float(img.mean())

        src_h, src_w = img.shape[:2]
        x0 = y0 = 0
        scale = 1.0  # 검출 영상 pixel → 원본 pixel 배율
        if self.crop:
            # 학습 데이터의 Roboflow 전처리 "Fill (with center crop)"과 맞추기 위한 정사각형 center crop.
            # 곧바로 학습 해상도(640x640)로 줄여 쓴다. (YOLO가 내부에서 줄이는 것과 같은 INTER_LINEAR라
            # 검출 결과는 같고, 이후 bbox·영상·JSON이 모두 640 기준 하나로 통일됨)
            s = min(src_h, src_w)
            x0, y0 = (src_w - s) // 2, (src_h - s) // 2
            img = cv2.resize(img[y0:y0 + s, x0:x0 + s], (IMGSZ, IMGSZ), interpolation=cv2.INTER_LINEAR)
            scale = s / IMGSZ
        h, w = img.shape[:2]

        t0 = time.time()
        # ByteTrack으로 같은 물체에 ID를 이어 붙임 (persist: 프레임 사이 상태 유지)
        r = self.model.track(img, imgsz=IMGSZ, conf=self.conf, persist=True,
                             tracker='bytetrack.yaml', verbose=False)[0]
        self.infer_ms += (time.time() - t0) * 1000

        dets = []
        for box in r.boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            cls = int(box.cls[0])
            label = self.class_names.get(cls, f'class_{cls}')
            black = black_ratio(img, (x1, y1, x2, y2), self.black_v) if label == ALERT_CLASS else None
            edge = label == ALERT_CLASS and touches_edge((x1, y1, x2, y2), w, self.edge_margin)
            dets.append({
                'class': label,
                'cls_id': cls,
                'conf': round(float(box.conf[0]), 3),
                'bbox': [x1, y1, x2, y2],
                'center': [(x1 + x2) // 2, (y1 + y2) // 2],
                'center_norm': [round((x1 + x2) / 2 / w, 4), round((y1 + y2) / 2 / h, 4)],
                'track_id': int(box.id[0]) if box.id is not None else None,
                'black': None if black is None else round(black, 3),
                'edge': edge,
                # 내 차 = class가 car + 검정 픽셀이 충분함 + 화면 가장자리에 안 닿음 (dummy·다른 색 car·사람 다리 제외)
                'mine': black is not None and black >= self.black_min and not edge,
            })
        # 내 차를 맨 앞에: 팀원 노드(rccar_follow)는 car 중 첫 번째만 쓰므로 오검출보다 내 차가 먼저 오게 한다
        dets.sort(key=lambda d: (not d['mine'], -d['conf']))
        self.cls_counter.update(d['class'] for d in dets)
        self.last_dets = [f"{d['class']}:{d['conf']:.2f}" for d in dets]

        # 내 차 ID: 이미 잡은 ID가 아직 보이면 그대로, 아니면 conf가 가장 높은 내 차
        mine = [d for d in dets if d['mine']]
        keep = next((d for d in mine if self.my_id is not None and d['track_id'] == self.my_id), None)
        chosen = keep or (mine[0] if mine else None)
        if chosen is not None:
            self.my_id = chosen['track_id']
        if self.alert.update(t_now, chosen is not None):
            if self.alert.active:
                self.get_logger().warn(
                    f"🚨 CAR ALERT ON  conf={chosen['conf']} black={chosen['black']} "
                    f"id={chosen['track_id']} center={chosen['center']}")
            else:
                self.get_logger().info("car alert OFF")
                self.my_id = None  # 알림이 꺼지면 다음에 보이는 내 차를 새로 잡음

        out = {
            'stamp': round(stamp.nanoseconds / 1e9, 3),
            'frame_id': 'webcam',
            'image_w': w,
            'image_h': h,
            'src_w': src_w,
            'src_h': src_h,
            'crop_offset': [x0, y0],
            'crop_scale': round(scale, 6),
            'car_alert': self.alert.active,
            'my_id': self.my_id if chosen is not None else None,
            'detections': [self.to_json(d, scale) for d in dets],
        }
        self.det_pub.publish(String(data=json.dumps(out)))
        self.alert_pub.publish(Bool(data=self.alert.active))

        # 영상은 보는 쪽(subscriber, 창, 저장)이 있을 때만 그린다
        need_img = self.img_pub.get_subscription_count() > 0
        need_comp = self.comp_pub.get_subscription_count() > 0
        need_save = self.save_dir is not None and len(dets) > 0
        if not (need_img or need_comp or need_save or self.show):
            return

        for d in dets:
            x1, y1, x2, y2 = d['bbox']
            text = f"{d['class']} {d['conf']:.2f}"
            if d['track_id'] is not None:
                text += f" #{d['track_id']}"
            if d['black'] is not None:
                text += f" b{d['black']:.0%}" + ("" if d['mine'] else " E" if d['edge'] else " X")  # X = 검정 부족, E = 가장자리에 닿음
            draw_box(img, x1, y1, x2, y2, text, class_color(d['cls_id'], d['class']))
        cv2.putText(img, f"objects: {len(dets)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        if self.alert.active:
            cv2.putText(img, "CAR ALERT", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

        header_stamp = stamp.to_msg()
        if need_img:
            msg = self.bridge.cv2_to_imgmsg(img, encoding='bgr8')
            msg.header.stamp = header_stamp
            msg.header.frame_id = 'webcam'
            self.img_pub.publish(msg)
        if need_comp:
            comp = CompressedImage()
            comp.header.stamp = header_stamp
            comp.header.frame_id = 'webcam'
            comp.format = 'jpeg'
            comp.data = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
            self.comp_pub.publish(comp)
        if need_save:
            cv2.imwrite(str(self.save_dir / f'det_{self.total_frames:06d}.jpg'), img)

        if self.show:
            if self.total_frames == 1:
                cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(WINDOW, 640, 640)
            cv2.imshow(WINDOW, img)
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
                f"car_alert={self.alert.active} my_id={self.my_id} "
                f"subs(det/alert/img/comp)={self.det_pub.get_subscription_count()}/"
                f"{self.alert_pub.get_subscription_count()}/{self.img_pub.get_subscription_count()}/"
                f"{self.comp_pub.get_subscription_count()}")
            if bright < BLACK_FRAME_MEAN:
                self.get_logger().warn(
                    "frames are black: privacy shutter closed or wrong camera? "
                    "try another --cam (see 'video devices' above)")
        self.n_frames = self.n_read_fail = 0
        self.infer_ms = self.brightness = 0.0
        self.cls_counter.clear()

    def destroy_node(self):
        if self.cap is not None:
            self.cap.release()
        if self.show:
            cv2.destroyAllWindows()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description='웹캠 car / dummy 검출 + car 알림 publish')
    parser.add_argument('--model', default=default_model(), help='.pt / .onnx / .engine')
    parser.add_argument('--cam', default='0', help='카메라 번호, 이미지 폴더, 또는 동영상 파일')
    parser.add_argument('--ns', default='webcam', help='topic 앞부분 (예: webcam → /webcam/car_alert)')
    parser.add_argument('--conf', type=float, default=0.8,
                        help='0.8이면 맵 벽 모서리 오검출(우리 이미지에서 최대 0.79)이 제거됨. '
                             'best_v26n의 Test 정답 최저 conf는 0.936')
    parser.add_argument('--width', type=int, default=1280, help='카메라 촬영 가로 해상도')
    parser.add_argument('--height', type=int, default=720, help='카메라 촬영 세로 해상도')
    parser.add_argument('--fps', type=int, default=30, help='카메라 촬영 FPS')
    parser.add_argument('--on-sec', type=float, default=0.3, help='알림 ON 판단 구간(초)')
    parser.add_argument('--on-ratio', type=float, default=0.6, help='알림 ON: 구간 중 내 차 검출 프레임 비율')
    parser.add_argument('--off-sec', type=float, default=0.7, help='알림 OFF: 내 차 미검출이 이만큼(초) 계속될 때')
    parser.add_argument('--black-v', type=int, default=110,
                        help='검정 판정 밝기(HSV V) 상한. 학습 데이터의 car bbox는 V<110 픽셀이 중앙값 65%%')
    parser.add_argument('--black-min', type=float, default=0.4, help='내 차: bbox 안 검정 픽셀 최소 비율')
    parser.add_argument('--edge-margin', type=int, default=3,
                        help='bbox가 검출 영상(640x640) 가장자리에서 이 pixel 안이면 내 차에서 제외 (0이면 끔)')
    parser.add_argument('--no-crop', dest='crop', action='store_false')
    parser.add_argument('--save', action='store_true',
                        help='검출된 프레임 jpg를 ./output/<실행시각>/ 에 저장')
    parser.add_argument('--no-show', dest='show', action='store_false', help='OpenCV 표시 창을 띄우지 않음')
    parser.add_argument('--log-interval', type=float, default=2.0, help='상태 log 출력 주기(초)')
    args, ros_args = parser.parse_known_args()
    if args.show and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        print("⚠️  no DISPLAY, disabling the display window")
        args.show = False

    if not os.path.exists(args.model):
        print(f"❌ File not found: {args.model}")
        sys.exit(1)
    suffix = Path(args.model).suffix.lower()
    if suffix not in ('.pt', '.onnx', '.engine'):
        print(f"❌ Unsupported model format: {suffix}")
        sys.exit(1)
    model = YOLO(args.model, task='detect')
    # 첫 추론의 GPU 초기화 지연(수백 ms)이 첫 프레임에 들어가지 않게 미리 1회 실행
    model.track(np.zeros((IMGSZ, IMGSZ, 3), np.uint8), imgsz=IMGSZ, persist=False, verbose=False)
    model.predictor.trackers[0].reset()  # 예열 때 쌓인 추적 상태를 지움

    rclpy.init(args=ros_args)
    try:
        node = DetectionAlertNode(model, args)
    except RuntimeError as e:
        print(f"❌ {e}: --cam 번호를 위 'video devices' 목록에서 다시 확인할 것")
        rclpy.shutdown()
        sys.exit(1)
    try:
        while rclpy.ok() and not node.should_shutdown:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        print("🔴 Shutdown requested. Exiting...")
    except RCLError:
        if rclpy.ok():  # 종료 중 생긴 오류가 아니면 그대로 알림
            raise
        print("🔴 Shutdown requested. Exiting...")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print("✅ Shutdown complete.")


if __name__ == '__main__':
    main()
