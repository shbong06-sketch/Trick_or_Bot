# 개발 환경·문서 관리 계획

- 작성: 2026-10-08_1550
- 문서 ID: ENV-TOB-001 (초안, 팀 검토 전)
- 목적: Day5 과제 "개발 환경 구축(맵 디자인, SW 개발, 문서 통합 관리)"에서 정해야 할 것을 한 페이지에 모은다.
- 관련 문서: [sdd.md](sdd.md) §3(PC·네트워크), §7.1(패키지 구조), [schedule.md](schedule.md)

---

## 1. 하드웨어와 PC 배치

| 자원 | 수량 | 용도 | 비고 |
|---|---|---|---|
| TurtleBot4 | 2대 | 술래(`/robot1`), 도망자(`/robot2`) | 로봇별 IP는 로봇 LED 화면에서 확인(튜터 Multi Robot Standard Setup) |
| PC | 4대 | PC1 술래 제어·AI, PC2 도망자 제어, PC3 게임 서버·웹·Discovery Server, PC4 CCTV | 배치는 SRD SR-004. 확정은 OI-15 |
| 웹캠 | 최대 2개(Lv1은 1개) | CCTV, 좌표 보정 | OI-05 |
| 호박 머리 코스튬 | 1개 | 도망자 표시·탐지 대상 | SR-014 (LiDAR·OAK-D 시야를 가리지 않아야 함) |
| 판자·상자 | 교육장 보유 | 아레나 벽·은신처 | 교육장 직원에게 이용 허락 필요(주제선정 회의) |

## 2. 소프트웨어 기준

| 항목 | 값 | 확인 |
|---|---|---|
| OS | Ubuntu 24.04 LTS | 이 PC에서 확인 (24.04.5) |
| ROS | ROS 2 Jazzy (`/opt/ros/jazzy`) | 확인 |
| Python | 3.12 | 확인 |
| 빌드 | colcon (`~/venvs/rokey_venv`) | 확인 |
| RMW | `rmw_fastrtps_cpp`, `ROS_DOMAIN_ID=1` | 이 PC의 `~/.bashrc`에서 확인. **팀 공통 값인지는 확인 필요** |
| Discovery | 이 PC는 `ROS_DISCOVERY_SERVER=;192.168.107.101:11811;`로 설정돼 있음 | 확인. 서버 PC·ID는 팀이 정한다 |
| 비전 | OpenCV, Ultralytics YOLO | 이전 프로젝트와 동일 |
| 웹·DB | FastAPI + React, SQLite3 (OI-07) | 미확정 |

## 3. 네트워크 (멀티 로봇)

튜터 DAY5의 세 문서(Notion에서 순서가 바뀌어 번호는 01 Custom Discovery, 02 Client Setup, 03 Standard)를 참고한다. 로컬 사본: `docs/ref/notion/tutors/day5-SystemMonitor_MultiRobot/`.

| 순서 | 할 일 | 문서 |
|---|---|---|
| 1 | 두 번째 로봇을 같은 공유기에 연결하고 IP를 확인 | Multi Robot Standard Setup |
| 2 | PC·로봇의 `ROS_DOMAIN_ID`, `ROS_DISCOVERY_SERVER` 설정 | Multi Robot Custom Discovery Setup |
| 3 | PC3를 Discovery Server(ID 0, UDP 11811)로 열고 TB4·PC1·PC2·PC4를 클라이언트로 설정 | Multi Robot Client Setup |
| 4 | `ros2 daemon stop/start` 뒤 `ros2 topic list`를 두 번 실행해 두 로봇의 토픽이 모두 보이는지 확인 | Multi Robot Standard Setup |
| 5 | `teleop_twist_keyboard`로 두 로봇을 각각 움직여 보기 (`/cmd_vel:=/robot<n>/cmd_vel`) | Multi Robot Standard Setup |

- "반드시 PC에서 실행" 문서가 있다. 로봇에서 설정을 실행했다면 바로 강사님이나 조교에게 알린다(튜터 문서).
- 일반 노드는 `ROS_SUPER_CLIENT=False`, 모니터링·rosbag 기록용 PC3 터미널만 `True`로 둔다(SR-005, 튜터 Client Setup).
- 한 PC에서 두 로봇의 Nav2를 돌리는 것은 성능 문제가 생길 수 있다. 튜터는 MSI 노트북을 권장한다.

## 4. 공간·지도

- 물리 공간은 이전 미니프로젝트와 같다. 이전 지도 `rokey_ws/maps/map_auto_261006_1214.{pgm,yaml}`(0.05 m/px, 161×338 px, 원점 (−5.879, −15.252))을 원본으로 쓴다.
- 레벨별 지도는 1214 지도 **복사본에 판자 위치를 그려** 만든다. 원점이 같아 열쇠 좌표와 웹캠 homography를 그대로 쓸 수 있다(SR-018).
- 아레나 3 m × 3 m 안에 레벨 설계가 들어가는지 배치도로 먼저 확인한다(OI-04). 실제 판자·상자 위치는 바닥 테이프로 고정하고 사진을 `docs/project/arena/`에 남긴다 `[제안]`.
- 맵 설계 원칙 7가지와 레벨 1~5 설정은 [srd.md](srd.md) §7.

## 5. 저장소와 폴더

```
Trick_or_Bot/
├── CLAUDE.md                # 사용자·Claude 작업 규칙
├── docs/
│   ├── project/             # 이 폴더. BRD 정리본, SRD, SDD, 일정, 개발환경, open_issues
│   ├── guidance/            # 실측 가이드(guidance_<n>.md), CLAUDE.md §1
│   ├── prompt/              # 프롬프트 기록
│   └── ref/                 # 참고 자료(튜터 Notion md, 강의 PDF, 이전 프로젝트, 팀 Notion 내보내기)
├── rokey_ws/
│   ├── src/                 # ROS 패키지만 (CLAUDE.md §2). SDD §7.1의 tob_* 패키지가 들어간다
│   └── maps/                # 지도
└── <theme>/result_<theme>/{log_<theme>, bag_<theme>}   # 실측 기록 (CLAUDE.md §2)
```

- 브랜치: Claude는 `feature/lwh`에서 작업한다(CLAUDE.md §3). 팀원들의 브랜치 운영 규칙(브랜치 이름, 병합 절차)은 아직 정해지지 않았다 → 팀이 정한다.
- 대용량 파일(rosbag `bag_*/`, 모델 가중치 `*.pt` 등)은 `.gitignore`로 제외돼 있다. 패키지에 포함하는 모델만 예외로 추가한다.
- 빌드 산출물(`build/`, `install/`, `log/`)은 git에 올리지 않는다.

## 6. 문서 관리 `[제안]`

| 문서 | 정본 | 사본 | 갱신 방법 |
|---|---|---|---|
| BRD | 팀 Notion `BRD-TrickorBot` | `docs/project/brd.md`(정리본) | Notion 내보내기 zip을 `docs/ref/notion/P4_Final_Project/`에 넣으면 Claude가 읽는다 |
| SRD, SDD | `docs/project/*.md` (git 버전관리) | 팀 Notion 페이지에 붙여 넣기 | md를 고치고 Notion에 반영 |
| 일정 | 팀 Notion 타임라인(간트) | `docs/project/schedule.md` | 날짜 변경은 Notion에서 하고 이 문서에는 모듈 백로그만 적는다 |
| 튜터 강의 자료 | 튜터 Notion | `docs/ref/notion/tutors/` | Claude가 `notion2md.py`로 받아 온다(CLAUDE.md §4) |
| 시스템 설계도(그림) | draw.io 파일 | SDD의 mermaid 초안 | 마감(10/13 오후) 전에 draw.io로 정리 |

- 문서 도입부의 `작성:` 항목은 `YYYY-MM-DD_HHMM` 형식으로 쓴다(CLAUDE.md §6).
- 팀 Notion은 Notion 커넥터로 열리지 않는다(404). 갱신하면 내보내기 zip을 `docs/ref/notion/P4_Final_Project/`에 올린다.

## 7. 빌드·실행 기본

```bash
# 빌드 (ROS 패키지는 rokey_ws/src 아래)
source /opt/ros/jazzy/setup.bash
cd ~/Trick_or_Bot/rokey_ws
colcon build --symlink-install
source install/setup.bash

# 터미널 로그 기록 (CLAUDE.md §2)
<명령> 2>&1 | tee -i <theme>/result_<theme>/log_<theme>/log_$(date +%y%m%d_%H%M%S).txt

# rosbag 기록
ros2 bag record -o <theme>/result_<theme>/bag_<theme>/bag_$(date +%y%m%d_%H%M%S) <토픽...>
```

- 이미지 토픽은 용량이 크므로 가능하면 `.../compressed`를 기록한다.
- 코드 주석·help 문자열은 한국어로 쓴다(CLAUDE.md §5).
- 모든 노드는 namespace를 코드에 넣지 않고 실행 때 붙인다(`--ros-args -r __ns:=/robot1`). 이전 프로젝트의 규칙을 그대로 따른다.

## 8. 정해야 할 것

| 항목 | 상태 |
|---|---|
| 팀 공통 `ROS_DOMAIN_ID`와 Discovery Server PC·ID | 미정 (OI-15) |
| 로봇 IP, 로봇 ↔ PC 연결 표 | 미정 |
| 브랜치 운영 규칙 | 미정 |
| 아레나 배치도(판자·상자·열쇠 위치) | 미정 (OI-04) |
| 웹 프레임워크 | 미정 (OI-07) |
