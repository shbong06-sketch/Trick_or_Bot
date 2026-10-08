"""웹캠 pixel → map 좌표 변환 행렬(homography)을 만든다.

준비물
  - 고정한 웹캠으로 찍은, 바닥이 비어 있는 원본 영상 (1280x720, crop 전)
      --image <파일> 로 주거나 --cam <번호> 로 바로 촬영 (webcam_detector가 카메라를 쓰고 있으면 먼저 끌 것)
  - 보정점(X 테이프)의 map 좌표: record_map_points 가 만든 map_points.yaml (--points)

창에서 X 테이프 중심을 map_points.yaml 과 같은 순서로 클릭
  왼쪽 클릭: 점 추가 / z: 마지막 점 취소 / Enter·Space: 계산 / Esc: 중단
  (map_points.yaml 에 pixel_points 가 있으면 클릭 없이 바로 계산)

결과
  homography.yaml          car_locator가 읽는 행렬 (기본: src/detection_alert/config/)
  homography_preview.jpg   map 격자를 영상 위에 그린 확인용 이미지
  잔차(m)                  구한 H로 각 점을 바꿨을 때 실제 map 좌표와의 거리. 0.05m 이하면 충분
  검증점 오차(m)           --check K: 마지막 K개 점은 H 계산에 안 쓰고 맞히는지만 확인. 0.1m 이하면 충분
                           (틀린 점 하나는 잔차에 잘 안 드러나므로, 가운데쪽 점 1개를 검증점으로 두는 것을 권장)

사용법:
  ros2 run detection_alert calib_homography --cam 4 [--points map_points.yaml] [--out homography.yaml]
  ros2 run detection_alert calib_homography --image floor.jpg ...
"""
import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

from detection_alert import homography as hg

WINDOW = 'calib_homography (click X marks in order / z: undo / Enter: done / Esc: quit)'


def grab(cam, width, height, n_skip=10):
    cap = cv2.VideoCapture(int(cam), cv2.CAP_V4L2)
    if not cap.isOpened():
        sys.exit(f'❌ 카메라 {cam} 을 열 수 없음 (webcam_detector가 쓰고 있으면 먼저 끌 것)')
    # webcam_detector와 같은 촬영 설정
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    img = None
    for _ in range(n_skip):  # 노출이 안정될 때까지 앞 프레임은 버림
        ok, frame = cap.read()
        if ok:
            img = frame
    cap.release()
    if img is None:
        sys.exit(f'❌ 카메라 {cam} 에서 프레임을 못 읽음')
    return img


def click_points(img, n_expected, map_points):
    pts = []
    h, w = img.shape[:2]
    s = min(h, w)
    crop = ((w - s) // 2, (h - s) // 2, s)  # webcam_detector가 검출에 쓰는 영역

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < n_expected:
            pts.append((x, y))

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, w, h)
    cv2.setMouseCallback(WINDOW, on_mouse)
    while True:
        view = img.copy()
        x0, y0, s = crop
        cv2.rectangle(view, (x0, y0), (x0 + s - 1, y0 + s - 1), (255, 0, 255), 1)
        cv2.putText(view, 'detector area (center crop)', (x0 + 5, y0 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
        for i, (u, v) in enumerate(pts, 1):
            cv2.drawMarker(view, (u, v), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.putText(view, str(i), (u + 8, v - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        if len(pts) < n_expected:
            x, y = map_points[len(pts)]
            msg = f'click X #{len(pts) + 1} / {n_expected}  (map {x:.2f}, {y:.2f})'
        else:
            msg = 'all points clicked: Enter = compute, z = undo'
        cv2.putText(view, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imshow(WINDOW, view)
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            cv2.destroyAllWindows()
            sys.exit('중단됨')
        if k == ord('z') and pts:
            pts.pop()
        if k in (13, 10, 32) and len(pts) == n_expected:
            break
    return pts


def main():
    parser = argparse.ArgumentParser(description='웹캠 pixel → map homography 보정')
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--image', help='바닥이 비어 있는 원본 영상 파일 (crop 전, 1280x720)')
    src.add_argument('--cam', help='카메라 번호: 바로 1장 촬영')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--points', default=str(hg.config_dir() / 'map_points.yaml'),
                        help='record_map_points가 만든 map 좌표 yaml')
    parser.add_argument('--out', default=str(hg.default_path()), help='저장할 homography yaml')
    parser.add_argument('--check', type=int, default=0,
                        help='마지막 K개 점은 계산에 쓰지 않고 검증에만 사용 (권장 1)')
    args = parser.parse_args()

    data = yaml.safe_load(Path(args.points).read_text())
    map_points = data['map_points']
    print(f'map 점 {len(map_points)}개: {args.points}')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            sys.exit(f'❌ 이미지를 못 읽음: {args.image}')
        source = args.image
    else:
        img = grab(args.cam, args.width, args.height)
        source = out.parent / 'calib_image.jpg'
        cv2.imwrite(str(source), img)
        print(f'촬영 원본 저장: {source}')
    h, w = img.shape[:2]
    if (w, h) != (args.width, args.height):
        print(f'⚠️  영상 크기 {w}x{h} ≠ webcam_detector 촬영 크기 {args.width}x{args.height}')

    if data.get('pixel_points'):
        pixel_points = [tuple(p) for p in data['pixel_points']]
        print('map_points.yaml의 pixel_points 사용 (클릭 생략)')
    else:
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            sys.exit('❌ 화면(DISPLAY)이 없어 클릭할 수 없음')
        pixel_points = click_points(img, len(map_points), map_points)

    k = len(map_points) - args.check
    H, res = hg.fit(pixel_points[:k], map_points[:k])
    check = [float(np.linalg.norm(hg.pixel_to_map(H, *p) - np.array(m)))
             for p, m in zip(pixel_points[k:], map_points[k:])]
    hg.save(out, H, (w, h), pixel_points[:k], map_points[:k], res, source)
    print(f'\n✅ 저장: {out}')
    print('  #   pixel(u, v)        map(x, y)          잔차')
    for i, ((u, v), (x, y)) in enumerate(zip(pixel_points, map_points)):
        e = f'{res[i]:.3f} m' if i < k else f'{check[i - k]:.3f} m  ← 검증점'
        print(f'  {i + 1:<3} ({u:6.1f}, {v:6.1f})   ({x:7.3f}, {y:7.3f})   {e}')
    print(f'  최대 {max(res):.3f} m / 평균 {np.mean(res):.3f} m'
          + ('  ⚠️ 0.05m 넘는 점: 클릭 위치나 map 좌표를 다시 확인' if max(res) > 0.05 else ''))
    if len(res) < 6:
        print(f'  ⚠️ 계산에 쓴 점이 {len(res)}개: 6개 이상 권장')
    if check:
        print(f'  검증점 오차 최대 {max(check):.3f} m'
              + ('  ⚠️ 0.1m 초과: 클릭 순서·위치, map 좌표를 다시 확인' if max(check) > 0.1 else '  ✅'))

    preview = hg.draw_overlay(img, H, pixel_points, map_points)
    pv = out.with_name('homography_preview.jpg')
    cv2.imwrite(str(pv), preview)
    print(f'확인용 이미지: {pv}  (초록 격자가 바닥과 자연스럽게 겹치면 OK)')
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        cv2.namedWindow('preview (any key)', cv2.WINDOW_NORMAL)
        cv2.imshow('preview (any key)', preview)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
