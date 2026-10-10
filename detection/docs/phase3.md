# Phase 3: 하이퍼파라미터 비교

[전체 안내](../README.md) · [이전 단계: Phase 2](phase2.md) · [다음 단계: Phase 4](phase4.md)

YOLO11n과 YOLOv8n의 하이퍼파라미터를 단계별로 비교합니다.
각 모델은 validation으로 설정을 독립적으로 선택하고 다음 단계는 해당 선택을 이어받습니다.
호스트 명령은 `detection/`에서 실행합니다.

## 비교 대상 모델과 선정 근거

Phase 2 증강 비교 결과를 바탕으로 **YOLO11n과 YOLOv8n**을 최종 후보로 선정하고,
두 모델의 Baseline 증강 설정을 유지한 상태에서 하이퍼파라미터를 비교합니다.

- 별도 Spatial·Photometric·Combined 증강은 전반적으로 Baseline 대비 추가 개선을 만들지 못했습니다.
- YOLO11n, YOLOv8n, D-FINE-N은 Baseline이 가장 안정적이었습니다.
- 이 중 D-FINE-N은 모델 크기가 커 최종 후보에서 제외했습니다.
- RF-DETR-N의 Combined 조건은 validation Recall·F1이 개선되었지만 test mAP50–95가 감소했습니다.
  따라서 종합적으로는 Baseline을 유지하며, Phase 3 비교 대상은 YOLO11n과 YOLOv8n으로 좁혔습니다.

이번 결과는 증강이 불필요하다는 의미보다, **각 프레임워크의 기본 학습 설정이 이미 충분한 증강을
포함하고 있었고, 별도 증강 설정으로 교체했을 때 추가 이득이 없었다**고 해석합니다.
Phase 3에서는 이 Baseline을 고정하고 옵티마이저·학습률·배치 크기·가중치 감쇠·스케줄러를 비교합니다.

## 실험 구성

설정은 `configs/phase3/`, 실행 스크립트는 `scripts/phase3/`에 있습니다.
현재 실험 01–05가 구현되어 있으며, 실험 05까지의 선택 결과와 모델별 최적 설정이 저장되어 있습니다.

| 단계 | 스크립트 | 비교 내용 | 실험 번호 |
| --- | --- | --- | --- |
| 실험 01 | `exp01.py` | AdamW와 SGD | 001, 002 |
| 실험 02 | `exp02.py` | SGD 학습률 0.005·0.02와 기존 0.01 | 003, 004; 002 재사용 |
| 실험 03 | `exp03.py` | 선택된 옵티마이저·학습률에서 batch 8과 기존 batch 16 | 005; 모델별 004 또는 002 재사용 |
| 실험 04 | `exp04.py` | 가중치 감쇠 0.0001·0.001과 기존 0.0005 | 006, 007; 모델별 004 또는 002 재사용 |
| 실험 05 | `exp05.py` | 기존 LambdaLR와 cosine 학습률 일정 | 008; 모델별 004 또는 007 재사용 |

두 모델에서 같은 조건은 같은 실험 번호를 사용합니다.
새 학습은 원래 사전 학습 가중치에서 시작합니다.
Phase 1 데이터·seed·평가 설정과 Phase 2의 baseline 증강을 사용합니다.
평가는 validation만 사용하며 Official Test는 사용하지 않습니다.

## 실행 방식

각 스크립트는 `list`, `train`, `evaluate`, `collect`, `run-all`을 제공합니다.
`list`는 조건을 표시하고 `run-all`은 실행할 명령만 출력합니다.
`run-all --execute`는 각 조건의 학습과 validation 평가를 순차 수행한 뒤 취합합니다.
학습 또는 평가가 실패하면 중단하며, 모든 조건이 성공해야 자동 취합합니다.
`collect`는 GPU 학습 없이 요약과 선택 결과를 갱신합니다.

같은 단계의 실행들은 독립적이므로 별도 GPU에 분배하거나 설정된 L4에서 하나씩 실행할 수 있습니다.
다음 단계로 넘어가기 전에는 필요한 실행의 validation 결과와 선택 JSON을 준비해야 합니다.
현재 계획과 다른 설정이 선택되면 후속 스크립트의 선행 조건 검사에서 진행을 막습니다.
설정은 validation mAP50–95 → F1 → recall → mAP50 순으로 비교해 선택합니다.
동률이면 최적 epoch까지 걸린 시간, 전체 학습 시간이 짧은 실행을 우선합니다.

## 실험 01: 옵티마이저

AdamW는 학습률 0.002·momentum 0.9, SGD는 학습률 0.01·momentum 0.937로 비교합니다.
각 옵티마이저에 맞는 시작 학습률과 momentum을 함께 사용합니다.
Phase 1 비교 결과와 Phase 2 모델별 기준 상세 결과가 필요합니다.

```bash
python3 scripts/phase3/exp01.py list
python3 scripts/phase3/exp01.py run-all
python3 scripts/phase3/exp01.py run-all --execute
python3 scripts/phase3/exp01.py collect
```

실행 순서는 YOLO11n 001 → YOLO11n 002 → YOLOv8n 001 → YOLOv8n 002입니다.
개별 조건도 실행할 수 있으며, `--execute`를 생략하면 명령만 출력합니다.

```bash
python3 scripts/phase3/exp01.py train --model yolo11n --experiment 001 --execute
python3 scripts/phase3/exp01.py evaluate --model yolo11n --experiment 001 --execute
```

`collect`는 요약, 기준 대비 변화량, `exp01_selection.json`을 갱신합니다.
미완료 실행의 지표는 빈칸으로 둡니다.

## 실험 02: 학습률

`exp02.py`는 두 모델 모두 실험 01에서 SGD·학습률 0.01을 선택했는지 확인하고,
완료된 002 validation 결과를 읽습니다.
모델별 새 조건은 003(학습률 0.005), 004(학습률 0.02)입니다.
002의 학습·YOLO 설정에서 `lr0`만 바꿉니다.

```bash
python3 scripts/phase3/exp02.py list
python3 scripts/phase3/exp02.py run-all            # 새 학습·평가 4쌍의 명령 출력
python3 scripts/phase3/exp02.py run-all --execute
python3 scripts/phase3/exp02.py collect
```

요약에는 002가 `reused_exp01` 상태로 포함되며 003·004와 함께 비교됩니다.
`exp02_delta.csv`는 각 학습률을 002와 비교합니다.
누적 CSV는 실험 01 행을 유지하고 모델별 새 실행 2개를 추가합니다.

## 실험 03: 배치 크기

`exp03.py`는 모델별 실험 02 선택 결과를 확인합니다.
현재 계획은 아래 batch 16 실행을 재사용하며 새 실험 005에서 batch 8만 학습합니다.

| 모델 | 재사용 실험 | 옵티마이저 | 학습률 | momentum |
| --- | --- | --- | --- | --- |
| YOLO11n | 004 | SGD | 0.02 | 0.937 |
| YOLOv8n | 002 | SGD | 0.01 | 0.937 |

Ultralytics의 `nbs`도 `batch_size`와 함께 8로 설정하여 유효 배치 크기를 바꿉니다.
나머지 YOLO 설정은 이어받습니다.

```bash
python3 scripts/phase3/exp03.py list
python3 scripts/phase3/exp03.py run-all            # 새 학습·평가 2쌍의 명령 출력
python3 scripts/phase3/exp03.py run-all --execute
python3 scripts/phase3/exp03.py collect
```

`exp03_summary.csv`는 모델별 기존 batch 16과 새 batch 8을 비교합니다.
`exp03_delta.csv`는 각 모델의 재사용 실행 대비 변화량입니다.
누적 CSV에는 실험 005만 추가합니다.

## 실험 04: 가중치 감쇠

`exp04.py`는 실험 03에서 두 모델 모두 batch 16을 선택했는지 확인합니다.
YOLO11n은 004, YOLOv8n은 002를 재사용하며 기본 가중치 감쇠는 0.0005입니다.
새 실험 006은 0.0001, 007은 0.001을 사용합니다.
선택된 설정을 이어받고 가중치 감쇠만 바꿉니다.

```bash
python3 scripts/phase3/exp04.py list
python3 scripts/phase3/exp04.py run-all            # 새 학습·평가 4쌍의 명령 출력
python3 scripts/phase3/exp04.py run-all --execute
python3 scripts/phase3/exp04.py collect
```

`exp04_summary.csv`는 세 가중치 감쇠 조건을 비교합니다.
`exp04_delta.csv`는 모델별 재사용 실행의 0.0005 대비 변화량입니다.
누적 CSV에는 실험 006·007만 추가합니다.

## 실험 05: 학습률 스케줄러

`exp05.py`는 실험 04의 선택 결과를 확인하고 모델별 LambdaLR 실행을 재사용합니다.
새 실험 008은 선택된 설정에서 `cos_lr=True`만 바꾸어 cosine 일정을 비교합니다.
결과 파일의 스케줄러 표기는 `CosineLR`입니다.

| 모델 | 재사용 실험 | 학습률 | 가중치 감쇠 | 공통 조건 |
| --- | --- | --- | --- | --- |
| YOLO11n | 004 | 0.02 | 0.0005 | SGD, momentum 0.937, batch 16 |
| YOLOv8n | 007 | 0.01 | 0.001 | SGD, momentum 0.937, batch 16 |

```bash
python3 scripts/phase3/exp05.py list
python3 scripts/phase3/exp05.py run-all            # 새 학습·평가 2쌍의 명령 출력
python3 scripts/phase3/exp05.py run-all --execute
python3 scripts/phase3/exp05.py collect

# 한 모델의 새 cosine 조건 실행
python3 scripts/phase3/exp05.py train --model yolo11n --execute
python3 scripts/phase3/exp05.py evaluate --model yolo11n --execute
```

`run-all`은 YOLO11n → YOLOv8n 순서로 실행하며 `--model`을 받지 않습니다.
`exp05_summary.csv`는 재사용 실행과 새 008을 비교하고,
`exp05_delta.csv`는 모델별 재사용 실행 대비 변화량을 기록합니다.
누적 CSV에는 실험 008만 추가합니다.
`collect`는 `exp05_selection.json`과 모델별 `<모델명>_best.yaml`도 갱신합니다.

### 저장된 최적 설정

`exp05_selection.json`과 모델별 최적 설정 YAML에서는 두 모델 모두 LambdaLR를 선택했습니다.
아래 mAP50–95는 validation 결과입니다.

| 모델 | 선택 실험 | 학습률 | 가중치 감쇠 | LambdaLR mAP50–95 | CosineLR mAP50–95 |
| --- | --- | --- | --- | --- | --- |
| YOLO11n | 004 | 0.02 | 0.0005 | 0.962979 | 0.960286 |
| YOLOv8n | 007 | 0.01 | 0.001 | 0.971843 | 0.959764 |

공통 최적 조건은 SGD, momentum 0.937, batch 16, seed 42, 입력 704×704입니다.
이 설정으로 선택된 체크포인트를 [Phase 4](phase4.md)의 최종 test 평가에서 사용합니다.

## 산출물

| 경로 | 내용 |
| --- | --- |
| `experiments/phase3/<번호>/<모델명>/` | 학습 파일, 체크포인트, epoch 로그, 상세 validation 결과 |
| `results/phase3/expNN_summary.csv` | 해당 단계의 조건별 요약 |
| `results/phase3/expNN_delta.csv` | 해당 단계의 기준 실행 대비 변화량 |
| `results/phase3/expNN_selection.json` | 모델별 선택 결과와 완료 상태 |
| `results/phase3/hyperparameter_summary.csv` | 단계별 실행의 누적 요약 |
| `results/phase3/hyperparameter_delta.csv` | Phase 2 baseline 대비 누적 변화량 |
| `results/phase3/yolo11n_best.yaml` | YOLO11n의 최적 설정, 원본 설정 경로, validation 지표 |
| `results/phase3/yolov8n_best.yaml` | YOLOv8n의 최적 설정, 원본 설정 경로, validation 지표 |

`NN`은 단계 번호 `01`–`05`입니다. `results/phase3/`에는 요약 CSV, 선택 JSON, 최적 설정 YAML을 저장합니다.
각 단계의 `collect`는 필요한 새 실행의 validation 결과가 갖춰지면 모델별로 설정을 선택합니다.

기존에 완료된 실험 01 실행은 `results/phase3/`에서 `experiments/phase3/`로 이동되었습니다.
이동된 실행에는 `relocation.json`이 있습니다.
원래 `args.yaml`·`config.yaml`에는 학습 당시 경로가 남아 있으며,
취합 스크립트는 현재 실험 디렉토리를 읽습니다.

## 코드 검사

```bash
python3 -m unittest discover -s scripts/phase3 -p 'test_exp*.py' -v
```
