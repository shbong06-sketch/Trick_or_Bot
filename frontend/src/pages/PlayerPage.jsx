import React, { useEffect, useRef, useState } from 'react';
import { GameEngine } from '../game/engine.js';
import { SPRITE, candySprite } from '../game/sprites.js';
import { HudDefs, ScreenEffects, StatusBar, SuspicionGauge } from '../game/Hud.jsx';
import { isMuted, playBoo, playHeartbeat, setMuted, unlockAudio } from '../game/audio.js';
import QuarterView from '../game/QuarterView.jsx';   // ★ 3D 쿼터뷰
import '../game/game.css';

// 도망자(펌킨) 플레이 화면: 3D 쿼터뷰 + HUD. 실시간 처리는 GameEngine, 여기서는 HUD와 화면 전환만 그린다.
//   (기존 1인칭 영상+AR canvas는 지우지 않고 숨겨 둔다 — GameEngine이 아직 필요로 함)
//   ready → (Enter/시작) → run → clear: 닉네임 입력 → 리더보드
//                              → over : 재시작 → 레벨 선택
export default function PlayerPage({ selectedLevel, onRestart, onLeaderboard }) {
  const videoRef = useRef(null);
  const miniRef = useRef(null);
  const engineRef = useRef(null);
  const [snap, setSnap] = useState(null);
  const [, setTick] = useState(0);  // 타이머·머무름 진행률 갱신용
  const [muted, setMutedState] = useState(isMuted());

  useEffect(() => {
    const engine = new GameEngine({ lv: selectedLevel, video: videoRef.current, minimap: miniRef.current, onChange: setSnap });
    engineRef.current = engine;
    engine.start();
    const timer = setInterval(() => setTick((n) => n + 1), 100);
    return () => { clearInterval(timer); engine.destroy(); };
  }, [selectedLevel]);

  // 소리는 사용자 입력 뒤에만 켤 수 있다. M = 소리 끄기/켜기
  useEffect(() => {
    const unlock = () => unlockAudio();
    const onKey = (e) => {
      unlock();
      if (e.code === 'KeyM' && !e.repeat && !(e.target instanceof HTMLInputElement)) {
        setMuted(!isMuted()); setMutedState(isMuted());
      }
    };
    addEventListener('pointerdown', unlock);
    addEventListener('keydown', onKey);
    return () => { removeEventListener('pointerdown', unlock); removeEventListener('keydown', onKey); };
  }, []);

  const engine = engineRef.current;
  const s = snap;
  const session = s?.session;
  const game = s?.game ?? { s: 'ready' };
  const collected = new Set(s?.collected ?? []);
  const total = session?.candies.length ?? 3;
  const allCollected = !!session && collected.size === total;

  // 두근두근: 부우와의 거리(5 Hz 위치)로 0~1. 반경 밖이면 0. 벽은 무시 (데바데 공포 반경처럼)
  const hud = s?.hud ?? { hp: 3, max: 3, bs: 'patrol', sg: 0, cc: 0 };
  const beatR = session?.hud?.heartbeatR ?? 2;
  const dist = s?.pose && s?.boo ? Math.hypot(s.pose[0] - s.boo[0], s.pose[1] - s.boo[1]) : Infinity;
  const heartbeat = game.s === 'run' && dist < beatR ? 1 - dist / beatR : 0;
  const chase = game.s === 'run' && hud.bs === 'chase';
  useHeartbeatSound(heartbeat);
  const shake = useHitShake(s?.hit);

  const remaining = engine && session ? Math.ceil(engine.remainingSec()) : null;
  const timerText = remaining == null ? '--:--' : `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;

  return (
    <div className={`pr-screen ${s?.debug ? '' : 'pr-nodebug'} ${shake ? 'pr-shake' : ''}`}>
      <HudDefs />
      {/* ★ 맨 아래 층: 3D 쿼터뷰. 지도·위치는 GameEngine이 받은 값을 그대로 넘긴다 */}
      {session && <QuarterView session={session} pose={s?.pose} boo={s?.boo} />}
      {/* ★ 기존 1인칭 영상 canvas: GameEngine이 필요로 해서 남겨두고 화면에서만 숨김 */}
      <canvas ref={videoRef} className="pr-video" style={{ display: 'none' }} />
      <ScreenEffects heartbeat={heartbeat} chase={chase} hit={s?.hit} />

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

      {/* 왼쪽 하단 상태 바, 중앙 하단 의심 게이지 */}
      {session && <StatusBar hud={hud} heartbeat={heartbeat} showCctv={(session.hud?.cctv ?? 0) > 0 || !!hud.cc} />}
      {game.s === 'run' && <SuspicionGauge sg={hud.sg} chase={chase} />}

      <Keys mask={s?.mask ?? 0} />
      <Toast toast={s?.toast} />

      {session?.mock && s?.debug && game.s === 'run' && <HudPreview />}
      {muted && <div className="pr-muted">🔇 소리 꺼짐 (M)</div>}

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

// 두근두근 소리: 가까울수록 빠르고 크게
function useHeartbeatSound(k) {
  const kRef = useRef(k);
  kRef.current = k;
  useEffect(() => {
    let timer;
    const loop = () => {
      const v = kRef.current;
      if (v > 0) playHeartbeat(v);
      timer = setTimeout(loop, v > 0 ? 60000 / (70 + 90 * v) : 300);
    };
    loop();
    return () => clearTimeout(timer);
  }, []);
}

// 피격: BOO!! 소리 + 화면 흔들림
function useHitShake(hit) {
  const [shake, setShake] = useState(false);
  useEffect(() => {
    if (!hit) return undefined;
    playBoo();
    setShake(true);
    const t = setTimeout(() => setShake(false), 500);
    return () => clearTimeout(t);
  }, [hit?.n]);
  return shake;
}

// mock 전용: 부우 판단 로직이 붙기 전에 HUD를 미리 보는 버튼 (서버 /api/debug/hud에 값을 넣는다)
function HudPreview() {
  const send = (body) => (e) => {
    e.currentTarget.blur();  // 포커스가 남으면 Enter·Space가 버튼을 다시 누른다
    fetch('/api/debug/hud', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  };
  return (
    <div className="pr-preview">
      <b>HUD 미리보기 (mock)</b>
      <button type="button" onClick={send({ sg: 0.3, bs: 'suspect' })}>의심 30%</button>
      <button type="button" onClick={send({ sg: 0.7, bs: 'suspect' })}>의심 70%</button>
      <button type="button" onClick={send({ sg: 1, bs: 'chase' })}>추적</button>
      <button type="button" onClick={send({ sg: 0.4, bs: 'search' })}>수색</button>
      <button type="button" onClick={send({ sg: 0, bs: 'patrol' })}>순찰(해제)</button>
      <button type="button" onClick={send({ cc: 1 })}>CCTV 발각</button>
      <button type="button" onClick={send({ cc: 0 })}>CCTV 해제</button>
      <button type="button" className="danger" onClick={send({ hit: true })}>피격</button>
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
          <p className="pr-small">W/S 전진·후진 · A/D 회전 · 부우에게 3번 잡히면 끝</p>
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
          <h1>{game.r === 'timeout' ? 'TIME OVER' : game.r === 'caught' ? '잡혔다!' : 'GAME OVER'}</h1>
          {game.r === 'caught' && <p>부우: “축제 시작 전에는 사탕 금지야!”</p>}
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
