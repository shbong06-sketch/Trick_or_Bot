# Phase 1 학습 config

공통 조건은 `common.yaml`, 모델별 training recipe는 아래 5개 파일로 관리합니다.
경로는 `detection/` 기준이며 Docker에서는 `/workspace`에 해당합니다.

| 파일 | 모델 |
|---|---|
| `yolo.yaml` | YOLOv8n / YOLO11n / YOLO26n |
| `dfine_n.yaml` | D-FINE-N |
| `deim_dfine_n.yaml` | DEIM-D-FINE-N |
| `rfdetr_n.yaml` | RF-DETR-N |
| `rtdetrv2_s.yaml` | RT-DETRv2-S |

공통 조건: seed 42, 입력 704×704, 최대 100 epoch, batch 16, early stopping,
patience 20, L4. 데이터는 기존 `dataset/`의 train/valid/test split을 그대로 사용합니다.
Phase 0의 실제 수량은 292/83/42, 총 417장이며 이번 config에서는 재분할하지 않습니다.

## 실행 스크립트가 적용할 값

`common.yaml`은 framework에 직접 전달하는 config가 아니라 실행 스크립트가 읽을 설정입니다.
모델별 config를 읽은 후 공통 조건을 아래 native 옵션에 연결합니다.

| 공통 값 | YOLO | RF-DETR | D-FINE / DEIM / RT-DETRv2 |
|---|---|---|---|
| dataset | `data=.../data.yaml` | `dataset_dir=...` | 기존 config의 COCO 경로 상속 |
| input_size | `imgsz=704` | Nano 생성·학습 `resolution=704` | resize·eval_spatial_size 설정 |
| epochs | `epochs=100` | `epochs=100` | D-FINE `epochs`, 나머지 `epoches` |
| batch_size | `batch=16` | `batch_size=16` | train/val `total_batch_size=16` |
| seed | `seed=42` | `seed=42` | CLI `--seed 42` |
| early stopping | `patience=20` | `early_stopping=True`, `early_stopping_patience=20` | 실행 코드에서 patience 종료 처리 필요 |
| workers | `workers=2` | `num_workers=2` | 기존 config에서 `num_workers=2` 상속 |

DETR config는 framework에 직접 전달할 수 있도록 epoch·batch·resize를 명시했습니다.
공통 값을 바꾸면 이 native 값과 augmentation/LR schedule도 함께 맞춰야 합니다.
config만으로 DETR early stopping이 동작하지는 않습니다. `scripts/train_models.py`가 validation
mAP50–95를 확인해 20 epoch 연속 개선이 없으면 학습을 종료합니다.

## 파인튜닝과 모델별 기본값

- `common.yaml`의 weights는 전체 pretrained detector checkpoint입니다.
  YOLO와 RF-DETR는 필요 시 자동 다운로드하며 DETR checkpoint는 Docker 안내대로 먼저 준비합니다.
- DETR의 `HGNetv2.pretrained=false` 또는 `PResNet.pretrained=false`는 별도 backbone 다운로드를 끕니다.
  전체 checkpoint는 학습 시 `-t` / `tuning`으로 로딩해 파인튜닝합니다.
- YOLO는 `optimizer=auto`로 고정된 Ultralytics 버전의 모델별 기본 recipe를 사용합니다.
  자동으로 결정된 optimizer와 LR은 이후 실행 산출물에 기록해야 합니다.
- D-FINE/DEIM/RT-DETRv2는 기존 config와 고정 upstream recipe를 상속합니다.
  최종 resize=704, multi-scale 비활성, augmentation 종료=88로 맞춥니다.
  D-FINE/RT-DETRv2는 LR milestone=80 및 warmup=100 iteration,
  DEIM은 flat=44/no_aug=12/warmup=100 iteration을 사용합니다.
- RF-DETR는 batch 16, accumulation 1, fixed resolution을 사용합니다. 자동 test는 꺼둡니다.
  YOLO와 DETR도 학습 중 train/validation만 사용하고 test 평가는 추후 별도로 수행합니다.

실행 방법은 저장소 루트 README를 참고하세요. 학습 코드를 구현할 때 실제 모델 학습·평가는 실행하지 않습니다.
