import "./title.css";
import React, { useEffect } from "react";
import { useState } from 'react';
import HomePage from './pages/HomePage.jsx';
import GameMenus from './components/GameMenus.jsx';
import PlayerPage from './pages/PlayerPage.jsx';
import AdminPage from './pages/AdminPage.jsx';
import LeaderboardPage from './pages/LeaderboardPage.jsx';

const pages = [
  { id: 'home', label: '메인 / 레벨 선택' },
  { id: 'player', label: '플레이어 화면' },
  { id: 'admin', label: '운영자 화면' },
];

export default function App() {
  const [page, setPage] = useState('intro');
  const [selectedLevel, setSelectedLevel] = useState(1);
  const [isAdmin, setIsAdmin] = useState(false);
  const [lastRecord, setLastRecord] = useState(null);  // 클리어 후 저장한 기록 {lv, id}

  useEffect(() => {
    if (page !== 'intro') return;

    const timer = setTimeout(() => {
      setPage('warning');
    }, 3500);

    return () => clearTimeout(timer);
  }, [page]);

  useEffect(() => {
    if (page !== 'warning') return;

    const timer = setTimeout(() => {
      setPage('title');
    }, 5000);

    return () => clearTimeout(timer);
  }, [page]);

  return (
    <div className="app-shell">
      {isAdmin && page === 'admin' && (
        <header className="admin-topbar">
          <div className="admin-topbar-brand">🎃 TRICK OR BOT | ADMIN</div>

          <nav>
            <button onClick={() => setPage('home')}>
              메인 / 레벨 선택
            </button>

            <button onClick={() => setPage('player')}>
              플레이어 화면
            </button>

            <button onClick={() => setPage('admin')}>
              운영자 화면
            </button>

            <button onClick={() => {
              setIsAdmin(false);
              setPage('title');
            }}>
              로그아웃
            </button>
          </nav>
        </header>
      )}


      {page === 'intro' && (
        <div className="intro-screen">
          <h1 className="intro-logo">
            TRICK <span>OR</span> BOT
          </h1>
        </div>
      )}

      {page === 'warning' && (
        <div className="warning-screen">
          <div className="warning-ratings">
            <img src="/assets/rating/violence.png" alt="폭력성" />
            <img src="/assets/rating/horror.png" alt="공포" />
            <img src="/assets/rating/test-rating.png" alt="시험용" />
          </div>

          <p className="warning-message">
            본 게임은 12세 이용가 게임물로 만 12세 미만의 어린이나 청소년이 이용하기 부적절합니다.
          </p>
        </div>
      )}

      {page === 'title' && (
        <main className="title-screen">
            <GameMenus onAdminLogin={() => { setIsAdmin(true); setPage("admin"); }} />
          <div className="title-content">
            <div className="title-pumpkin">🎃</div>
            <h1 className="game-title">TRICK <span>OR</span> BOT</h1>
            <p className="game-subtitle">HALLOWEEN SURVIVAL GAME</p>
            <button
              className="game-start-button"
              onClick={() => setPage('home')}
            >
              ▶ GAME START
            </button>
          </div>
        </main>
      )}
      {page === 'home' && <HomePage selectedLevel={selectedLevel} onSelectLevel={setSelectedLevel} onOpenPlayer={() => setPage('player')} />}
      {page === 'player' && (
        <PlayerPage
          selectedLevel={selectedLevel}
          onRestart={() => setPage('home')}
          onLeaderboard={(record) => { setLastRecord(record); setPage('leaderboard'); }}
        />
      )}
      {page === 'leaderboard' && (
        <LeaderboardPage lv={lastRecord?.lv ?? selectedLevel} highlightId={lastRecord?.id} onHome={() => setPage('home')} />
      )}
      {page === 'admin' && <AdminPage />}
    </div>
  );
}
