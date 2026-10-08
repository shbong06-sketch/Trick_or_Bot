import React from "react";
import { levels } from '../data/levels.js';
import Panel from '../components/Panel.jsx';

// 메인 화면의 배치만 정의합니다. 게임 시작/로봇 연동은 아직 구현하지 않습니다.
export default function HomePage({ selectedLevel, onSelectLevel, onOpenPlayer }) {
  return (
    <main className="home page">
      <section className="home-hero" aria-label="게임 소개">
        <p className="eyebrow">HALLOWEEN ROBOT ESCAPE EXPERIENCE</p>
        <h1>TRICK <span>or</span> BOT</h1>
        <p className="subtitle">로봇의 감시를 피해 목표를 완료하고 탈출하라</p>
        <div className="hero-decoration" aria-hidden="true">☾ <span>✦</span> 🎃 <span>✦</span> ☽</div>
      </section>

      <Panel title="LEVEL SELECT" className="level-panel">
        <div className="level-panel-heading">
          <p>체험할 레벨을 선택하세요</p>
          <span className="muted">LEVEL 01 — 05</span>
        </div>
        <div className="level-grid">
          {levels.map((level) => (
            <button
              key={level.id}
              type="button"
              className={`level-card ${selectedLevel === level.id ? 'selected' : ''}`}
              onClick={() => onSelectLevel(level.id)}
              aria-pressed={selectedLevel === level.id}
            >
              <span className="level-no">LEVEL {String(level.id).padStart(2, '0')}</span>
              <strong>{level.name}</strong>
              <small>제한 시간 {level.duration}</small>
              <span className="level-card-foot" aria-hidden="true">{selectedLevel === level.id ? '● 선택됨' : '○ 선택 가능'}</span>
            </button>
          ))}
        </div>
        <div className="home-action-row">
          <div className="selected-level-info">
            <span className="muted">선택한 레벨</span>
            <strong>LEVEL {selectedLevel} · {levels.find((level) => level.id === selectedLevel)?.name}</strong>
          </div>
          <button className="primary-button" type="button" onClick={onOpenPlayer}>
            플레이어 화면 미리보기 →
          </button>
        </div>
        <p className="home-notice">현재는 화면 틀만 제공합니다. 실제 게임 시작 및 로봇 연결 기능은 없습니다.</p>
      </Panel>
    </main>
  );
}
