import React, { useEffect, useRef, useState } from 'react';

// 데드 바이 데이라이트(생존자 상태 아이콘·공포 반경 심장박동)와 제5인격(감지 경고·화면 가장자리 연출)을 참고한 HUD.
// 값은 모두 서버가 준다: hud = {hp, max, bs(부우 상태), sg(의심 0~1), cc(CCTV 감지)}, heartbeat = 부우와의 거리로 계산한 0~1

const Heart = ({ full }) => (
  <svg viewBox="0 0 24 22" aria-hidden="true">
    <path d="M12 21s-8.5-5.6-10.6-10.3C-.3 6.6 2.4 2 6.6 2c2.4 0 4 1.3 5.4 3.1C13.4 3.3 15 2 17.4 2c4.2 0 6.9 4.6 5.2 8.7C20.5 15.4 12 21 12 21z"
      fill={full ? 'url(#pr-heart-fill)' : 'none'} stroke={full ? '#ffb3b3' : '#6b4a5a'} strokeWidth="1.6" />
  </svg>
);

const PumpkinFace = () => (
  <svg viewBox="0 0 40 40" aria-hidden="true">
    <path d="M20 9c1-3 3-5 5-5" stroke="#3f6b2a" strokeWidth="3" fill="none" strokeLinecap="round" />
    <ellipse cx="20" cy="23" rx="16" ry="13" fill="url(#pr-pumpkin-fill)" />
    <path d="M14 11c-3 4-3 20 0 24M26 11c3 4 3 20 0 24" stroke="#b4460a" strokeWidth="1.4" fill="none" />
    <path d="M10 19l5-3 2 5zM30 19l-5-3-2 5z" fill="#3a1600" />
    <path d="M11 26q9 7 18 0l-3 2-2-2-2 2-2-2-2 2-2-2-2 2z" fill="#3a1600" />
  </svg>
);

const GhostIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a8 8 0 0 0-8 8v12l3-2 2.5 2 2.5-2 2.5 2 2.5-2 3 2V10a8 8 0 0 0-8-8z" fill="currentColor" />
    <circle cx="9" cy="10" r="1.6" fill="#1a0b14" /><circle cx="15" cy="10" r="1.6" fill="#1a0b14" />
  </svg>
);

const PulseIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 21s-8.5-5.6-10.6-10.3C-.3 6.6 2.4 2 6.6 2c2.4 0 4 1.3 5.4 3.1C13.4 3.3 15 2 17.4 2c4.2 0 6.9 4.6 5.2 8.7C20.5 15.4 12 21 12 21z" fill="currentColor" />
    <path d="M3 11h4l2-3 3 6 2-4 1 1h6" stroke="#1a0b14" strokeWidth="1.6" fill="none" strokeLinejoin="round" />
  </svg>
);

const EyeIcon = ({ open }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {open ? (
      <>
        <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" fill="currentColor" />
        <circle cx="12" cy="12" r="4" fill="#1a0b14" /><circle cx="12" cy="12" r="1.8" fill="#ff4d4d" />
      </>
    ) : (
      <path d="M2 10q10 9 20 0M5 13l-2 3M9 15l-1 3M15 15l1 3M19 13l2 3" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" />
    )}
  </svg>
);

// SVG 그라데이션 정의 (한 번만)
export const HudDefs = () => (
  <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
    <defs>
      <linearGradient id="pr-heart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff6b6b" /><stop offset="1" stopColor="#b3122e" /></linearGradient>
      <radialGradient id="pr-pumpkin-fill" cx=".35" cy=".35" r=".8"><stop offset="0" stopColor="#ffc46b" /><stop offset=".6" stopColor="#ff7a00" /><stop offset="1" stopColor="#a63c00" /></radialGradient>
    </defs>
  </svg>
);

// ---- 왼쪽 하단 상태 바: 초상화 + 하트 + 추적 / 두근두근 / CCTV ----
export function StatusBar({ hud, heartbeat, showCctv }) {
  const hpRatio = hud.max ? hud.hp / hud.max : 1;
  const chase = hud.bs === 'chase';
  const search = hud.bs === 'search';
  const ring = chase ? 'chase' : hpRatio <= 1 / 3 ? 'low' : hpRatio < 1 ? 'hurt' : 'ok';

  // 하트가 줄어든 순간 해당 칸에 깨지는 연출
  const prevHp = useRef(hud.hp);
  const [lost, setLost] = useState(null);
  useEffect(() => {
    if (hud.hp < prevHp.current) {
      setLost(hud.hp);
      const t = setTimeout(() => setLost(null), 900);
      prevHp.current = hud.hp;
      return () => clearTimeout(t);
    }
    prevHp.current = hud.hp;
    return undefined;
  }, [hud.hp]);

  const beatSec = heartbeat > 0 ? 60 / (70 + 90 * heartbeat) : 1;

  return (
    <div className="pr-status-bar">
      <div className={`pr-portrait ring-${ring}`}><PumpkinFace /></div>
      <div className="pr-status-right">
        <div className="pr-hearts">
          {Array.from({ length: hud.max }, (_, i) => (
            <span key={i} className={`pr-heart ${i < hud.hp ? 'full' : 'empty'} ${lost === i ? 'lost' : ''}`}><Heart full={i < hud.hp} /></span>
          ))}
        </div>
        <div className="pr-status-icons">
          <div className={`pr-tile chase ${chase ? 'on' : search ? 'warn' : ''}`} title="추적 여부">
            <GhostIcon /><small>{chase ? '추적 중' : search ? '수색 중' : '추적'}</small>
          </div>
          <div className={`pr-tile beat ${heartbeat > 0 ? 'on' : ''}`} title="두근두근: 부우가 가까이 있음"
            style={{ '--beat': `${beatSec}s`, '--beat-scale': 1.08 + 0.25 * heartbeat }}>
            <PulseIcon /><small>{heartbeat > 0 ? '두근두근' : '조용함'}</small>
          </div>
          {showCctv && (
            <div className={`pr-tile cctv ${hud.cc ? 'on' : ''}`} title="CCTV 감지">
              <EyeIcon open={!!hud.cc} /><small>{hud.cc ? '들켰다!' : 'CCTV'}</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- 중앙 하단 의심 게이지: 0이면 숨김, 차오를수록 ? → ! ----
export function SuspicionGauge({ sg, chase }) {
  const v = chase ? 1 : sg;
  const full = v >= 1;
  const level = v >= 0.66 ? 'high' : v >= 0.33 ? 'mid' : 'low';
  return (
    <div className={`pr-gauge ${v > 0 ? 'show' : ''} ${level} ${full ? 'full' : ''}`} style={{ '--sg': v }}>
      <div className="pr-gauge-icon">{full ? '!' : '?'}</div>
      <div className="pr-gauge-body">
        <div className="pr-gauge-label">{chase ? '부우가 쫓아온다!' : full ? '발각!' : '부우가 수상하게 여긴다'}</div>
        <div className="pr-gauge-track">
          <i className="pr-gauge-fill" />
          <span className="pr-gauge-tick" style={{ left: '33%' }} /><span className="pr-gauge-tick" style={{ left: '66%' }} />
        </div>
      </div>
    </div>
  );
}

// ---- 화면 연출: 공포 반경 맥박, 추적 중 흐림·붉어짐, 피격 BOO!! ----
export function ScreenEffects({ heartbeat, chase, hit }) {
  const [boo, setBoo] = useState(null);
  useEffect(() => {
    if (!hit) return undefined;
    setBoo(hit.n);
    const t = setTimeout(() => setBoo(null), 1300);
    return () => clearTimeout(t);
  }, [hit?.n]);

  const beatSec = heartbeat > 0 ? 60 / (70 + 90 * heartbeat) : 1;
  return (
    <>
      {heartbeat > 0 && (
        <div className="pr-fx-beat" style={{ '--beat': `${beatSec}s`, '--beat-k': 0.25 + 0.65 * heartbeat }} />
      )}
      {chase && <div className="pr-fx-chase" />}
      {boo != null && (
        <div key={boo} className="pr-fx-hit"><span>BOO!!</span></div>
      )}
    </>
  );
}
