# detection_alert 패키지 가이드 (웹캠 Detection Alert)

- 작성: 2026-10-07_0920
- 위치: `rokey_ws/src/detection_alert/`
- 한 줄 설명: **고정 웹캠으로 RC car를 검출해 알리고, 그 car의 위치를 SLAM 지도(map) 좌표로 바꿔 발행하는 패키지**
- 관련 가이던스: `docs/guidance/guidance_4.md`(패키지 기초), `guidance_6.md`(로봇 있을 때 보정·실행),
  `guidance_6_1.md`(로봇 없이 보정·오차 측정), `guidance_6_2.md`(모듈 테스트)

---

## 0. 1분 요약 (설명할 때 이 순서로)

1. **무엇을**: 경기장 위 삼각대에 고정한 USB 웹캠으로 car를 YOLO로 검출한다.
2. **알림**: **내 차**(car + 검정 40% 이상, ID 추적)가 최근 0.3초 중 60% 이상 보이면 `/webcam/car_alert = true` → AMR 출발 신호.
3. **좌표**: car bbox의 **아래쪽 가운데**(바퀴가 바닥에 닿는 점)를 **homography**로 지도 좌표 (x, y)로 바꾼다.
   카메라가 고정이고 car는 항상 바닥 위에 있으므로, 화면의 한 pixel은 항상 바닥의 같은 한 점이다.
   그래서 깊이(depth) 카메라 없이 RGB 웹캠만으로 위치를 구할 수 있다.
4. **보정**: 지도와 화면 양쪽에서 보이는 바닥 점 6~7개로 변환 행렬을 한 번 구한다. 카메라를 움직이면 다시 한다.
5. **정확도**: 실측 결과 car 위치 오차 약 **0.15~0.2 m**. AMR은 car 근처로 간 뒤 자기 카메라로 다시 찾으므로 충분하다.

---

## 1. 미니 프로젝트에서의 위치

교안(Day2 PDF p47) 예시 시나리오의 앞부분을 맡는다.

```
[이 패키지]                                           [AMR 쪽 (amr_controller / 팀원 rccar_follow)]
WebCam Detect Object → Car? ─Yes→ 알림 + car 지도 좌표 ──▶ start AMR → move AMR(Nav2) → Detect Car(OAK-D) → Approach
            ▲            │No
            └────────────┘
```

| 교안 Subsystem 항목 | 이 패키지에서 하는 곳 |
|---|---|
| Camera Capture | `webcam_detector` (1280x720 MJPG 촬영) |
| Object Detection | `webcam_detector` (YOLO26n `best_v26n.pt`) |
| Send messages to other subsystems | `/webcam/car_alert`, `/webcam/detections`, `/webcam/car_point` |
| (DAY3 과제) Design a way to get information about the target | `car_locator` (homography로 car 지도 좌표) |

---

## 2. 전체 흐름

```
 USB 웹캠 (삼각대 고정)
     │ 1280x720
     ▼
┌──────────────────── webcam_detector ────────────────────┐
│ ① 가운데 720x720 잘라 곧바로 640x640으로 줄임               │
│ ② YOLO26n Tracking (640, conf ≥ 0.8, 15Hz 고정) → ID 부여  │
│ ③ 내 차 판정: car + 검정 ≥ 40% + 화면 가장자리에 안 닿음      │
│ ④ 알림 안정화(시간 기준): 최근 0.3초 중 60% → ON / 0.7초 없음 → OFF │
└───────────────────────────────────────────────────────────┘
     │ /webcam/car_alert (Bool)      ──────────────▶ AMR 출발 신호
     │ /webcam/detections (JSON)     ──┐
     │ /webcam/image(/compressed)      │ (bbox 그린 영상, 확인·rosbag용)
     ▼                                 ▼
┌──────────────────── car_locator ─────────────────────────┐
│ ⑤ 내 차 ID의 bbox 아래쪽 가운데 → 원본 1280x720 좌표로 되돌림  │
│ ⑥ homography.yaml 의 3x3 행렬 H 로 → 지도 좌표 (x, y)        │
│ ⑦ 발행 규칙: 처음 발견 / 이동 확정(0.3m, 0.2초) / 멈춤(1초)     │
└───────────────────────────────────────────────────────────┘
     │ /webcam/car_point_raw (PointStamped, 매 프레임)  → RViz 확인용
     │ /webcam/car_point     (PointStamped, 규칙에 따라) → AMR 목표 (goto_car)
```

---

## 3. 핵심 원리

### 3-1. 왜 가운데만 보나, 왜 곧바로 640으로 줄이나 (center crop)

- 학습 데이터를 Roboflow에서 "Fill (with center crop)"으로 정사각형으로 잘라 만들었다.
  실제 사용 영상도 같은 방식으로 잘라야 학습 때와 같은 모양·크기로 보인다.
- 학습 이미지는 이미 640x640이었다. 그래서 잘라낸 720x720을 **곧바로 640x640으로 줄여** YOLO에 넣는다.
  (YOLO가 내부에서 줄이는 것과 같은 방식(INTER_LINEAR)이라 검출 결과가 같다: 36프레임 63개 검출에서 bbox 차이 0.0px)
  영상·bbox·JSON이 모두 640x640 기준 하나이고, JSON으로 내보낼 때만 **bbox × crop_scale(=720/640=1.125)**로 crop 기준(720)으로 되돌려 보낸다. (팀원 노드가 `원본 = bbox + crop_offset` 규약으로 계산하므로)
- **한계**: 화면 좌우 가장자리(각 280px)에 있는 car는 검출되지 않는다.

### 3-2. 알림을 바로 내지 않는 이유 (시간 기준 판단)

- 한 프레임 검출만으로 알리면 순간 오검출에도 AMR이 출발한다.
- 708초 실측에서 car 미검출은 대부분 1~2프레임짜리 순간 미검출이었다.
  → **ON: 최근 0.3초 중 60% 이상 / OFF: 0.7초 연속 미검출**로 안정화. 프레임 수가 아니라 **초 단위**라 `--rate`를 바꿔도 같다.
- **내 차**: class가 car이고 bbox 안 검정 픽셀(HSV V<110)이 40% 이상이며 bbox가 화면 가장자리에 닿지 않음. dummy·다른 색 car·가장자리의 사람 다리는 알림에서 제외한다.
  (검정 비율만으로는 사람 신발이 안 걸러진다: guidance_7 S8. 잘린 물체는 아래 가운데 좌표도 믿기 어려워 가장자리에 닿으면 제외)
  ByteTrack ID로 같은 차를 계속 추적하고, car_locator는 그 ID의 bbox만 좌표로 바꾼다.

### 3-3. pixel → 지도 좌표: homography

- **조건 2개**: ① 카메라가 고정 ② car는 항상 같은 평면(바닥) 위.
- 이 조건이면 화면의 pixel (u, v)와 바닥의 지도 좌표 (x, y)는 **3x3 행렬 H 하나**로 1:1 대응된다.

```
[x, y, 1]ᵀ ∝ H · [u, v, 1]ᵀ      (∝ : 마지막 값으로 나눠 맞춤)
```

- H는 8개의 미지수 → **(pixel, 지도 좌표) 짝 4개 이상**이면 구할 수 있다. 실제로는 6개 이상 + 검증점 1개를 쓴다.
- **bbox 아래쪽 가운데를 쓰는 이유**: homography는 "바닥 위의 점"만 맞게 바꾼다.
  bbox 중심은 차체 높이만큼 바닥에서 떠 있어서 좌표가 밀린다. 아래쪽 가운데가 바퀴가 바닥에 닿는 점에 가장 가깝다.
- **AMR(OAK-D)과의 차이**: AMR은 depth 카메라라 "거리"를 직접 재고 TF로 지도 좌표를 구한다 (3_3_e).
  웹캠은 거리를 모르는 대신 "바닥 평면"이라는 조건으로 위치를 구한다.

### 3-4. 보정 (calibration)

- 지도와 웹캠 화면 **양쪽에서 같은 점을 찾을 수 있는 바닥 위 점**이 필요하다.
  - 로봇 있을 때: 바닥 X 테이프 위에 로봇을 세우고 로봇 위치(TF)를 기록 (`record_map_points`)
  - 로봇 없을 때: 지도에 보이는 **벽 꼭짓점**을 RViz에서 클릭 (`record_map_points --clicked`)
- 그다음 웹캠 화면에서 같은 점을 같은 순서로 클릭 → 행렬 계산 (`calib_homography`)
- 🔴 **보정점은 화면 전체(특히 car가 다닐 영역)에 퍼져 있어야 한다.**
  6-1 실측에서 6점이 모두 먼 벽 한 줄에 몰려, 가까운 바닥에서 0.3~0.5 m 틀렸다.
  car 측정 위치 12개를 보정점에 더해 재보정 → 왼쪽 벽 바닥선 오차 0.39 m → 0.03 m.
- 보정 품질 확인 3가지: `잔차`(0.05 m 이하), `검증점 오차`(0.1 m 이하), 확인 그림의 초록 격자가 바닥에 맞는지.

### 3-5. car_point 발행 규칙 (car_locator)

| 언제 | 무엇을 |
|---|---|
| 내 차 알림이 켜지고 처음 보일 때 | 그 위치 |
| **이동 확정**: 기준 위치에서 최근 0.5초 평균이 0.3 m 이상 벗어난 상태가 0.2초 이상 계속 | 그 위치. 이동 중에는 마지막 전송에서 0.3 m 더 갈 때마다 |
| car가 **1초 동안 5 cm 안**에 머물러 "멈춤"이 됐을 때 | 멈춘 위치(1초 평균) — 직전 값과 5 cm 넘게 다르면. 이 위치가 새 기준 |

- 0.2초보다 짧은 튐(손 가림, 순간 오검출)은 이동으로 치지 않는다. 시간 기준이라 `--rate`와 무관.
- 알림이 켜진 채 한 프레임만 car를 못 봐도 기록을 지우지 않는다. (알림이 꺼질 때만 초기화)

- QoS **transient_local**: AMR node를 나중에 켜도 마지막 좌표를 바로 받는다.
- `require_stop:=true`로 켜면 "멈췄을 때만" 보낸다.

---

## 4. 패키지 구성

```
detection_alert/
├── package.xml, setup.py, setup.cfg, resource/
├── models/best_v26n.pt               YOLO26n 가중치 (24개 run 비교에서 선정)
├── config/                           🔴 보정 결과 (git으로 팀 공유)
│   ├── homography.yaml               현재 쓰는 변환 행렬 (10/6 재보정: 벽 6 + car 12점)
│   ├── homography_preview.jpg        확인 그림 (초록 격자 = 지도 0.5m)
│   ├── homography_wall6*.yaml/jpg    재보정 전 백업 (먼 벽 6점)
│   ├── map_points.yaml               보정점의 지도 좌표
│   └── calib_image.jpg               보정 때 찍은 원본 (check_camera 기준)
├── launch/webcam_eval.launch.py      로봇 없이: 지도 + RViz + 검출 + 좌표 변환 한 번에
├── rviz/webcam_eval.rviz             지도 + car 점(빨강) + 클릭 점(파랑)
├── docs_wc_det/                      이 문서
└── detection_alert/
    ├── webcam_detector_node.py       ① 웹캠 → YOLO → 알림·검출 발행
    ├── car_locator_node.py           ② bbox → 지도 좌표 발행
    ├── homography.py                 (공용) 행렬 계산·적용·저장·확인 그림
    ├── record_map_points.py          (보정) 보정점의 지도 좌표 기록
    ├── calib_homography.py           (보정) 화면 클릭 → 행렬 계산
    ├── check_camera.py               (점검) 보정 이후 카메라가 움직였는지
    └── eval_car_point.py             (검증) RViz 클릭과 웹캠 좌표 오차 측정
```

---

## 5. 실행 파일 사용법

공통 준비 (터미널마다):

```bash
source ~/venvs/rokey_venv/bin/activate
source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash
# 로봇 없이 이 PC 안에서만 쓸 때만 추가: source ~/ROKEY_mP4_A1/wc/ros_local.sh
```

웹캠 번호 확인: `v4l2-ctl --list-devices` → `Web Camera` 아래 첫 번째 `/dev/videoN`의 N (아래 예시는 5)

| 실행 파일 | 용도 | 예시 |
|---|---|---|
| `webcam_detector` | 검출·알림 발행 | `ros2 run detection_alert webcam_detector --cam 5` |
| `car_locator` | 지도 좌표 발행 | `ros2 run detection_alert car_locator` |
| `check_camera` | 카메라가 보정 이후 움직였는지 (✅/❌) | `ros2 run detection_alert check_camera --cam 5` |
| `record_map_points` | 보정점 지도 좌표 기록 (로봇) | `ros2 run detection_alert record_map_points` |
| | 〃 (RViz 클릭, 로봇 없이) | `ros2 run detection_alert record_map_points --clicked` |
| `calib_homography` | 화면에서 보정점 클릭 → 행렬 | `ros2 run detection_alert calib_homography --cam 5 --check 1` |
| `eval_car_point` | 오차 측정 (RViz 클릭 vs 웹캠) | `ros2 run detection_alert eval_car_point --out eval.csv` |
| launch | 로봇 없이 확인 환경 한 번에 | `ros2 launch detection_alert webcam_eval.launch.py cam:=5` |

- `webcam_detector`의 `--cam`에는 이미지 폴더나 동영상 파일도 넣을 수 있다 (웹캠 없이 시험).
- 창 단축키: 검출 창 `q` 종료 / 보정 창 `z` 취소·`Enter` 계산·`Esc` 중단.

---

## 6. topic

| topic | 타입 | 발행 | 내용 |
|---|---|---|---|
| `/webcam/car_alert` | std_msgs/Bool | webcam_detector | car 알림 상태 (매 프레임) |
| `/webcam/detections` | std_msgs/String (JSON) | webcam_detector | 매 프레임 검출 목록 (아래) |
| `/webcam/image`, `/webcam/image/compressed` | Image / CompressedImage | webcam_detector | bbox 그린 영상 (보는 쪽이 있을 때만) |
| `/webcam/car_point_raw` | geometry_msgs/PointStamped (frame `map`) | car_locator | car 지도 좌표, 매 프레임 (RViz 확인용) |
| `/webcam/car_point` | geometry_msgs/PointStamped (frame `map`) | car_locator | AMR 목표용, 3-5 규칙에 따라 (transient_local) |

`/webcam/detections` JSON 예시:

```json
{"stamp": 1759555555.123, "frame_id": "webcam", "image_w": 640, "image_h": 640,
 "src_w": 1280, "src_h": 720, "crop_offset": [280, 0], "crop_scale": 1.125,
 "car_alert": true, "my_id": 3,
 "detections": [{"class": "car", "conf": 0.95, "bbox": [x1, y1, x2, y2],
                 "bbox_img": [..], "center": [cx, cy], "center_norm": [u, v],
                 "track_id": 3, "black": 0.62, "edge": false, "mine": true}]}
```

- `bbox`·`center`는 crop한 정사각형(720) 기준 pixel. **원본 pixel = bbox + crop_offset** (기존 규약 그대로). `bbox_img`는 `/webcam/image`(640x640) 위의 bbox.
- detections는 **내 차가 맨 앞**, 그 안에서 confidence 높은 순.
- `track_id`: ByteTrack ID(없으면 null) / `black`: car bbox 안 검정 비율(car만) / `mine`: 내 차 여부 / `my_id`: 지금 내 차의 ID
- detections는 confidence 높은 순.

---

## 7. 설정값

**webcam_detector** (명령줄 `--이름 값`)

| 이름 | 기본 | 뜻 |
|---|---|---|
| `--cam` | `0` | 🔴 웹캠 번호 (반드시 지정) / 이미지 폴더 / 동영상 |
| `--conf` | 0.8 | 검출 confidence 하한. 0.8이면 벽 모서리 오검출(최대 0.79) 제거 |
| (처리 주기) | 15 고정 | `--rate` 없음. 이유는 `webcam_detector_node.py` 상단 "처리 주기 15Hz" |
| `--width`, `--height` | 1280, 720 | 🔴 촬영 해상도. **보정 때와 같아야 함** |
| `--fps` | 30 | 카메라 촬영 FPS |
| `--on-sec`, `--on-ratio`, `--off-sec` | 0.3, 0.6, 0.7 | 알림 ON(최근 0.3초 중 60%) / OFF(0.7초 미검출) |
| `--black-v`, `--black-min` | 110, 0.4 | 내 차 판정: 밝기 V<110 픽셀이 bbox의 40% 이상 |
| `--edge-margin` | 3 | bbox가 640 영상 가장자리에서 이 pixel 안이면 내 차에서 제외 (0이면 끔) |
| `--no-crop`, `--no-show`, `--save` | | crop 끄기 / 창 끄기 / 검출 프레임 저장 |

**car_locator** (`--ros-args -p 이름:=값`)

| 이름 | 기본 | 뜻 |
|---|---|---|
| `homography` | `src/detection_alert/config/homography.yaml` | 보정 파일 |
| `target_class` | car | 좌표를 낼 class |
| `require_stop` | false | true면 멈췄을 때만 car_point 발행 |
| `stop_sec`, `stop_tol` | 1.0 s, 0.05 m | 멈춤 판단 |
| `resend_dist` | 0.3 m | 이동 판단 거리. 기준 위치에서 이만큼 벗어나면 이동 |
| `avg_sec`, `hold_sec` | 0.5 s, 0.2 s | 최근 0.5초 평균이 0.2초 이상 계속 벗어나야 이동 확정 (그보다 짧은 튐은 무시) |

---

## 8. 상황별 사용 절차 (요약, 자세한 커맨드는 가이던스)

| 상황 | 할 일 | 가이던스 |
|---|---|---|
| 🔴 **매번 쓰기 전** | `check_camera` → `✅` 확인. `❌`면 다시 보정 | 6_2의 1-3 |
| 삼각대를 새로 세움 / 맵을 새로 만듦 | 보정 다시 (로봇 있으면 X 테이프, 없으면 벽 꼭짓점) | 6 B / 6_1 B |
| 정확도 확인 | launch + `eval_car_point`로 RViz 클릭과 비교 (10회 이상) | 6_2 |
| AMR과 함께 실행 | `webcam_detector` + `car_locator` + AMR node | 6 C |

🔴 **다시 보정하면** 팀원 `rccar_follow/config/homography.yaml`(feature/real-trial-261003)도 같이 바꿔야 한다
(팀원 패키지가 이 패키지의 보정 파일을 복사해 쓰고 있음).

---

## 9. 검증 결과 (2026-10-06 실측)

| 항목 | 결과 |
|---|---|
| 검출 모델 | YOLO26n: Test 오류(FP/FN) 0, 정답 최저 conf 0.936 (24개 run 비교) |
| 검출 안정성 | car가 멈춰 있을 때 지도 좌표 흔들림 0.1~0.3 cm |
| 좌표 오차 (먼 벽 6점 보정) | 평균 0.25 m, 최대 0.48 m (가까운 쪽에서 크게 틀림) |
| 좌표 오차 (재보정, 교차검증) | **평균 0.165 m**, 최대 0.33 m |
| 좌표 오차 (6-2 모듈 테스트) | 1회 측정 0.194 m |
| 클릭과 무관한 검증 | 왼쪽 벽 바닥선 → 지도 벽까지 0.39 m → **0.03 m** (재보정 후) |
| 카메라 이동 (6-2 측정 전·후) | 1.1 cm / 0.0 cm → 측정 유효 |

- 남는 오차 약 0.13 m는 **기준값(RViz 클릭) 자체의 오차**로 판단 (지도에 car가 안 보여 눈짐작으로 찍음).

---

## 10. 한계와 주의

| 한계 | 영향 | 대응 |
|---|---|---|
| 화면 좌우 가장자리 검출 안 됨 (center crop) | 그 영역의 car는 알림·좌표 없음 | 삼각대 방향을 car가 다닐 영역 중심으로 |
| 사람 다리를 car로 오검출 (6-2, conf 0.82) | 좌표가 진짜 car와 번갈아 발행 | 시연 중 사람은 화면 밖 (실제 스테이지에서는 해당 없음) |
| 화면 맨 아래에 잘린 car | bbox 아래쪽이 바퀴가 아님 → 좌표 틀림 | 잘린 car는 무시 |
| 카메라가 움직이면 보정 무효 | 전체 좌표가 틀어짐 | 매번 `check_camera` |
| 보정 파일이 두 곳 (이 패키지, rccar_follow) | 한쪽만 바꾸면 좌표 불일치 | 다시 보정하면 둘 다 갱신 |

---

## 11. 예상 질문과 답

**Q. 웹캠은 RGB라 거리를 모르는데 어떻게 지도 좌표를 구하나?**
A. 카메라가 고정이고 car는 바닥 위에만 있으므로, 화면의 한 점은 바닥의 한 점과 1:1이다.
이 대응을 3x3 행렬(homography)로 한 번 구해 두고 계속 쓴다. "바닥 평면" 조건이 depth를 대신한다.

**Q. 보정은 어떻게 했나?**
A. 지도에 보이는 벽 꼭짓점을 RViz에서 클릭해 지도 좌표를 얻고, 웹캠 화면에서 같은 점을 클릭해 짝을 만들었다.
처음 보정은 점이 먼 벽에 몰려 가까운 쪽 오차가 컸고, 실측한 car 위치를 보정점에 더해 재보정했다.

**Q. 정확도는?**
A. 약 0.15~0.2 m. 기준값(RViz 클릭) 자체 오차가 약 0.1 m 포함된 값이다.
AMR은 이 좌표 근처로 간 뒤 OAK-D로 다시 찾으므로 시나리오에는 충분하다.

**Q. 왜 bbox 중심이 아니라 아래쪽 가운데인가?**
A. 변환은 바닥 위의 점에만 맞다. bbox 중심은 차체 높이만큼 떠 있고, 아래쪽 가운데가 바퀴가 바닥에 닿는 점이다.

**Q. 알림은 왜 바로 안 내나?**
A. 순간 오검출로 로봇이 출발하지 않게, 최근 0.3초 중 60% 이상 내 차가 보일 때만 켠다.

**Q. node를 왜 둘로 나눴나 (webcam_detector / car_locator)?**
A. 검출은 이미 실측까지 끝나 안정적이고, 보정은 카메라가 움직일 때마다 바뀐다.
좌표 변환을 따로 두면 YOLO를 다시 띄우지 않고 보정만 바꿀 수 있고, rosbag으로 좌표 변환만 따로 시험할 수 있다.

---

## 12. 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `Package 'detection_alert' not found` | 이 터미널에서 `source ~/ROKEY_mP4_A1/rokey_ws/install/setup.bash` 안 함 |
| `Failed to open webcam` / `카메라를 열 수 없음` | `--cam` 번호 확인 / 웹캠을 쓰는 다른 프로그램(카메라 앱, 화상회의) 끄기 |
| 화면이 검음 (`frames are black`) | 웹캠 렌즈 가림막이 닫힘 또는 내장 카메라 번호를 씀 |
| 다른 터미널에서 topic이 안 보임 | 로봇 미연결인데 discovery server 설정 → 모든 터미널에서 `ros_local.sh` |
| car_locator `보정 파일 없음` | 보정 안 함 → 가이던스 6 B 또는 6_1 B |
| car_locator `⚠️ 보정 영역 밖` | car가 보정점들로 둘러싼 범위 밖 → 오차 큼. 바깥쪽에 보정점 추가 |
| check_camera `❌` | 삼각대가 움직임 → 다시 보정 |
