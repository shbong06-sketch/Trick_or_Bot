# Phase 1 Model Screening

이 디렉터리는 실행 안내와 검토한 최종 결과를 Git으로 관리하는 곳입니다.
실제 학습·평가 결과는 Git에서 제외된 `detection/experiments/phase1/`에 저장합니다.
코드 준비 과정에서는 모델 학습·validation·test·GPU benchmark를 실행하지 않습니다.

## 설정과 준비

저장소 루트에서 명령을 실행합니다. CPU 환경의 prepare/명령 출력은 PyYAML만 필요합니다.
공통 평가 의존성은 `detection/scripts/phase1/requirements.txt`이고 기존 Dockerfile에 설치합니다.
모델 weights 준비 방법은 [Docker 안내](../../docker/README.md)를 참고하세요.
Docker Compose의 기존 단일 GPU 매핑을 사용하며 실행 시 실제 GPU 이름이 L4인지 검사합니다.

```bash
python3 -m pip install PyYAML==6.0.2
# 기존 Docker 이미지에 새 공통 평가 의존성을 반영하는 빌드는 사용자가 수행합니다.
docker compose -f detection/docker/yolo/docker-compose.yaml build

python3 detection/scripts/phase1/run.py prepare \
  --model yolov8n --run-name v01_seed42_screening01
```

모델 ID: `yolov8n`, `yolo11n`, `yolo26n`, `dfine_n`, `deim_dfine_n`, `rfdetr_n`, `rtdetrv2_s`.
각 모델은 해당 Docker 환경을 먼저 빌드합니다. config는
`detection/configs/phase1/screening.yaml` 한 곳에서 선택하며
`prepare --config PATH`로 다른 screening config를 지정할 수 있습니다.
seed=42, input=704×704, max epochs=100, batch=16, early stopping=true,
patience=20, GPU=L4는 변경 시 오류를 내므로 Phase 1 고정 조건이 유지됩니다.
GPU memory 부족 시 batch를 자동 축소하지 않고 실패합니다.

prepare는 Phase 0 manifest의 원본 SHA-256과 파일 집합을 검증하고 config·소스 hash·manifest를
run별로 고정합니다. 현재 데이터는 292/83/42, 총 417장이며 재분할하지 않습니다.
416장 조건과의 차이 및 Phase 0 leakage 후보는 해결됐다고 간주하지 않습니다.

## 사용자가 실행하는 학습과 평가

아래 명령은 `--execute`가 없으면 Docker 명령만 출력합니다.
명령 출력에는 모델 import, 다운로드, GPU 접근, 학습, 평가가 없습니다.

```bash
python3 detection/scripts/phase1/run.py train \
  --model yolov8n --run-name v01_seed42_screening01
python3 detection/scripts/phase1/run.py evaluate \
  --model yolov8n --run-name v01_seed42_screening01 --eval-name best_fp32_01

# 실제 실행은 사용자가 명시적으로 선택합니다.
python3 detection/scripts/phase1/run.py train \
  --model yolov8n --run-name v01_seed42_screening01 --execute
python3 detection/scripts/phase1/run.py evaluate \
  --model yolov8n --run-name v01_seed42_screening01 --eval-name best_fp32_01 --execute

# 완료한 결과를 모두 모으되 기존 파일은 덮어쓰지 않습니다.
python3 detection/scripts/phase1/run.py summarize \
  --output detection/records/phase1/screening_results_01.csv
```

train은 train과 epoch별 validation만 수행합니다. RF-DETR의 자동 test는 꺼져 있습니다.
evaluate는 저장된 best checkpoint로 validation 및 test를 각각 수행합니다.
test는 checkpoint 선택, optimizer 선택, confidence 튜닝에 사용하지 않습니다.
실패한 학습도 같은 run에 재실행하지 않으며 새 run 이름을 사용하세요.
학습 run/config/source가 바뀌면 새 prepare가 필요합니다. 평가 재실행은 새 eval 이름을 씁니다.

## 결과 구조와 실제 적용값

```text
experiments/phase1/<model>/<run_id>/
  run.json                         # config·분석/실행 코드·Docker/config source hashes
  resolved_config.yaml
  dataset_snapshot.json
  dataset_manifest.csv
  training/
    environment.json               # GPU·CUDA·cuDNN·패키지 버전
    applied_hyperparameters.json    # 실제 optimizer param groups·scheduler·recipe
    vendor_resolved.yaml            # DETR: include 병합·704 resize까지 적용한 전체 설정
    epoch_history.json
    training_summary.json          # 종료 epoch·best epoch·시간·checkpoint hash·크기·VRAM
    status.json
    ... framework checkpoints/logs
  evaluation/<eval_id>/
    environment.json
    evaluation_config.json
    val/{predictions,metrics,latency_samples}.json
    test/{predictions,metrics,latency_samples}.json
    model_screening_summary.csv
    model_screening_summary.json
    status.json
```

CSV/JSON schema는 `scripts/phase1/results.py:FIELDS`로 통일합니다.
학습값은 요청 config만 복사하지 않고 실제 optimizer type/defaults/param groups,
scheduler type/state, parameter count 및 framework가 적용한 recipe를 수집합니다.
초기 pretrained weights의 SHA-256과 epoch별 학습률도 기록합니다.
YOLO는 `trainer.args`, DETR는 include를 병합한 YAML, RF-DETR는 모델 설정과 native
`training_config.json`을 함께 보관합니다. RF-DETR 기본 optimizer/augmentation 설정은
고정 패키지의 native training config에 기록됩니다.
YOLOv8n/11n은 AdamW cosine, YOLO26n은 MuSGD cosine으로 명시했습니다.
DETR 계열은 고정 upstream N/S recipe의 optimizer와 augmentation을 상속합니다.
100 epoch에 맞춰 augmentation 종료=88, LR milestone=80을 설정하고,
DEIM은 flat=44/no_aug=12/warmup_iter=100으로 설정했습니다.
모든 최종 tensor는 704×704이며 multi-scale은 꺼집니다.

D-FINE/DEIM/RT-DETRv2는 공식 소스를 수정하지 않고 고정된 `fit` 함수 AST의
validation 직후 best 저장과 epoch 끝 patience 종료를 연결합니다.
지원하는 루프 구조가 아니면 조용히 진행하지 않고 실패합니다.
공통 DETR best/early-stop metric은 validation mAP50–95, min_delta=0입니다.
RF-DETR는 native EMA mAP50–95 early stopping, YOLO는 native validation fitness를 사용하며
각 training summary에 monitor를 기록합니다. epoch 값은 모두 1부터 시작합니다.

## 공통 평가 기준과 수식

- 모든 class를 pumpkin=0으로 정규화합니다. GT는 기존 split별 COCO를 사용하고 negative 이미지를 포함합니다.
- `confidence=0.25`, `match_iou=0.50`, `nms_iou=0.70`, AP score floor=0.001은 screening.yaml에서 관리합니다.
  NMS IoU는 YOLO 후처리 설정이고 matching IoU와 별개입니다. DETR는 native NMS-free 후처리를 유지합니다.
- 예측은 이미지당 최대 100개, score 내림차순으로 GT와 같은 class의 최대 IoU 미사용 GT에 일대일 matching합니다.
  IoU >= match_iou이면 TP, 나머지 예측은 FP, 미매칭 GT는 FN입니다.
- Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN). 분모가 0이면 0입니다.
- Validation Precision/Recall은 공통 confidence에서 계산합니다. F1 peak는 validation에서
  AP floor·0.01 간격의 confidence grid·모든 관측 score 경계값으로 계산하고 동률이면 낮은 confidence를 선택합니다.
  F1 confidence는 test threshold를 변경하지 않습니다.
- `% Correct Predictions`=100×TP/(TP+FP+FN): object detection의 matching 정확도로 정의합니다.
  분모가 0이면 null입니다. 별도 `test_image_exact_match_percent`는 FP=FN=0인 이미지 비율이며
  정상 negative도 정답으로 포함합니다.
- Average Confidence는 test threshold 이상 모든 예측(TP+FP)의 평균이며 예측이 없으면 null입니다.
- mAP50·mAP50–95는 같은 pycocotools evaluator로 계산합니다. AP는 test confidence로 자르지 않고
  AP score floor 이상 예측을 사용합니다. maxDets=[1,10,100], 표준 COCO IoU/recall grid를 씁니다.
  GT가 없어서 COCO가 -1을 반환하면 null로 저장합니다.
- 속도: 동일 L4, eager FP32(TF32 비활성), batch 1. decoded RGB PIL 이미지부터 전처리·GPU 전송·forward·후처리·CPU 결과 반환까지 측정합니다.
  파일 읽기·모델 로딩·공통 matching·JSON 저장은 제외합니다. 20회 warmup 후 전체 split을 3회 반복하며
  매 호출 전후 CUDA synchronize, perf_counter를 사용합니다. 모든 sample의 산술평균 ms/image를 기록합니다.
  framework별 native 전처리/후처리 비용을 포함하므로 순수 network forward 시간과는 다릅니다.
- Total Training Time은 framework 초기화·학습·epoch validation·checkpoint 저장을 포함한 worker wall time입니다.
  Docker 시작 시간은 제외합니다. Peak VRAM은 training worker의 torch.cuda.max_memory_allocated()이며
  nvidia-smi의 전체 GPU 점유와 다릅니다. Model size는 선택된 checkpoint의 byte 크기이며
  DETR optimizer state 포함 여부 등 저장 형식에 따른 차이가 있습니다. Parameter count는 총 parameter 수입니다.

## 실행 없는 검증

```bash
python3 -m unittest discover -s detection/scripts/phase1/tests -v
```

검증은 synthetic bbox, config, 명령 생성, early-stop hook, schema, 덮어쓰기 방지입니다.
Docker build·모델 import·학습·validation·test·실제 L4 메모리/속도 확인은 사용자 실행 단계에 남습니다.
모든 seed가 같아도 CUDA/framework 차이에 따라 bitwise 동일 결과를 보장하지 않습니다.
데이터 frozen manifest가 일치하는 것이 leakage 후보가 해결됐음을 의미하지는 않습니다.
