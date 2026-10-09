import React, { useEffect, useState } from 'react';
import Panel from '../components/Panel.jsx';
import { levels } from '../data/levels.js';

// 클리어 기록 순위 (빠른 순). highlightId = 방금 저장한 기록
export default function LeaderboardPage({ lv, highlightId, onHome }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const level = levels.find((l) => l.id === lv);

  useEffect(() => {
    fetch(`/api/leaderboard?lv=${lv}&limit=10`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`불러오기 실패 (${r.status})`))))
      .then((body) => setRows(body.records))
      .catch((e) => setError(e.message));
  }, [lv]);

  const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

  return (
    <main className="page leaderboard">
      <Panel title={`LEADERBOARD · LEVEL ${lv} ${level?.name ?? ''}`} className="leaderboard-panel">
        {error && <p className="muted">{error}</p>}
        {!rows && !error && <p className="muted">불러오는 중…</p>}
        {rows && rows.length === 0 && <p className="muted">아직 기록이 없습니다.</p>}
        {rows && rows.length > 0 && (
          <ol className="leaderboard-list">
            {rows.map((r) => (
              <li key={r.id} className={r.id === highlightId ? 'me' : ''}>
                <span className="lb-rank">{r.rank}</span>
                <span className="lb-name">{r.nickname}{r.id === highlightId ? ' (나)' : ''}</span>
                <span className="lb-time">{fmt(r.time)}</span>
              </li>
            ))}
          </ol>
        )}
        {rows && highlightId != null && !rows.some((r) => r.id === highlightId) && (
          <p className="muted">내 기록은 10위 밖입니다.</p>
        )}
        <div className="home-action-row">
          <span className="muted">기록은 클리어 시간 기준 빠른 순</span>
          <button type="button" className="primary-button" onClick={onHome}>레벨 선택으로 →</button>
        </div>
      </Panel>
    </main>
  );
}
