# Trick or Bot — React UI

실행 방법·게임 규칙·통신 구조는 저장소 루트 [`README.md`](../README.md)를 보세요.

```bash
npm ci          # 처음 한 번
npm run dev     # http://localhost:5173 (게임 서버 8000이 켜져 있어야 함)
npm run build   # dist/ → 게임 서버가 http://<서버>:8000 에서 그대로 보여줌
```

## 화면
- 인트로 → 경고 → 타이틀 → 레벨 선택 (`HomePage`, 서버에 설정된 레벨만 시작 가능)
- 도망자 플레이 화면 (`PlayerPage`): 1인칭 영상 + AR(사탕·탈출문) + HUD(타이머, 사탕, 미니맵, 상태 바, 의심 게이지)
- 게임오버 → 재시작 → 레벨 선택 / 클리어 → 닉네임 → 리더보드 (`LeaderboardPage`)
- 운영자 화면 (`AdminPage`): 아직 정적 레이아웃

## 폴더
- `src/pages/` 화면
- `src/game/` 플레이 화면 실시간 처리
  - `engine.js`: 서버 통신(/ws/game, /ws/video), WASD, 영상·AR·미니맵 그리기
  - `geometry.js`: 맵 → 카메라 → 화면 투영, 벽 가림 판정
  - `sprites.js`: 사탕·탈출문 그림
  - `Hud.jsx`, `game.css`: 상태 바·의심 게이지·화면 연출
  - `audio.js`: 효과음 (Web Audio 합성)
- `src/components/` 공통 UI, `src/data/levels.js` 레벨 표시 데이터
