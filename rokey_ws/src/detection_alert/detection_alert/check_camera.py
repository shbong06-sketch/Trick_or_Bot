"""웹캠이 보정 이후 움직였는지 확인한다.

지금 웹캠 화면 1장을 보정 때 사진(config/calib_image.jpg)과 비교해,
같은 특징점이 움직인 양을 map 거리(m)로 바꿔 잰다. (검출 영역 = 화면 가운데 720x720 안의 점만)
pixel 하나의 실제 거리는 화면 위치마다 다르므로 pixel이 아니라 map 거리로 판정한다.
움직였으면 homography.yaml은 더 이상 맞지 않는다.

사용법:
  ros2 run detection_alert check_camera --cam 5
  결과: ✅ (map 이동 0.05m 미만) / ❌ (0.05m 이상 → 다시 보정)
  비교 그림: config/check_camera.jpg (왼쪽: 보정 때, 오른쪽: 지금)
"""
import argparse
import sys

import cv2
import numpy as np

from detection_alert import homography as hg
from detection_alert.calib_homography import grab

LIMIT_M = 0.05


def main():
    parser = argparse.ArgumentParser(description='웹캠이 보정 이후 움직였는지 확인')
    parser.add_argument('--cam', required=True, help='카메라 번호')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--ref', default=str(hg.config_dir() / 'calib_image.jpg'), help='보정 때 사진')
    args = parser.parse_args()

    ref = cv2.imread(args.ref)
    if ref is None:
        sys.exit(f'❌ 보정 사진 없음: {args.ref}')
    now = grab(args.cam, args.width, args.height)

    a = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(now, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(4000)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None:
        sys.exit('❌ 특징점을 못 찾음 (화면이 너무 어둡거나 렌즈가 가려짐)')
    matches = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db),
                     key=lambda m: m.distance)[:500]
    pa = np.float32([ka[m.queryIdx].pt for m in matches])
    pb = np.float32([kb[m.trainIdx].pt for m in matches])
    _, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 3.0)
    ok = inl.ravel() == 1 if inl is not None else np.zeros(len(pa), bool)
    w = a.shape[1]
    s = min(a.shape)
    x0 = (w - s) / 2
    inside = ok & (pa[:, 0] >= x0) & (pa[:, 0] < x0 + s)   # 검출 영역(가운데 crop) 안의 점
    if inside.sum() < 20:
        print(f'❌ 같은 장면으로 보기 어려움 (검출 영역 일치 {inside.sum()}개): 카메라 방향이 크게 바뀜 → 다시 보정')
        shift = float('inf')
    else:
        H = hg.load(hg.default_path())['H']
        d_m = [np.linalg.norm(hg.pixel_to_map(H, *q) - hg.pixel_to_map(H, *p))
               for p, q in zip(pa[inside], pb[inside])]
        d_px = np.linalg.norm(pb[inside] - pa[inside], axis=1)
        shift = float(np.median(d_m))
        print(f'보정 사진 대비 이동: map {shift * 100:.1f} cm (상위 10% {np.percentile(d_m, 90) * 100:.1f} cm), '
              f'pixel {np.median(d_px):.1f} px (검출 영역 일치 {inside.sum()}개)')

    out = hg.config_dir() / 'check_camera.jpg'
    cv2.imwrite(str(out), np.hstack([cv2.resize(ref, (640, 360)), cv2.resize(now, (640, 360))]))
    print(f'비교 그림: {out} (왼쪽: 보정 때, 오른쪽: 지금)')
    if shift < LIMIT_M:
        print(f'✅ 카메라 이동이 {LIMIT_M * 100:.0f}cm 미만. 다음 단계로 진행')
    else:
        print('❌ 카메라가 움직였음. 이대로 측정하면 결과가 무효 → 다시 보정 (guidance_6_1 B)')
        sys.exit(1)


if __name__ == '__main__':
    main()
