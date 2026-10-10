import React, { useEffect, useState } from "react";
import { levels } from '../data/levels.js';
import Panel from '../components/Panel.jsx';

// 레벨 선택. 게임 서버에 설정이 있는 레벨만 시작할 수 있다 (GET /api/levels)
export default function HomePage({ selectedLevel, onSelectLevel, onOpenPlayer }) {
  const [available, setAvailable] = useState(null);  // 서버에 준비된 레벨 id 목록, null = 확인 중
  useEffect(() => {
    fetch('/api/levels').then((r) => (r.ok ? r.json() : [])).then((list) => setAvailable(list.map((l) => l.id))).catch(() => setAvailable([]));
  }, []);
  const ready = (id) => available?.includes(id);
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
              disabled={available != null && !ready(level.id)}
            >
              <span className="level-no">LEVEL {String(level.id).padStart(2, '0')}</span>
              <strong>{level.name}</strong>
              <small>제한 시간 {level.duration}</small>
              <span className="level-card-foot" aria-hidden="true">
                {available != null && !ready(level.id) ? '준비 중' : selectedLevel === level.id ? '● 선택됨' : '○ 선택 가능'}
              </span>
            </button>
          ))}
        </div>
        <div className="home-action-row">
          <div className="selected-level-info">
            <span className="muted">선택한 레벨</span>
            <strong>LEVEL {selectedLevel} · {levels.find((level) => level.id === selectedLevel)?.name}</strong>
          </div>
          <button className="primary-button" type="button" onClick={onOpenPlayer} disabled={!ready(selectedLevel)}>
            게임 시작 →
          </button>
        </div>
        <p className="home-notice">
          {available == null ? '게임 서버 확인 중…' : available.length === 0 ? '게임 서버에 연결할 수 없습니다. 백엔드가 켜져 있는지 확인하세요.'
            : '게임 시작 후 Enter로 출발합니다. W/S 전진·후진, A/D 회전.'}
        </p>
      </Panel>
    </main>
  );
}
