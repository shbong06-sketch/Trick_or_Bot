# Detection Docker 실행

결과는 호스트의 `detection/experiments/`에 저장됩니다.

Phase 1의 7개 모델 비교는 [공통 CLI 안내](../records/phase1/README.md)를 사용합니다.
아래 smoke run과 Phase 1 조건은 다릅니다. Docker build context는 `detection/`이며
공통 평가 의존성을 `scripts/phase1/requirements.txt`에서 설치합니다.

## 빌드 및 GPU 확인

각 환경 디렉터리에서 실행합니다.

| 환경 | 디렉터리 | 서비스 |
|---|---|---|
| YOLO | `detection/docker/yolo` | `yolo-trainer` |
| D-FINE | `detection/docker/dfine` | `trainer` |
| DEIM-D-FINE | `detection/docker/deim` | `trainer` |
| RF-DETR | `detection/docker/rfdetr` | `trainer` |
| RT-DETRv2-S | `detection/docker/rtdetrv2` | `trainer` |

```bash
docker compose build
docker compose run --rm <서비스> nvidia-smi
```

YOLO 이미지는 Dockerfile에서 `ultralytics/ultralytics:8.4.152`로 고정합니다.

## Weight 다운로드

다운로드는 최초 한 번만 수행합니다. `wget`은 호스트에서, `gdown`은 일회용 컨테이너에서 실행합니다.

| 모델 | 방식 | 저장 파일 (`detection/checkpoints/` 기준) |
|---|---|---|
| YOLO | 자동 다운로드 | 컨테이너 작업 디렉터리 `/workspace`에 저장 |
| D-FINE-N | `wget` (GitHub Releases) | `dfine_n_coco.pth` |
| DEIM-D-FINE-N | `gdown` (Google Drive) | `deim_dfine_n_coco.pth` |
| RF-DETR-N | 자동 다운로드 | `rfdetr/` |
| RT-DETRv2-S | `wget` (GitHub Releases) | `rtdetrv2_s_coco.pth` |

## YOLO smoke run

`detection/docker/yolo`에서 실행합니다.

```bash
for model in yolov8n yolo11n yolo26n; do
  docker compose run --rm yolo-trainer \
    yolo detect train \
    model="${model}.pt" data=dataset/data.yaml \
    epochs=1 imgsz=640 batch=8 workers=2 device=0 amp=True seed=0 \
    project=/workspace/experiments/yolo name="${model}_smoke" || break
done
```

## D-FINE smoke run

`detection/docker/dfine`에서 checkpoint를 최초 한 번 다운로드합니다.

```bash
mkdir -p ../../checkpoints
wget --tries=3 --timeout=30 \
  --output-document=../../checkpoints/dfine_n_coco.pth \
  https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_n_coco.pth
```

```bash
docker compose run --rm trainer \
  python /opt/dfine/train.py \
  -c /workspace/configs/dfine_n.yaml \
  -t /workspace/checkpoints/dfine_n_coco.pth \
  --device cuda:0 --use-amp --seed 0 \
  --output-dir /workspace/experiments/dfine/dfine_n_smoke \
  -u epochs=1
```

## DEIM-D-FINE smoke run

`detection/docker/deim`에서 [공식 N checkpoint](https://drive.google.com/file/d/1ZPEhiU9nhW4M5jLnYOFwTSLQC1Ugf62e/view)를
최초 한 번 다운로드합니다. Google Drive 파일은 일회용 컨테이너에서 `gdown`으로 받습니다.

```bash
docker compose run --rm trainer bash -lc '
  pip install --no-cache-dir gdown==5.2.0 &&
  mkdir -p /workspace/checkpoints &&
  gdown 1ZPEhiU9nhW4M5jLnYOFwTSLQC1Ugf62e \
    -O /workspace/checkpoints/deim_dfine_n_coco.pth
'
```

```bash
docker compose run --rm trainer \
  python /opt/deim/train.py \
  -c /workspace/configs/deim_dfine_n.yaml \
  -t /workspace/checkpoints/deim_dfine_n_coco.pth \
  --device cuda:0 --use-amp --seed 0 \
  --output-dir /workspace/experiments/deim/deim_dfine_n_smoke \
  -u epoches=1
```

## RF-DETR smoke run

`detection/docker/rfdetr`에서 실행합니다. Pretrained weight는 자동 다운로드되어
`detection/checkpoints/rfdetr/`에 보관됩니다. Hugging Face 캐시는
`detection/checkpoints/huggingface/`에 남습니다. 별도 수동 다운로드는 필요하지 않습니다.
학습 전에 weight만 준비하려면 다음 명령을 실행합니다.

```bash
docker compose run --rm trainer python -c \
  'from rfdetr import RFDETRNano; RFDETRNano(device="cpu")'
```

```bash
docker compose run --rm trainer python -c '
from rfdetr import RFDETRNano
model = RFDETRNano(device="cuda")
model.train(
    dataset_dir="/workspace/dataset", dataset_file="yolo",
    epochs=1, batch_size=4, grad_accum_steps=2, num_workers=2, seed=0,
    resolution=384, run_test=False,
    output_dir="/workspace/experiments/rfdetr/rfdetr_n_smoke",
)
'
```

## RT-DETRv2-S smoke run

`detection/docker/rtdetrv2`에서 [공식 S (ResNet-18) checkpoint](https://github.com/lyuwenyu/RT-DETR/tree/main/rtdetrv2_pytorch#model-zoo)를
최초 한 번 다운로드합니다.

```bash
mkdir -p ../../checkpoints
wget --tries=3 --timeout=30 \
  --output-document=../../checkpoints/rtdetrv2_s_coco.pth \
  https://github.com/lyuwenyu/storage/releases/download/v0.2/rtdetrv2_r18vd_120e_coco_rerun_48.1.pth
```

```bash
docker compose run --rm trainer \
  python /opt/rtdetr/rtdetrv2_pytorch/tools/train.py \
  -c /workspace/configs/rtdetrv2_s.yaml \
  -t /workspace/checkpoints/rtdetrv2_s_coco.pth \
  --device cuda:0 --use-amp --seed 0 \
  --output-dir /workspace/experiments/rtdetrv2/rtdetrv2_s_smoke \
  -u epoches=1
```

1 epoch는 실행 확인용입니다. 본 학습 조건은 실험 계획에 맞춰 설정합니다.
DEIM과 RT-DETRv2의 epoch 인자는 공식 코드에 맞춰 `epoches`를 사용합니다.
모델은 한 번에 하나씩 실행합니다.
