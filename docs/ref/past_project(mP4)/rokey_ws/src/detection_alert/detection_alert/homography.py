"""웹캠 pixel ↔ map 좌표 변환 (homography) 공용 함수.

카메라가 고정돼 있고 car가 항상 바닥(평면) 위에 있으므로,
원본 영상 pixel (u, v) 와 map 좌표 (x, y) 사이는 3x3 행렬 H 하나로 바뀐다.
    [x, y, 1]ᵀ ∝ H · [u, v, 1]ᵀ
H는 바닥 위 4개 이상 점의 (pixel, map) 짝으로 구한다 (calib_homography).
"""
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml

PACKAGE = 'detection_alert'
FILE_NAME = 'homography.yaml'


def config_dir():
    """보정 파일을 두는 폴더.

    git으로 공유되도록 workspace의 src/detection_alert/config/ 를 우선 쓴다.
    (install/detection_alert/share/detection_alert → workspace = 4단계 위)
    src를 찾지 못하면 설치된 share/ 쪽을 쓴다.
    """
    try:
        from ament_index_python.packages import get_package_share_directory
        share = Path(get_package_share_directory(PACKAGE))
        src = share.parents[3] / 'src' / PACKAGE / 'config'
        return src if src.parent.is_dir() else share / 'config'
    except Exception:  # colcon build 없이 소스 파일을 직접 실행한 경우
        return Path(__file__).resolve().parents[1] / 'config'


def default_path():
    return config_dir() / FILE_NAME


def fit(pixel_points, map_points):
    """(pixel, map) 짝으로 H를 구하고, 각 점의 잔차(m)를 돌려준다.

    잔차: 구한 H로 그 점의 pixel을 바꿨을 때 실제 map 좌표와의 거리.
    점이 4개면 H가 모든 점을 정확히 지나 잔차가 0이라 확인이 안 된다 → 6개 이상 권장.
    잘못 클릭했거나 map 좌표가 틀린 점은 잔차가 크게 나온다.
    """
    px = np.asarray(pixel_points, np.float64).reshape(-1, 2)
    mp = np.asarray(map_points, np.float64).reshape(-1, 2)
    if len(px) != len(mp):
        raise ValueError(f'pixel 점 {len(px)}개, map 점 {len(mp)}개: 개수가 같아야 함')
    if len(px) < 4:
        raise ValueError(f'점이 {len(px)}개: 최소 4개 필요 (6개 이상 권장)')
    H, _ = cv2.findHomography(px, mp, 0)
    if H is None:
        raise ValueError('H를 구하지 못함: 점들이 한 직선 위에 있지 않은지 확인')
    residual = [float(np.linalg.norm(pixel_to_map(H, *p) - m)) for p, m in zip(px, mp)]
    return H, residual


def pixel_to_map(H, u, v):
    p = H @ np.array([u, v, 1.0])
    return p[:2] / p[2]


def map_to_pixel(H, x, y):
    p = np.linalg.inv(H) @ np.array([x, y, 1.0])
    return p[:2] / p[2]


def save(path, H, image_size, pixel_points, map_points, residual, source=''):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source_image': str(source),
        'image_size': [int(image_size[0]), int(image_size[1])],
        'homography': [[float(v) for v in row] for row in H],
        'pixel_points': [[float(u), float(v)] for u, v in pixel_points],
        'map_points': [[float(x), float(y)] for x, y in map_points],
        'residual_m': [round(e, 4) for e in residual],
    }
    header = ('# 웹캠 원본 영상 pixel (u, v) → map (x, y) 변환 행렬. calib_homography가 만듦\n'
              '# 삼각대(카메라)가 움직이거나 맵을 새로 만들면 다시 보정할 것\n')
    path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def load(path):
    data = yaml.safe_load(Path(path).read_text())
    data['H'] = np.array(data['homography'], np.float64)
    return data


def draw_overlay(img, H, pixel_points, map_points, step=0.5, margin=1.0):
    """map 격자(step m 간격)와 보정점을 영상 위에 그린다. 격자가 바닥 선과 맞으면 보정이 잘 된 것."""
    out = img.copy()
    mp = np.asarray(map_points, np.float64).reshape(-1, 2)
    x0, y0 = np.floor((mp.min(0) - margin) / step) * step
    x1, y1 = np.ceil((mp.max(0) + margin) / step) * step
    Hinv = np.linalg.inv(H)

    def project(pts):
        p = cv2.perspectiveTransform(np.asarray(pts, np.float64).reshape(-1, 1, 2), Hinv)
        return p.reshape(-1, 2)

    for x in np.arange(x0, x1 + 1e-6, step):
        line = project([[x, y] for y in np.linspace(y0, y1, 40)])
        cv2.polylines(out, [line.astype(np.int32)], False, (0, 255, 255) if abs(x) < 1e-6 else (0, 200, 0), 1)
    for y in np.arange(y0, y1 + 1e-6, step):
        line = project([[x, y] for x in np.linspace(x0, x1, 40)])
        cv2.polylines(out, [line.astype(np.int32)], False, (0, 255, 255) if abs(y) < 1e-6 else (0, 200, 0), 1)
    for i, ((u, v), (x, y)) in enumerate(zip(pixel_points, mp), 1):
        cv2.circle(out, (int(u), int(v)), 6, (0, 0, 255), -1)
        cv2.putText(out, f'{i} ({x:.2f},{y:.2f})', (int(u) + 8, int(v) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.putText(out, f'green grid: map {step} m', (10, out.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
    return out
