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
# 탐지 노드가 공유하는 모델 로딩과 추론 기능을 제공하는 일반 Python 모듈.
# [입출력]
# 입력: 이미지와 모델 설정. 출력: 박스, 클래스, 신뢰도 목록.
# [구현]
# 모델을 초기화 시 로딩하고 추론할 때 재사용한다.
# 사용하기로 한 탐지 라이브러리의 기존 API를 이용한다.
# 결과를 두 탐지 노드가 동일하게 해석할 수 있는 간단한 형식으로 반환한다.
# [실패 처리]
# 잘못된 모델 경로·이미지·추론 오류를 호출자에게 전달한다.
# [범위]
# 한 모델에 필요한 함수나 작은 클래스만 작성한다.
# 여러 모델을 교체하는 플러그인 시스템, 학습 파이프라인, ROS 통신은 넣지 않는다.
# [완료 기준]
# 정상 이미지와 대상 없는 이미지에서 일관된 결과 형식을 반환한다.

"""GPU-based Pumpkin detection without ROS dependencies."""

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO


@dataclass(frozen=True)
class Detection:
    """One detection with original-image pixel coordinates (x1, y1, x2, y2)."""

    bbox: tuple[float, float, float, float]
    class_id: int
    confidence: float
    

class Detector:
    """Load a local PT model once and reuse it for BGR image inference."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.5,
        device: int = 0,
        target_class_id: int = 0,
    ):
        """Validate configuration and load the model onto the selected GPU."""
        path = Path(model_path).expanduser()
        if not path.is_file() or path.suffix.lower() != '.pt':
            raise ValueError(f'Model must be an existing .pt file: {path}')
        if (
            isinstance(confidence_threshold, bool)
            or not isinstance(confidence_threshold, (int, float))
            or not math.isfinite(confidence_threshold)
            or not 0.0 <= confidence_threshold <= 1.0
        ):
            raise ValueError('confidence_threshold must be between 0 and 1')
        if isinstance(device, bool) or not isinstance(device, int) or device < 0:
            raise ValueError('device must be a nonnegative GPU index')
        if (
            isinstance(target_class_id, bool)
            or not isinstance(target_class_id, int)
            or target_class_id < 0
        ):
            raise ValueError('target_class_id must be a nonnegative integer')
        if not torch.cuda.is_available() or device >= torch.cuda.device_count():
            raise RuntimeError(f'GPU {device} is unavailable; CUDA is required')

        try:
            self._model = YOLO(str(path.resolve()), task='detect')
            if self._model.task != 'detect':
                raise ValueError('Model must support object detection')
            if target_class_id not in self._model.names:
                raise ValueError(
                    f'Unknown target class {target_class_id}; '
                    f'available classes: {self._model.names}'
                )
            self._model.to(f'cuda:{device}')
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f'Failed to load model {path}: {exc}') from exc

        self.confidence_threshold = float(confidence_threshold)
        self.device = device
        self.target_class_id = target_class_id

    def detect(self, image: np.ndarray) -> list[Detection]:
        """Return target detections, or an empty list for a normal absent target."""
        if (
            not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or image.shape[0] == 0
            or image.shape[1] == 0
        ):
            raise ValueError('image must be a nonempty HxWx3 uint8 BGR array')

        try:
            results = self._model.predict(
                source=image,
                conf=self.confidence_threshold,
                classes=[self.target_class_id],
                device=self.device,
                verbose=False,
                save=False,
                show=False,
                stream=False,
            )
            if len(results) != 1 or results[0].boxes is None:
                raise RuntimeError('Model returned an invalid detection result')
            boxes = results[0].boxes.cpu()
            detections = []
            for bbox, class_id, confidence in zip(
                boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()
            ):
                if not all(math.isfinite(value) for value in [*bbox, confidence]):
                    raise RuntimeError('Model returned nonfinite detection values')
                if int(class_id) != self.target_class_id:
                    continue
                if confidence < self.confidence_threshold:
                    continue
                detections.append(Detection(
                    bbox=tuple(float(value) for value in bbox),
                    class_id=int(class_id),
                    confidence=float(confidence),
                ))
            return detections
        except Exception as exc:
            raise RuntimeError(f'Detection inference failed: {exc}') from exc
