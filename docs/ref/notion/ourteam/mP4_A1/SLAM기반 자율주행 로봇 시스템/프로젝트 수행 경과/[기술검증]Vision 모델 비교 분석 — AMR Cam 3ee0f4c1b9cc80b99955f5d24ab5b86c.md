# [기술검증]Vision 모델 비교 분석 — AMR Cam

관련 이슈·To-do: [기술검증]Vision 모델 활용과 성능 평가 방법 이해 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%ED%99%9C%EC%9A%A9%EA%B3%BC%20%EC%84%B1%EB%8A%A5%20%ED%8F%89%EA%B0%80%20%EB%B0%A9%EB%B2%95%20%EC%9D%B4%ED%95%B4%203ed0f4c1b9cc80c68987d8779a03f04e.md)
날짜: 2026년 10월 3일
기록일: 2026년 10월 3일
담당자: 봉승현
마지막 수정: 2026년 10월 6일 오전 10:07
분류: 실험
분야: Vision
생성일: 2026년 10월 3일 오후 2:42
작성 상태: 정리 완료

# 0. 요약

모델 3개 × 학습 설정 3개, 총 9개 실험을 비교하고 실시간 탐지용 1차 후보를 선정한 기록.

**잠정 선정: YOLO11n + mosaic_05.** Test 오류가 없고 측정된 평균 추론 시간이 가장 짧았다.

**평가 구분:** Validation 지표와 고정 confidence에서 직접 집계한 Test 지표는 서로 다른 평가다.

# 1. 실험 개요

| 항목 | 내용 |
| --- | --- |
| 모델 | YOLOv8n / YOLO11n / YOLO26n · 각 3개 설정 |
| 작업 | 객체 탐지(Detection) · RC car 탐지 및 AMR 적용 가능성 검토 |
| 출력 | Bounding Box, class ID, confidence |
| 클래스 | 2개 클래스 · ID 0: car / ID 1: dummy — experiment_info.json의 class_names 순서 기준 |
| Ultralytics | 8.4.171 |
| 실험 이름 | 각 모델의 baseline / adamw_lr / mosaic_05. |
| 목표 / 기록 | 탐지 정확도·오탐·미탐·추론 지연·학습 시간 비교
AMR 적용 1차 후보 선정 |
| 최적 모델 대응 시점 | 선정 run은 총 80 epoch 수행.
([best.pt](http://best.pt) epoch 60) |
| 평가 분할 | Train 175장 / Validation 50장 / Test 25장 · 이미지 비중 70% / 20% / 10%. |
| 학습 방식 | 각 실험마다 원본 pretrained 모델에서 새로 학습 · seed=42 단일 학습 |
| 핵심 설정 | 최대 100 epoch, patience=20, batch=16, imgsz=640, device=0, workers=2, pretrained=true, deterministic=true, amp=true, cache=false |

## 1-1. 비교한 학습 설정

| 실험 | 요청 optimizer | 실제 optimizer | 기록된 초기 LR | mosaic |
| --- | --- | --- | --- | --- |
| baseline | auto | AdamW | 0.001667 · 3개 param group 동일 | 1.0 |
| adamw_lr | AdamW | AdamW | 0.001 · 3개 param group 동일 | 1.0 |
| mosaic_05 | auto | AdamW | 0.001667 · 3개 param group 동일 | 0.5 |

모든 조합의 실제 optimizer는 AdamW다. adamw_lr 결과는 AdamW 도입 효과가 아니라, 자동 선택에서 명시 선택으로 전환하고 기록된 초기 학습률을 변경한 실험으로 해석한다. 초기 LR 기록만으로 학습 전 구간의 LR 스케줄까지 같다고 판단하지 않는다.

# 2. 최적 모델 성능

**상세 기록 대상: YOLO11n + mosaic_05의 [best.pt](http://best.pt).** 아래 표는 별도 Validation 평가 결과이며, 모든 모델 중 각 지표의 최고값을 의미하지 않는다.

| 지표 | Bounding Box · Validation |
| --- | --- |
| Precision | 99.774% |
| Recall | 99.000% |
| mAP50 | 99.462% |
| mAP50-95 | 95.404% |
- Precision: 예측한 객체 중 정답으로 인정된 비율. 위 값은 Validation 요약 값이다.
- Recall: 실제 정답 객체 중 찾아낸 비율. 위 값은 Validation 요약 값이다.

## 2-1. 고정 기준 Test 성능과 처리 시간

| 항목 | 내용 |
| --- | --- |
| GT / 예측 / TP | 50 / 50 / 50 |
| FP / FN | 0 / 0 |
| Test Precision / Recall / F1 | 100% / 100% / 100% · 이번 Test 집계 기준 |
| 정답 예측 평균 confidence | 94.963% |
| 평균 추론 시간 | 3.925 ms/image |
| 추론 시간 표준편차 | 0.332 ms |
| 추론 시간 p95 | 4.173 ms |
| 추론 시간 환산 FPS | 254.75 · 순수 추론 시간의 역수 |
| 평균 전처리 / 후처리 | 0.973 / 0.929 ms |
| 전처리+추론+후처리 평균 합계 | 5.828 ms · 카메라·통신·ROS2 처리 미포함 |

Test는 이미지 25장에 포함된 car·dummy 전체 정답 객체 50개를 평가한 결과다. 클래스별 객체 수와 차량만의 성능은 별도 집계해야 한다. 오류 0개는 해당 Test에서의 관측 결과이며 실제 환경에서 오류가 없음을 보장하지 않는다. 추론 환산 FPS는 실제 카메라 또는 ROS2 노드 FPS가 아니다.

## 2-2. 9개 실험 비교

![comparison.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/comparison.png)

단위: 성능은 %, 시간은 ms/image 및 분.

| 모델 | 설정 | Val mAP50 | TP / FP / FN | 평균 추론(ms/image) | p95 | 학습 시간(min/image) |
| --- | --- | --- | --- | --- | --- | --- |
| yolov8n | baseline | 99.480% | 50 / 0 / 0 | 4.878 | 5.629 | 6.506 |
| yolov8n | adamw_lr | 99.461% | 50 / 0 / 0 | 4.028 | 4.067 | 5.822 |
| yolov8n | mosaic_05 | 99.280% | 50 / 1 / 0 | 4.051 | 4.094 | 3.776 |
| yolo11n | baseline | 99.462% | 50 / 0 / 0 | 4.124 | 4.142 | 5.992 |
| yolo11n | adamw_lr | 99.075% | 50 / 1 / 0 | 4.088 | 4.120 | 3.937 |
| yolo11n | mosaic_05 | 99.462% | 50 / 0 / 0 | 3.925 | 4.173 | 5.259 |
| yolo26n | baseline | 99.500% | 50 / 0 / 0 | 4.334 | 4.386 | 5.689 |
| yolo26n | adamw_lr | 99.500% | 49 / 0 / 1 | 4.303 | 4.387 | 7.751 |
| yolo26n | mosaic_05 | 99.500% | 50 / 0 / 0 | 4.347 | 4.362 | 6.774 |

### 실험 Hyperparameter 비교

| 번호 | 모델 | 실험 | optimizer 요청값 | 실제 optimizer | lr0 명시 설정 | 실제 초기 LR | mosaic | mixup | close_mosaic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | YOLOv8n | baseline | auto | AdamW | 미지정 | 0.001667 | 1.0 | 0.0 | 10 |
| 2 | YOLOv8n | adamw_lr | AdamW | AdamW | 0.001 | 0.001000 | 1.0 | 0.0 | 10 |
| 3 | YOLOv8n | mosaic_05 | auto | AdamW | 미지정 | 0.001667 | 0.5 | 0.0 | 10 |
| 4 | YOLO11n | baseline | auto | AdamW | 미지정 | 0.001667 | 1.0 | 0.0 | 10 |
| 5 | YOLO11n | adamw_lr | AdamW | AdamW | 0.001 | 0.001000 | 1.0 | 0.0 | 10 |
| 6 | YOLO11n | mosaic_05 | auto | AdamW | 미지정 | 0.001667 | 0.5 | 0.0 | 10 |
| 7 | YOLO26n | baseline | auto | AdamW | 미지정 | 0.001667 | 1.0 | 0.0 | 10 |
| 8 | YOLO26n | adamw_lr | AdamW | AdamW | 0.001 | 0.001000 | 1.0 | 0.0 | 10 |
| 9 | YOLO26n | mosaic_05 | auto | AdamW | 미지정 | 0.001667 | 0.5 | 0.0 | 10 |

### 모든 실험의 공통 설정

| Hyperparameter | 값 |
| --- | --- |
| epochs | 100 |
| patience | 20 |
| batch | 16 |
| imgsz | 640 |
| device | 0 |
| seed | 42 |
| workers | 2 |
| pretrained | true |
| deterministic | true |
| amp | true |
| cache | false |
| data | `/content/dataset_3x3/custom_data.yaml` |

Batch size는 Ultralytics 공식 기본값인 16으로 명시 설정했다. 9개 실험에 동일한 배치 크기를 적용하여 모델 및 학습 옵션 비교 시 배치 크기 차이의 영향을 통제했다. 배치 크기별 비교 실험은 수행하지 않았으므로, 16을 최적값으로 주장하지 않는다.

## 2-3. 선정 판단 흐름

1. AMR 대상 탐지에서는 미탐과 오탐을 먼저 확인한다. 대상 상실과 잘못된 대상 접근에 직접 영향을 주기 때문이다.
2. 동일한 Test 조건에서 FP=0, FN=0인 6개 조합을 우선 후보로 남긴다.
3. 후보 간 Validation 차이와 처리 시간을 비교한다. YOLO26n baseline의 Val mAP50는 99.500%, YOLO11n mosaic_05는 99.462%로 차이는 약 0.038%p다. 단일 학습·소규모 Test로 우열을 확정하기 어렵다.
4. YOLO11n mosaic_05는 평균 추론 시간 3.925 ms로 가장 짧고 Test 오류가 없어 실시간 탐지용 1차 후보로 선정한다. YOLO26n baseline 대비 이번 평균 추론 시간은 약 9.4% 짧다.
5. 평균 속도만으로 확정하지 않는다. YOLOv8n adamw_lr의 p95는 4.067 ms로 선정 모델의 4.173 ms보다 짧다. 측정 순서·GPU 상태 등을 통제한 재측정이 필요하다.
6. 실제 AMR 카메라의 거리·조명·가림·회전·대상 없는 장면에서 탐지 연속성, 오탐 빈도, 전체 처리 지연을 비교하여 최종 확정한다.

정답 예측 평균 confidence는 선정의 주 지표로 사용하지 않는다. YOLO26n adamw_lr는 평균 confidence 98.394%로 가장 높지만 FN=1이다. 놓친 객체는 정답 예측 confidence 평균에 포함되지 않는다.

**추가 검증 후보:** YOLOv8n adamw_lr(낮은 측정 지연 변동), YOLO26n baseline(높은 Validation 지표). Test를 보고 선정한 후보이므로 최종 검증에는 별도의 새 영상·데이터를 사용한다.

# 3. 데이터셋과 클래스

## 3-1. 라벨 분포

클래스 순서는 공유된 experiment_info.json에서 확인했다. 학습 객체 합계는 349개이며, 클래스별 학습 라벨 분포는 labels.jpg 또는 라벨 원본 확인이 필요하다. 가중치 내부 names와의 직접 대조는 아직 수행하지 않았다.

| ID | 클래스 | Train | Validation | Test | 전체 | 전체 비중 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | car | 175 | 50 | 25 | 250 | 50.10% |
| 1 | dummy | 174 | 50 | 25 | 249 | 49.90% |
| **합계** |  | **349** | **100** | **50** | **499** | **100%** |

## 3-2. 평가 데이터와 분할 확인

| 분할 | 이미지 수 | GT 객체 수 | 이미지 비중 |
| --- | --- | --- | --- |
| train | 175 | 349 | 70% |
| val | 50 | 100 | 20% |
| test | 25 | 50 | 10% |
| 합계 | 250 | 499 | 100% |
- 전체 이미지당 평균 객체 수는 약 2개다. 분할별·클래스별 균등 분포를 의미하지 않는다.
- 학습 종료 후 [best.pt](http://best.pt) 검증 로그의 Validation 클래스별 GT는 car 50개, dummy 50개다.
- Test 클래스별 GT는 현재 표만으로 확정할 수 없다.
- 같은 촬영 영상·유사 프레임이 여러 분할에 섞였는지 확인 필요.
- 데이터셋 ZIP: `/content/drive/MyDrive/My_Colab_Notebooks/AMR_Cam.v1.yolov8.zip`.
    
    [AMR_Cam.v1.yolov8.zip](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/AMR_Cam.v1.yolov8.zip)
    
- 실제 AMR 카메라의 새로운 거리·조명·배경·각도로 추가 검증한다.

# 4. 학습 옵션

## 4-1. 기본 학습·실행

| 옵션 | 값 | 의미 |
| --- | --- | --- |
| task / mode | Detection / train · 코드 기준 | 객체 탐지 학습 |
| epochs | 100 · 실제 수행 80 | 목표 최대 epoch와 실제 수행량 구분 |
| patience | 20 | 최적 점수 개선 대기 설정 |
| batch | 16 | 학습 배치 크기 |
| imgsz | 640 | 입력 크기 기준 |
| device | 0 | GPU 0번 · Tesla T4 |
| workers | 2 | 데이터 로딩 작업자 |
| pretrained | true | 사전학습 가중치 사용 |
| resume | false | 코드는 매 실험 원본 pretrained 모델로 시작 |
| amp | true | 학습 자동 혼합 정밀도 |
| cache | false | 학습 이미지 캐시 비활성화 |
| fraction | 1.0 | train 데이터 전체 사용 |
| seed / deterministic | 42 / true | 재현성 관련 설정 · seed 반복 실험 없음 |
| single_cls | false | car·dummy 두 클래스 유지 |
| rect | false | 직사각형 배치 학습 비활성화 |
| multi_scale | 0.0 | 멀티스케일 학습 비활성화 |
| freeze | None | 사용자가 별도 레이어 동결 범위를 지정하지 않음 |
| compile | false | 모델 컴파일 비활성화 |
| time | None | 시간 기반 종료 한도 미지정 |

## 4-2. 경로

| 항목 | 내용 |
| --- | --- |
| model / resume | [yolo11n.pt](http://yolo11n.pt) · resume=false · 각 실험 원본 pretrained에서 새로 학습 |
| data | /content/dataset_3x3/custom_data.yaml |
| project | /content/drive/MyDrive/My_Colab_Notebooks/yolo_3x3_seed42_v1/runs |
| name | yolo11n__mosaic_05 |
| save_dir | ROOT/runs/yolo11n__mosaic_05 |
| 평가 가중치 | ROOT/runs/yolo11n__mosaic_05/weights/[best.pt](http://best.pt) |

## 4-3. 최적화·학습률

| 옵션 | 설정값 | 의미 |
| --- | --- | --- |
| `optimizer` | `auto` → **실제 AdamW** | optimizer 자동 선택 |
| `lr0` | `0.01` → **실제 초기 LR 0.001667** | `auto`에서 설정값을 무시하고 자동 결정 |
| `lrf` | `0.01` | 최종 학습률의 초기 학습률 대비 비율 |
| `momentum` | `0.937` → **자동 선택 로그 0.9** | AdamW에서는 beta1에 대응 |
| `weight_decay` | `0.0005` | 가중치 감쇠 설정·파라미터 그룹별 적용은 다름 |
| `warmup_epochs` | `3.0` | 학습 초반 워밍업 기간 설정 |
| `warmup_momentum` | `0.8` | 워밍업 시작 모멘텀 설정 |
| `warmup_bias_lr` | `0.1` | 로그의 설정값·자동 optimizer 적용 후 값과 구분 필요 |
| `cos_lr` | `false` | 코사인 학습률 스케줄 비활성화 |
| `nbs` | `64` | 배치 관련 내부 스케일링 기준 |

## 4-4. 데이터 증강

| 옵션 | 적용값 | 의미 |
| --- | --- | --- |
| `hsv_h / hsv_s / hsv_v` | `0.015 / 0.7 / 0.4` | 색조·채도·밝기 변화 범위 |
| `translate` | `0.1` | 이미지 크기를 기준으로 이동 범위 설정 |
| `scale` | `0.5` | 크기 변화 범위 설정 |
| `fliplr` | `0.5` | 좌우 반전 확률 50% |
| `flipud` | `0.0` | 상하 반전 비활성화 |
| `degrees / shear / perspective` | `0.0 / 0.0 / 0.0` | 회전·기울임·원근 증강 비활성화 |
| `bgr` | `0.0` | RGB↔BGR 채널 순서 변경 비활성화 |
| **`mosaic`** | **`0.5`** | Mosaic 적용 확률 50% |
| `close_mosaic` | `10` | 예정된 학습 종료 전 마지막 10 epoch에 Mosaic 종료 설정 |
| `mixup / cutmix / copy_paste` | `0.0 / 0.0 / 0.0` | 비활성화 |
| `copy_paste_mode` | `flip` | 방식 설정이며, 적용 확률이 0이므로 비활성 상태 |

## 4-5. 검증·저장·기타

| 옵션 | 확인된 값 | 의미 |
| --- | --- | --- |
| `val / split` | true / val | 학습 중 Validation 수행 |
| `plots / save` | true / true | 학습 그래프·모델 가중치 저장 |
| `save_period` | -1 | 주기적인 별도 epoch 체크포인트 저장 비활성화 |
| `conf` | 학습 None / 별도 Val 0.001 / Test 0.25 | 단계별 confidence 설정 구분 |
| `iou` | 0.7 | 예측 후처리에 전달한 IoU 설정 |
| `MATCH_IOU` | 0.5 | Test 정답 인정용 매칭 기준 |
| `max_det` | 300 | 이미지당 최대 검출 수 설정 |
| `save_json` | false | 내장 평가 결과 JSON 내보내기 비활성화 |
| `retina_masks` | false | 이번 Detection 실험에서는 해당 없음 |
| `augment` | false | 증강 추론 비활성화 |
| 평가 `batch` | Val 16 / Test 1 | 평가 배치 크기 |
| 평가 `device / half` | 0 / false | GPU 0번·반정밀도 추론 비활성화 |

# 5. 학습 진행과 [best.pt](http://best.pt) 선택

## 5-1. 주요 epoch 성능

YOLO11n의 `mosaic=0.5` 실험은 최대 100 epoch로 설정했으며, 실제로는 80 epoch까지 수행했다. 아래는 학습 중 Validation 지표이며, 단위는 %다. Detection 실험이므로 Mask 지표는 해당 없음이다.

| Epoch | Precision | Recall | Box mAP50 | Box mAP50-95 |
| --- | --- | --- | --- | --- |
| 1 | 0.167 | 50.000 | 32.081 | 26.310 |
| 10 | 57.326 | 68.000 | 73.831 | 51.296 |
| 20 | 98.561 | 99.000 | 98.691 | 90.260 |
| 30 | 99.808 | 99.000 | 98.823 | 91.406 |
| 40 | 99.451 | 99.865 | 99.500 | 92.294 |
| 50 | 99.712 | 100.000 | 99.500 | 91.859 |
| **60 · Best** | **99.772** | **99.000** | **99.462** | **95.404** |
| 70 | 99.737 | 99.000 | 99.480 | 93.132 |
| **80 · 마지막** | **99.810** | **100.000** | **99.500** | **95.082** |

20 epoch에서 mAP50가 98.691%에 도달했고, 이후 높은 수준을 유지했다. 40→60 epoch에서는 mAP50 변화가 작지만 mAP50-95가 3.110%p 상승해, 더 엄격한 IoU 기준에서의 탐지 성능이 개선됐다.

## 5-2. 지표별 최고값

| 지표 | 최고값 | Epoch |
| --- | --- | --- |
| Precision(B) | 100.000% | 8, 18 |
| Recall(B) | 100.000% | 49, 50, 51, 53, 80 |
| mAP50(B) | 99.500% | 40, 41, 47, 50, 51, 52, 54, 76~80 |
| mAP50-95(B) | **95.404%** | **60** |

9개 모델 중 Validation 최고값은 선정 모델의 학습 중 epoch별 최고값과 다른 개념이다.

## 5-3. 최적 모델이 60 epoch 근거

선정 실험의 EarlyStopping 로그에 다음 문장이 명시되어 있다.

> Best results observed at epoch 60, best model saved as [best.pt](http://best.pt).
> 

CSV에서도 **60 epoch의 mAP50-95가 전체 학습 중 최고값인 95.404%**로 확인된다.

80 epoch의 마지막 모델은 Precision·Recall·mAP50가 조금 높지만, mAP50-95는 95.082%로 최적 모델보다 0.322%p 낮다. 따라서 마지막 모델과 최적 모델을 구분하고, 후속 평가에는 60 epoch에서 선정된 best.pt를 사용했다.

## 5-4. 종료 시점과 시간

| 항목 | 결과 |
| --- | --- |
| 최대 학습 설정 | 100 epoch |
| 최적 모델 선정 | **60 epoch** |
| 실제 학습 종료 | **80 epoch** |
| 종료 사유 | 이후 20 epoch 동안 선정 기준 점수 개선 없음 |
| 조기 종료 설정 | `patience=20` |
| CSV 마지막 누적 시간 | 306.295초 · 약 5.105분 |
| 코드에서 측정한 학습 실행 시간 | 315.523초 · 약 5.259분 |

# 6. 클래스별 AP50

| 클래스 | 정답 객체 수 | Box AP50 | Box AP50-95 | 해석 |
| --- | --- | --- | --- | --- |
| car | 50 | 99.5% | **98.3%** | 엄격한 IoU 기준에서도 높은 성능 |
| dummy | 50 | 99.4% | **92.5%** | car보다 엄격한 위치 기준에서 성능이 낮음 |
| 전체 | 100 | 99.5% | 95.4% | 두 클래스 평균 |

전체 mAP50는 car·dummy 두 클래스의 평균이며, 차량 클래스 AP50와 구분한다.

# 7. 혼동행렬 상세 분석

## 7-1. 분석 자료와 평가 조건

선정 모델의 별도 Validation 결과와 Test 결과를 구분한다.

| 구분 | 평가 대상 | 평가 조건 |
| --- | --- | --- |
| Validation 혼동행렬 | 50장·정답 객체 100개 | Ultralytics Validation에서 생성 |
| Validation 요약 | 동일 Validation 분할 | 검증 호출 `conf=0.001`, NMS `iou=0.7` |
| Test 결과 | 25장·정답 객체 50개 | `conf=0.25`, NMS IoU=0.7, 정답 매칭 IoU≥0.5 |

검증 호출의 conf와 NMS Iou를 혼동행렬의 내부 매칭 기준과 동일하게 간주하지 않는다.

## 7-2. 축과 background 의미

| 위치 | 의미 |
| --- | --- |
| 가로축 True | 실제 정답 클래스 |
| 세로축 Predicted | 예측 클래스 |
| 대각선 | 정답과 올바르게 매칭된 검출 |
| 클래스 사이 비대각선 | 다른 클래스 예측으로 매칭된 오류 |
| 맨 아래 background 행 | 매칭되지 않은 실제 물체 · FN |
| 맨 오른쪽 background 열 | 정답에 매칭되지 않은 예측 · FP |

background 열에는 배경 오인식뿐 아니라 중복 검출, bbox 위치 불일치, 라벨 누락 등이 포함될 수 있다.

## 7-3. Validation 개수 행렬

![confusion_matrix.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/confusion_matrix.png)

- 실제 car 50개 중 36개를 car, 14개를 dummy로 예측했다.
- 실제 dummy 50개 중 30개를 dummy, 20개를 car로 예측했다.
- GT와 매칭되지 않은 예측은 car 308개, dummy 1,577개로 총 1,885개다.
- 대각선 매칭은 67개, 클래스 간 오분류 매칭은 33개다.

## 7-4. 혼동행렬에서 계산한 클래스별 지표

| 클래스 | 정답 수 | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| car | 50 | 37 | 20+308 = **328** | 13 | **10.14%** | **74.00%** |
| dummy | 50 | 30 | 13+1,577 = **1,590** | 20 | **1.85%** | **60.00%** |
| **합계 / Micro** | **100** | **67** | **1,918** | **33** | **3.38%** | **67.00%** |

이 지표는 해당 혼동행렬의 매칭 결과에서 계산한 값이며, Validation 요약의 Precision-Recall 또는 Test 지표와 구분한다.

## 7-5. 정규화 행렬 해석

![confusion_matrix_normalized.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/confusion_matrix_normalized.png)

| 실제 클래스 | 올바른 클래스 매칭 | 다른 클래스 매칭 | 매칭되지 않은 정답 |
| --- | --- | --- | --- |
| car | 74% | dummy로 26% | 0% |
| dummy | 60% | car로 40% | 0% |

background 열의 약 0.16 / 0.84는 정답과 매칭되지 않은 예측 1,885개 중 car가 약 16%, dummy가 약 84%라는 의미이다. 전체 배경의 84%를 dummy로 잘못 인식했다는 뜻은 아니다.

## 7-6. Test 결과

클래스별 예측과 정답 매칭 여부를 확인한 결과는 다음과 같다.

| 클래스 | Test 정답 수 | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| car | 25 | 25 | 0 | 0 | 100% | 100% |
| dummy | 25 | 25 | 0 | 0 | 100% | 100% |
| **합계 / Micro** | **50** | **50** | **0** | **0** | **100%** | **100%** |

평가 기준은 confidence=0.25, 동일 클래스의 정답과 IoU≥0.5인 일대일 매칭이다.

이번 Test에서는 오류가 관찰되지 않았다. 다만 클래스별 정답이 25개이므로, 실제 운영 환경에서도 오류가 없다고 일반화하지 않는다.

## 7-7. 높은 AP와 혼동행렬의 차이

Validation 요약은 Precision 약 **99.77%**, Recall **99.00%**, mAP50 약 **99.46%**로 높지만, 저장된 혼동행렬에서 계산한 지표는 낮다.

AP는 confidence 순위와 클래스별 정답 매칭을 이용해 계산하며, 혼동행렬은 별도의 매칭 절차로 집계한다. 따라서 동일한 결과에서도 두 지표가 달라질 수 있다. Ultralytics의 공개 구현에서도 두 계산 절차는 구분된다.

따라서 해당 차이에 대하여 현 단계에서는 다음과 같이 기록한다.

선정 모델은 Validation AP와 이번 Test 평가에서 높은 성능을 보였다. 반면 Validation 혼동행렬에는 다수의 미매칭 예측과 클래스 간 오분류 매칭이 나타났다. 평가·매칭 방식의 차이를 고려해 두 결과를 분리하여 보고하며, 낮은 confidence threshold만으로 차이의 원인을 단정하지 않는다.

# 8. 그래프 이미지별 분석

본 절은 `validation` 폴더의 Box 그래프와 학습 폴더의 `results.png`, `results.csv`를 기준으로 작성한다.

## 8-1. Box F1–Confidence

![BoxF1_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/BoxF1_curve.png)

그래프 표시값은 **전체 클래스 F1 약 0.99, confidence 약 0.870**이다.

- 기록된 선택 threshold는 **0.86987**, 해당 지점의 평균 F1은 **0.99383**이다.
- confidence 약 0.25 부근의 평균 F1도 **약 0.98415**로 높다.
- 매우 낮은 threshold에서는 F1이 낮고, 중간 구간에서는 높은 수준을 유지한다. 높은 threshold 끝부분에서는 Recall 감소와 함께 F1이 급락한다.

**해석:** Validation에서 Precision과 Recall의 균형이 높은 구간이 넓게 나타난다. 0.870은 Validation에서 선택된 값이며, 이번 Test에는 적용하지 않았다.

Test에서 올바르게 검출된 dummy 중 confidence가 **약 0.268**인 객체도 있다. 따라서 threshold를 0.870으로 높였으면 Test 성능이 더 좋았을 것이라고 결론 내릴 수 없다.

## 8-2. Box Precision–Confidence

![BoxP_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/BoxP_curve.png)

- confidence가 증가하면서 Precision이 전반적으로 높아진다.
- 그래프 표시값은 **Precision 1.00 at confidence 0.975**다.
- 낮은 confidence 구간에서는 dummy의 Precision이 car보다 낮게 나타난다.

**해석:** 높은 threshold는 오탐을 줄일 수 있지만 검출 수와 Recall도 감소시킬 수 있다. **Precision=1.00인 지점을 최적 운영 threshold로 바로 선택하지 않는다.**

## 8-3. Box Precision–Recall

![BoxPR_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/BoxPR_curve.png)

| 구분 | 그래프의 AP50 표시값 |
| --- | --- |
| car | 0.995 |
| dummy | 0.994 |
| 전체 mAP50 | 0.995 |

두 클래스의 곡선은 오른쪽 위에 가깝게 위치한다. Validation에서 높은 Recall까지 높은 Precision을 유지하는 결과다.

전체 그래프 값 0.995는 반올림 표시이며, `validation_summary.json`의 mAP50은 **0.994615**다. 이는 **IoU=0.5에서의 AP**로, 더 엄격한 위치 정확도를 평가하는 mAP50-95와 구분한다.

## 8-4. Box Recall–Confidence

![BoxR_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/BoxR_curve.png)

- 낮은 threshold에서 Recall은 1.00에 가깝다.
- 중간 구간에서도 높은 Recall을 유지한다.
- 높은 confidence 구간에서는 Recall이 급격히 감소하며, dummy가 car보다 먼저 감소한다.

**해석:** threshold를 지나치게 높이면 실제 객체의 예측도 제거된다. Recall 그래프와 Precision 그래프를 함께 보아야 한다.

## 8-5. Confusion Matrix · 개수

![confusion_matrix.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/confusion_matrix%201.png)

정답 100개 중 대각선 매칭은 67개, 다른 클래스 매칭은 33개다. 정답과 매칭되지 않은 예측은 1,885개이며, 그중 dummy가 1,577개로 많다.

**해석:** 이 그림의 평가·매칭 조건에서는 dummy 예측의 미매칭 수가 크게 나타난다. 이를 Test conf=0.25에서의 오류 수로 해석하지 않는다. 상세 계산은 7번에 기록한다.

## 8-6. Confusion Matrix · 정규화

![confusion_matrix_normalized.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/confusion_matrix_normalized%201.png)

car의 대각선 비율은 74%, dummy는 60%다. dummy→car 매칭 비율 40%가 car→dummy 매칭 비율 26%보다 높다.

background 열의 16%·84%는 **미매칭 예측의 클래스 구성비**다. 정규화 그림은 상대적인 비율을 보여주므로, 오류 규모는 개수 행렬과 함께 확인한다.

## 8-7. Epoch별 학습·검증 추이

![results.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%20%EB%B6%84%EC%84%9D%20%E2%80%94%20AMR%20Cam/results.png)

| Epoch | Box mAP50 | Box mAP50-95 |
| --- | --- | --- |
| 20 | 98.691% | 90.260% |
| 40 | 99.500% | 92.294% |
| **60 · best** | **99.462%** | **95.404%** |
| 80 · 마지막 | 99.500% | 95.082% |
- 학습 초반에는 지표 변동이 크지만, 약 20 epoch부터 높은 수준으로 안정된다.
- mAP50은 일찍 높은 수준에 도달하고, 이후에는 더 엄격한 위치 정확도를 반영하는 mAP50-95에서 차이가 나타난다.
- **최적 epoch는 60**, 종료 epoch는 80이다.
- 마지막 epoch의 mAP50은 조금 높지만, mAP50-95는 최적 epoch보다 낮다.

**해석:** mAP50 하나만으로 마지막 모델이 더 좋다고 판단하지 않는다. 이번 기록에서는 60 epoch의 `best.pt`를 선정 모델로 사용한다.

## 8-8. results.png 손실 항목 상세

| 손실 항목 | 의미 | Epoch 20 | Epoch 80 |
| --- | --- | --- | --- |
| train/box_loss | 학습 데이터의 Box 위치 회귀 손실 | 0.47549 | 0.34900 |
| train/cls_loss | 학습 데이터의 클래스 예측 손실 | 0.57145 | 0.30523 |
| train/dfl_loss | 학습 데이터의 경계 위치 분포 학습 손실 | 0.87678 | 0.84566 |
| val/box_loss | 검증 데이터의 Box 위치 회귀 손실 | 0.42566 | 0.30280 |
| val/cls_loss | 검증 데이터의 클래스 예측 손실 | 0.53601 | 0.25957 |
| val/dfl_loss | 검증 데이터의 경계 위치 분포 학습 손실 | 0.83985 | 0.81251 |

학습·검증 손실 모두 전반적으로 감소한다. **검증 손실이 지속적으로 상승하는 뚜렷한 과적합 패턴은 관찰되지 않는다.** 다만 손실 감소가 매 epoch의 AP 향상을 보장하지는 않으므로, 모델 선정은 검증 지표와 함께 판단한다.

# 9. 원본 설정 및 기록

## 9-1. 실행 환경과 데이터셋

| 항목 | 확인 내용 |
| --- | --- |
| Ultralytics | 8.4.171 |
| PyTorch | 2.11.0+cu130 |
| GPU | Tesla T4 |
| 클래스 순서 | 0: car / 1: dummy |
| 데이터셋 규모 | 이미지 250장·객체 499개 |
| 데이터 분할 | Train 175장·349개 / Val 50장·100개 / Test 25장·50개 |
| 클래스별 객체 수 | Train: car 175·dummy 174 / Val: 각각 50 / Test: 각각 25 |
| 실험 구성 | 3개 모델 × 3개 학습 설정 = 9개 실험 |
| 재현성 설정 | seed=42, deterministic=true |

모든 실험에 최대 100 epoch, patience=20, batch=16, imgsz=640을 공통 적용했다. 원본 수치는 정밀도를 유지하고, 본문 표시값만 반올림했다.

## 9-2. 확보한 원본과 확인 사항

| 자료 | 확인 사항 |
| --- | --- |
| `experiment_info.json` | 모델·공통 설정·변경 설정·클래스·실행 환경·평가 기준 |
| `yolo_3x3_experiments.ipynb` | 학습·검증·Test 실행 절차, 정답 매칭 로직, 속도 측정 방식 |
| 데이터셋 집계·`class_balance.csv` | 분할별 이미지·객체 수와 클래스별 라벨 분포 |
| `final_comparison.csv` | 9개 실험의 학습·Validation·Test·속도 요약 |
| 학습 로그 | 조기 종료 실험의 best epoch, 선정 모델의 best epoch=60·종료 epoch=80 |
| `requested_args.json` | 선정 실험에 전달한 학습 옵션 |
| `training_summary.json` | 선정 모델의 학습 시간 약 315.52초와 종료 epoch |
| `effective_optimizer.json` | 실제 optimizer와 초기 학습률 기록 |
| `results.csv` / `results.png` | Epoch별 손실·검증 지표, 지표별 최고값과 학습 추이 |
| `validation_summary.json` / `f1_curve.csv` | Validation 요약과 confidence별 평균 F1 |
| `validation/`의 혼동행렬·Box 곡선 | 별도 Validation의 매칭 결과와 confidence별 성능 |
| `test_summary.json` | Test TP=50, FP=0, FN=0 및 속도 요약 |
| `test_per_image.csv` / `test_detections.csv` | 이미지별 집계, 클래스·confidence·정답 매칭 여부 |
| `speed_samples.csv` | 개별 속도 측정값과 분포 |

첫 Test 이미지로 **5회 워밍업**, 전체 Test 이미지에 대해 **3회 속도 측정**을 수행한다. Test 이미지 25장 기준 속도 표본은 총 75개다.

## 9-3. 요청 설정과 실제 적용값

| 실험 | optimizer 요청값 | 실제 optimizer | 실제 초기 학습률 | mosaic |
| --- | --- | --- | --- | --- |
| baseline | auto | AdamW | 0.001667 | 1.0 |
| adamw_lr | AdamW | AdamW | 0.001000 | 1.0 |
| mosaic_05 | auto | AdamW | 0.001667 | 0.5 |

baseline과 mosaic_05는 `lr0`를 직접 지정하지 않았으며, 자동 선택된 실제 초기 학습률은 0.001667이다.

따라서 `adamw_lr`는 실제 optimizer 종류를 바꾼 실험이라기보다 **AdamW를 명시 지정하고 초기 학습률을 낮춘 실험**이다. `mosaic_05`는 baseline 대비 Mosaic 적용 확률을 낮춘 실험이다.

## 9-4. 평가 자료 구분과 기록 기준

| 구분 | 기록 기준 |
| --- | --- |
| 최적 모델 | 60 epoch의 `best.pt` |
| 마지막 학습 모델 | 80 epoch의 마지막 checkpoint |
| Validation 요약 | `validation_summary.json` |
| Validation 혼동행렬·곡선 | `validation/` 하위 파일 |
| Epoch별 학습 추이 | 학습 폴더의 `results.csv` / `results.png` |
| Test 성능 | confidence=0.25, NMS IoU=0.7, 동일 클래스 정답 매칭 IoU≥0.5 |
| Validation F1 선택점 | confidence 약 0.870. Test에는 적용하지 않음 |

학습 폴더와 `validation` 폴더에 동일한 이름의 혼동행렬이 존재하며, 수치도 다르다. 본문 7·8번은 별도 `validation` 폴더를 기준으로 작성하고, 두 파일의 수치를 혼합하지 않는다.

혼동행렬에서 계산한 Precision·Recall, Validation 요약 지표, Test 지표는 평가·매칭 조건이 다르므로 각각 분리하여 기록한다. 혼동행렬과 AP의 차이를 Test confidence=0.25 때문이라고 단정하지 않는다.

## 9-5. 검증 한계

- **단일 seed 실험:** seed=42에서 얻은 결과이므로 반복 학습에 따른 성능 변동은 확인하지 않았다.
- **작은 평가 규모:** Validation 객체 100개, Test 객체 50개로 작은 성능 차이나 현장 오류율을 확정하기 어렵다.
- **높은 Validation mAP50:** 모든 후보가 높은 값을 보여 현재 데이터만으로 일반화 성능을 충분히 구분하기 어렵다.
- **Test를 참고한 모델 선정:** Test 성능과 속도를 모델 선정에 활용했으므로, 해당 Test를 모델 선택과 독립된 최종 평가로 간주하지 않는다.
- **속도 측정 범위:** Tesla T4에서의 모델 추론 시간이다. 카메라 입력·통신·ROS2 결과 발행을 포함한 전체 지연이나 AMR 실행 장비의 속도를 의미하지 않는다.
- **운영 기능 평가 범위:** 연속 영상의 탐지 끊김, bbox 중심 흔들림, tracking ID 유지 성능은 이번 평가에 포함되지 않았다.
- **Threshold 해석:** Validation F1 최대점 약 0.870을 운영 최적값으로 확정하지 않는다. 이번 Test 결과는 실제 적용한 confidence=0.25에 한정된다.

추가 실험은 수행하지 않으며, 최종 결론은 확보한 원본과 이번 평가 범위에 한정한다.

## 9-6. 기록 결론

**YOLO11n mosaic_05를 이번 비교 실험의 선정 모델로 기록한다.** 60 epoch의 `best.pt`는 이번 Test에서 TP=50, FP=0, FN=0을 기록했고, 9개 실험 중 평균 모델 추론 시간이 가장 짧았다.

평균 추론 시간은 **약 3.93ms**, Test 정답 매칭 예측의 평균 confidence는 **약 0.950**이었다. 다만 이 결과는 소규모 Test와 Tesla T4 측정 조건에 한정되며, 현장 일반화 성능·운영 threshold·tracking 성능까지 검증한 결과로 확대하지 않는다.

# 10. Glossary

- `deterministic=true`  — 같은 조건에서 결과를 재현하려는 설정
    - 가능한 연산에 결정적인 계산 방식을 사용
        - seed : 무작위 선택의 출발점 통일
        - deterministic : 연산 결과의 재현성을 위한 계산 방식
- `amp=true`  — 계산 정밀도를 섞어 사용하는가
    - Automatic Mixed Precision, 자동 혼합 정밀도
    - 학습 계산 방식으로, 연산에 따라 FP16, FP32 등을 활용해 계산 부담과 GPU 메모리 사용을 줄인다.
- `cache=false`  — 이미지를 미리 캐시에 보관하는가
    - 학습 이미지를 RAM이나 디스크 캐시에 미리 모아두는 기능을 끈다.
    - 반복적인 이미지 읽기가 병목일 경우 고려 가능하나, 추가 저장 공간이 필요
- adamW
    - Adam 최적화 알고리즘에 Weight Decay(가중치 감쇠)를 분리 적용한 최적화 알고리즘
        - Momentum과 RMSprop의 아이디어를 결합한 알고리즘
    - Adam 최적화 방법에 가중치 감쇠(weight decay)를 적용한 변형
        - weight decay(가중치 감쇠)
            - 파라미터 자체를 매 스텝별로 조금씩 줄여서 가중치가 지나치게 커지는 것을 규제(L2 규제, Ridge Regression)
    - 과적합을 방지하고 일반화 성능을 향상시키는데 도움을 준다.
        
        $$
        \theta_{t+1}=(1-\alpha \lambda)\theta_t -\frac{\alpha\cdot \hat m_t}{\sqrt {\hat v_t + \epsilon}}
        $$
        
        - lambda(weight_decay, 가중치 감쇠) 일반적으로 0.01
    - Weight Decay를 통해 가중치가 지나치게 커지는 것을 규제하여 과적합을 완화하고 일반화 성능을 향상에 도움을 준다.
        - Adam은 각 파라미터마다 학습률을 다르게 조절하므로, L2 정규화 효과도 파라미터마다 달라지는 문제가 존재한다.
        - AdamW는 업데이트 후 별도로 weight decay를 적용하기 때문에 weight decay 효과를 깔끔하게 분리시켜 적용할 수 있다.