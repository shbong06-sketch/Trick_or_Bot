"""DESIGN_TEMP sections 5, 7, 8, 10: inference contract and errors."""

# 실행: python -m pytest -q <이 파일 경로>
# 결과 형식·필터링·모델 재사용과 설정·입력·추론 실패를 검증한다.
# GPU 가용성과 모델 실행만 대체하며 Ultralytics 결과 타입은 실제로 사용한다.
# 신뢰도 범위·박스 면적 위반은 실패로 남긴다. 실제 모델 정확도 검증은 GPU 테스트에서 한다.

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import torch
from ultralytics.engine.results import Results


def prediction(rows):
    """Use the library's real result representation at the model boundary."""
    image = np.zeros((120, 200, 3), dtype=np.uint8)
    boxes = torch.tensor(rows, dtype=torch.float32).reshape(-1, 6)
    return [Results(image, 'fixture.jpg', {0: 'pumpkin', 1: 'other'}, boxes=boxes)]


@pytest.fixture
def model_boundary(tmp_path, monkeypatch, detector_module):
    """Replace model execution, never the Detector logic under test."""
    weights = tmp_path / 'model.pt'
    weights.write_bytes(b'model loading is replaced in unit tests')
    model = Mock()
    model.task = 'detect'
    model.names = {0: 'pumpkin', 1: 'other'}
    model.predict.return_value = prediction([])
    loader = Mock(return_value=model)
    monkeypatch.setattr(detector_module, 'YOLO', loader)
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'device_count', lambda: 1)
    return SimpleNamespace(path=weights, model=model, loader=loader)


def test_detection_and_absence_have_consistent_public_format(
    detector_module, model_boundary,
):
    detector = detector_module.Detector(str(model_boundary.path))
    model_boundary.model.predict.side_effect = [
        prediction([[20, 30, 80, 90, 0.9, 0]]), prediction([]),
    ]
    image = np.zeros((120, 200, 3), dtype=np.uint8)
    found = detector.detect(image)
    absent = detector.detect(image)
    assert isinstance(found, list) and isinstance(absent, list)
    assert len(found) == 1 and absent == []
    assert isinstance(found[0], detector_module.Detection)
    assert found[0].bbox == pytest.approx((20, 30, 80, 90))
    assert found[0].class_id == 0
    assert found[0].confidence == pytest.approx(0.9)
    # One instance must reuse its model across successive images.
    assert model_boundary.loader.call_count == 1


def test_class_and_confidence_filtering(detector_module, model_boundary):
    model_boundary.model.predict.return_value = prediction([
        [10, 10, 30, 30, 0.49, 0],
        [40, 10, 60, 30, 0.95, 1],
        [70, 10, 90, 30, 0.5, 0],
        [100, 10, 120, 30, 0.9, 0],
    ])
    detector = detector_module.Detector(str(model_boundary.path))
    found = detector.detect(np.zeros((120, 200, 3), dtype=np.uint8))
    assert sorted(item.confidence for item in found) == pytest.approx([0.5, 0.9])
    assert all(item.class_id == 0 for item in found)


@pytest.mark.parametrize('image', [
    None, [], np.zeros((0, 100, 3), dtype=np.uint8),
    np.zeros((100, 100), dtype=np.uint8),
    np.zeros((100, 100, 4), dtype=np.uint8),
    np.zeros((100, 100, 3), dtype=np.float32),
])
def test_invalid_images_raise_without_inference(
    image, detector_module, model_boundary,
):
    detector = detector_module.Detector(str(model_boundary.path))
    with pytest.raises(ValueError):
        detector.detect(image)
    model_boundary.model.predict.assert_not_called()


@pytest.mark.parametrize(('name', 'value'), [
    ('confidence_threshold', -0.1), ('confidence_threshold', 1.1),
    ('confidence_threshold', float('nan')), ('confidence_threshold', True),
    ('device', -1), ('device', True), ('device', '0'),
    ('target_class_id', -1), ('target_class_id', True),
])
def test_invalid_settings_rejected_before_loading(
    name, value, detector_module, model_boundary,
):
    with pytest.raises(ValueError):
        detector_module.Detector(str(model_boundary.path), **{name: value})
    model_boundary.loader.assert_not_called()


@pytest.mark.parametrize('path_kind', ['missing', 'directory', 'wrong_suffix'])
def test_invalid_model_paths_rejected(
    path_kind, tmp_path, detector_module, model_boundary,
):
    path = tmp_path / 'missing.pt'
    if path_kind == 'directory':
        path.mkdir()
    elif path_kind == 'wrong_suffix':
        path = tmp_path / 'model.txt'
        path.write_bytes(b'not a PT model')
    with pytest.raises(ValueError):
        detector_module.Detector(str(path))
    model_boundary.loader.assert_not_called()


@pytest.mark.parametrize('available', [False, True])
def test_missing_gpu_rejected_without_cpu_fallback(
    available, monkeypatch, detector_module, model_boundary,
):
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: available)
    with pytest.raises(RuntimeError):
        detector_module.Detector(str(model_boundary.path), device=1)
    model_boundary.loader.assert_not_called()


def test_unknown_class_rejected(detector_module, model_boundary):
    with pytest.raises(ValueError):
        detector_module.Detector(str(model_boundary.path), target_class_id=8)


def test_load_failure_reaches_caller(detector_module, model_boundary):
    model_boundary.loader.side_effect = OSError('damaged checkpoint')
    with pytest.raises(RuntimeError):
        detector_module.Detector(str(model_boundary.path))


def test_inference_failure_is_not_absence(detector_module, model_boundary):
    detector = detector_module.Detector(str(model_boundary.path))
    model_boundary.model.predict.side_effect = RuntimeError('GPU failure')
    with pytest.raises(RuntimeError):
        detector.detect(np.zeros((120, 200, 3), dtype=np.uint8))


@pytest.mark.parametrize('result', [[], [SimpleNamespace(boxes=None)]])
def test_invalid_model_response_is_not_absence(
    result, detector_module, model_boundary,
):
    model_boundary.model.predict.return_value = result
    detector = detector_module.Detector(str(model_boundary.path))
    with pytest.raises(RuntimeError):
        detector.detect(np.zeros((120, 200, 3), dtype=np.uint8))


def test_nonfinite_model_output_rejected(detector_module, model_boundary):
    model_boundary.model.predict.return_value = prediction([
        [float('nan'), 10, 50, 60, 0.9, 0],
    ])
    detector = detector_module.Detector(str(model_boundary.path))
    with pytest.raises(RuntimeError):
        detector.detect(np.zeros((120, 200, 3), dtype=np.uint8))


@pytest.mark.parametrize('row', [
    [20, 30, 80, 90, 1.2, 0],
    [80, 30, 20, 90, 0.9, 0],
    [20, 30, 20, 90, 0.9, 0],
])
def test_corrupt_model_values_are_errors_not_valid_detections(
    row, detector_module, model_boundary,
):
    """Confidence is a probability; xyxy boxes must have positive area."""
    model_boundary.model.predict.return_value = prediction([row])
    detector = detector_module.Detector(str(model_boundary.path))
    with pytest.raises(RuntimeError):
        detector.detect(np.zeros((120, 200, 3), dtype=np.uint8))
