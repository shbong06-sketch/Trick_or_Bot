# YOLO 외 객체검출 모델 탐색 — Web Cam (팀장님 공유용)

- 작성: 2026-10-04_1100
- 목적: 미니프로젝트 **Detection Alert**(고정 웹캠으로 car·dummy 검출 → AMR에 알림)에 쓸 수 있는 YOLO 외 모델 후보 정리
- 판단 기준(미니프로젝트 핵심): ① **car를 놓치지 않을 것**(가림·원거리·뒷모습·가장자리) ② **car 오알림이 없을 것** ③ 웹캠 30fps(33ms) 안에 처리 ④ 학습 데이터가 적음(원본 212장)
- 수치(COCO AP, latency)는 각 논문·공식 문서 기준이며, 우리 데이터에서 직접 측정한 값이 아님

## 탐색 방향 (6가지)

| 방향 | 핵심 질문 | 대표 모델 |
|---|---|---|
| A. 실시간 Transformer(DETR 계열) | YOLO보다 정확하면서 속도도 비슷한가? | RF-DETR, D-FINE, DEIMv2, RT-DETR |
| B. 경량·엣지 특화 (팀장님 방향) | 더 작은 연산으로 더 빠른가? | SSDLite-MobileNetV3, EfficientDet-Lite, PP-PicoDet, NanoDet-Plus |
| C. 2-stage 기준선 | 전통적인 고정밀 방식과 비교하면? | Faster R-CNN |
| D. Open-vocabulary(zero-shot) | 학습 없이 글자("black toy jeep")로 찾을 수 있나? | Grounding DINO, OWLv2, YOLOE |
| E. 고정 카메라 전용 고전 CV | 카메라가 고정이라면 딥러닝 없이도 되나? | 배경 차분(MOG2) + 윤곽선 |
| F. 시간 정보 보강 | 한 프레임 미검출을 앞뒤 프레임으로 메울 수 있나? | ByteTrack, BoT-SORT (검출 모델 위에 추가) |

## A. 실시간 Transformer (DETR 계열)

| 모델 | 요약 | 크기·속도 (공식) | 우리에게 |
|---|---|---|---|
| **RF-DETR** (Roboflow, ICLR 2026) | DINOv2 backbone + DETR. NMS 없음. **적은 데이터 fine-tuning에 강하도록 설계** | Nano 2.3ms / COCO 48.0 AP, Small 3.5ms / 53.0 AP (T4, TensorRT FP16) | `pip install rfdetr`, **YOLO 형식 데이터셋을 그대로 학습** 가능 → 바로 비교 가능 |
| D-FINE | box 좌표를 확률 분포로 정밀하게 다듬는 DETR | L 54.0 AP / 8.07ms, Nano 42.7 AP / 2.1ms | 공식 repo 학습, COCO 형식 변환 필요 |
| DEIMv2 | DINOv3 특징을 쓰는 실시간 DETR | S 50.9 AP (11M params) | 최신, 공식 repo |
| RT-DETR (v1~v4) | Baidu의 최초 실시간 DETR | rtdetr-l 약 32M params | **Ultralytics에 내장** (`RTDETR('rtdetr-l.pt')`) → 지금 노트북에 거의 그대로 추가 가능 |

- 장점: NMS가 없어 **붙어 있는 car·dummy**(박스 겹침)에서 유리할 수 있고, 큰 사전학습 backbone이라 소량 데이터에 강함
- 단점: 학습 메모리·시간이 YOLO보다 큼 (8GB GPU면 batch를 줄여야 함)

## B. 경량·엣지 특화 (추론 속도 우선 — 팀장님 방향)

| 모델 | 요약 | 우리에게 |
|---|---|---|
| SSDLite-MobileNetV3 | 모바일용 고전 경량 detector. **torchvision 내장** | 구현 쉬움. 정확도는 YOLO n보다 낮을 가능성 |
| EfficientDet-Lite0~4 | Google, TFLite·Edge TPU용 | TF 환경 필요 |
| PP-PicoDet | Baidu PaddleDetection, CPU·모바일용 1M급 | Paddle 환경 필요 |
| NanoDet-Plus | 1~2M params, CPU에서 빠름 | 공식 repo |
| (OAK-D 장치 내 추론) MobileNet-SSD, YOLOv6n | TurtleBot4 OAK-D(RVC2 VPU)에서 **카메라 안에서 직접 추론**. MobileNet-SSD 약 31FPS | **AMR 쪽 후보**. 노트북 GPU 없이 동작, 영상 전송 지연 없음 |

- 참고: 모델을 바꾸지 않고 **TensorRT / ONNX FP16 변환**만으로도 2~3배 빨라지는 경우가 많음 (방향과 별개로 함께 적용 가능)

## C. 2-stage 기준선

| 모델 | 요약 | 우리에게 |
|---|---|---|
| Faster R-CNN (ResNet50-FPN) | 후보 영역을 먼저 찾고 분류하는 고전 고정밀 방식. torchvision 내장 | 느림(수십 ms). **"1-stage 실시간 모델과 정확도 차이가 거의 없다"는 근거용 기준선**으로 의미 |

## D. Open-vocabulary (학습 없이 글자로 검출)

| 모델 | 요약 | 우리에게 |
|---|---|---|
| Grounding DINO | 글자 프롬프트로 임의 물체 검출 | 느림. 검은 장난감 지프를 정확히 구분하기는 어려움. **추가 데이터 자동 라벨링 도구**로 활용 가치 |
| OWLv2 | Google, 예시 이미지로도 검색 가능 | 위와 같음 |
| YOLOE / YOLO-World | YOLO 기반 open-vocabulary | 이름은 YOLO지만 방식이 다름 |

## E. 고정 카메라 전용 고전 CV

| 방법 | 요약 | 우리에게 |
|---|---|---|
| 배경 차분(MOG2) + 윤곽선 | 빈 경기장 배경과 다른 부분을 찾음. CPU 1ms 수준 | **카메라가 고정이고 바닥이 회색 단색**이라 "움직이는 물체 있음"은 잘 찾음. 하지만 car/dummy 구분, 사람·그림자·조명 변화에 약함 → **단독으로는 부적합, 딥러닝과 결합(움직임 감지 시에만 검출)은 가능** |

## F. 시간 정보 보강 (Tracking)

| 방법 | 요약 | 우리에게 |
|---|---|---|
| ByteTrack / BoT-SORT | 프레임 사이에서 같은 물체를 이어 붙임. Ultralytics `model.track()` 내장 | 708초 실측의 **순간 미검출(가림·가장자리)** 을 메우고 car ID를 유지 → 알림 안정화. AMR Track & Approach와도 연결 |

## 추천

| 순위 | 대상 | 추천 | 이유 |
|---|---|---|---|
| 1 | 웹캠 (정확도·견고성) | **RF-DETR Nano/Small** | 소량 데이터 fine-tuning에 강함, 속도도 yolo26n급, YOLO 형식 데이터 그대로 사용 → 같은 데이터·같은 평가로 공정 비교 가능 |
| 2 | 웹캠 (비교 용이성) | **RT-DETR** (Ultralytics) | 지금 노트북·평가 코드 그대로 추가 가능. "Transformer vs CNN" 비교 근거 |
| 3 | 웹캠 (근거용 기준선) | **SSDLite-MobileNetV3**, **Faster R-CNN** | 경량 극단 / 고정밀 극단 기준선. "YOLO·RF-DETR가 둘 사이에서 가장 균형이 좋다"를 보여주는 용도 |
| - | 웹캠 (모델 외 보강) | **Tracking(ByteTrack)** + N프레임 판단 | 실측 미검출 대부분이 순간적인 것이라 모델 교체보다 효과가 클 수 있음 |
| - | AMR (팀장님 방향) | **OAK-D 장치 내 MobileNet-SSD / YOLOv6n**, 또는 노트북에서 TensorRT FP16 | 추론 속도·지연 최우선 |

## 출처
- RF-DETR 공식 문서: https://rfdetr.roboflow.com/
- RF-DETR 논문 (ICLR 2026): https://arxiv.org/abs/2511.09554
- RF-DETR 소개: https://blog.roboflow.com/rf-detr/
- D-FINE: https://arxiv.org/abs/2410.13842
- DEIMv2 (Real-Time Object Detection Meets DINOv3): https://arxiv.org/abs/2509.20787
- RT-DETRv2: https://arxiv.org/abs/2407.17140 / RT-DETRv4: https://arxiv.org/abs/2510.25257
- Luxonis RVC2 (OAK-D): https://docs.luxonis.com/hardware/platform/rvc/rvc2/
- Luxonis 포럼 (RVC2 가장 빠른 모델): https://discuss.luxonis.com/d/3404-object-detection-fastest-model
