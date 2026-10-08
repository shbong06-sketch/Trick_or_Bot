import React, { useState } from 'react';
import './GameMenus.css';

const settingTabs = [
  { id: 'language', icon: '文', label: '언어' },
  { id: 'sound', icon: '♫', label: '사운드' },
  { id: 'graphics', icon: '▣', label: '그래픽' },
];

const settingItems = {
  language: [
    ['텍스트 언어', '한국어'],
    ['음성 언어', '한국어'],
  ],
  sound: [
    ['마스터 볼륨', '10'],
    ['배경음', '10'],
    ['보이스', '10'],
    ['효과음', '10'],
    ['다이내믹 레인지', '기본값'],
  ],
  graphics: [
    ['그래픽 품질', '높음'],
    ['해상도', '높음'],
    ['프레임 레이트', '30'],
    ['음영 품질', '높음'],
    ['반사 품질', '높음'],
    ['캐릭터 품질', '높음'],
    ['필드 세부 사항', '높음'],
    ['이펙트 품질', '중간'],
    ['광원 효과', '중간'],
  ],
};

export default function GameMenus({ onAdminLogin }) {
  const [menu, setMenu] = useState(null);
  const [tab, setTab] = useState('language');
  const [adminId, setAdminId] = useState('');
  const [adminPassword, setAdminPassword] = useState('');

  const openSettings = () => {
    setTab('language');
    setMenu('settings');
  };

  return (
    <>
      <aside className="game-side-menu">
        <button onClick={() => setMenu('notice')}>
          <span>▤</span>공지사항
        </button>
        <button onClick={openSettings}>
          <span>⚙</span>설정
        </button>
        <button onClick={() => setMenu('admin')}>
          <span>♙</span>관리자 전용
        </button>
      </aside>

      {menu && (
        <div className="game-menu-overlay">
          <section className="game-menu-panel">
            <button
              className="game-menu-close"
              onClick={() => setMenu(null)}
              aria-label="닫기"
            >
              ×
            </button>

            {menu === 'notice' && (
              <>
                <h2 className="game-menu-heading">공지사항</h2>
                <div className="notice-layout">
                  <aside className="notice-list">
                    <div className="notice-selected">
                      공지사항
                    </div>
                  </aside>
                  <article className="notice-detail">
                    <h3>공지사항</h3>
                    <div className="notice-placeholder">
                      등록된 공지사항이 없습니다.
                    </div>
                  </article>
                </div>
              </>
            )}

            {menu === 'settings' && (
              <>
                <h2 className="game-menu-heading">설정</h2>
                <div className="settings-layout">
                  <nav className="settings-tabs">
                    {settingTabs.map(item => (
                      <button
                        key={item.id}
                        className={
                          tab === item.id ? 'selected' : ''
                        }
                        onClick={() => setTab(item.id)}
                      >
                        <span>{item.icon}</span>
                        <small>{item.label}</small>
                      </button>
                    ))}
                  </nav>

                  <main className="settings-content">
                    <h3>
                      {settingTabs.find(x => x.id === tab)?.label}
                      {' '}설정
                    </h3>

                    {settingItems[tab].map(([name, value]) => (
                      <div className="settings-row" key={name}>
                        <span>{name}</span>
                        <div className="settings-value">
                          {value}
                          <span className="settings-arrow">▾</span>
                        </div>
                      </div>
                    ))}
                  </main>
                </div>
              </>
            )}

            {menu === 'admin' && (
              <div className="admin-login">
                <h2>관리자 로그인</h2>

                <form onSubmit={(e) => {
                  e.preventDefault();

                  // UI 테스트용 로그인
                  if (adminId === 'admin' && adminPassword === '1234') {
                    onAdminLogin();
                    setMenu(null);
                    setAdminPassword('');
                  } else {
                    alert('아이디 또는 비밀번호가 올바르지 않습니다.');
                  }
                }}>
                  <input
                    type="text"
                    placeholder="관리자 아이디"
                    value={adminId}
                    onChange={(e) => setAdminId(e.target.value)}
                    required
                  />

                  <input
                    type="password"
                    placeholder="비밀번호"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    required
                  />

                  <button type="submit">로그인</button>
                </form>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
