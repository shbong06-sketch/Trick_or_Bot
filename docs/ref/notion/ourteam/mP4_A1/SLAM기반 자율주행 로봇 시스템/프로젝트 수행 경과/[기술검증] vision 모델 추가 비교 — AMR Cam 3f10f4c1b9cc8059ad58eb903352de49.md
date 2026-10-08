# [기술검증] vision 모델 추가 비교 — AMR Cam

날짜: 2026년 10월 5일
기록일: 2026년 10월 6일
담당자: 봉승현
마지막 수정: 2026년 10월 6일 오전 10:12
분류: 실험
분야: Vision
생성일: 2026년 10월 6일 오전 10:04
작성 상태: 작성 중

# RT-DETR-L 실험 결과

```
## 데이터셋

- train: 이미지 175장, 객체 349개
- valid: 이미지 50장, 객체 100개
- test: 이미지 25장, 객체 50개

## 실험 조건

- 완료 모델: 1 / 1
- 모델: RT-DETR-L
- 입력 크기: 640
- Seed: 42
- 최대 epoch: 100
- Batch size: 4
- 조기 종료 patience: 20
- AMP 학습 사용
- 실행 환경: Colab 기본 Python

## 모델 및 confidence 선정

- 학습 중 Ultralytics가 선정한 best.pt를 평가했다.
- 별도로 전체 epoch checkpoint를 재평가하지 않았다.
- checkpoint epoch가 없으면 results.csv의 최고 mAP50-95 epoch로 추정했다.
- 운영 confidence는 Validation Micro F1이 최대인 값으로 선정했다.
- 탐색 간격은 0.005이며, F1 동점이면 낮은 confidence를 선택했다.
- 최종 모델 및 confidence 선정에 Test 결과를 사용하지 않았다.

## 평가 기준

- Test 공통 confidence: 0.25
- GT 매칭 IoU: 0.5
- TP 매칭: confidence 내림차순, 같은 클래스, GT당 1회
- AP: COCO bbox 평가, maxDets=100
- AP 계산용 예측 최소 confidence: 0.001
- 혼동행렬: class-aware 집계, 오분류는 FP와 FN으로 기록

## 속도 측정

- Warmup: 5회
- Test 이미지 반복: 3회
- 측정 범위: 디코딩된 RGB 이미지부터 CPU 예측 결과까지
- 전처리·모델 실행·후처리·CPU 결과 변환 포함
- 파일 읽기·ROS 통신·결과 발행 제외
- 평균 시간의 역수로 계산한 FPS는 ROS 출력 FPS와 다르다.

## 해석 범위

- 단일 seed와 Test 객체 50개로 작은 성능 차이의 안정성을 확정할 수 없다.
- 모델별 공개 사전학습과 native 학습 설정 차이를 함께 고려해야 한다.
- 기존 YOLO 결과는 AP 계산 방식과 속도 측정 범위가 달라 참고용으로 분리했다.
- ONNX 및 rosbag 기반 하드웨어 평가는 별도 단계다.

## 결과 요약

```csv
Model,Input_size,Best_epoch,Training_Time_min,Val_mAP50,Val_mAP50_95,F1_Confidence,Correct_Predictions,Test_FP,Test_FN,Test_Precision,Test_Recall,Predict_Total_ms,Predict_Total_ms_p95
rtdetr_l,640,65,31.145072087016665,1.0,0.9600565415561615,0.395,50,1,0,0.9803921568627451,1.0,51.974137839976414,57.01587769981415
```
```