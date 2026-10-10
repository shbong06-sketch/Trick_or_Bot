# Trick_or_Bot

## Phase 4 Final Benchmark

Phase 3 `exp05_selection.json`의 최종 YOLO11n·YOLOv8n 체크포인트를 고정된
test set에서 평가합니다. 학습이나 threshold 조정은 수행하지 않습니다.

```bash
python3 detection/scripts/final_benchmark.py
python3 detection/scripts/final_benchmark.py --execute
```

첫 명령은 Phase 1~3 이력과 선택 설정을 검증하고 Docker 명령을 출력합니다.
`--execute`는 NVIDIA L4 Docker 환경에서 두 모델을 순서대로 평가합니다.
공통 설정은 `detection/configs/phase1/evaluation.yaml`에서 읽고, 선택된
실험의 검증 평가 설정과 다르면 중단합니다. 산출물은
`detection/results/final/`의 `final_comparison.csv/json`, `error_analysis.csv`,
`report.md`, 이미지별 `predictions/<model>/*.json`, `fp_samples/`, `fn_samples/`입니다.
FP가 없으면 `fp_samples/`는 빈 디렉터리입니다. 속도는 warmup 20회와
test 전체 3회 반복을 적용한 FP32, batch 1 측정입니다.
