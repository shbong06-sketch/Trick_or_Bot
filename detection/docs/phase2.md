# Phase 2: 데이터 증강 비교

[전체 안내](../README.md) · [이전 단계: Phase 1](phase1.md) · [다음 단계: Phase 3](phase3.md)

YOLO11n, YOLOv8n, RF-DETR-N, D-FINE-N의 데이터 증강 조건을 비교합니다.
호스트 명령은 `detection/`에서 실행합니다.

## 비교 대상 모델과 선정 이유

Phase 1 비교 결과를 바탕으로 다음 상위 4개 모델을 비교 대상으로 선정했습니다.

| 모델 | 선정 이유 |
| --- | --- |
| YOLO11n | 종합 균형이 가장 우수 |
| YOLOv8n | 실시간성 우수 |
| RF-DETR-N | 높은 검출 품질의 DETR 대표 후보 |
| D-FINE-N | 경량 DETR 계열의 비교 후보 |

## 선행 조건과 기준 결과

`scripts/phase2.py`는 `results/phase1/model_comparison.csv`에서 위 4개 모델의 결과를 읽고,
각 모델의 `experiments/phase1/<모델명>/evaluation/model_screening_summary.json`과 대조합니다.
필요한 모델이 없거나 두 파일의 체크포인트 정보가 다르면 진행하지 않습니다.

설정은 `configs/phase2/<모델명>/`의 `baseline.yaml`, `spatial.yaml`,
`photometric.yaml`, `combined.yaml`에 있습니다.
`baseline`은 Phase 1 체크포인트와 지표를 재사용하며 새로 학습하지 않습니다.
나머지 3개 조건은 Phase 1과 같은 사전 학습 가중치에서 다시 시작하고,
학습 일정과 평가 기준도 Phase 1을 따릅니다.

## 증강 조건

### 조건의 의미

| 조건 | 의미 | 주요 적용 |
| --- | --- | --- |
| Baseline | 각 프레임워크의 기본 권장 증강 설정 | 모델이 기본 제공하는 공간·색상 증강을 그대로 사용 |
| Spatial | 객체의 위치·크기 편향 완화 | 좌우 반전, ±5° 회전, 이동, 배율 조정 등 공간 변형 중심 |
| Photometric | 조명·색상 변화에 대한 강건성 확인 | 밝기, 대비, 채도, 약한 색조 변화 중심 |
| Combined | 공간·조명 변화를 함께 반영 | Spatial과 Photometric을 강도를 낮춰 동시에 적용 |

> Spatial은 bbox의 상단 위치 편향을 완화하고, Photometric은 실제 OAK-D 운용 환경의 조명 변화에 대한 일반화를 확인하기 위한 조건이다. `pumpkin`의 주황색 자체가 주요 특징이므로 Hue 변화는 매우 약하게 제한하였다.

### 조건별 적용 수치

증강은 train split에만 적용합니다. validation과 test는 기존 split과 평가 설정을 유지합니다.
A/B/C에서는 프레임워크의 기본 Mosaic, MixUp, CutMix, 수직 반전,
YOLO copy-paste를 끕니다. Phase 1 기준 조건은 유지합니다.
Baseline의 모델별 수치는 [Phase 1의 Baseline 증강 설정](phase1.md#baseline-증강-설정)에 정리했습니다.

| 조건 | 공간 변환 | 색상 변환 |
| --- | --- | --- |
| `baseline` | 모델별 Phase 1 설정 재사용 ([상세 수치](phase1.md#baseline-증강-설정)) | 모델별 Phase 1 설정 재사용 |
| `spatial` (A) | 좌우 반전 확률 0.5, 회전 ±5°, 이동 ±20%, 배율 0.7–1.3 | 없음 |
| `photometric` (B) | 없음 | 색조 ±0.005, 채도 ±20%, 밝기 ±25%, 대비 ±18% |
| `combined` (C) | 좌우 반전 확률 0.5, 회전 ±5°, 이동 ±15%, 배율 0.8–1.2 | 색조 ±0.005, 채도 ±15%, 밝기 ±20%, 대비 ±15% |

변환은 각 프레임워크가 지원하는 방식으로 적용합니다.
YOLO는 기본 HSV 증강에 독립적인 대비 옵션이 없어 B/C에 대비 전용 Albumentations 변환을
추가하고, A/B/C의 기본 blur·gray 변환은 제거합니다.
D-FINE은 등록된 torchvision v2 `RandomAffine`·`ColorJitter`를 사용합니다.
RF-DETR는 Docker의 `augment` 추가 의존성으로 설치한 Albumentations를 사용합니다.
프레임워크마다 변환을 샘플링하는 방식이 달라, 완전히 같은 분포보다 실험 의도를 맞춥니다.

## 실행

RF-DETR 이미지에는 증강 의존성이 포함되어 있어야 합니다. 이미지가 이전 버전이면 재빌드하세요.

```bash
docker compose -f docker/rfdetr/docker-compose.yaml build trainer

# 12개 학습·평가 쌍의 명령만 출력
python3 scripts/phase2.py run-all

# 전체 조건 순차 실행
python3 scripts/phase2.py run-all --execute
```

YOLO11n → YOLOv8n → RF-DETR-N → D-FINE-N 순서로 진행하며,
각 모델에서는 spatial → photometric → combined 순서로 실행합니다.
각 학습 직후 평가를 수행하고, 첫 실패에서 중단합니다.
12개 실행이 모두 성공하면 결과를 취합합니다.

한 모델만 실행하거나 개별 조건을 실행할 수도 있습니다.

```bash
python3 scripts/phase2.py run-all --model yolo11n --execute
python3 scripts/phase2.py train --model yolo11n --condition spatial --execute
python3 scripts/phase2.py evaluate --model yolo11n --condition spatial --execute
python3 scripts/phase2.py collect
```

`--model`에는 `yolo11n`, `yolov8n`, `rfdetr_n`, `dfine_n`을,
`--condition`에는 `spatial`, `photometric`, `combined`를 사용합니다.
개별 `train`·`evaluate`도 `--execute`를 생략하면 명령만 출력합니다.

## 산출물과 해석

학습·평가 상세 산출물은 `experiments/phase2/<조건>/<모델명>/`에 저장됩니다.
`collect`는 아래 결과를 갱신합니다.

| 경로 | 내용 |
| --- | --- |
| `results/phase2/augmentation_summary.csv` | 모델별·조건별 지표와 실행 상태 |
| `results/phase2/augmentation_delta.csv` | Phase 1 기준 결과 대비 변화량 |
| `results/phase2/<모델명>/details.json` | 조건별 설정, 지표, 기준 대비 변화량 |

학습·평가가 끝나지 않은 A/B/C 행은 `pending`이며, 지표와 변화량은 빈칸으로 둡니다.
기준 행의 상태는 `reused_phase1`, 완료된 조건은 `complete`입니다.
mAP50, precision, recall, F1 변화량은 validation 기준이며,
정답 예측 비율과 추론 시간은 test 기준입니다.
추론 속도 변화율이 양수이면 기준보다 빠릅니다.
추론 시간 변화량(ms)은 새 조건에서 기준값을 뺀 값이므로 음수이면 지연 시간이 줄었습니다.

## 코드 검사

```bash
python3 -m unittest discover -s scripts/tests -p 'test_phase2.py' -v
```
