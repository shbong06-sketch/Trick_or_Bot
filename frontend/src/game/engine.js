// 도망자(펌킨) 플레이 화면의 실시간 부분. React는 HUD만 그리고, 영상·AR·미니맵 canvas와 통신은 여기서 처리한다.
//   /api/session  : 정적 데이터 (레벨·맵·카메라) — 시작할 때 한 번
//   /ws/game      : 조작 입력, 위치 5 Hz, 상태·사탕·탈출문 이벤트
//   /ws/video     : 44바이트 헤더 + JPEG
import { cameraToPixel, makeOccluded, mapToCamera, unpackOcc } from './geometry.js';
import { BODY, GH, GW, SPRITE, candySprite, gateOpenness, renderGate } from './sprites.js';

const KEY_BITS = { KeyW: 1, KeyA: 2, KeyS: 4, KeyD: 8 };  // e.code라 한글 입력 상태에서도 동작
const HEARTBEAT_MS = 100;
const HEADER = 44, FLAG_POSE = 1;
const CANDY_R = 0.08;                  // 사탕 크기 기준 반지름 (m)
const GATE_W = 0.5;                    // 탈출문 폭 (m)
const ICON_MIN = 6, ICON_MAX = 140;    // 사탕 아이콘 반지름 한계 (canvas px)
const MINI_W = 260;                    // 미니맵 CSS 폭 (px)

const wsUrl = (path) => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`;

export class GameEngine {
  constructor({ lv, video, minimap, onChange }) {
    this.lv = lv;
    this.video = video;
    this.vctx = video.getContext('2d');
    this.minimap = minimap;
    this.onChange = onChange;

    this.session = null;
    this.occluded = () => false;
    this.pose = null;                  // 펌킨 [x, y, yaw], 5 Hz
    this.boo = null;                   // 부우 [x, y, yaw], 5 Hz
    this.game = { s: 'ready', t0: null, dur: 0, r: null, el: null };
    this.collected = new Set();
    this.gate = { op: null, dw: null, need: 3 };
    this.gateOpenAt = null;            // 문이 열리기 시작한 시각 (performance.now)
    this.pendingGone = new Map();      // id → {ts, rx} 획득 측정
    this.debug = true;
    this.busy = false;
    this.connected = false;
    this.error = null;
    this.toast = null;                 // {text, n}
    this.pick = null;                  // 마지막 획득 측정 결과
    this.hud = { hp: 3, max: 3, bs: 'patrol', sg: 0, cc: 0 };  // 하트·부우 상태·의심 게이지·CCTV 감지
    this.hit = null;                   // 마지막 피격 {n, hp} (BOO!! 연출용)

    this.ws = null; this.wsVideo = null;
    this.seq = 0; this.mask = 0; this.heartbeat = null;
    this.rtt = null; this.clockOffset = null; this.offsetSamples = [];
    this.pending = null; this.decoding = false; this.lastFrame = null;
    this.vs = { frames: 0, bytes: 0, dropped: 0, lat: [], noPose: 0 };
    this.gs = { bytes: 0, msgs: 0 };
    this.stats = '';
    this.timers = [];
    this.stopped = false;
  }

  // ---- 수명 ----
  async start() {
    try {
      const r = await fetch(`/api/session?lv=${this.lv}`);
      if (!r.ok) throw new Error(r.status === 404 ? `Level ${this.lv}은 아직 준비 중입니다` : `세션 로드 실패 (${r.status})`);
      this.session = await r.json();
    } catch (e) {
      this.error = e.message;
      this.emit();
      return;
    }
    if (this.stopped) return;
    const occ = unpackOcc(this.session.map);
    this.occ = occ;
    this.occluded = makeOccluded(this.session.map, occ);
    this.game.dur = this.session.time;
    this.buildMinimapBase();
    this.drawMinimap();

    this.onKeyDown = this.onKeyDown.bind(this);
    this.onKeyUp = this.onKeyUp.bind(this);
    this.onBlur = () => this.setMask(0);
    this.onVisibility = () => { if (document.hidden) this.setMask(0); };
    addEventListener('keydown', this.onKeyDown);
    addEventListener('keyup', this.onKeyUp);
    addEventListener('blur', this.onBlur);
    document.addEventListener('visibilitychange', this.onVisibility);

    this.connectGame();
    this.connectVideo();
    this.timers.push(setInterval(() => this.send({ t: 'ping', s: ++this.seq, c: performance.now() }), 2000));
    this.timers.push(setInterval(() => this.updateStats(), 1000));
    this.emit();
  }

  destroy() {
    this.stopped = true;
    this.setMask(0);
    removeEventListener('keydown', this.onKeyDown);
    removeEventListener('keyup', this.onKeyUp);
    removeEventListener('blur', this.onBlur);
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.timers.forEach(clearInterval);
    this.stopHeartbeat();
    this.ws?.close();       // 서버는 연결이 끊기면 로봇을 정지시킨다
    this.wsVideo?.close();
  }

  emit() {
    if (!this.stopped) this.onChange(this.snapshot());
  }

  snapshot() {
    return {
      error: this.error, session: this.session, game: { ...this.game }, gate: { ...this.gate },
      collected: [...this.collected], busy: this.busy, connected: this.connected, mask: this.mask,
      debug: this.debug, toast: this.toast, pick: this.pick, stats: this.stats, statsBad: !!this.statsBad,
      hasVideo: !!this.lastFrame, hud: { ...this.hud }, hit: this.hit,
      pose: this.pose, boo: this.boo,
    };
  }

  // ---- 시간 (서버 시작 시각 기준, 브라우저 카운트다운) ----
  serverNow() { return (Date.now() + (this.clockOffset ?? 0)) / 1000; }
  remainingSec() {
    const g = this.game;
    if (g.s === 'ready' || g.t0 == null) return g.dur;
    if (g.s === 'clear' || g.s === 'over') return g.el == null ? 0 : Math.max(0, g.dur - g.el);  // 끝난 순간에 멈춤
    return Math.max(0, g.t0 + g.dur - this.serverNow());
  }
  dwellProgress() {
    return this.gate.dw == null ? 0 : Math.min(1, Math.max(0, (this.serverNow() - this.gate.dw) / this.gate.need));
  }
  allCollected() { return !!this.session && this.collected.size === this.session.candies.length; }

  // ---- /ws/game ----
  connectGame() {
    const ws = new WebSocket(wsUrl('/ws/game'));
    this.ws = ws;
    ws.onopen = () => {
      this.busy = false; this.connected = true;
      this.send({ t: 'ping', s: ++this.seq, c: performance.now() });
      this.emit();
    };
    ws.onclose = () => {
      this.stopHeartbeat(); this.mask = 0; this.connected = false;
      this.emit();
      if (!this.stopped) setTimeout(() => this.connectGame(), 1000);
    };
    ws.onmessage = (e) => this.onGameMessage(e.data);
  }

  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
  }

  sendStart() { this.send({ t: 'start' }); }

  onGameMessage(raw) {
    this.gs.bytes += raw.length; this.gs.msgs++;
    const m = JSON.parse(raw);
    switch (m.t) {
      case 'a': {
        const d = performance.now() - m.c;
        this.rtt = this.rtt == null ? d : this.rtt * 0.8 + d * 0.2;
        // 왕복이 가장 짧았던 최근 표본으로 시계 차이를 추정 (서버 시각은 왕복의 중간이라고 가정)
        this.offsetSamples.push({ d, off: m.st * 1000 + d / 2 - Date.now() });
        if (this.offsetSamples.length > 20) this.offsetSamples.shift();
        this.clockOffset = this.offsetSamples.reduce((a, b) => (b.d < a.d ? b : a)).off;
        return;
      }
      case 'p':
        if (m.a) this.pose = m.a;
        if (m.b) this.boo = m.b;
        this.drawMinimap();
        this.emit();  // 두근두근(부우와의 거리)에 쓰므로 항상 갱신
        return;
      case 'st':
        // 레벨 선택에서 새로 들어왔는데 지난 회차가 끝난 상태로 남아 있으면 시작 전 상태로 되돌린다
        if (!this.sawState && (m.s === 'clear' || m.s === 'over')) fetch('/api/game/reset', { method: 'POST' }).catch(() => {});
        this.sawState = true;
        this.game = { s: m.s, t0: m.t0 ?? null, dur: m.dur, r: m.r ?? null, el: m.el ?? null };
        if (m.s !== 'run') this.setMask(0);
        break;
      case 'gt': {
        const wasOpen = this.gate.op != null;
        this.gate = { op: m.op, dw: m.dw, need: m.need };
        // 열린 시각을 브라우저 시계로 옮겨 애니메이션 시작점으로 쓴다 (늦게 접속했으면 이미 다 열린 상태)
        this.gateOpenAt = m.op == null ? null : performance.now() - (this.serverNow() - m.op) * 1000;
        if (!wasOpen && m.op != null && this.serverNow() - m.op < 2) this.showToast('🚪 문이 열렸다! 안으로 들어가자');
        this.drawMinimap();
        break;
      }
      case 'hud': this.hud = { hp: m.hp, max: m.max, bs: m.bs, sg: m.sg, cc: m.cc }; break;
      case 'hit': this.hit = { n: (this.hit?.n ?? 0) + 1, hp: m.hp }; break;
      case 'err': this.showToast(m.m); break;
      case 'busy': this.busy = true; break;
      case 'own': this.busy = false; break;
      case 'cds':
        this.collected = new Set(m.ids);
        this.pendingGone.clear();
        this.drawMinimap();
        break;
      case 'cd':
        // 서버 판정 결과만 따른다. 다음에 그리는 프레임부터 이 사탕을 빼고, 사라진 시각을 잰다
        this.collected.add(m.id);
        this.pendingGone.set(m.id, { ts: m.ts * 1000, rx: Date.now() });
        this.drawMinimap();
        if (this.allCollected()) this.showToast(`🎃 달빛 사탕 ${m.n}개! 탈출문 앞 원 안에서 ${this.gate.need}초 기다리자`);
        break;
      default:
        return;
    }
    this.emit();
  }

  showToast(text) {
    this.toast = { text, n: (this.toast?.n ?? 0) + 1 };
  }

  // ---- 키 입력: 상태가 바뀔 때만 보내고, 누르는 동안 100 ms heartbeat ----
  setMask(next) {
    if (next === this.mask) return;
    this.mask = next;
    this.send({ t: 'k', b: next, s: ++this.seq, c: performance.now() });
    if (next && !this.heartbeat) {
      this.heartbeat = setInterval(() => this.send({ t: 'h', s: ++this.seq, c: performance.now() }), HEARTBEAT_MS);
    }
    if (!next) this.stopHeartbeat();
    this.emit();
  }
  stopHeartbeat() { clearInterval(this.heartbeat); this.heartbeat = null; }

  onKeyDown(e) {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;  // 닉네임 입력 중
    if (e.code === 'Enter' && !e.repeat && this.game.s === 'ready') { this.sendStart(); return; }
    if (e.code === 'KeyG' && !e.repeat) { this.debug = !this.debug; this.emit(); return; }
    const bit = KEY_BITS[e.code];
    if (!bit) return;
    e.preventDefault();
    if (!e.repeat) this.setMask(this.mask | bit);
  }
  onKeyUp(e) {
    const bit = KEY_BITS[e.code];
    if (bit) this.setMask(this.mask & ~bit);
  }

  // ---- /ws/video ----
  connectVideo() {
    const v = new WebSocket(wsUrl('/ws/video'));
    v.binaryType = 'arraybuffer';
    this.wsVideo = v;
    v.onmessage = (e) => {
      this.vs.bytes += e.data.byteLength;
      if (this.pending) this.vs.dropped++;
      this.pending = e.data;  // 디코딩 중에 온 프레임은 최신 1장만 남긴다
      if (!this.decoding) this.decodeLatest();
    };
    v.onclose = () => { if (!this.stopped) setTimeout(() => this.connectVideo(), 1000); };
  }

  async decodeLatest() {
    this.decoding = true;
    while (this.pending && !this.stopped) {
      const buf = this.pending; this.pending = null;
      const dv = new DataView(buf);
      const meta = {
        seq: dv.getUint32(4, true),
        stamp: dv.getFloat64(8, true),
        pose: dv.getUint8(1) & FLAG_POSE ? Array.from({ length: 7 }, (_, i) => dv.getFloat32(16 + 4 * i, true)) : null,
      };
      try {
        const bmp = await createImageBitmap(new Blob([new Uint8Array(buf, HEADER)], { type: 'image/jpeg' }));
        this.drawFrame(bmp, meta);
        bmp.close();
      } catch (err) { console.warn('JPEG 디코딩 실패', err); }
    }
    this.decoding = false;
  }

  drawFrame(bmp, meta) {
    const video = this.video, g = this.vctx, dpr = devicePixelRatio || 1;
    const W = Math.round(video.clientWidth * dpr), H = Math.round(video.clientHeight * dpr);
    if (video.width !== W || video.height !== H) { video.width = W; video.height = H; }
    // 비율 유지(contain): AR 좌표 변환에 같은 배율·오프셋을 쓴다
    const k = Math.min(W / bmp.width, H / bmp.height);
    const dw = bmp.width * k, dh = bmp.height * k, dx = (W - dw) / 2, dy = (H - dh) / 2;
    g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
    g.drawImage(bmp, dx, dy, dw, dh);
    const firstFrame = !this.lastFrame;
    this.lastFrame = { ...meta, w: bmp.width, h: bmp.height, k, dx, dy };
    if (meta.pose && this.session) this.drawAR(this.lastFrame);
    if (this.pendingGone.size) this.reportGone();
    this.vs.frames++;
    if (!meta.pose) this.vs.noPose++;
    if (this.clockOffset != null) this.vs.lat.push(Date.now() + this.clockOffset - meta.stamp * 1000);
    if (firstFrame) this.emit();
  }

  // ---- AR ----
  // 바닥 점 하나를 화면에 놓을 수 있으면 {X, Y, pxPerM, dist} (canvas px), 벽 뒤·카메라 뒤·화면 밖이면 null
  placeOnFloor(f, x, y) {
    if (this.occluded(f.pose[0], f.pose[1], x, y)) return null;
    const pc = mapToCamera(f.pose, [x, y, 0]);
    if (pc[2] <= 0.05) return null;
    const cam = this.session.cam, [u, v] = cameraToPixel(cam, f, pc);
    if (u < 0 || u >= f.w || v < 0 || v >= f.h) return null;
    return { X: f.dx + u * f.k, Y: f.dy + v * f.k, pxPerM: cam.fx * (f.w / cam.w) / pc[2] * f.k, dist: Math.hypot(pc[0], pc[2]) };
  }

  drawAR(f) {
    const items = [];
    for (const cd of this.session.candies) {
      if (this.collected.has(cd.id)) continue;
      const p = this.placeOnFloor(f, cd.x, cd.y);
      if (p) items.push({ kind: 'candy', id: cd.id, ...p, r: Math.min(ICON_MAX, Math.max(ICON_MIN, p.pxPerM * CANDY_R)) });
    }
    if (this.allCollected() && this.gate.op == null) this.drawGateZone(f);
    const gp = this.placeOnFloor(f, this.session.gate.x, this.session.gate.y);  // 탈출문은 항상 (잠김/열림)
    if (gp) items.push({ kind: 'gate', id: 'gate', ...gp });
    items.sort((a, b) => b.dist - a.dist);  // 먼 것부터 그려 가까운 것이 위에 오게
    const t = performance.now() / 1000;
    for (const it of items) it.kind === 'gate' ? this.drawGate(it, t) : this.drawCandy(it, t);
  }

  gateFront() {
    const g = this.session.gate, yaw = g.yaw ?? 0;
    return [g.x + g.front * Math.cos(yaw), g.y + g.front * Math.sin(yaw)];
  }

  // 문 앞 구역: 바닥에 빛나는 고리 + 머문 시간만큼 채워지는 호
  drawGateZone(f) {
    const [fx, fy] = this.gateFront(), R = this.session.gate.zoneR, N = 40, g = this.vctx;
    if (this.occluded(f.pose[0], f.pose[1], fx, fy)) return;
    const cam = this.session.cam, yaw = this.session.gate.yaw ?? 0;
    const pts = [];
    for (let i = 0; i <= N; i++) {
      const a = yaw + Math.PI + 2 * Math.PI * i / N;  // 문 반대쪽(다가오는 쪽)에서 시작
      const pc = mapToCamera(f.pose, [fx + R * Math.cos(a), fy + R * Math.sin(a), 0]);
      if (pc[2] <= 0.05) { pts.push(null); continue; }
      const [u, v] = cameraToPixel(cam, f, pc);
      pts.push([f.dx + u * f.k, f.dy + v * f.k]);
    }
    const stroke = (to, style, width) => {
      g.strokeStyle = style; g.lineWidth = width; g.beginPath();
      let pen = false;
      for (let i = 0; i <= to; i++) {
        const p = pts[i];
        if (!p) { pen = false; continue; }
        if (pen) g.lineTo(p[0], p[1]); else g.moveTo(p[0], p[1]);
        pen = true;
      }
      g.stroke();
    };
    const dpr = devicePixelRatio || 1, pulse = 0.5 + 0.5 * Math.sin(performance.now() / 250);
    g.save();
    g.shadowColor = 'rgba(190,120,255,.9)'; g.shadowBlur = 14 * dpr;
    stroke(N, `rgba(190,120,255,${0.45 + 0.35 * pulse})`, 3 * dpr);
    const prog = this.dwellProgress();
    if (prog > 0) { g.shadowColor = 'rgba(255,190,80,.9)'; stroke(Math.round(N * prog), '#ffc56b', 7 * dpr); }
    g.restore();
  }

  // 바닥 점(X, Y)에 그림자를 깔고, 그 위에 사탕을 띄운다
  drawCandy({ id, X, Y, r, dist }, t) {
    const g = this.vctx;
    const phase = id.charCodeAt(id.length - 1);         // 사탕마다 움직임이 어긋나게
    const bob = (Math.sin(t * 2.2 + phase) + 1) / 2;
    const bodyR = r * 0.7, cy = Y - r * (0.9 + 0.35 * bob);
    g.save();
    const sw = r * (1.15 - 0.25 * bob), sh = sw * 0.32;
    const sg = g.createRadialGradient(X, Y, 0, X, Y, sw);
    sg.addColorStop(0, `rgba(0,0,0,${0.55 - 0.2 * bob})`); sg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = sg; g.beginPath(); g.ellipse(X, Y, sw, sh, 0, 0, 7); g.fill();
    const k = bodyR / BODY;
    g.translate(X, cy);
    g.rotate(Math.sin(t * 1.3 + phase) * 0.18);
    g.drawImage(candySprite, -SPRITE / 2 * k, -SPRITE / 2 * k, SPRITE * k, SPRITE * k);
    g.restore();
    this.arLabel(`${id} ${dist.toFixed(1)}m`, X, cy - bodyR * 1.9, r);
  }

  drawGate({ X, Y, pxPerM, dist }, t) {
    const g = this.vctx, open = gateOpenness(this.gateOpenAt);
    const w = Math.min(600, Math.max(18, pxPerM * GATE_W)), h = w * GH / GW;
    g.save();
    const sg = g.createRadialGradient(X, Y, 0, X, Y, w * 0.7);
    sg.addColorStop(0, open > 0 ? `rgba(255,160,40,${0.5 * open})` : 'rgba(0,0,0,.45)');
    sg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = sg; g.beginPath(); g.ellipse(X, Y, w * 0.7, w * 0.2, 0, 0, 7); g.fill();
    g.translate(X - w / 2, Y - h); g.scale(w / GW, h / GH);
    renderGate(g, open, t, this.session.candies.map((c) => c.id), this.collected);
    g.restore();
    this.arLabel(`탈출문${open < 1 ? '(잠김)' : ''} ${dist.toFixed(1)}m`, X, Y - h - 6, w / 3);
  }

  arLabel(text, X, Y, r) {
    if (!this.debug) return;
    const g = this.vctx;
    g.save();
    g.font = `${Math.max(11, Math.min(18, r * 0.45))}px monospace`;
    g.textAlign = 'center';
    g.fillStyle = 'rgba(0,0,0,.6)'; g.fillText(text, X + 1, Y + 1);
    g.fillStyle = '#fff'; g.fillText(text, X, Y);
    g.restore();
  }

  // ---- 획득 측정: 서버 판정 → 수신 → 화면에서 사라짐 ----
  reportGone() {
    const now = Date.now(), off = this.clockOffset ?? 0;
    for (const [id, e] of this.pendingGone) {
      const rx = e.rx + off - e.ts, gone = now + off - e.ts;
      console.log(`[획득] ${id} 판정→수신 ${rx.toFixed(0)} ms, 판정→화면에서 사라짐 ${gone.toFixed(0)} ms`);
      this.send({ t: 'cdlog', id, rx: Math.round(rx), gone: Math.round(gone) });
      this.pick = { id, rx: Math.round(rx), gone: Math.round(gone) };
    }
    this.pendingGone.clear();
    this.emit();
  }

  // ---- 미니맵: 점유 격자로 바탕을 한 번만 그리고, 위치만 5 Hz로 덧그린다 ----
  buildMinimapBase() {
    const m = this.session.map, dpr = devicePixelRatio || 1, c = this.minimap;
    c.style.height = `${Math.round(MINI_W * m.h / m.w)}px`;
    c.width = Math.round(MINI_W * dpr); c.height = Math.round(MINI_W * m.h / m.w * dpr);
    const base = document.createElement('canvas');
    base.width = c.width; base.height = c.height;
    const g = base.getContext('2d'), k = c.width / m.w;
    g.fillStyle = '#1a1526'; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = '#c9b8ff';
    for (let r = 0; r < m.h; r++) {
      for (let col = 0; col < m.w; col++) if (this.occ[r * m.w + col]) g.fillRect(col * k, r * k, Math.ceil(k), Math.ceil(k));
    }
    this.miniBase = base;
  }

  drawMinimap() {
    if (!this.session || !this.miniBase) return;
    const c = this.minimap, g = c.getContext('2d'), m = this.session.map, dpr = devicePixelRatio || 1;
    const k = c.width / m.w;
    const toC = (x, y) => [(x - m.ox) / m.res * k, c.height - (y - m.oy) / m.res * k];
    g.drawImage(this.miniBase, 0, 0);
    for (const cd of this.session.candies) {           // 남은 사탕
      if (this.collected.has(cd.id)) continue;
      const [u, v] = toC(cd.x, cd.y);
      g.drawImage(candySprite, u - 14 * dpr, v - 14 * dpr, 28 * dpr, 28 * dpr);
    }
    if (this.allCollected() && this.gate.op == null) { // 문 앞 구역
      const [fx, fy] = this.gateFront(), [u, v] = toC(fx, fy), r = this.session.gate.zoneR / m.res * k;
      g.strokeStyle = '#c084fc'; g.lineWidth = 1.5 * dpr; g.setLineDash([3 * dpr, 2 * dpr]);
      g.beginPath(); g.arc(u, v, r, 0, 7); g.stroke(); g.setLineDash([]);
    }
    {                                                  // 탈출문: 잠김 / 열림
      const [u, v] = toC(this.session.gate.x, this.session.gate.y), w = 20 * dpr, h = w * GH / GW;
      g.save(); g.translate(u - w / 2, v - h / 2); g.scale(w / GW, h / GH);
      renderGate(g, gateOpenness(this.gateOpenAt), performance.now() / 1000, this.session.candies.map((cd) => cd.id), this.collected);
      g.restore();
    }
    if (this.boo) {                                    // 부우: 하얀 유령
      const [u, v] = toC(this.boo[0], this.boo[1]), r = 6 * dpr;
      g.fillStyle = '#f4f4ff';
      g.beginPath(); g.arc(u, v - r * 0.2, r, Math.PI, 0); g.lineTo(u + r, v + r * 0.9);
      for (let i = 0; i < 3; i++) g.lineTo(u + r - (i + 0.5) * (2 * r / 3), v + r * (i % 2 ? 0.9 : 0.5));
      g.lineTo(u - r, v + r * 0.9); g.closePath(); g.fill();
      g.fillStyle = '#222';
      g.beginPath(); g.arc(u - r * 0.35, v - r * 0.2, r * 0.18, 0, 7); g.arc(u + r * 0.35, v - r * 0.2, r * 0.18, 0, 7); g.fill();
    }
    if (this.pose) {                                   // 나(펌킨): 주황 원 + 바라보는 방향
      const [u, v] = toC(this.pose[0], this.pose[1]), yaw = this.pose[2], r = 6 * dpr;
      g.strokeStyle = '#ffb347'; g.lineWidth = 2 * dpr;
      g.beginPath(); g.moveTo(u, v); g.lineTo(u + 2.3 * r * Math.cos(yaw), v - 2.3 * r * Math.sin(yaw)); g.stroke();
      g.fillStyle = '#ff7a00'; g.beginPath(); g.arc(u, v, r, 0, 7); g.fill();
      g.strokeStyle = '#fff'; g.lineWidth = 1.5 * dpr; g.stroke();
    }
  }

  // ---- 개발용 수치 (G) ----
  updateStats() {
    const vs = this.vs, gs = this.gs;
    const lat = vs.lat.length ? vs.lat.reduce((a, b) => a + b) / vs.lat.length : null;
    const vk = vs.bytes * 8 / 1000, gk = gs.bytes * 8 / 1000;
    const lines = [
      this.busy ? '다른 탭이 조작 중 — 이 탭에서 키를 누르면 가져옴'
        : this.rtt == null ? '입력 RTT —' : `입력 RTT ${this.rtt.toFixed(0)} ms`,
      `영상 ${vs.frames} fps  ${vk.toFixed(0)} kbps  지연 ${lat == null ? '—' : `${lat.toFixed(0)} ms`}` +
        (vs.dropped ? `  건너뜀 ${vs.dropped}` : '') + (vs.noPose ? `  포즈 없음 ${vs.noPose}` : '') +
        (this.lastFrame ? `  ${this.lastFrame.w}×${this.lastFrame.h}` : ''),
      `게임 ${gs.msgs} msg/s  ${gk.toFixed(1)} kbps   합계 ${(vk + gk).toFixed(0)} kbps`,
    ];
    this.statsBad = (lat != null && lat > 500) || vk > 2000 || (this.rtt ?? 0) > 300 || this.busy;
    this.stats = lines.join('\n');
    Object.assign(vs, { frames: 0, bytes: 0, dropped: 0, lat: [], noPose: 0 });
    Object.assign(gs, { bytes: 0, msgs: 0 });
    if (this.debug) this.emit();
  }
}
