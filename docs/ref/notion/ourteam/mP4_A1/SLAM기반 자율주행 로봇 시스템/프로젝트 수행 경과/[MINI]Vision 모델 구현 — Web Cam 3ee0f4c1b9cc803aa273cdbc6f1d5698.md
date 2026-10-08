# [MINI]Vision 모델 구현 — Web Cam

관련 이슈·To-do: [기술검증]Vision AI detection with YOLO (웹캠 파트) (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20AI%20detection%20with%20YOLO%20(%EC%9B%B9%EC%BA%A0%20%ED%8C%8C%ED%8A%B8)%203ee0f4c1b9cc802e9bcbe4729d97558f.md), [기술검증]Vision 모델 활용과 성능 평가 방법 이해 (../%EC%9D%B4%EC%8A%88%20&%20To-do%20%ED%8A%B8%EB%9E%98%EC%BB%A4/%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5DVision%20%EB%AA%A8%EB%8D%B8%20%ED%99%9C%EC%9A%A9%EA%B3%BC%20%EC%84%B1%EB%8A%A5%20%ED%8F%89%EA%B0%80%20%EB%B0%A9%EB%B2%95%20%EC%9D%B4%ED%95%B4%203ed0f4c1b9cc80c68987d8779a03f04e.md)
기록일: 2026년 10월 2일 → 2026년 10월 3일
담당자: 09180_이원호, 민서 김
마지막 수정: 2026년 10월 6일 오전 10:01
분류: 구현
분야: Vision
생성일: 2026년 10월 3일 오전 10:42
작성 상태: 정리 완료

## **1. 진행 절차**

### **1-1. 목표**

- 미니프로젝트 시나리오 **Detection Alert → Navigate to a position → Track & Approach** 중 **Detection Alert** 담당
- 경기장 위 고정 웹캠으로 **car**(검은 장난감 지프)와 **dummy**(검은 LAN-hub 박스)를 실시간 검출
- 검출 결과 영상을 ROS 2 topic으로 publish (이후 AMR에 알림)

![웹캠 설치](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/20261003_111748.jpg)

### **1-2. 환경**

- PC: Ubuntu 24.04, ROS 2 Jazzy, Ultralytics YOLO 8.4.170, CUDA GPU
- 카메라: USB Web Camera 1920x1080 (`/dev/video4`)
- 모델: yolo26s 학습 모델 `best_v26s.pt` (모델 선정: [기술검증] YOLO 모델 비교분석 — Web Cam)

### **1-3. 데이터 수집**

- 웹캠으로 경기장 안의 car·dummy를 위치·방향을 바꿔 가며 214장 촬영 (가림·가장자리·두 물체 근접 포함)
- Roboflow 라벨링·전처리(640x640 center crop)·증강 → 508장으로 학습

![수집 이미지 16장](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/grid_webcam_raw_16.jpg)

### **1-4. Roboflow**

- 경기장에서 car를 계속 옮겨 가며 약 12분(708초) 실행
- terminal log(`tee`)와 rosbag(`/processed_image/compressed`, `/rosout`)을 함께 기록해 분석

### **1-5. ROS 2 publisher node 구현 (`2_4_e_yolo_publisher_wc_best.py`)**

[2_4_e_yolo_publisher_wc_best.py](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/2_4_e_yolo_publisher_wc_best.py)

1. 웹캠 캡처 (1920x1080, 약 10Hz)
2. **center crop** → 가운데 1080x1080 (학습 데이터 전처리와 동일)
3. YOLO 추론 (`conf 0.8`)
4. bbox 그리기: **car = 주황색, dummy = 하늘색**
5. publish
    - `/processed_image` (`sensor_msgs/Image`)
    - `/processed_image/compressed` (`sensor_msgs/CompressedImage`, JPEG 80)
6. 2초마다 상태 log: fps, 추론 시간, 밝기, class별 검출 수, 마지막 검출 좌표, 구독자 수

### **1-6. 실측**

- 경기장에서 car를 계속 옮겨 가며 약 12분(708초) 실행
- terminal log(`tee`)와 rosbag(`/processed_image/compressed`, `/rosout`)을 함께 기록해 분석

## **2. 트러블 슈팅**

### **2-1. 구현 중 문제**

| # | 현상 | 원인 | 대응 |
| --- | --- | --- | --- |
| T1 | 카메라 화면이 검게 나옴 | 노트북 내장 카메라(`/dev/video0`)를 열었음 | 시작할 때 비디오 장치 목록을 log로 출력해 Web Camera 번호(`video4`)를 확인하고 `--cam`으로 지정. 검은 프레임이면 경고 log |
| T2 | 실행 중 log가 거의 없고 bbox 화면이 안 보임 | 원본 코드에 상태 출력과 화면 표시가 없음 | 2초마다 상태 log, OpenCV 창(`q`로 종료) 추가 |
| T3 | 화면 가장자리 벽을 car/dummy로 오검출 | 학습은 center crop 이미지인데 추론은 16:9 전체 화면 | 추론할 때도 center crop + `conf 0.8` (벽 오검출 최대 0.79) |
| T4 | rosbag 용량 폭증 (7.6초에 230MB) | 1080x1080 raw 이미지 topic(장당 3.5MB)을 기록 | `/processed_image/compressed` 추가 publish 후 이것만 기록 → 약 1MB/s |
| T5 | `ros2 topic hz /processed_image`가 측정 안 됨 | raw 이미지가 너무 커서 best-effort 구독에서 메시지가 버려짐 | compressed topic으로 측정 (10.0Hz 확인) |
| T6 | car와 dummy bbox가 같은 색이라 구분이 어려움 | 모든 class를 빨간색 하나로 그림 | class별 색상 (car 주황, dummy 하늘색), 라벨 배경도 class 색 |

### **2-2. 실측 중 이상 상황 (708초 실측의 output 이미지)**

**car 미검출** — 미니프로젝트에서 영향이 가장 큰 경우 (알림 누락)

[제목 없음](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/%EC%A0%9C%EB%AA%A9%20%EC%97%86%EC%9D%8C%203ee0f4c1b9cc80bead33e4dbcd03b6aa.csv)

- **대응**
    - 위 장면(가림, 원거리, 뒷모습, 가장자리)을 추가 촬영해 재학습
    - 알림 판단은 한 프레임이 아니라 **최근 N프레임 중 M프레임 이상 검출**로 해서, 순간적인 미검출에 흔들리지 않게 함

**car가 아닌 물체를 car로 검출** — car·dummy 외 물체는 운용 대상이 아님 (참고)

[제목 없음](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/%EC%A0%9C%EB%AA%A9%20%EC%97%86%EC%9D%8C%203ee0f4c1b9cc8062ba4bcaa9c0e435cd.csv)

**정상 동작 확인 (참고)**

[제목 없음](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/%EC%A0%9C%EB%AA%A9%20%EC%97%86%EC%9D%8C%203ee0f4c1b9cc80258319ef762c3416cd.csv)

## **3. 결과**

![검출 결과 16장](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/grid_yolo_output_16.jpg)

![output_1790937515.jpg](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/output_1790937515.jpg)

![output_1790937842.jpg](%5BMINI%5DVision%20%EB%AA%A8%EB%8D%B8%20%EA%B5%AC%ED%98%84%20%E2%80%94%20Web%20Cam/output_1790937842.jpg)

| 항목 | 결과 |
| --- | --- |
| 실행 시간 / 프레임 | 708초 / 7,073 프레임 |
| fps | 9.0 ~ 10.1 (중앙값 10.0) |
| 추론 시간 | 10.3 ~ 14.9 ms (중앙값 11.8) |
| topic | `/processed_image/compressed` 10.0 Hz |
| rosbag | 695초, 674 MiB (약 1 MB/s) |
| dummy 검출 | 전체 프레임의 약 99.7%, conf 0.89~0.90 |
| car 검출 | car가 화면에 있는 구간 프레임의 약 95.5%, conf 0.81~0.92 |
| 벽 오검출 | 없음 (center crop + conf 0.8) |
- 웹캠 → YOLO → ROS 2 topic → rosbag 파이프라인이 **10Hz로 12분간 끊김 없이 동작**
- car 미검출은 주로 **가림 / 원거리 / 뒷모습 / 화면 가장자리**에서 발생 → 추가 데이터로 재학습 예정
- **다음 단계**: 검출된 car 위치를 AMR에 알리는 메시지(topic) 정의, N프레임 판단 로직 추가