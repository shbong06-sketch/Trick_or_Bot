# Phase 1: 모델 학습·평가

[전체 안내](../README.md) · [환경 준비](setup.md) · [다음 단계: Phase 2](phase2.md)

7개 모델을 공통 조건으로 학습하고, 완료된 모델의 validation·test 결과를 비교합니다.
호스트 명령은 `detection/`에서 실행합니다. 먼저 [환경 준비](setup.md)에 따라
사용할 Docker 이미지를 빌드하고 사전 학습 체크포인트를 준비하세요.

## 학습 설정

공통 조건은 `configs/phase1/common.yaml`, 모델별 학습 설정은 아래 5개 파일로 관리합니다.
경로는 `detection/` 기준이며 Docker에서는 `/workspace`에 해당합니다.

| 파일 (`configs/phase1/` 기준) | 모델 |
|---|---|
| `yolo.yaml` | YOLOv8n / YOLO11n / YOLO26n |
| `dfine_n.yaml` | D-FINE-N |
| `deim_dfine_n.yaml` | DEIM-D-FINE-N |
| `rfdetr_n.yaml` | RF-DETR-N |
| `rtdetrv2_s.yaml` | RT-DETRv2-S |

공통 조건은 seed 42, 입력 704×704, 최대 100 epoch, batch 16, 조기 종료,
patience 20, L4입니다. 데이터는 기존 `dataset/`의 train/valid/test 분할을 그대로 사용합니다.
Phase 0의 실제 수량은 292/83/42, 총 417장이며 이 설정에서는 재분할하지 않습니다.

### 실행 스크립트가 적용할 값

`configs/phase1/common.yaml`은 실행 스크립트가 읽는 공통 설정입니다.
모델별 설정을 읽은 후 공통 조건을 아래 프레임워크 고유 옵션에 연결합니다.

| 공통 값 | YOLO | RF-DETR | D-FINE / DEIM / RT-DETRv2 |
|---|---|---|---|
| dataset | `data=.../data.yaml` | `dataset_dir=...` | 기존 config의 COCO 경로 상속 |
| input_size | `imgsz=704` | Nano 생성·학습 `resolution=704` | resize·eval_spatial_size 설정 |
| epochs | `epochs=100` | `epochs=100` | D-FINE `epochs`, 나머지 `epoches` |
| batch_size | `batch=16` | `batch_size=16` | train/val `total_batch_size=16` |
| seed | `seed=42` | `seed=42` | CLI `--seed 42` |
| early stopping | `patience=20` | `early_stopping=True`, `early_stopping_patience=20` | 실행 코드에서 patience 종료 처리 필요 |
| workers | `workers=2` | `num_workers=2` | 기존 config에서 `num_workers=2` 상속 |

DETR 설정은 프레임워크에 직접 전달할 수 있도록 epoch·batch·resize를 명시했습니다.
공통 값을 바꾸면 이 고유 설정과 증강·학습률 일정도 함께 맞춰야 합니다.
DETR의 조기 종료는 `scripts/train_models.py`가 validation
mAP50–95를 확인해 20 epoch 연속 개선이 없으면 학습을 종료합니다.

### 파인튜닝과 모델별 기본값

- `configs/phase1/common.yaml`의 weights는 사전 학습된 전체 탐지 모델 체크포인트입니다.
  YOLO와 RF-DETR는 필요 시 자동 다운로드하며 DETR 체크포인트는 [환경 준비](setup.md)에 따라 먼저 준비합니다.
- DETR의 `HGNetv2.pretrained=false` 또는 `PResNet.pretrained=false`는 별도 백본 다운로드를 끕니다.
  전체 체크포인트는 학습 시 `-t` / `tuning`으로 로딩해 파인튜닝합니다.
- YOLO는 `optimizer=auto`로 고정된 Ultralytics 버전의 모델별 기본 학습 설정을 사용합니다.
  자동으로 결정된 옵티마이저와 학습률은 실행 산출물에 기록됩니다.
- D-FINE/DEIM/RT-DETRv2는 기존 설정과 고정된 공식 구현의 학습 설정을 상속합니다.
  최종 resize=704, 다중 해상도 비활성, 증강 종료=88로 맞춥니다.
  D-FINE/RT-DETRv2는 LR milestone=80 및 warmup=100 iteration,
  DEIM은 flat=44/no_aug=12/warmup=100 iteration을 사용합니다.
- RF-DETR는 batch 16, 기울기 누적 1, 고정 해상도를 사용합니다. 자동 test는 꺼둡니다.
  YOLO와 DETR도 학습 중 train/validation만 사용하고 test 평가는 추후 별도로 수행합니다.

### Baseline 증강 설정

Phase 2의 Baseline은 Phase 1에서 학습한 체크포인트와 지표를 그대로 재사용합니다.
아래는 Phase 2 비교 대상 4개 모델의 Phase 1 증강 설정입니다.
각 프레임워크의 기본 변환에 이 저장소의 고정 해상도·증강 종료 설정을 적용한 값이며,
모든 모델이 동일한 증강 강도를 사용하는 것은 아닙니다.

| 모델 | 공간 변환 | 색상 변환 |
| --- | --- | --- |
| YOLO11n / YOLOv8n | 좌우 반전 확률 0.5, 회전 0°, 이동 ±10%, 배율 0.5–1.5, Mosaic 확률 1.0 | HSV 설정 `hsv_h=0.015`, `hsv_s=0.7`, `hsv_v=0.4` |
| RF-DETR-N | 기본 좌우 반전 확률 0.5, 704×704 고정 리사이즈, 임의 크롭·해상도 변동 비활성 | 기본 색상 증강 없음 |
| D-FINE-N | 좌우 반전 확률 0.5, ZoomOut 확률 0.5·캔버스 배율 1.0–4.0, IoU 기반 크롭 확률 0.8, 최종 704×704 리사이즈 | `RandomPhotometricDistort`: 밝기 배율 0.875–1.125, 대비·채도 배율 0.5–1.5, 색조 변화 −0.05–0.05, 각 변형 확률 0.5 |

#### YOLO11n / YOLOv8n

두 모델은 동일한 증강 값을 사용합니다. 아래 값은 Baseline 상세 기록의
`training_hyperparameters.settings`에서 확인했습니다.

| 옵션 | 값 | 의미 |
| --- | --- | --- |
| `fliplr` / `flipud` | 0.5 / 0.0 | 좌우 반전 확률 / 수직 반전 비활성 |
| `degrees` | 0.0 | 회전 비활성 |
| `translate` | 0.1 | 가로·세로 이동 범위 ±10% |
| `scale` | 0.5 | 배율 0.5–1.5 |
| `shear` / `perspective` | 0.0 / 0.0 | 전단·원근 변환 비활성 |
| `mosaic` | 1.0 | Mosaic 적용 확률 |
| `close_mosaic` | 10 | 학습 마지막 10 epoch에서 Mosaic 종료 |
| `mixup` / `cutmix` / `copy_paste` | 0.0 / 0.0 / 0.0 | 해당 합성 증강 비활성 |
| `hsv_h` / `hsv_s` / `hsv_v` | 0.015 / 0.7 / 0.4 | 색조·채도·명도 변형 강도 |
| `bgr` | 0.0 | RGB↔BGR 채널 순서 변환 비활성 |
| `multi_scale` | false | 입력 해상도 변동 비활성 |

HSV 값은 Ultralytics의 옵션값이며 변형 확률이 아닙니다.
이 표는 객체 탐지의 주요 공간·색상·합성 증강 설정을 정리한 것입니다.
전체 프레임워크 옵션은 [YOLO11n 상세 기록](../results/phase2/yolo11n/details.json)과
[YOLOv8n 상세 기록](../results/phase2/yolov8n/details.json)에 보관되어 있습니다.

#### RF-DETR-N

Baseline 기록은 `aug_config=None`, `augmentation_backend=cpu`입니다.
사용자 정의 증강을 전달하지 않아 고정 버전 RF-DETR 1.11.2의 기본 좌우 반전 확률 0.5를 사용합니다.
기본 증강에는 밝기·대비·채도·색조 변형이 없습니다.
저장소 설정은 `multi_scale=false`, `expanded_scales=false`, `scale_jitter=false`이며,
실행 기록의 `multi_scale` 표기는 `off`입니다.
`scale_jitter=false`로 임의 크롭 경로를 끄고 704×704 고정 리사이즈를 사용합니다.

설정값은 [RF-DETR 상세 기록](../results/phase2/rfdetr_n/details.json)에서,
상속되는 기본 변환은 [RF-DETR 1.11.2 변환 구현](https://github.com/roboflow/rf-detr/blob/1.11.2/src/rfdetr/datasets/coco.py)과
[기본 증강 설정](https://github.com/roboflow/rf-detr/blob/1.11.2/src/rfdetr/datasets/aug_configs.py)에서 확인할 수 있습니다.

#### D-FINE-N

`configs/phase1/dfine_n.yaml`은 변환 종류와 `RandomPhotometricDistort.p=0.5`,
`RandomIoUCrop.p=0.8`, `RandomZoomOut.fill=0`을 명시합니다.
생략된 값은 고정된 D-FINE 구현과 torchvision 0.20.1의 기본값을 사용합니다.

- `RandomZoomOut`: 확률 0.5, 캔버스 크기를 원본의 1.0–4.0배로 확장한 뒤 검정색으로 채웁니다.
  객체 자체를 1.0–4.0배 확대하는 변환은 아닙니다.
- `RandomIoUCrop`: 확률 0.8, 크롭 너비·높이 비율 0.3–1.0, 종횡비 0.5–2.0입니다.
  이 범위는 A/B/C의 객체 배율 설정과 의미가 다릅니다.
- `RandomHorizontalFlip`: 확률 0.5입니다.
- `RandomPhotometricDistort`: 표의 범위로 밝기·대비·채도·색조를 바꾸고 채널 순서도 무작위로 바꿉니다.
  `p=0.5`는 개별 색상 변형의 적용 확률입니다.
- epoch 88부터 `RandomPhotometricDistort`, `RandomZoomOut`, `RandomIoUCrop`을 종료합니다.
  좌우 반전과 최종 리사이즈는 유지합니다.

변환 목록과 종료 정책은 [D-FINE 상세 기록](../results/phase2/dfine_n/details.json)에 있습니다.
생략된 기본값은 [고정 D-FINE 변환 구현](https://github.com/Peterande/D-FINE/blob/956d1709314c2c6a4df6f34de232054578a7449f/src/data/transforms/_transforms.py),
[torchvision 공간 변환 구현](https://github.com/pytorch/vision/blob/v0.20.1/torchvision/transforms/v2/_geometry.py),
[torchvision 색상 변환 문서](https://docs.pytorch.org/vision/0.20/generated/torchvision.transforms.v2.RandomPhotometricDistort.html)를 기준으로 정리했습니다.

Baseline에서도 train에만 증강을 적용하며 validation·test에는 평가용 리사이즈와 전처리만 적용합니다.
[Phase 2](phase2.md)의 Spatial·Photometric·Combined는 이 Baseline과 비교하는 별도 조건입니다.

## 학습 실행

```bash
# 학습 명령만 출력
python3 scripts/train_models.py --model yolov8n

# 실제 학습
python3 scripts/train_models.py --model yolov8n --execute
```

모델 식별자는 `yolov8n`, `yolo11n`, `yolo26n`, `dfine_n`, `deim_dfine_n`,
`rfdetr_n`, `rtdetrv2_s`입니다. 한 번에 한 모델을 학습합니다.
스크립트는 의존성 설치나 Docker 빌드를 수행하지 않습니다.
학습 중에는 validation으로 최적 체크포인트와 조기 종료를 결정하며 test는 사용하지 않습니다.

### 학습 산출물

결과는 `experiments/phase1/<모델명>/`에 저장됩니다.

| 파일 | 내용 |
| --- | --- |
| `config.yaml` | 적용 공통 조건, 모델 정보, 프레임워크 설정 |
| `training.log` | 콘솔 표준 출력·오류 로그 |
| `run_info.json` | 실행 상태, 시간, 환경, 실제 옵티마이저 값, 종료 epoch, 가능한 최대 VRAM 사용량 |
| 프레임워크 기본 산출물 | YOLO의 `results.csv`·`weights`, RF-DETR의 로그·체크포인트, DETR의 `log.txt`·체크포인트 |
| DETR 추가 산출물 | `framework_config.yaml`, `metrics.jsonl`, `best_phase1.pth` |

DETR의 `best_phase1.pth`는 실제 validation에 사용된 EMA 또는 일반 모델 가중치입니다.
학습 시간에는 모델 초기화, 학습, epoch별 validation, 체크포인트 저장이 포함되며
Docker 시작 시간은 제외됩니다. VRAM은 PyTorch 메모리 할당기의 최대 할당량입니다.

같은 모델을 다시 실행하면 설정, 콘솔 로그, 실행 기록을 갱신합니다.
기존 프레임워크 산출물은 일부 남거나 로그에 누적될 수 있습니다.
자동 재개, 실행 이름 지정, 덮어쓰기 방지, 전체 모델 순차 실행은 지원하지 않습니다.

## 평가와 결과 취합

완료된 학습의 `run_info.json`, `config.yaml`, 기록된 최적 체크포인트가 필요합니다.
평가는 설정된 L4 GPU에서 validation과 test를 모두 사용합니다.

```bash
# 평가 명령만 출력
python3 scripts/evaluate_models.py --model yolov8n

# 실제 평가
python3 scripts/evaluate_models.py --model yolov8n --execute

# 완료된 평가 결과를 비교 CSV로 취합
python3 scripts/evaluate_models.py --collect
```

평가 조건은 `configs/phase1/evaluation.yaml`에서 관리합니다.
기본값은 confidence 0.25, 정답 매칭 IoU 0.50, YOLO NMS IoU 0.70,
AP 계산 점수 하한 0.001입니다. 추론 시간은 FP32, batch 1,
20회 준비 실행 후 test 전체를 3회 반복하여 측정합니다.
DETR 계열에는 NMS를 적용하지 않습니다.

상세 결과는 `experiments/phase1/<모델명>/evaluation/`에 저장됩니다.

| 파일 | 내용 |
| --- | --- |
| `validation_metrics.json` | validation의 AP, precision, recall, F1 등 |
| `test_metrics.json` | test의 AP, 정답 예측 비율, 추론 시간 등 |
| `model_screening_summary.json` | 학습 기록과 평가 지표를 합친 상세 요약 |
| `model_screening_summary.csv` | 해당 모델의 요약 CSV |

`--collect`는 완료된 유효 평가를 모아 `results/phase1/model_comparison.csv`를 갱신합니다.
학습 기록보다 오래된 평가는 취합에서 제외됩니다.
평가의 형식이나 기록된 체크포인트 크기가 현재 파일과 다르면 오류로 종료합니다.
유효한 평가가 하나도 없으면 오류로 종료합니다.
Phase 2를 진행하려면 그 단계가 요구하는 4개 모델의 비교 CSV와 상세 JSON이 모두 필요합니다.

## 코드 검사

아래 명령은 실제 학습·GPU 평가 없이 테스트를 실행합니다.

```bash
python3 -m unittest discover -s scripts/tests -p 'test_train_models.py' -v
python3 -m unittest discover -s scripts/tests -p 'test_evaluate_models.py' -v
```
