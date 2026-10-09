import React, { useEffect, useRef, useState } from 'react';
import { GameEngine } from '../game/engine.js';
import { SPRITE, candySprite } from '../game/sprites.js';
import '../game/game.css';

// 도망자(펌킨) 플레이 화면: 1인칭 영상 + AR + HUD. 실시간 처리는 GameEngine, 여기서는 HUD와 화면 전환만 그린다.
//   ready → (Enter/시작) → run → clear: 닉네임 입력 → 리더보드
//                              → over : 재시작 → 레벨 선택
export default function PlayerPage({ selectedLevel, onRestart, onLeaderboard }) {
  const videoRef = useRef(null);
  const miniRef = useRef(null);
  const engineRef = useRef(null);
  const [snap, setSnap] = useState(null);
  const [, setTick] = useState(0);  // 타이머·머무름 진행률 갱신용

  useEffect(() => {
    const engine = new GameEngine({ lv: selectedLevel, video: videoRef.current, minimap: miniRef.current, onChange: setSnap });
    engineRef.current = engine;
    engine.start();
    const timer = setInterval(() => setTick((n) => n + 1), 100);
    return () => { clearInterval(timer); engine.destroy(); };
  }, [selectedLevel]);

  const engine = engineRef.current;
  const s = snap;
  const session = s?.session;
  const game = s?.game ?? { s: 'ready' };
  const collected = new Set(s?.collected ?? []);
  const total = session?.candies.length ?? 3;
  const allCollected = !!session && collected.size === total;

  const remaining = engine && session ? Math.ceil(engine.remainingSec()) : null;
  const timerText = remaining == null ? '--:--' : `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;

  return (
    <div className={`pr-screen ${s?.debug ? '' : 'pr-nodebug'}`}>
      {!s?.hasVideo && <span className="pr-placeholder">영상 기다리는 중…</span>}
      <canvas ref={videoRef} className="pr-video" />

      {/* 상단 중앙: 남은 시간 + 사탕 */}
      <div className="pr-top">
        <div className={`pr-timer ${game.s === 'run' && remaining != null && remaining <= 30 ? 'warn' : ''}`}>{timerText}</div>
        <div className="pr-candies">
          {(session?.candies ?? []).map((c) => <CandyIcon key={c.id} on={collected.has(c.id)} />)}
          <span className="pr-candy-n">{collected.size}/{total}</span>
        </div>
      </div>
      {game.s === 'run' && allCollected && <GateHint engine={engine} gate={s.gate} />}

      {/* 우측 상단: 미니맵 */}
      <canvas ref={miniRef} className="pr-minimap" />

      {/* 이후 단계에서 채울 자리: 하트, 추적 여부, 두근두근, CCTV 눈 아이콘 / 의심 게이지 */}
      <div className="pr-status-bar">
        <div data-slot="hearts" /><div data-slot="chase" /><div data-slot="heartbeat" /><div data-slot="cctv-eye" />
      </div>
      <div className="pr-gauge" />

      <Keys mask={s?.mask ?? 0} />
      <Toast toast={s?.toast} />

      <div className="pr-debug">
        <div className={s?.statsBad ? 'bad' : ''}>{s?.connected ? s.stats : '서버 연결 중…'}</div>
        {s?.pick && <div className={s.pick.gone > 500 ? 'bad' : 'pick'}>획득 {s.pick.id}: 판정→사라짐 {s.pick.gone} ms (수신 {s.pick.rx} ms)</div>}
        {session && (
          <div>
            Lv.{session.lv} {session.name}{session.mock ? ' (MOCK)' : ''}  상태 {game.s}{'\n'}
            {s.pose ? `펌킨 ${s.pose[0].toFixed(2)}, ${s.pose[1].toFixed(2)}` : '펌킨 —'}   {s.boo ? `부우 ${s.boo[0].toFixed(2)}, ${s.boo[1].toFixed(2)}` : '부우 —'}
          </div>
        )}
      </div>

      <Overlay
        snap={s} engine={engine} total={total} collected={collected.size}
        onRestart={onRestart} onLeaderboard={onLeaderboard}
      />
    </div>
  );
}

function CandyIcon({ on }) {
  const ref = useRef(null);
  useEffect(() => {
    const g = ref.current.getContext('2d');
    g.clearRect(0, 0, 68, 68);
    g.drawImage(candySprite, 0, 0, SPRITE, SPRITE, 0, 0, 68, 68);  // 후광이 잘리지 않게 스프라이트 전체를 넣는다
  }, []);
  return <canvas ref={ref} width={68} height={68} className={on ? 'on' : ''} />;
}

// 사탕을 다 모은 뒤 할 일: 문 앞 구역에서 기다리기 → 문으로 들어가기
function GateHint({ engine, gate }) {
  const opened = gate.op != null;
  const p = opened ? 1 : engine.dwellProgress();
  const text = opened ? '🚪 문이 열렸다! 안으로 들어가자'
    : gate.dw == null ? `탈출문 앞 보라색 원 안에서 ${gate.need}초 기다리기`
      : `문 여는 중… ${(p * gate.need).toFixed(1)} / ${gate.need}초 (원 밖으로 나가면 처음부터)`;
  return (
    <div className="pr-gatehint">
      {text}
      <div className="pr-gatebar"><i style={{ width: `${(p * 100).toFixed(0)}%` }} /></div>
    </div>
  );
}

function Keys({ mask }) {
  const key = (bit, label) => <span className={mask & bit ? 'on' : ''}>{label}</span>;
  return <div className="pr-keys"><i />{key(1, 'W')}<i />{key(2, 'A')}{key(4, 'S')}{key(8, 'D')}</div>;
}

function Toast({ toast }) {
  const [shown, setShown] = useState(null);
  useEffect(() => {
    if (!toast) return undefined;
    setShown(toast);
    const t = setTimeout(() => setShown(null), 3000);
    return () => clearTimeout(t);
  }, [toast?.n]);
  return shown ? <div key={shown.n} className="pr-toast">{shown.text}</div> : null;
}

function Overlay({ snap, engine, total, collected, onRestart, onLeaderboard }) {
  const [nickname, setNickname] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const game = snap?.game ?? { s: 'ready' };
  const session = snap?.session;

  if (snap?.error) {
    return (
      <div className="pr-overlay">
        <div><h1>준비 중</h1><p>{snap.error}</p><button type="button" className="pr-button" onClick={onRestart}>레벨 선택으로</button></div>
      </div>
    );
  }

  if (game.s === 'ready') {
    return (
      <div className="pr-overlay">
        <div>
          <h1>🎃 Pumpkin Run</h1>
          <p>Lv.{session?.lv ?? '-'} {session?.name ?? ''} — 달빛 사탕 {total}개를 모아 부우를 피해 탈출하라!</p>
          <p className="pr-small">W/S 전진·후진 · A/D 회전</p>
          <button type="button" className="pr-button" disabled={!snap?.connected} onClick={() => engine?.sendStart()}>시작 (Enter)</button>
        </div>
      </div>
    );
  }

  if (game.s === 'over') {
    const restart = async () => {
      await fetch('/api/game/reset', { method: 'POST' }).catch(() => {});
      onRestart();
    };
    return (
      <div className="pr-overlay">
        <div>
          <h1>{game.r === 'timeout' ? 'TIME OVER' : 'GAME OVER'}</h1>
          <p>달빛 사탕 {collected}/{total}</p>
          <button type="button" className="pr-button" onClick={restart}>재시작</button>
        </div>
      </div>
    );
  }

  if (game.s === 'clear') {
    const el = game.el ?? 0;
    const record = `${Math.floor(el / 60)}:${(el % 60).toFixed(1).padStart(4, '0')}`;
    const submit = async (e) => {
      e.preventDefault();
      const name = nickname.trim();
      if (!name) return;
      setSaving(true); setSaveError(null);
      try {
        const r = await fetch('/api/records', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nickname: name }),
        });
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail ?? `저장 실패 (${r.status})`);
        onLeaderboard({ lv: body.lv, id: body.id });
      } catch (err) {
        setSaveError(err.message);
        setSaving(false);
      }
    };
    return (
      <div className="pr-overlay clear">
        <div>
          <h1>🎃 CANDY ESCAPE!</h1>
          <p>달빛 사탕 {total}개를 모두 모았다! 펌킨의 할로윈 대작전 성공!</p>
          <p className="pr-record">기록 {record}</p>
          <form className="pr-nick" onSubmit={submit}>
            <input
              autoFocus maxLength={12} placeholder="닉네임 (최대 12자)" value={nickname}
              onChange={(e) => setNickname(e.target.value)} disabled={saving}
            />
            <button type="submit" className="pr-button" disabled={saving || !nickname.trim()}>기록 저장</button>
          </form>
          {saveError && <p className="pr-error">{saveError}</p>}
        </div>
      </div>
    );
  }

  return null;
}
