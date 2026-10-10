"""Real CUDA acceptance checks; expected boxes must come from human labels."""

# 실행: python -m pytest -q <이 파일> --run-gpu --gpu-cases /path/cases.json
# --run-gpu 미지정 시 SKIP. 지정한 경우 CUDA·모델·이미지·정답 오류는 실패한다.
# JSON 예: [{"image": "present.jpg", "boxes": [[20, 30, 80, 90]]},
#           {"image": "absent.jpg", "boxes": []}]
# 이미지 경로는 JSON 기준. 박스는 사람이 확인한 원본 픽셀 xyxy이며 위 좌표는 형식 예시다.
# 실제 추론을 정답 개수·IoU >= 0.5로 검증한다. 정답을 탐지 출력에서 만들지 않는다.
# 양성·음성 이미지 모두 필요하며 카메라 처리율·네트워크 지연·장기 안정성은 별도 검증한다.

import json
from itertools import permutations
import math
from pathlib import Path

import cv2
import pytest
import torch
import yaml

from conftest import PACKAGE_DIR


@pytest.fixture(scope='module')
def gpu_detector(request, detector_module):
    if not request.config.getoption('--run-gpu'):
        pytest.skip('Real GPU checks require --run-gpu and labelled images')
    assert torch.cuda.is_available(), 'GPU tests requested, but CUDA unavailable'
    params = yaml.safe_load((PACKAGE_DIR / 'config/detectors.yaml').read_text())[
        'boo_detector_node'
    ]['ros__parameters']
    model = PACKAGE_DIR / params['model_path']
    return detector_module.Detector(
        model_path=str(model), device=params['device'],
        target_class_id=params['target_class_id'],
        confidence_threshold=params['confidence_threshold'],
    )


@pytest.mark.gpu
def test_real_model_loaded_on_gpu(gpu_detector):
    assert next(gpu_detector._model.parameters()).is_cuda


def iou(first, second):
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_first = (first[2] - first[0]) * (first[3] - first[1])
    area_second = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (area_first + area_second - intersection)


@pytest.mark.gpu
def test_real_images_match_independent_ground_truth(request, gpu_detector):
    manifest_path = request.config.getoption('--gpu-cases')
    assert manifest_path, '--gpu-cases must provide independently labelled images'
    manifest = Path(manifest_path).resolve()
    cases = json.loads(manifest.read_text())
    assert isinstance(cases, list) and cases
    assert any(case['boxes'] for case in cases), 'Positive cases required'
    assert any(not case['boxes'] for case in cases), 'Negative cases required'
    for case in cases:
        image_path = manifest.parent / case['image']
        image = cv2.imread(str(image_path))
        assert image is not None, f'Cannot read {image_path}'
        height, width = image.shape[:2]
        expected = case['boxes']
        for box in expected:
            assert len(box) == 4 and all(math.isfinite(v) for v in box)
            assert 0 <= box[0] < box[2] <= width
            assert 0 <= box[1] < box[3] <= height
        for _ in range(3):
            actual = gpu_detector.detect(image)
            assert len(actual) == len(expected), f'Unexpected detection count: {image_path}'
            for item in actual:
                assert item.class_id == gpu_detector.target_class_id
                assert gpu_detector.confidence_threshold <= item.confidence <= 1
                assert all(math.isfinite(value) for value in item.bbox)
                assert 0 <= item.bbox[0] < item.bbox[2] <= width
                assert 0 <= item.bbox[1] < item.bbox[3] <= height
            # Any one-to-one matching is valid; prediction order is irrelevant.
            assert any(
                all(iou(item.bbox, box) >= 0.5 for item, box in zip(actual, ordering))
                for ordering in permutations(expected)
            ), f'Wrong object/location: {image_path}'
