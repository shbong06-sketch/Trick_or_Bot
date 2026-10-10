# tob_perception 임시 설계 문서

- 작성일: 2026-10-10
- 담당: 승현
- 상태: 세부 설계 용.
- 작업 원칙: 작업 전 계획을 검토하고, 파일 수정은 사용자 승인 후 진행한다.

## 1. 오늘의 목표와 범위

AMR 카메라의 압축 RGB 영상을 구독하고 PT 모델로 Pumpkin을 탐지한 뒤, `/tob/perception/pumpkin_detection`으로 탐지 결과를 발행한다.

오늘의 탐지 구현 범위는 모델 로딩, 영상 디코딩, 추론, 대상 선택, 탐지 메시지 발행 및 선택적 디버그 영상 발행이다. 본문은 `tob_perception`의 세부 설계이며, 위치 계산과 관련 인터페이스 조율은 하단의 추후 계획에서 다룬다.

## 2. 사용자 확정 사항

- 입력 토픽: `/robot1/oakd/rgb/image_raw/compressed`.
- 모델 경로는 ROS 파라미터로 지정한다.
- 기본 모델: `yolo11n_boo.pt`.
- 추론 장치: GPU.
- `--debug` 실행 옵션을 지정한 경우에만 탐지 결과를 그린 디버그 영상을 발행한다.

## 3. 탐지 인터페이스 기준

- `docs/interfaces.md`
- `ros2_ws/src/tob_interfaces/msg/TargetObservation.msg`

실제 메시지 필드 이름과 타입은 `TargetObservation.msg`를 따른다. 바운딩 박스는 원본 RGB 영상 기준으로 정규화한 0~1 값이다.

## 4. 탐지 처리 흐름

```text
/robot1/oakd/rgb/image_raw/compressed
  → boo_detector_node.py: 압축 영상 디코딩
  → detector.py: GPU 모델 추론
  → 대상 클래스 및 신뢰도 필터링
  → /tob/perception/pumpkin_detection (TargetObservation)
```

`--debug` 지정 시 탐지 노드에서 별도의 디버그 영상 토픽도 발행한다.

## 5. 모듈 책임

### detector.py

- ROS 통신과 독립적인 모델 로딩 및 추론 모듈.
- 시작 시 모델을 한 번 로딩하고 재사용한다.
- 이미지 입력에 대해 원본 영상 기준 박스, 클래스 ID, 신뢰도를 반환한다.
- 잘못된 모델, 이미지 또는 추론 실패를 호출자에게 전달한다.
- 모델 실행 라이브러리와 모델 호환성은 구현 전 확인한다.

### boo_detector_node.py

- `sensor_msgs/msg/CompressedImage` 구독 및 디코딩.
- 원본 영상의 촬영 시각과 `frame_id` 보존.
- 추론 호출, 대상 선택 및 메시지 변환.
- 탐지 결과와 선택적 디버그 영상 발행.
- 깊이 계산, TF 변환, 추격 행동 및 게임 판정은 수행하지 않는다.

## 6. 탐지 입출력과 메시지

| 항목 | 설계 |
|---|---|
| 입력 토픽 | `/robot1/oakd/rgb/image_raw/compressed` |
| 입력 타입 | `sensor_msgs/msg/CompressedImage` |
| 출력 토픽 | `/tob/perception/pumpkin_detection` |
| 출력 타입 | `tob_interfaces/msg/TargetObservation` |
| source | `boo_camera` |

| 필드 | 탐지 성공 | 정상 영상에서 미탐지 |
|---|---|---|
| `header` | 입력 영상의 시각 및 frame_id | 동일 |
| `source` | `boo_camera` | 동일 |
| `detected` | true | false |
| `confidence` | 선택 대상의 신뢰도 | 0 |
| `bbox_center_x/y` | 원본 너비/높이로 정규화한 박스 중심 | 0 |
| `bbox_width/height` | 원본 너비/높이로 정규화한 박스 크기 | 0 |
| `map_valid` | false | false |
| `target_position` | 기본값, 무효 | 기본값, 무효 |
| `distance_m` | 기본값, 무효 | 기본값, 무효 |

탐지 단계에서 위치와 거리는 무효이며 `map_valid=false`일 때 사용해서는 안 된다. 박스는 디코딩된 원본 RGB 영상의 너비와 높이를 기준으로 정규화하며, 모델 내부 리사이즈 좌표를 그대로 발행하지 않는다.

## 7. 대상 선택과 처리 방식 — 검토안

- 대상 클래스와 신뢰도 기준을 통과한 탐지만 사용한다.
- 단일 대상 메시지에 맞춰 최고 신뢰도 대상 하나를 선택하는 방식을 제안한다.
- 단일 처리 흐름으로 시작하고 입력 대기 깊이는 1로 제한한다.
- 입력 속도가 추론 속도를 초과하면 모든 카메라 프레임의 처리를 보장하지 않는다.
- 실제로 처리한 정상 프레임마다 탐지 또는 미탐지 결과를 발행한다.
- 과거 프레임 결과를 새로운 촬영 시각으로 재발행하지 않는다.

## 8. 파라미터 및 실행 옵션

| 항목 | 값 또는 검토 상태 |
|---|---|
| `model_path` | 기본값: 설치된 패키지의 `models/yolo11n_boo.pt`; 다른 PT 경로 지정 가능 |
| `image_topic` | `/robot1/oakd/rgb/image_raw/compressed` |
| `detection_topic` | `/tob/perception/pumpkin_detection` |
| `source` | `boo_camera` |
| `target_class_id` | 모델 클래스 확인 후 확정 |
| `confidence_threshold` | 0.5 제안, 아직 미확정 |
| `device` | GPU 사용 확정; 라이브러리별 지정 형식 및 GPU 인덱스 확인 필요 |
| `use_sim_time` | 실제 장비에서는 false 제안 |
| `debug_image_topic` | `/tob/perception/debug/image` 제안 |
| 실행 옵션 `--debug` | 지정 시에만 디버그 영상 발행 |

파라미터는 시작 시 읽고 검증하는 방식을 제안한다. 실행 중 모델 교체는 이번 설계 범위에 포함하지 않는다.

GPU를 사용할 수 없는 경우 Warning 경고를 한 뒤, 자동 종료한다. 구체적인 장치 값은 모델 라이브러리와 실행 환경 확인 후 결정한다.

`--debug`는 노드 전용 실행 옵션으로 처리하고 ROS 실행 인자와 분리한다. 디버그를 활성화하는 별도 ROS 파라미터는 두지 않는다. 실제 실행 진입점 등록 후 실행 명령을 확정한다.

## 9. 디버그 영상

- `--debug` 미지정: 디버그 publisher 미생성한다.
- `--debug` 지정: 처리한 원본 RGB 영상에 선택한 대상의 박스, 클래스 및 신뢰도를 표시해 발행한다.
- 미탐지 프레임도 발행하여 정상 영상 입력과 미탐지를 확인할 수 있게 한다.
- 디코딩/추론 실패 프레임은 정상 디버그 결과로 발행하지 않는다.
- 디버그 영상의 header는 입력 영상의 시각과 frame_id를 유지한다.
- 출력 타입은 `sensor_msgs/msg/Image`, 인코딩은 `bgr8`을 제안한다.
- GUI 창은 필수로 띄우지 않으며 ROS 영상 뷰어에서 확인한다.
- 디버그 영상이 유일한 탐지 결과가 되지 않도록 정식 탐지 토픽은 항상 별도로 발행한다.

## 10. QoS 및 실패 처리

입력 영상과 디버그 영상은 다음 QoS로 설정한다. 
> RELIABLE / VOLATILE / KEEP_LAST / depth=1

| 상황 | 동작 |
|---|---|
| 모델 경로/로딩, 클래스 설정, 필수 파라미터 오류 | 원인을 알리고 시작 중단 |
| GPU 사용 불가 | 원인을 알리고 중단 |
| 정상 영상에서 대상 없음 | detected=false 발행 |
| 디코딩 또는 추론 실패 | 오류 기록, 해당 관측 발행 생략 |
| 카메라 입력 중단 | 과거 결과 재발행 금지; 수신자가 만료 검사 |

## 11. 탐지 구현 전 확인 사항

1. PT 모델의 라이브러리 호환성과 실제 Pumpkin 클래스 ID/이름.
2. GPU 실행 환경, 사용 GPU 인덱스 및 device 지정 형식.
3. 실제 RGB 토픽의 자료형, frame_id, 해상도와 QoS.
4. 대상 선택 정책과 신뢰도 기준의 승인.
5. 디버그 영상 토픽/타입 및 실행 옵션 처리 방식의 승인.

## 12. 탐지 구현의 예상 수정 범위와 검증

향후 구현 후보: detector.py, boo_detector_node.py, config/detectors.yaml, setup.py, package.xml. 모델/설정 설치 항목과 실행 진입점을 포함하되, 정확한 변경 내용은 구현 전 승인받는다. 현재는 이 설계 문서만 작성한다.

탐지 구현 후 확인할 항목:

- 기본 모델 및 지정 모델 경로로 GPU 로딩 가능.
- 실제 압축 영상에서 대상 탐지와 미탐지 구분.
- 정규화 박스, 원본 header 및 map_valid=false 확인.
- 카메라 중단과 처리 오류가 정상 미탐지로 위장되지 않음.
- --debug 지정 시 영상 토픽 발행, 미지정 시 디버그 publisher 없음.
- 정식 탐지 결과와 디버그 영상의 시각/박스 일치.
- 탐지 토픽의 자료형과 발행 필드가 실제 TargetObservation 정의와 일치함.

## 13. 추후 계획

### 13.1 위치 계산 방식과 데이터 연결

우선 `tob_localization/target_localizer_node.py` 지침의 깊이 기반 방식을 사용한다. 탐지 결과에 대응하는 깊이와 CameraInfo로 카메라 좌표계의 3D 점을 구한 뒤, 관측 시각의 TF로 `map` 좌표계에 변환한다.

```text
/tob/perception/pumpkin_detection (TargetObservation)
  → target_localizer_node.py
      + RGB에 정렬된 깊이 영상
      + 대응하는 CameraInfo
      + 관측 시각의 TF
  → 카메라 좌표계 3D 점
  → map 좌표계 변환
  → /tob/target/observation (TargetObservation)
```

실제 추론 속도 및 좌표 계산 정확도를 확인한 뒤, 깊이 카메라 대신 detection 시 `/<ns>/amcl_pose`를 받아 좌표를 계산하는 방식도 추후 고려한다. 이 대안은 현재 깊이 기반 노드의 구현 지침과 구분하며, 적용 전 별도 설계 및 인터페이스 검토가 필요하다.

### 13.2 깊이 및 TF 연결 조건

- 깊이 토픽, RGB 정렬 상태, CameraInfo 토픽 및 TF 경로를 확인한다.
- 깊이는 RGB에 정렬되어 있어야 하며 해상도와 좌표 대응을 확인한다.
- 메시지에 영상 크기 필드가 없으므로 원본 RGB 크기와 대응하는 CameraInfo/영상 크기를 검증한 뒤 정규화 박스를 픽셀 좌표로 복원한다.
- RGB 촬영 시각을 유지하고 깊이와 허용 시각 차이 및 시간 동기화를 검사한다.
- CameraInfo의 투영 모델, 영상 크기 및 광학 좌표계가 실제 영상과 일치해야 한다.
- 왜곡/정류 여부를 확인한 뒤 역투영 방식을 정한다.
- 깊이 인코딩, 단위, 유효 범위와 무효값을 확인한다.
- 박스 내 대표 깊이 및 대표 픽셀 선택 정책을 확정한다. 박스 중심이 실제 대상 표면임을 가정하지 않는다.
- 유효한 깊이와 카메라 모델로 카메라 광학 좌표계의 3D 점을 구한다.
- 관측 시각의 TF가 유효한 경우에만 map 좌표로 변환한다.
- 감지 없음, 깊이 없음, 정렬/시각 불일치, 무효값 또는 TF 실패 시 map_valid=false로 전달한다.
- 감지 상실 뒤 과거 위치를 현재 관측으로 갱신하지 않는다.
- 우선 깊이 방식에서는 Pumpkin 자신의 지도 위치로 깊이 관측을 대체하지 않는다.

### 13.3 위치 및 거리 인터페이스 검토

- 3D 대표점과 로봇 중심 위치의 관계를 정의한다.
- `target_position`에 부여할 시각의 의미를 확정한다.
- 기존 `distance_m`은 두 로봇 기준점 사이의 평면 거리로 정의되어 있다. 카메라 깊이나 3D 대표점까지의 거리를 그대로 대입하지 않으며, 깊이 기반 방식과의 의미 정합성을 검토한다.
- `docs/interfaces.md`의 Level 1은 깊이 기반 위치 계산을 제외하고 두 로봇 지도 위치를 결합하도록 정의한다. 반면 위치 계산 노드 지침은 깊이와 TF를 사용한다. 사용자 지시에 따라 깊이 방식을 우선하되, 공유 문서 변경 필요성과 팀 인터페이스 합의를 추후 검토한다.

### 13.4 후속 검증 및 확장

- 위치 계산 노드의 탐지 메시지 수신과 깊이/CameraInfo 연결을 확인한다.
- 깊이 및 TF 연결 구현 후 기준 위치에서 3D/map 좌표 정확도를 검증한다.
- 깊이 또는 TF 실패가 정상 위치 관측과 구분되는지 검증한다.
- 처리 주기 제한, 병렬 추론 또는 추적 기능은 성능 측정 후 필요성이 확인되면 별도로 검토한다.
