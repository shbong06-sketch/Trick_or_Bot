# Detection Docker 실행

결과는 호스트의 `detection/experiments/`에 저장됩니다.

## 빌드 및 GPU 확인

각 환경 디렉터리에서 실행합니다.

| 환경 | 디렉터리 | 서비스 |
|---|---|---|
| YOLO | `detection/docker/yolo` | `yolo-trainer` |
| D-FINE | `detection/docker/dfine` | `trainer` |
| DEIM-D-FINE | `detection/docker/deim` | `trainer` |
| RF-DETR | `detection/docker/rfdetr` | `trainer` |
| RT-DETRv4 | `detection/docker/rtdetrv4` | `trainer` |

```bash
docker compose build
docker compose run --rm <서비스> nvidia-smi
```

YOLO 이미지는 Dockerfile에서 `ultralytics/ultralytics:8.4.152`로 고정합니다.

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
curl --fail --location --retry 3 \
  https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_n_coco.pth \
  --output ../../checkpoints/dfine_n_coco.pth
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

[공식 N checkpoint](https://drive.google.com/file/d/1ZPEhiU9nhW4M5jLnYOFwTSLQC1Ugf62e/view)를
`detection/checkpoints/deim_dfine_n_coco.pth`로 저장한 뒤 `detection/docker/deim`에서 실행합니다.

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
`detection/checkpoints/` 아래에 보관됩니다.

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

## RT-DETRv4 smoke run

다음 weight를 `detection/checkpoints/`에 준비한 뒤 `detection/docker/rtdetrv4`에서 실행합니다.

- [공식 S checkpoint](https://drive.google.com/file/d/1jDAVxblqRPEWed7Hxm6GwcEl7zn72U6z): `rtdetrv4_s_coco.pth`
- [DINOv3 공식 다운로드](https://github.com/facebookresearch/dinov3#pretrained-models):
  ViT-B/16 LVD-1689M weight를 `dinov3_vitb16_pretrain_lvd1689m.pth`로 저장

```bash
docker compose run --rm trainer \
  python /opt/rtdetrv4/train.py \
  -c /workspace/configs/rtdetrv4_s.yaml \
  -t /workspace/checkpoints/rtdetrv4_s_coco.pth \
  --device cuda:0 --use-amp --seed 0 \
  --output-dir /workspace/experiments/rtdetrv4/rtdetrv4_s_smoke \
  -u epoches=1
```

1 epoch는 실행 확인용입니다. 본 학습 조건은 실험 계획에 맞춰 설정합니다.
DEIM과 RT-DETRv4의 epoch 인자는 공식 코드에 맞춰 `epoches`를 사용합니다.
모델은 한 번에 하나씩 실행합니다. RT-DETRv4는 DINOv3 teacher를 포함합니다.
