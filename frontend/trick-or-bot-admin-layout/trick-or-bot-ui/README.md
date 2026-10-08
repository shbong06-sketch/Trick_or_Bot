# Trick or Bot — React UI 틀

최신 기획안 기준으로 만든 **React 화면 구조 초안**입니다.

## 현재 들어 있는 화면
- 메인 / Level 1~5 선택
- 플레이어 화면 (OAK-D 카메라 영역, 타이머, 목표 진행, 미니맵 표시 영역)
- 운영자 화면 (아레나 맵, 장비 연결 상태, 운영 제어, 이벤트 영역)

## 이번 단계에서 구현하지 않은 것
- 실제 WASD 로봇 조작
- 로봇 카메라 실시간 영상
- ROS 2 / Fast DDS 연결
- FastAPI / WebSocket 서버
- SQLite 기록
- 실제 게임 규칙, 타이머, 안전 정지 로직
- Three.js 장면

운영 제어 버튼은 클릭해도 동작하지 않습니다. 탭 이동과 레벨 선택만 UI 미리보기를 위해 작동합니다.

## 폴더
- `src/pages/` 화면
- `src/components/` 공통 UI
- `src/data/levels.js` 레벨 표시 데이터
- `src/styles.css` 화면 스타일
