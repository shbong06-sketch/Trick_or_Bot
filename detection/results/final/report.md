# Phase 4 Final Benchmark

## 공통 평가 조건

- Test: `dataset/images/test` (42장), COCO annotation SHA-256 `361f168cefe61b13fbc8d550114ae07c20bb65c91cdfd3a8a8a775d9b55c943b`
- 입력: 704×704, confidence 0.25, matching IoU 0.5, NMS IoU 0.7, AP cutoff 0.001
- 하드웨어: NVIDIA L4; FP32, batch 1, warmup 20회, 전체 test 3회 측정
- 속도 범위: 디코딩된 RGB에서 전처리·GPU 전송·추론·후처리·CPU 박스 반환까지. 파일 읽기, 모델 로드, 매칭, 저장 제외.
- Correct Prediction Rate = TP / (TP + FP + FN) × 100. Average Confidence = 운영 threshold 이상 예측의 평균.

## 최종 비교

| Model | Recall | F1 | mAP50 | Correct % | ms/image | mAP50-95 | TP/FP/FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| yolo11n | 1.0000 | 1.0000 | 1.0000 | 100.00 | 13.454 | 0.9492 | 33/0/0 |
| yolov8n | 0.9697 | 0.9846 | 1.0000 | 96.97 | 11.591 | 0.9774 | 32/0/1 |

## 선정 근거

**yolo11n** 선택. Test Recall → F1 → mAP50 → Correct Prediction Rate → 추론 속도 순으로 비교했습니다.
동률이면 다음 지표를 사용합니다. Test 성능은 모델 선택에만 사용하며 threshold 조정이나 재학습은 하지 않았습니다.

yolo11n은 FN 0개, yolov8n은 FN 1개입니다. yolov8n은 추론 속도(11.591 ms/image)와 mAP50-95(0.9774)에서 앞섭니다.

## 학습 및 검증 이력

### yolo11n

- Phase 3 실험 004: SGD, lr0=0.02, momentum=0.937, batch=16, weight decay=0.0005, LambdaLR
- 마지막 학습 epoch: 100 (run_info epochs_ending=101); 총 학습 시간: 301.06초
- Validation mAP50=1.0000, Precision=1.0000, Recall=1.0000, F1 peak=1.0000 @ confidence=0.4172
- Test 평균 confidence=0.9228; checkpoint=5489626 bytes, params=2590035, training peak VRAM=2732735488 bytes, evaluation peak VRAM=74228224 bytes
- 이력: `results/phase1/model_comparison.csv`, `results/phase2/augmentation_summary.csv`, `results/phase3/hyperparameter_summary.csv`; validation: `experiments/phase3/004/yolo11n/evaluation/validation_metrics.json`

### yolov8n

- Phase 3 실험 007: SGD, lr0=0.01, momentum=0.937, batch=16, weight decay=0.001, LambdaLR
- 마지막 학습 epoch: 100 (run_info epochs_ending=101); 총 학습 시간: 256.53초
- Validation mAP50=1.0000, Precision=1.0000, Recall=1.0000, F1 peak=1.0000 @ confidence=0.6122
- Test 평균 confidence=0.9468; checkpoint=6267114 bytes, params=3011043, training peak VRAM=2394496000 bytes, evaluation peak VRAM=81795584 bytes
- 이력: `results/phase1/model_comparison.csv`, `results/phase2/augmentation_summary.csv`, `results/phase3/hyperparameter_summary.csv`; validation: `experiments/phase3/007/yolov8n/evaluation/validation_metrics.json`

## Error analysis

`error_analysis.csv`에 이미지별 TP/FP/FN, 예측 confidence와 최대 미매칭 GT IoU를 기록했습니다.
`predictions/<model>/`에는 운영 threshold 이상 예측과 매칭 결과가 이미지마다 JSON으로 저장됩니다.
FP/FN 샘플은 각 디렉터리에 모델명 접두어로 저장됩니다. 초록=GT, 청록=TP, 빨강=FP, 노랑=FN입니다.
`error_type`은 수동 분류를 위한 빈 칸입니다.
