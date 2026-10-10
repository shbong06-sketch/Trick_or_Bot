# Detection

객체 탐지 모델의 학습·평가와 단계별 비교 실험을 관리합니다.
Docker 환경을 준비한 뒤 Phase 1 모델 비교, Phase 2 데이터 증강 비교,
Phase 3 하이퍼파라미터 비교, Phase 4 최종 평가 순서로 진행합니다.

## 문서

| 문서 | 내용 |
| --- | --- |
| [환경 준비](docs/setup.md) | Docker 빌드, GPU 확인, 사전 학습 가중치 준비, 1 epoch 실행 확인 |
| [Phase 1](docs/phase1.md) | 7개 모델의 학습 설정, 학습·평가 명령, 결과 취합 |
| [Phase 2](docs/phase2.md) | 4개 모델의 공간·색상 증강 비교와 기준 결과 대비 변화량 |
| [Phase 3](docs/phase3.md) | YOLO 2개 모델의 옵티마이저·학습률·배치 크기·가중치 감쇠·스케줄러 비교 |
| [Phase 4 (최종)](docs/phase4.md) | 최적 설정의 test 평가, 최종 모델 선정, 오류 분석 |

## 디렉토리

```text
detection/
├── README.md       # 전체 안내와 문서 링크
├── docs/           # 환경 준비와 단계별 사용 안내
├── configs/        # 모델별 기본 설정과 Phase 1–3 실험 설정
├── docker/         # 프레임워크별 Dockerfile과 Compose 설정
├── scripts/        # 학습·평가·취합, Phase 2·3 실험, 데이터 수집, 테스트
├── dataset/        # 이미지, 라벨, COCO 주석, data.yaml
├── checkpoints/    # 준비 또는 다운로드한 사전 학습 가중치
├── experiments/    # 실행별 체크포인트, 로그, 적용 설정, 상세 평가 결과
└── results/        # 단계별 비교·선택 결과, final 최종 보고서와 오류 분석
```

`checkpoints/`는 가중치를 준비하면 생성됩니다. 데이터 파일, 학습 산출물,
체크포인트는 `detection/.gitignore`의 제외 대상이며 `dataset/data.yaml`은 예외입니다.

## 실행 경로와 흐름

문서의 호스트 명령은 별도 안내가 없으면 `detection/`에서 실행합니다.
저장소 루트에서 먼저 아래 명령으로 이동하세요.

```bash
cd detection
```

Docker 컨테이너에서는 이 디렉토리가 `/workspace`에 연결됩니다.
호스트에서 명령을 생성하거나 결과를 취합하려면 Python 3와 PyYAML이 필요합니다.

1. [환경 준비](docs/setup.md)에 따라 사용할 모델의 이미지를 빌드하고 가중치를 준비합니다.
2. [Phase 1](docs/phase1.md)에서 모델별 학습·평가를 수행하고 비교 CSV를 만듭니다.
3. [Phase 2](docs/phase2.md)에서 Phase 1 결과를 기준으로 증강 조건을 비교합니다.
4. [Phase 3](docs/phase3.md)에서 이전 단계의 결과와 선택 설정을 확인하며 실험을 진행합니다.
5. [Phase 4](docs/phase4.md)에서 모델별 최적 체크포인트를 test로 비교하고 최종 모델을 선정합니다.

현재 최종 결과에서는 **YOLO11n**을 선택했습니다. YOLO11n은 test 42장에서
TP/FP/FN이 33/0/0이며, YOLOv8n은 32/0/1입니다.
평가 조건, 속도 비교, 선정 우선순위는 [Phase 4 문서](docs/phase4.md)에 정리했습니다.
원본 수치와 실행 이력은 [최종 결과 보고서](results/final/report.md)와
[최종 비교 CSV](results/final/final_comparison.csv)에서 확인할 수 있습니다.

학습·평가 명령은 `--execute`를 붙여야 실제 실행됩니다.
`collect` 및 `--collect`는 해당 옵션 없이도 결과 파일을 갱신합니다.
실험은 기본적으로 설정된 L4 GPU에서 순차 실행합니다.
