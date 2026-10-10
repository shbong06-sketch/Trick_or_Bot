// 효과음은 파일 없이 Web Audio로 합성한다. 브라우저 정책상 사용자 입력(클릭·키) 뒤에 unlock()을 불러야 소리가 난다.
let ctx = null;
let muted = false;

export function unlockAudio() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
}
export function setMuted(v) { muted = v; }
export function isMuted() { return muted; }

function thump(at, freq, gain) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = 'sine';
  o.frequency.setValueAtTime(freq, at);
  o.frequency.exponentialRampToValueAtTime(freq * 0.55, at + 0.12);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(gain, at + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
  o.connect(g).connect(ctx.destination);
  o.start(at); o.stop(at + 0.2);
}

// 심장 박동 한 번 (쿵-쿵). strength 0~1
export function playHeartbeat(strength) {
  if (!ctx || muted || ctx.state !== 'running') return;
  const t = ctx.currentTime, v = 0.15 + 0.45 * strength;
  thump(t, 70, v);
  thump(t + 0.16, 58, v * 0.7);
}

// 피격 "부우~": 내려가는 톱니파 + 떨림
export function playBoo() {
  if (!ctx || muted || ctx.state !== 'running') return;
  const t = ctx.currentTime;
  const o = ctx.createOscillator(), lfo = ctx.createOscillator(), lg = ctx.createGain(), g = ctx.createGain();
  const f = ctx.createBiquadFilter();
  o.type = 'sawtooth';
  o.frequency.setValueAtTime(320, t);
  o.frequency.exponentialRampToValueAtTime(90, t + 0.7);
  lfo.frequency.value = 9; lg.gain.value = 18;
  lfo.connect(lg).connect(o.frequency);
  f.type = 'lowpass'; f.frequency.value = 1200;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.35, t + 0.03);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.8);
  o.connect(f).connect(g).connect(ctx.destination);
  o.start(t); lfo.start(t); o.stop(t + 0.85); lfo.stop(t + 0.85);
}
