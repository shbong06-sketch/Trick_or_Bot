# 탐지 모델
펌킨 탐지에 사용할 학습 모델을 보관하는 폴더입니다.
사용할 모델 경로는 config/detectors.yaml에 설정합니다.

`setup.py`는 이 폴더의 `.pt` 파일을 `share/tob_perception/models`에 설치합니다.
`model_path: models/yolo11n_boo.pt`처럼 패키지 share 디렉터리 기준 상대 경로를 지정하거나 외부 모델의 절대 경로를 지정할 수 있습니다.
노드 실행 시 `--ros-args --params-file <detectors.yaml 경로>`로 설정을 적용합니다. `model_path`를 지정하지 않으면 시작을 중단합니다.

## yolo11n_boo.pt, yolov8n_boo.pt

- Boo (추격 로봇)이 Pumpkin (플레이어 로봇)을 탐지하는데 사용할 pt 파일입니다.

- 실물 test 후 최종 모델 하나를 결정하여 사용할 예정입니다.
