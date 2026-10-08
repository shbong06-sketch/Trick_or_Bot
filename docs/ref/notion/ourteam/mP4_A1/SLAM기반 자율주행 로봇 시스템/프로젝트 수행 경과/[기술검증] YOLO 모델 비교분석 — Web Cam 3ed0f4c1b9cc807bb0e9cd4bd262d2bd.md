# [기술검증] YOLO 모델 비교분석 — Web Cam

관련 이슈·To-do: [기술검증]Vision 모델 활용과 성능 평가 방법 이해 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%ED%99%9C%EC%9A%A9%EA%B3%BC%20%EC%84%B1%EB%8A%A5%20%ED%8F%89%EA%B0%80%20%EB%B0%A9%EB%B2%95%20%EC%9D%B4%ED%95%B4%203ed0f4c1b9cc80c68987d8779a03f04e.md), [기술검증]Vision AI detection with YOLO (웹캠 파트) (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20AI%20detection%20with%20YOLO%20(%EC%9B%B9%EC%BA%A0%20%ED%8C%8C%ED%8A%B8)%203ee0f4c1b9cc802e9bcbe4729d97558f.md)
날짜: 2026년 10월 3일
기록일: 2026년 10월 2일 → 2026년 10월 3일
담당자: 민서 김, 09180_이원호
마지막 수정: 2026년 10월 6일 오전 9:53
분류: 실험
분야: Vision
생성일: 2026년 10월 2일 오후 8:16
작성 상태: 정리 완료

# **0. 요약**

모델 6개 × 학습 증강 설정 4개(기본 1 + 증강 개수 3), 총 24개 실험을 비교하고 고정 웹캠 Detection Alert용 1차 후보를 선정한 기록.

**잠정 선정: YOLO26n (증강 수: ultralytics defalt값).** Test 오류(FP·FN)가 없고, Validation·Test 두 평가 모두에서 mAP50-95가 가장 높았다. 정답 예측의 최저 confidence가 0.936으로, 웹캠 publisher 운용 기준 conf 0.8보다 충분히 높다.

**평가 구분:** Validation 지표와 고정 confidence에서 직접 집계한 Test 지표는 서로 다른 평가다.

# **1. 실험 개요**

| 항목 | 내용 |
| --- | --- |
| 모델 | YOLO26n / YOLO26s / YOLO11n / YOLO11s / YOLOv8n / YOLOv8s · 각 4개 설정 |
| 작업 | 객체 탐지(Detection) · 고정 웹캠으로 경기장 안의 car 탐지 → AMR에 알림(Detection Alert) |
| 출력 | Bounding Box, class ID, confidence |
| 클래스 | 2개 클래스 · ID 0: car(검은 장난감 지프) / ID 1: dummy(검은 LAN-hub 박스) — `data.yaml`의 names 순서 기준 |
| Ultralytics | 8.4.170 |
| 실험 이름 | 실험 1: `<모델>` (기본 증강) / 실험 2: `<모델>_aug0`, `_aug2`, `_aug4` |
| 목표 / 기록 | 탐지 정확도·오탐·미탐·추론 지연·학습 시간 비교
Detection Alert 적용 1차 후보 선정 |
| 최적 모델 대응 시점 | 선정 run은 총 100 epoch 수행 (최대 epoch 도달).
(best.pt epoch 82) |
| 평가 분할 | Train 444장 / Validation 43장 / Test 21장 · 이미지 비중 87.4% / 8.5% / 4.1% |
| 학습 방식 | 각 실험마다 원본 pretrained 모델에서 새로 학습 · seed=0 단일 학습 |
| 핵심 설정 | 최대 100 epoch, patience=20, batch=16, imgsz=640, device=GPU 0, workers=8, pretrained=true, deterministic=true, amp=true, cache=false |

## **1-1. 비교한 학습 설정**

| 실험 | 요청 optimizer | 실제 optimizer | 기록된 초기 LR | 켜는 학습 증강 (개수) |
| --- | --- | --- | --- | --- |
| 기본 (실험 1) | auto | AdamW | 0.001667 | Ultralytics 기본값 (mosaic 1.0, hsv_h/s/v, translate, scale, fliplr) |
| aug0 | auto | AdamW | 0.001667 | 없음 (0) |
| aug2 | auto | AdamW | 0.001667 | mosaic 1.0, hsv_v 0.4 (2) |
| aug4 | auto | AdamW | 0.001667 | mosaic 1.0, hsv_v 0.4, translate 0.1, scale 0.5 (4) |

24개 run 모두 실제 optimizer는 AdamW(lr=0.001667, momentum=0.9)다 (학습 log의 `optimizer:` 줄 24개 확인). aug0/aug2/aug4에서는 위 표의 증강 외에 fliplr·flipud·hsv_h·hsv_s·degrees·shear·perspective·mixup·copy_paste를 모두 0으로 껐다.

실험 2는 켜는 증강의 **개수와 종류가 같이 바뀌는** 설계이므로, 결과는 "증강 개수의 효과"보다 "증강 조합의 효과"로 해석한다. 데이터셋 자체에 Roboflow 증강(3장/원본)이 이미 들어 있으며, 여기서 바꾼 것은 그 위에 학습 중 추가로 거는 Ultralytics 증강이다.

# **2. 최적 모델 성능**

**상세 기록 대상: YOLO26n (기본 증강)의 best.pt.** 아래 표는 별도 Validation 평가 결과이며, 모든 모델 중 각 지표의 최고값을 의미하지 않는다.

| 지표 | Bounding Box · Validation |
| --- | --- |
| Precision | 98.185% |
| Recall | 100.000% |
| mAP50 | 99.473% |
| mAP50-95 | 94.499% |
- Precision: 예측한 객체 중 정답으로 인정된 비율. 위 값은 Validation 요약 값이다.
- Recall: 실제 정답 객체 중 찾아낸 비율. 위 값은 Validation 요약 값이다.
- 학습 중 82 epoch의 Validation mAP50-95는 95.055%로, 별도 Validation(94.499%)과 약 0.56%p 다르다. 두 값은 평가 호출이 다르므로 섞지 않는다.

## **2-1. 고정 기준 Test 성능과 처리 시간**

| 항목 | 내용 |
| --- | --- |
| GT / 예측 / TP | 37 / 37 / 37 (car 21, dummy 16) |
| FP / FN | 0 / 0 |
| Test Precision / Recall / F1 | 100% / 100% / 100% · 이번 Test 집계 기준 |
| Test mAP50 / mAP50-95 | 99.5% / 95.52% · Ultralytics val(split=test) |
| 정답 예측 평균 confidence | 95.73% (최저 car 0.936, dummy 0.941) |
| 운용 conf 0.8 기준 car 미검출 / 오검출 | 0 / 0 |
| 평균 추론 시간 | 3.853 ms/image |
| 추론 시간 표준편차 | 0.172 ms |
| 추론 시간 p95 | 4.143 ms |
| 추론 시간 환산 FPS | 259.5 · 순수 추론 시간의 역수 |
| 평균 전처리 / 후처리 | 0.366 / 0.525 ms |
| 전처리+추론+후처리 평균 합계 | 4.744 ms · 카메라·통신·ROS2 처리 미포함 |

Test는 이미지 21장에 포함된 car 21개·dummy 16개, 정답 객체 37개를 평가한 결과다. 오류 0개는 해당 Test에서의 관측 결과이며 실제 환경에서 오류가 없음을 보장하지 않는다. 추론 환산 FPS는 실제 카메라 또는 ROS2 노드 FPS가 아니다 (웹캠은 30fps, publisher는 10Hz로 동작).

## **2-2. 24개 실험 비교**

![comparison.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/comparison.png)

단위: mAP는 비율(0~1), 시간은 ms/image 및 분. 순서: 실험 1 → 실험 2, 각 실험 안에서 최신 모델부터.

| 모델 | 설정 | Val mAP50-95 | Test mAP50-95 | TP / FP / FN | conf 0.8 car FN | 평균 추론(ms/image) | p95 | 학습 시간(min/image) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| yolo26n | 기본 | **0.9506** | **0.9552** | 37 / 0 / 0 | 0 | 3.853 | 4.143 | 4.49 |
| yolo26s | 기본 | 0.9242 | 0.9067 | 37 / 0 / 0 | 0 | 3.816 | 4.129 | 4.05 |
| yolo11n | 기본 | 0.9164 | 0.9051 | 37 / 0 / 0 | 0 | 3.187 | 3.431 | 1.82 |
| yolo11s | 기본 | 0.9326 | 0.9183 | 37 / 0 / 0 | 0 | 3.498 | 3.665 | 4.87 |
| yolov8n | 기본 | 0.9332 | 0.9335 | 37 / 0 / 0 | 0 | 2.426 | 2.613 | 2.17 |
| yolov8s | 기본 | 0.9364 | 0.9211 | 37 / 0 / 0 | 0 | 3.676 | 3.763 | 5.06 |
| yolo26n | aug0 | 0.9231 | 0.9374 | 37 / 0 / 0 | **2** | 3.793 | 4.091 | 1.67 |
| yolo26n | aug2 | 0.9398 | 0.9451 | 37 / 0 / 0 | 0 | 3.706 | 3.843 | 4.48 |
| yolo26n | aug4 | 0.9384 | 0.9231 | 37 / 0 / 0 | 0 | 3.694 | 3.993 | 2.47 |
| yolo26s | aug0 | 0.9049 | 0.9267 | 37 / 0 / 0 | 0 | 3.809 | 4.057 | 3.23 |
| yolo26s | aug2 | 0.9464 | 0.9398 | 37 / 0 / 0 | 0 | 3.847 | 4.163 | 8.49 |
| yolo26s | aug4 | 0.9453 | 0.9390 | 37 / 0 / 0 | 0 | 3.776 | 4.023 | 8.50 |
| yolo11n | aug0 | 0.9333 | 0.9295 | 37 / 0 / 0 | 0 | 3.292 | 3.486 | 2.87 |
| yolo11n | aug2 | 0.9413 | 0.9312 | 37 / 0 / 0 | 0 | 3.237 | 3.555 | 3.84 |
| yolo11n | aug4 | 0.9238 | 0.9247 | 37 / 0 / 0 | 0 | 3.178 | 3.469 | 1.96 |
| yolo11s | aug0 | 0.9175 | 0.9107 | 37 / 0 / 0 | 0 | 3.518 | 3.700 | 4.13 |
| yolo11s | aug2 | 0.9348 | 0.9338 | 37 / 0 / 0 | 0 | 3.503 | 3.683 | 4.51 |
| yolo11s | aug4 | 0.9223 | 0.9230 | 37 / **9** / 0 | 0 | 3.470 | 3.555 | 3.92 |
| yolov8n | aug0 | 0.9294 | 0.9396 | 37 / 0 / 0 | 0 | 2.473 | 2.682 | 2.30 |
| yolov8n | aug2 | 0.9286 | 0.9300 | 37 / 0 / 0 | 0 | 2.437 | 2.665 | 2.04 |
| yolov8n | aug4 | 0.9450 | 0.8859 | 37 / 0 / 0 | 0 | 2.453 | 2.619 | 2.92 |
| yolov8s | aug0 | 0.9126 | 0.9304 | 37 / **1** / 0 | 0 | 3.648 | 3.728 | 3.43 |
| yolov8s | aug2 | 0.9294 | 0.9073 | 37 / 0 / 0 | 0 | 3.641 | 3.703 | 3.95 |
| yolov8s | aug4 | 0.9426 | 0.9289 | 37 / 0 / 0 | 0 | 3.660 | 3.714 | 7.18 |
- Val mAP50는 24개 run 모두 0.9915~0.9950, Test mAP50은 모두 0.995로 포화되어 비교 지표로 쓰지 않았다.
- yolo11s_aug4의 FP 9개는 모두 conf 0.27~0.42의 car 예측(정답과 IoU 0), yolov8s_aug0의 FP 1개는 conf 0.73의 car 예측이다. 운용 기준 conf 0.8에서는 두 run 모두 FP 0이다.
- yolo26n_aug0은 conf 0.25에서는 오류가 없지만, car 2개의 confidence가 0.71·0.77이라 운용 기준 conf 0.8에서는 미검출이 된다.

**증강 설정별 Val mAP50-95 (실험 2)**

| 모델 | aug0 | aug2 | aug4 |
| --- | --- | --- | --- |
| yolo26n | 0.9231 | 0.9398 | 0.9384 |
| yolo26s | 0.9049 | 0.9464 | 0.9453 |
| yolo11n | 0.9333 | 0.9413 | 0.9238 |
| yolo11s | 0.9175 | 0.9348 | 0.9223 |
| yolov8n | 0.9294 | 0.9286 | 0.9450 |
| yolov8s | 0.9126 | 0.9294 | 0.9426 |
| **평균** | 0.9201 | **0.9367** | 0.9362 |

Validation에서는 aug0이 평균 약 0.017 낮지만, 같은 run들의 Test mAP50-95 평균은 aug0 0.9290 / aug2 0.9312 / aug4 0.9208로 일관된 경향이 없다. aug0 run은 18~56 epoch에서 일찍 최적점이 나와 조기 종료됐다.

### **실험 Hyperparameter 비교**

| 번호 | 모델 | 실험 | optimizer 요청값 | 실제 optimizer | 실제 초기 LR | mosaic | hsv_v | translate | scale | fliplr | hsv_h / hsv_s | close_mosaic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1~6 | 6개 모델 | 기본 | auto | AdamW | 0.001667 | 1.0 | 0.4 | 0.1 | 0.5 | 0.5 | 0.015 / 0.7 | 10 |
| 7~12 | 6개 모델 | aug0 | auto | AdamW | 0.001667 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 | 10 |
| 13~18 | 6개 모델 | aug2 | auto | AdamW | 0.001667 | 1.0 | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 | 10 |
| 19~24 | 6개 모델 | aug4 | auto | AdamW | 0.001667 | 1.0 | 0.4 | 0.1 | 0.5 | 0.0 | 0.0 / 0.0 | 10 |

### **모든 실험의 공통 설정**

| Hyperparameter | 값 |
| --- | --- |
| epochs | 100 |
| patience | 20 |
| batch | 16 |
| imgsz | 640 |
| device | GPU 0 (RTX 4070 Laptop 8GB) |
| seed | 0 (Ultralytics 기본값) |
| workers | 8 |
| pretrained | true |
| deterministic | true |
| amp | true |
| cache | false |
| data | `result_detection/custom_data.yaml` |

Batch size는 16으로 통일했다. 32로 하면 8GB GPU에서 s 모델이 CUDA out of memory를 내고, 이때 Ultralytics가 자동으로 16으로 낮춰 재시도해 run마다 batch가 달라지기 때문이다. 24개 run의 `args.yaml`에서 batch=16을 확인했다. 배치 크기별 비교 실험은 수행하지 않았으므로, 16을 최적값으로 주장하지 않는다.

## **2-3. 선정 판단 흐름**

1. Detection Alert에서는 **car 미탐(알림 누락)과 car 오탐(잘못된 알림)**을 먼저 확인한다. AMR이 출동하지 않거나 엉뚱한 위치로 출동하는 데 직접 영향을 주기 때문이다.
2. 동일한 Test 조건(conf 0.25)에서 FP=0, FN=0인 22개 조합을 남긴다 (yolo11s_aug4 FP 9, yolov8s_aug0 FP 1 제외).
3. 웹캠 publisher가 실제로 쓰는 **conf 0.8**에서 다시 확인한다. yolo26n_aug0은 car 2개를 놓쳐 제외 → 21개 후보.
4. 처리 시간은 21개 모두 전처리+추론+후처리 3.3~4.8 ms로, 웹캠 프레임 간격(33 ms)의 15% 이하다. **이번 과제에서는 속도가 우열을 가르는 요인이 아니다.**
5. 다음으로 box 위치 정밀도(mAP50-95)를 본다. 검출 box 중심이 AMR이 갈 목표 위치 계산에 쓰이기 때문이다. YOLO26n(기본)은 Validation 0.9506, Test 0.9552로 **두 평가 모두 1위**다. Validation 2위 yolo26s_aug2(0.9464)와 차이는 약 0.4%p로 크지 않지만, 두 평가 모두 1위인 run은 YOLO26n뿐이다.
6. 평가 간 순위가 뒤집히는 run이 있다. yolov8n_aug4는 Validation 0.9450(4위)이지만 Test 0.8859(24위)다. 따라서 Validation 하나만으로 고르지 않는다.
7. 정답 예측 confidence는 주 지표로 쓰지 않지만, 운용 conf 0.8에서의 여유를 보여준다. YOLO26n의 Test 정답 예측 최저 confidence는 0.936이다. 반면 현재 웹캠 publisher에 적용된 yolo26s(기본)는 평균 0.867로 24개 중 가장 낮다. 708초 실측의 car 검출률(약 95.5%)이 이 낮은 confidence와 관련 있을 수 있으며, 같은 실측 영상으로 확인이 필요하다.
8. 실제 웹캠의 거리·가림·뒷모습·화면 가장자리 장면(708초 실측 rosbag)에서 탐지 연속성, 오탐 빈도, 전체 처리 지연을 비교하여 최종 확정한다.

**추가 검증 후보:** YOLO26s aug2(Validation 2위, Test 0.940), YOLOv8n 기본(추론 2.43 ms로 가장 빠르고 Val·Test 모두 0.933). Test를 보고 선정한 후보이므로 최종 검증에는 별도의 새 영상·데이터를 사용한다.

# **3. 데이터셋과 클래스**

## **3-1. 라벨 분포**

클래스 순서는 `data.yaml`의 names(`['car', 'dummy']`)로 확인했다.

| ID | 클래스 | Train | Validation | Test | 전체 | 전체 비중 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | car | 369 | 36 | 21 | 426 | 50.00% |
| 1 | dummy | 375 | 35 | 16 | 426 | 50.00% |
| **합계** | car & dummy | **744** | **71** | **37** | **852** | **100%** |

![labels.jpg](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/labels.jpg)

## **3-2. 평가 데이터와 분할 확인**

| 분할 | 이미지 수 | GT 객체 수 | 이미지 비중 |
| --- | --- | --- | --- |
| train | 444 | 744 | 87.4% |
| val | 43 | 71 | 8.5% |
| test | 21 | 37 | 4.1% |
| 합계 | 508 | 852 | 100% |
- 웹캠(1920x1080)으로 경기장 안의 car·dummy를 촬영한 원본 212장 → Roboflow 라벨링 → 전처리 640x640(Fill, center crop) → train만 증강 3배(원본 148장 × 3 = 444장).
- Roboflow 증강 (README 기준): 좌우 반전 50%, 회전 ±5°, 밝기 ±15%, Gaussian blur 0~1px.
- 전체 이미지당 평균 객체 수는 약 1.7개다.
- **같은 촬영 시퀀스의 유사 프레임이 분할에 섞여 있다.** 파일 이름의 촬영 시각 기준으로 Validation 43장 중 35장, Test 21장 중 16장이 2초 이내에 찍힌 train 이미지를 갖는다. Validation·Test 점수가 실제 일반화 성능보다 높게 나올 수 있다.
- 데이터셋: `rokey_ws/src/wc/data_wc/rokey_mp4_a1.v2i.yolo26` (Roboflow `rokey_mp4_a1` v2)
- 실제 웹캠의 새로운 촬영(다른 날·조명)으로 추가 검증한다.

# **4. 학습 옵션**

## **4-1. 기본 학습·실행**

| 옵션 | 값 | 의미 |
| --- | --- | --- |
| task / mode | Detection / train | 객체 탐지 학습 |
| epochs | 100 · 실제 수행 100 | 목표 최대 epoch와 실제 수행량 구분 (선정 run은 최대치까지 수행) |
| patience | 20 | 최적 점수 개선 대기 설정 |
| batch | 16 | 학습 배치 크기 |
| imgsz | 640 | 입력 크기 기준 |
| device | '' → GPU 0 | 자동 선택 · RTX 4070 Laptop GPU |
| workers | 8 | 데이터 로딩 작업자 |
| pretrained | true | COCO 사전학습 가중치 사용 |
| resume | false | 매 실험 원본 pretrained 모델로 시작 |
| amp | true | 학습 자동 혼합 정밀도 |
| cache | false | 학습 이미지 캐시 비활성화 |
| fraction | 1.0 | train 데이터 전체 사용 |
| seed / deterministic | 0 / true | 재현성 관련 설정 · seed 반복 실험 없음 |
| single_cls | false | car·dummy 두 클래스 유지 |
| rect | false | 직사각형 배치 학습 비활성화 |
| multi_scale | 0.0 | 멀티스케일 학습 비활성화 |
| freeze | None | 레이어 동결 범위를 지정하지 않음 |
| compile | false | 모델 컴파일 비활성화 |
| time | None | 시간 기반 종료 한도 미지정 |

## **4-2. 경로**

| 항목 | 내용 |
| --- | --- |
| model / resume | yolo26n.pt · resume=false · 각 실험 원본 pretrained에서 새로 학습 |
| data | `result_detection/custom_data.yaml` (Roboflow data.yaml을 절대 경로로 변환) |
| project | `result_detection/exp1_models` |
| name | yolo26n |
| save_dir | `result_detection/exp1_models/yolo26n` |
| 평가 가중치 | `result_detection/exp1_models/yolo26n/weights/best.pt` |

## **4-3. 최적화·학습률**

| 옵션 | 설정값 | 의미 |
| --- | --- | --- |
| `optimizer` | `auto` → **실제 AdamW** | optimizer 자동 선택 |
| `lr0` | `0.01` → **실제 초기 LR 0.001667** | `auto`에서 설정값을 무시하고 자동 결정 |
| `lrf` | `0.01` | 최종 학습률의 초기 학습률 대비 비율 |
| `momentum` | `0.937` → **자동 선택 log 0.9** | AdamW에서는 beta1에 대응 |
| `weight_decay` | `0.0005` | 가중치 감쇠 설정 · 파라미터 그룹별 적용은 다름 |
| `warmup_epochs` | `3.0` | 학습 초반 워밍업 기간 설정 |
| `warmup_momentum` | `0.8` | 워밍업 시작 모멘텀 설정 |
| `warmup_bias_lr` | `0.1` | bias 워밍업 학습률 설정 |
| `cos_lr` | `false` | 코사인 학습률 스케줄 비활성화 |
| `nbs` | `64` | 배치 관련 내부 스케일링 기준 |

## **4-4. 데이터 증강**

| 옵션 | 적용값 | 의미 |
| --- | --- | --- |
| `hsv_h / hsv_s / hsv_v` | `0.015 / 0.7 / 0.4` | 색조·채도·밝기 변화 범위 |
| `translate` | `0.1` | 이미지 크기를 기준으로 이동 범위 설정 |
| `scale` | `0.5` | 크기 변화 범위 설정 |
| `fliplr` | `0.5` | 좌우 반전 확률 50% |
| `flipud` | `0.0` | 상하 반전 비활성화 |
| `degrees / shear / perspective` | `0.0 / 0.0 / 0.0` | 회전·기울임·원근 증강 비활성화 |
| `bgr` | `0.0` | RGB↔BGR 채널 순서 변경 비활성화 |
| **`mosaic`** | **`1.0`** | Mosaic 적용 확률 100% |
| `close_mosaic` | `10` | 마지막 10 epoch에 Mosaic 종료 |
| `mixup / cutmix / copy_paste` | `0.0 / 0.0 / 0.0` | 비활성화 |
| `copy_paste_mode` | `flip` | 방식 설정이며, 적용 확률이 0이므로 비활성 상태 |

선정 run은 Ultralytics 기본 증강 그대로다. Roboflow에서 이미 좌우 반전·회전·밝기·blur를 적용한 데이터 위에 학습 증강이 한 번 더 걸린다.

## **4-5. 검증·저장·기타**

| 옵션 | 확인된 값 | 의미 |
| --- | --- | --- |
| `val / split` | true / val | 학습 중 Validation 수행 |
| `plots / save` | true / true | 학습 그래프·모델 가중치 저장 |
| `save_period` | -1 | 주기적인 별도 epoch 체크포인트 저장 비활성화 |
| `conf` | 학습 None / 별도 Val 0.001 / Test 0.25 / 운용 0.8 | 단계별 confidence 설정 구분 |
| `iou` | 0.7 | 예측 후처리에 전달한 IoU 설정 |
| `MATCH_IOU` | 0.5 | Test 정답 인정용 매칭 기준 |
| `max_det` | 300 | 이미지당 최대 검출 수 설정 |
| `save_json` | false | 내장 평가 결과 JSON 내보내기 비활성화 |
| `augment` | false | 증강 추론 비활성화 |
| 평가 `batch` | Val 16 / Test 집계·속도 1 | 평가 배치 크기 |
| 평가 `device / half` | GPU 0 / false | 반정밀도 추론 비활성화 |

# **5. 학습 진행과 best.pt 선택**

## **5-1. 주요 epoch 성능**

YOLO26n 기본 증강 실험은 최대 100 epoch로 설정했으며, 실제로도 100 epoch까지 수행했다. 아래는 학습 중 Validation 지표이며, 단위는 %다.

| Epoch | Precision | Recall | Box mAP50 | Box mAP50-95 |
| --- | --- | --- | --- | --- |
| 1 | 0.136 | 50.000 | 26.586 | 21.307 |
| 10 | 98.314 | 100.000 | 98.676 | 89.153 |
| 20 | 98.183 | 100.000 | 99.432 | 88.359 |
| 30 | 99.329 | 100.000 | 99.500 | 91.326 |
| 40 | 99.601 | 98.607 | 99.473 | 91.768 |
| 50 | 99.542 | 100.000 | 99.500 | 92.660 |
| 60 | 98.063 | 100.000 | 99.473 | 91.441 |
| 70 | 99.723 | 99.643 | 99.500 | 94.461 |
| 80 | 98.169 | 100.000 | 99.473 | 93.229 |
| **82 · Best** | **98.184** | **100.000** | **99.473** | **95.055** |
| 90 | 98.186 | 100.000 | 99.473 | 94.017 |
| **100 · 마지막** | **98.137** | **100.000** | **99.473** | **94.475** |

10 epoch에서 mAP50가 98.676%에 도달했고, 이후 높은 수준을 유지했다. mAP50은 일찍 포화됐지만 mAP50-95는 20 epoch 88.4% → 82 epoch 95.1%로 계속 올라, 더 엄격한 IoU 기준의 box 위치 정밀도가 학습 후반까지 개선됐다.

## **5-2. 지표별 최고값**

| 지표 | 최고값 | Epoch |
| --- | --- | --- |
| Precision(B) | 99.804% | 46 |
| Recall(B) | 100.000% | 4, 10, 15, 18~26 등 59개 epoch (75~100 연속) |
| mAP50(B) | 99.500% | 25, 26, 30, 32, 33, 35, 36, 39, 48~52, 64~67, 70~72 |
| mAP50-95(B) | **95.055%** | **82** |

24개 모델 중 Validation 최고값은 선정 모델의 학습 중 epoch별 최고값과 다른 개념이다.

## **5-3. 최적 모델이 82 epoch인 근거**

Ultralytics 8.4.170의 best.pt 선정 기준(fitness)은 **mAP50-95** 하나다 (`metrics.py`: 가중치 `[P, R, mAP50, mAP50-95] = [0, 0, 0, 1]`). `results.csv`에서 **82 epoch의 mAP50-95가 전체 학습 중 최고값인 95.055%**로 확인된다. 선정 run은 최대 epoch에 도달해 EarlyStopping log가 없으므로 CSV로 확인했다. (EarlyStopping이 걸린 다른 run은 log의 "Best results observed at epoch N"과 CSV 기준이 일치함을 확인했다.)

100 epoch의 마지막 모델은 mAP50-95가 94.475%로 최적 모델보다 0.580%p 낮다. 따라서 마지막 모델과 최적 모델을 구분하고, 후속 평가에는 82 epoch에서 선정된 best.pt를 사용했다.

## **5-4. 종료 시점과 시간**

| 항목 | 결과 |
| --- | --- |
| 최대 학습 설정 | 100 epoch |
| 최적 모델 선정 | **82 epoch** |
| 실제 학습 종료 | **100 epoch** |
| 종료 사유 | 최대 epoch 도달 (82 이후 18 epoch 동안 개선이 없었지만 patience 20에 못 미침) |
| 조기 종료 설정 | `patience=20` |
| CSV 마지막 누적 시간 | 269.388초 · 약 4.49분 |

최대 epoch에 도달했으므로, epoch를 늘리면 성능이 조금 더 오를 여지가 있다. 24개 run 중 6개가 100 epoch까지 수행됐다.

# **6. 클래스별 AP50**

| 클래스 | 정답 객체 수 | Box AP50 | Box AP50-95 | 해석 |
| --- | --- | --- | --- | --- |
| car | 36 | 99.45% | **92.78%** | dummy보다 엄격한 위치 기준에서 성능이 낮음 |
| dummy | 35 | 99.50% | **96.22%** | 엄격한 IoU 기준에서도 높은 성능 |
| 전체 | 71 | 99.47% | 94.50% | 두 클래스 평균 |

전체 mAP50은 car·dummy 두 클래스의 평균이며, car 클래스 AP50과 구분한다. car는 방향(앞·옆·뒷모습)에 따라 모양이 크게 바뀌고, dummy는 단순한 직육면체라 box 경계가 더 일정한 것으로 보인다.

# **7. 혼동행렬 상세 분석**

## **7-1. 분석 자료와 평가 조건**

선정 모델의 별도 Validation 결과와 Test 결과를 구분한다.

| 구분 | 평가 대상 | 평가 조건 |
| --- | --- | --- |
| Validation 혼동행렬 | 43장 · 정답 객체 71개 | Ultralytics Validation에서 생성 |
| Validation 요약 | 동일 Validation 분할 | 검증 호출 `conf=0.001`, NMS `iou=0.7` |
| Test 결과 | 21장 · 정답 객체 37개 | `conf=0.25`, NMS IoU=0.7, 정답 매칭 IoU≥0.5 |

검증 호출의 conf와 NMS IoU를 혼동행렬의 내부 매칭 기준과 동일하게 간주하지 않는다.

## **7-2. 축과 background 의미**

| 위치 | 의미 |
| --- | --- |
| 가로축 True | 실제 정답 클래스 |
| 세로축 Predicted | 예측 클래스 |
| 대각선 | 정답과 올바르게 매칭된 검출 |
| 클래스 사이 비대각선 | 다른 클래스 예측으로 매칭된 오류 |
| 맨 아래 background 행 | 매칭되지 않은 실제 물체 · FN |
| 맨 오른쪽 background 열 | 정답에 매칭되지 않은 예측 · FP |

background 열에는 배경 오인식뿐 아니라 중복 검출, bbox 위치 불일치, 라벨 누락 등이 포함될 수 있다.

## **7-3. Validation 개수 행렬**

![confusion_matrix.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/confusion_matrix.png)

- 실제 car 36개는 36개 모두 car로 예측했다.
- 실제 dummy 35개 중 31개를 dummy, 4개를 car로 예측했다.
- background 행은 비어 있다. 매칭되지 않은 정답(FN)은 0개다.
- GT와 매칭되지 않은 예측은 car 46개, dummy 25개로 총 71개다.
- 대각선 매칭은 67개, 클래스 간 오분류 매칭은 4개다.

## **7-4. 혼동행렬에서 계산한 클래스별 지표**

| 클래스 | 정답 수 | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| car | 36 | 36 | 4+46 = **50** | 0 | **41.86%** | **100.00%** |
| dummy | 35 | 31 | 0+25 = **25** | 4 | **55.36%** | **88.57%** |
| **합계 / Micro** | **71** | **67** | **75** | **4** | **47.18%** | **94.37%** |

이 지표는 해당 혼동행렬의 매칭 결과에서 계산한 값이며, Validation 요약의 Precision·Recall 또는 Test 지표와 구분한다.

## **7-5. 정규화 행렬 해석**

![confusion_matrix_normalized.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/confusion_matrix_normalized.png)

| 실제 클래스 | 올바른 클래스 매칭 | 다른 클래스 매칭 | 매칭되지 않은 정답 |
| --- | --- | --- | --- |
| car | 100% | 0% | 0% |
| dummy | 89% | car로 11% | 0% |

background 열의 약 0.65 / 0.35는 정답과 매칭되지 않은 예측 71개 중 car가 약 65%, dummy가 약 35%라는 의미다. 전체 배경의 65%를 car로 잘못 인식했다는 뜻은 아니다.

## **7-6. Test 결과**

| 클래스 | Test 정답 수 | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| car | 21 | 21 | 0 | 0 | 100% | 100% |
| dummy | 16 | 16 | 0 | 0 | 100% | 100% |
| **합계 / Micro** | **37** | **37** | **0** | **0** | **100%** | **100%** |

평가 기준은 confidence=0.25, 동일 클래스의 정답과 IoU≥0.5인 일대일 매칭이다. 운용 기준 conf 0.8로 높여도 결과가 같다 (정답 예측 최저 confidence 0.936).

이번 Test에서는 오류가 관찰되지 않았다. 다만 정답이 37개이고 Test 21장 중 16장이 train과 2초 이내 연속 촬영이므로, 실제 운영 환경에서도 오류가 없다고 일반화하지 않는다.

## **7-7. 높은 AP와 혼동행렬의 차이**

Validation 요약은 Precision 약 **98.19%**, Recall **100%**, mAP50 약 **99.47%**로 높지만, 혼동행렬에서 계산한 지표(Precision 47.18%)는 낮다.

AP는 confidence 순위와 클래스별 정답 매칭을 이용해 계산하며, 혼동행렬은 별도의 매칭 절차로 집계한다. 따라서 동일한 결과에서도 두 지표가 달라질 수 있다.

선정 모델은 Validation AP와 이번 Test 평가에서 높은 성능을 보였다. 반면 Validation 혼동행렬에는 미매칭 예측 71개와 dummy→car 매칭 4개가 나타났다. 평가·매칭 방식의 차이를 고려해 두 결과를 분리하여 보고하며, 낮은 confidence threshold만으로 차이의 원인을 단정하지 않는다. Detection Alert에서 중요한 **실제 car의 미매칭(FN)은 혼동행렬·Test 모두 0개**다.

# **8. 그래프 이미지별 분석**

본 절은 `selected/yolo26n/validation/` 폴더의 Box 그래프와 학습 폴더의 `results.png`, `results.csv`를 기준으로 작성한다.

## **8-1. Box F1–Confidence**

![BoxF1_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/BoxF1_curve.png)

그래프 표시값은 **전체 클래스 F1 약 0.99, confidence 약 0.677**이다.

- confidence 약 0.05~0.90의 넓은 구간에서 F1이 0.97 이상으로 평평하다.
- car 곡선은 0.8 부근과 0.87 이후에 조금씩 내려가고, dummy는 약 0.94까지 유지되다 급락한다.
- 0.90 이후에는 Recall 감소와 함께 F1이 급락한다.

**해석:** Validation에서 Precision과 Recall의 균형이 높은 구간이 넓다. 운용 conf 0.8은 이 평평한 구간 안에 있다. 0.677은 Validation에서 선택된 값이며, 운용 threshold로 확정하지 않는다.

## **8-2. Box Precision–Confidence**

![BoxP_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/BoxP_curve.png)

- confidence가 증가하면서 Precision이 전반적으로 높아진다.
- 그래프 표시값은 **Precision 1.00 at confidence 0.992**다.
- 낮은 confidence 구간에서는 car의 Precision이 dummy보다 낮게 나타난다 (dummy → car 오분류 4개, car 미매칭 예측 46개와 일치).

**해석:** 높은 threshold는 오탐을 줄일 수 있지만 검출 수와 Recall도 감소시킬 수 있다. **Precision=1.00인 지점을 최적 운영 threshold로 바로 선택하지 않는다.**

## **8-3. Box Precision–Recall**

![BoxPR_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/BoxPR_curve.png)

| 구분 | AP50 |
| --- | --- |
| car | 0.994 |
| dummy | 0.995 |
| 전체 mAP50 | 0.995 |

두 클래스의 곡선은 오른쪽 위에 가깝게 위치한다. Validation에서 높은 Recall까지 높은 Precision을 유지하는 결과다. 전체 그래프 값 0.995는 반올림 표시이며, 별도 Validation의 mAP50은 **0.99473**이다. 이는 **IoU=0.5에서의 AP**로, 더 엄격한 위치 정확도를 평가하는 mAP50-95와 구분한다.

## **8-4. Box Recall–Confidence**

![BoxR_curve.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/BoxR_curve.png)

- confidence 약 0.7까지 두 클래스 모두 Recall 1.00이다.
- **car는 약 0.73부터 Recall이 내려가기 시작해 conf 0.8 부근에서 약 0.97**(36개 중 1개 탈락)이다. dummy는 약 0.94까지 1.00을 유지한다.
- 0.9 이후에는 두 클래스 모두 급격히 감소한다.

**해석:** 운용 conf 0.8에서 car가 dummy보다 먼저 탈락한다. car 알림 누락을 줄이려면 conf를 0.7~0.75로 낮추는 것도 검토할 수 있지만, 벽 오검출(최대 0.79, 708초 실측)과 함께 판단해야 한다. Recall 그래프와 Precision 그래프를 함께 보아야 한다.

## **8-5. Confusion Matrix · 개수**

![confusion_matrix.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/confusion_matrix%201.png)

정답 71개 중 대각선 매칭은 67개, 다른 클래스 매칭은 4개(dummy → car)다. 정답과 매칭되지 않은 예측은 71개이며, 그중 car가 46개로 많다.

**해석:** 이 그림의 평가·매칭 조건에서는 car 예측의 미매칭 수가 크게 나타난다. 이를 Test conf=0.25에서의 오류 수로 해석하지 않는다. 상세 계산은 7번에 기록한다.

## **8-6. Confusion Matrix · 정규화**

![confusion_matrix_normalized.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/confusion_matrix_normalized%201.png)

car의 대각선 비율은 100%, dummy는 89%다. dummy→car 매칭 비율 11%가 있고 car→dummy는 0%다.

background 열의 65%·35%는 **미매칭 예측의 클래스 구성비**다. 정규화 그림은 상대적인 비율을 보여주므로, 오류 규모는 개수 행렬과 함께 확인한다.

## **8-7. Epoch별 학습·검증 추이**

![results.png](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5D%20YOLO%20%EB%AA%A8%EB%8D%B8%20%EB%B9%84%EA%B5%90%EB%B6%84%EC%84%9D%20%E2%80%94%20Web%20Cam/results.png)

| Epoch | Box mAP50 | Box mAP50-95 |
| --- | --- | --- |
| 20 | 99.432% | 88.359% |
| 50 | 99.500% | 92.660% |
| **82 · best** | **99.473%** | **95.055%** |
| 100 · 마지막 | 99.473% | 94.475% |
- 학습 초반 10 epoch 안에 Precision·Recall·mAP50이 높은 수준으로 안정된다.
- mAP50은 일찍 포화되고, 이후에는 mAP50-95에서 차이가 나타난다.
- **최적 epoch는 82**, 종료 epoch는 100이다.
- 마지막 epoch의 mAP50은 같지만, mAP50-95는 최적 epoch보다 낮다.

**해석:** mAP50 하나만으로 마지막 모델이 더 좋다고 판단하지 않는다. 이번 기록에서는 82 epoch의 `best.pt`를 선정 모델로 사용한다.

## **8-8. results.png 손실 항목 상세**

YOLO26은 DFL을 쓰지 않아 `dfl_loss` 대신 `l1_loss`가 기록된다.

| 손실 항목 | 의미 | Epoch 20 | Epoch 82 · best | Epoch 100 |
| --- | --- | --- | --- | --- |
| train/box_loss | 학습 데이터의 Box 위치 회귀 손실 | 0.69437 | 0.43589 | 0.35522 |
| train/cls_loss | 학습 데이터의 클래스 예측 손실 | 0.49796 | 0.20416 | 0.16776 |
| train/l1_loss | 학습 데이터의 Box 좌표 L1 손실 | 0.00451 | 0.00249 | 0.00269 |
| val/box_loss | 검증 데이터의 Box 위치 회귀 손실 | 0.57615 | 0.36371 | 0.33598 |
| val/cls_loss | 검증 데이터의 클래스 예측 손실 | 0.41263 | 0.17554 | 0.18790 |
| val/l1_loss | 검증 데이터의 Box 좌표 L1 손실 | 0.00449 | 0.00262 | 0.00235 |

학습·검증 손실 모두 전반적으로 감소한다. val/cls_loss가 82 → 100 epoch에서 0.176 → 0.188로 조금 오르지만, **검증 손실이 지속적으로 상승하는 뚜렷한 과적합 패턴은 관찰되지 않는다.** 손실 감소가 매 epoch의 AP 향상을 보장하지는 않으므로, 모델 선정은 검증 지표와 함께 판단한다.

# **9. 원본 설정 및 기록**

## **9-1. 실행 환경과 데이터셋**

| 항목 | 확인 내용 |
| --- | --- |
| Ultralytics | 8.4.170 |
| PyTorch | 2.14.1+cu130 |
| Python | 3.12.3 (`~/venvs/rokey_venv`) |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU (8GB) |
| 클래스 순서 | 0: car / 1: dummy |
| 데이터셋 규모 | 이미지 508장 · 객체 852개 |
| 데이터 분할 | Train 444장·744개 / Val 43장·71개 / Test 21장·37개 |
| 클래스별 객체 수 | Train: car 369·dummy 375 / Val: car 36·dummy 35 / Test: car 21·dummy 16 |
| 실험 구성 | 6개 모델 × 4개 설정(기본, aug0, aug2, aug4) = 24개 실험 |
| 재현성 설정 | seed=0, deterministic=true |

모든 실험에 최대 100 epoch, patience=20, batch=16, imgsz=640을 공통 적용했다. 원본 수치는 정밀도를 유지하고, 본문 표시값만 반올림했다.

## **9-2. 확보한 원본과 확인 사항**

모두 `rokey_ws/src/wc/03_YOLO_v8_object_detection/` 기준이다.

| 자료 | 확인 사항 |
| --- | --- |
| `2_4_a_yolov8_obj_det_ak _a1.ipynb` | 학습·검증·Test 집계·속도 측정 절차 전체, 정답 매칭 로직 |
| `result_detection/custom_data.yaml` | 데이터 경로·클래스 |
| `result_detection/log/log_261003_175840.txt` | 24개 run 학습 log (실제 optimizer, EarlyStopping best epoch) |
| `result_detection/compare_models.csv / .png` | 실험 1 Validation 비교표 |
| `result_detection/compare_aug.csv`, `compare_aug_map.csv / .png` | 실험 2 Validation 비교표 |
| `result_detection/test_eval/final_comparison.csv` | 24개 run의 학습·Validation·Test·속도 요약 |
| `result_detection/test_eval/test_detections.csv` | 예측별 class·confidence·정답 매칭 여부 |
| `result_detection/test_eval/speed_samples.csv` | 개별 속도 측정값 (run당 63개) |
| `result_detection/test_eval/comparison.png` | 24개 run 비교 그래프 |
| `result_detection/exp1_models/yolo26n/` | 선정 run의 `args.yaml`, `results.csv`, `results.png`, `weights/best.pt` |
| `result_detection/selected/yolo26n/validation/` | 별도 Validation의 혼동행렬·Box 곡선 |
| `result_detection/selected/yolo26n/per_class_ap.csv` | 클래스별 P·R·AP50·AP50-95 |

첫 Test 이미지로 **5회 워밍업**, 전체 Test 이미지에 대해 **3회 속도 측정**을 수행했다. Test 이미지 21장 기준 속도 표본은 run당 63개다.

## **9-3. 요청 설정과 실제 적용값**

| 실험 | optimizer 요청값 | 실제 optimizer | 실제 초기 학습률 | 켜는 학습 증강 |
| --- | --- | --- | --- | --- |
| 기본 | auto | AdamW | 0.001667 | Ultralytics 기본값 |
| aug0 | auto | AdamW | 0.001667 | 없음 |
| aug2 | auto | AdamW | 0.001667 | mosaic, hsv_v |
| aug4 | auto | AdamW | 0.001667 | mosaic, hsv_v, translate, scale |

모든 실험은 `lr0`를 직접 지정하지 않았으며, 자동 선택된 실제 초기 학습률은 0.001667이다. 따라서 실험 간 차이는 **모델 구조와 학습 증강 설정**에서만 나온다.

## **9-4. 평가 자료 구분과 기록 기준**

| 구분 | 기록 기준 |
| --- | --- |
| 최적 모델 | 82 epoch의 `best.pt` |
| 마지막 학습 모델 | 100 epoch의 마지막 checkpoint (`last.pt`) |
| Validation 요약 | 별도 Validation (`selected/yolo26n/validation`, conf 0.001) |
| Validation 혼동행렬·곡선 | `selected/yolo26n/validation/` 하위 파일 |
| Epoch별 학습 추이 | 학습 폴더의 `results.csv` / `results.png` |
| Test 성능 | confidence=0.25, NMS IoU=0.7, 동일 클래스 정답 매칭 IoU≥0.5 (운용 conf 0.8 참고 집계 포함) |
| Validation F1 선택점 | confidence 약 0.677. Test에는 적용하지 않음 |

학습 폴더와 `validation` 폴더에 동일한 이름의 혼동행렬이 존재하며, 수치도 다를 수 있다. 본문 7·8번은 별도 `validation` 폴더를 기준으로 작성하고, 두 파일의 수치를 혼합하지 않는다.

## **9-5. 검증 한계**

- **단일 seed 실험:** seed=0에서 얻은 결과이므로 반복 학습에 따른 성능 변동은 확인하지 않았다. Validation·Test 순위가 뒤집힌 run(yolov8n_aug4 등)이 있어 변동 폭이 작지 않을 수 있다.
- **작은 평가 규모:** Validation 객체 71개, Test 객체 37개로 작은 성능 차이나 현장 오류율을 확정하기 어렵다.
- **분할 간 유사 프레임:** Validation 43장 중 35장, Test 21장 중 16장이 train과 2초 이내 연속 촬영이다. 점수가 실제보다 높게 나올 수 있다.
- **높은 Validation mAP50:** 모든 후보가 0.99 이상이라 현재 데이터만으로 일반화 성능을 충분히 구분하기 어렵다.
- **Test를 참고한 모델 선정:** Test 성능과 속도를 모델 선정에 활용했으므로, 해당 Test를 모델 선택과 독립된 최종 평가로 간주하지 않는다.
- **속도 측정 범위:** RTX 4070 Laptop GPU에서의 모델 처리 시간이다. 카메라 입력·center crop·ROS2 결과 발행을 포함한 전체 지연은 포함하지 않는다.
- **운영 기능 평가 범위:** 연속 영상의 탐지 끊김, bbox 중심 흔들림, tracking ID 유지 성능은 이번 평가에 포함되지 않았다.
- **Threshold 해석:** Validation F1 최대점 약 0.677을 운영 최적값으로 확정하지 않는다. 이번 Test 결과는 conf 0.25와 운용 conf 0.8에 한정된다.

## **9-6. 기록 결론**

**YOLO26n(기본 증강)을 이번 비교 실험의 선정 모델로 기록한다.** 82 epoch의 `best.pt`는 이번 Test에서 TP=37, FP=0, FN=0을 기록했고, 24개 실험 중 Validation mAP50-95(0.9506)와 Test mAP50-95(0.9552)가 모두 가장 높았다.

평균 모델 처리 시간은 **약 4.74ms**(추론 3.85ms), Test 정답 매칭 예측의 평균 confidence는 **약 0.957**(최저 0.936)이었다. 다만 이 결과는 소규모·유사 프레임이 섞인 Test와 RTX 4070 Laptop 측정 조건에 한정되며, 현장 일반화 성능·운영 threshold·tracking 성능까지 검증한 결과로 확대하지 않는다. 다음 단계로 708초 실측 영상에서 현재 적용 모델(yolo26s)과 비교한다.

# **10. Glossary**

- `mAP50-95` — box 위치까지 엄격하게 보는 정확도
    - IoU 기준을 0.50부터 0.95까지 0.05 간격으로 바꿔 가며 구한 AP의 평균
    - mAP50(IoU 0.5 한 기준)보다 box 경계가 정답과 얼마나 정확히 겹치는지를 더 잘 보여준다
    - Ultralytics는 이 값을 best.pt 선정 기준(fitness)으로 쓴다
- `IoU` (Intersection over Union) — 예측 box와 정답 box가 겹치는 정도
    - 두 box의 교집합 넓이 ÷ 합집합 넓이 (0~1)
- `conf` (confidence) — 모델이 그 box를 해당 class라고 믿는 정도
    - conf threshold보다 낮은 예측은 버린다. 웹캠 publisher는 0.8을 쓴다
- `NMS` (Non-Maximum Suppression) — 같은 물체에 겹친 여러 예측 중 가장 확신이 높은 것만 남기는 후처리
    - YOLO26은 구조상 NMS 없이 끝까지 학습되는(end-to-end) 모델이다
- `mosaic` — 학습 이미지 4장을 잘라 한 장으로 붙이는 증강
    - 물체가 다양한 위치·크기로 보이게 해 작은 물체·가장자리 물체 학습에 도움이 된다
    - `close_mosaic=10`: 마지막 10 epoch는 원래 이미지로 학습해 실제 분포에 맞춘다
- `fitness` — Ultralytics가 best.pt를 고르는 점수
    - 8.4.170 기준 `mAP50-95` 하나 (P·R·mAP50 가중치 0)
- `deterministic=true` — 같은 조건에서 결과를 재현하려는 설정
    - seed : 무작위 선택의 출발점 통일
    - deterministic : 연산 결과의 재현성을 위한 계산 방식
- `amp=true` — Automatic Mixed Precision, 자동 혼합 정밀도
    - 연산에 따라 FP16, FP32 등을 섞어 계산 부담과 GPU 메모리 사용을 줄인다
- `AdamW` — Adam에 Weight Decay(가중치 감쇠)를 분리 적용한 최적화 알고리즘
    - `optimizer=auto`에서 학습 iteration 수가 적으면 Ultralytics가 자동으로 고른다
    - 초기 학습률은 class 수로 자동 계산: `lr = 0.002 × 5 / (4 + nc)` = 0.002 × 5 / 6 ≈ 0.001667