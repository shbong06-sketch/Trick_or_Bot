import React from "react";
import Panel from '../components/Panel.jsx';
import { levels } from '../data/levels.js';

// UI 배치만 구현한 정적 플레이어 화면. 실제 로봇 데이터 및 조작은 연결하지 않음.
export default function PlayerPage({ selectedLevel }) {
  const level = levels.find((item) => item.id === selectedLevel);

  return (
    <main className="page player-screen">
      <div className="player-heading">
        <div><span className="player-eyebrow">SURVIVOR VIEW · UI PREVIEW</span><h1>도망자 플레이 화면</h1></div>
        <span className="player-mode-label">시안 · 실시간 데이터 미연결</span>
      </div>

      <div className="player-layout-v2">
        <section className="player-main" aria-label="1인칭 영상 및 게임 정보">
          <div className="player-hud-top">
            <span className="hud-pill">LEVEL {selectedLevel} · {level?.name || '레벨 미정'}</span>
            <span className="hud-pill hud-timer">⏱ {level?.duration || '--:--'}</span>
            <span className="hud-pill hud-objectives">목표 0 / —</span>
          </div>

          <div className="player-camera-frame">
            <div className="player-feed-header"><span><i className="feed-indicator" /> SURVIVOR CAM</span><span>OAK-D · 미연결</span></div>
            <div className="player-feed-empty">
              <span className="player-camera-symbol">◈</span>
              <strong>1인칭 영상 표시 영역</strong>
              <p>도망자 AMR 카메라 연결 예정</p>
            </div>
            <div className="player-feed-footer"><span>W / S · 전진 / 후진</span><span>A / D · 회전</span><span>키 입력 미연결</span></div>
          </div>

          <div className="player-bottom-row">
            <Panel title="발전기 진행"><div className="player-placeholder-progress"><span>현재 진행</span><b>0 / —</b></div><div className="progress-track"/><p className="muted">실제 게임 상태 연동 전</p></Panel>
            <Panel title="아이템"><div className="player-item-slots"><div>1<small>아이템</small></div><div>2<small>아이템</small></div><div>3<small>아이템</small></div></div><p className="muted">레벨별 표시 내용 연결 예정</p></Panel>
          </div>
        </section>

        <aside className="player-aside">
          <Panel title="미니맵"><div className="player-map-frame"><div className="player-map-label">ARENA MAP</div><small>아레나 위치 데이터 미연결</small></div><p className="muted">플레이어용 공개 정보만 표시 예정</p></Panel>
          <Panel title="탈출 목표"><div className="player-info-row"><span>현재 레벨</span><strong>LEVEL {selectedLevel}</strong></div><div className="player-info-row"><span>제한 시간</span><strong>{level?.duration || '--:--'}</strong></div><div className="player-info-row"><span>탈출문</span><strong>상태 미연결</strong></div></Panel>
          <Panel title="술래 상태"><div className="player-state-empty">상태 데이터 미연결</div><div className="progress-track"/><p className="muted">의심 게이지 표시 예정</p></Panel>
          <Panel title="안내"><p className="player-guide">이 화면은 레이아웃 확인용입니다. 현재 로봇은 움직이지 않으며, 타이머도 작동하지 않습니다.</p></Panel>
        </aside>
      </div>
    </main>
  );
}
