// 사탕·탈출문 그림. 처음 한 번만 offscreen canvas에 그려 두고 프레임마다 크기만 바꿔 찍는다.

// ---- 사탕 스프라이트: 한 번만 그려 두고 프레임마다 크기만 바꿔 찍는다 ----
export const SPRITE = 256, BODY = 0.25 * SPRITE;   // 스프라이트 크기, 그 안의 몸통 반지름
export const candySprite = (() => {
  const c = document.createElement('canvas');
  c.width = c.height = SPRITE;
  const g = c.getContext('2d'), m = SPRITE / 2;

  // 달빛 사탕 후광
  const glow = g.createRadialGradient(m, m, BODY * 0.6, m, m, SPRITE * 0.5);
  glow.addColorStop(0, 'rgba(255,214,120,.55)');
  glow.addColorStop(1, 'rgba(255,214,120,0)');
  g.fillStyle = glow; g.fillRect(0, 0, SPRITE, SPRITE);

  // 양쪽 포장지: 몸통에서 퍼지는 부채꼴 + 주름
  for (const s of [-1, 1]) {
    const x0 = m + s * BODY * 0.75, x1 = m + s * BODY * 1.85;
    const wrap = g.createLinearGradient(x0, 0, x1, 0);
    wrap.addColorStop(0, '#c2410c'); wrap.addColorStop(0.45, '#fb923c'); wrap.addColorStop(1, '#fdba74');
    g.fillStyle = wrap;
    g.beginPath();
    g.moveTo(x0, m - BODY * 0.22);
    g.quadraticCurveTo(m + s * BODY * 1.3, m - BODY * 0.35, x1, m - BODY * 0.78);
    g.quadraticCurveTo(m + s * BODY * 1.62, m, x1, m + BODY * 0.78);
    g.quadraticCurveTo(m + s * BODY * 1.3, m + BODY * 0.35, x0, m + BODY * 0.22);
    g.closePath(); g.fill();
    g.strokeStyle = 'rgba(124,45,18,.45)'; g.lineWidth = SPRITE * 0.008;
    for (const k of [-0.5, -0.2, 0.15, 0.45]) {
      g.beginPath();
      g.moveTo(m + s * BODY * 0.95, m + k * BODY * 0.35);
      g.lineTo(m + s * BODY * 1.75, m + k * BODY * 1.5);
      g.stroke();
    }
    // 매듭 (몸통과 포장지 사이 조여진 부분)
    g.fillStyle = '#9a3412';
    g.beginPath(); g.ellipse(m + s * BODY * 0.92, m, BODY * 0.12, BODY * 0.28, 0, 0, 7); g.fill();
  }

  // 몸통: 왼쪽 위에서 빛을 받는 구
  const body = g.createRadialGradient(m - BODY * 0.35, m - BODY * 0.4, BODY * 0.1, m, m, BODY);
  body.addColorStop(0, '#ffe7a3'); body.addColorStop(0.35, '#ff9f1c');
  body.addColorStop(0.8, '#e2550f'); body.addColorStop(1, '#8a2c06');
  g.fillStyle = body;
  g.beginPath(); g.arc(m, m, BODY, 0, 7); g.fill();

  // 소용돌이 줄무늬 (몸통 안쪽으로 잘라 그림)
  g.save();
  g.beginPath(); g.arc(m, m, BODY, 0, 7); g.clip();
  g.strokeStyle = 'rgba(255,250,240,.9)'; g.lineWidth = BODY * 0.2; g.lineCap = 'round';
  for (let k = 0; k < 3; k++) {
    g.beginPath();
    for (let t = 0; t <= 1.001; t += 0.04) {
      const ang = k * 2.094 + t * 3.6, rr = BODY * (0.08 + 0.95 * t);
      const x = m + rr * Math.cos(ang), y = m + rr * Math.sin(ang);
      t === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.stroke();
  }
  // 줄무늬 위에 다시 음영을 얹어 둥글게 보이게
  const shade = g.createRadialGradient(m - BODY * 0.3, m - BODY * 0.35, BODY * 0.2, m, m, BODY * 1.02);
  shade.addColorStop(0, 'rgba(0,0,0,0)'); shade.addColorStop(0.7, 'rgba(60,20,0,.15)');
  shade.addColorStop(1, 'rgba(60,20,0,.55)');
  g.fillStyle = shade; g.fillRect(m - BODY, m - BODY, BODY * 2, BODY * 2);
  g.restore();

  // 반사광과 아래쪽 테두리 빛
  const spec = g.createRadialGradient(m - BODY * 0.38, m - BODY * 0.45, 0, m - BODY * 0.38, m - BODY * 0.45, BODY * 0.42);
  spec.addColorStop(0, 'rgba(255,255,255,.95)'); spec.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = spec;
  g.beginPath(); g.ellipse(m - BODY * 0.38, m - BODY * 0.45, BODY * 0.42, BODY * 0.28, -0.6, 0, 7); g.fill();
  g.strokeStyle = 'rgba(255,220,160,.5)'; g.lineWidth = BODY * 0.06;
  g.beginPath(); g.arc(m, m, BODY * 0.93, 0.3, 1.9); g.stroke();
  return c;
})();

// ---- 탈출문: 처음엔 잠긴 문, 사탕을 다 모으면 양쪽 문짝이 열린다 ----
// 층을 나눠 한 번만 그려 두고(틀·빛·문짝 두 장), 그릴 때 열린 정도(0~1)에 맞춰 합친다
export const GW = 256, GH = 320;                                  // 탈출문 스프라이트 크기
export const G_IN = GW * 0.07;                                    // 틀 두께
export const G_X0 = GW * 0.18 + G_IN, G_X1 = GW * 0.82 - G_IN;    // 안쪽(문짝) 좌우 끝 = 경첩 위치
export const GATE_OPEN_MS = 1200;                                 // 문 열리는 시간

function gateArch(g, inset) {
  const x0 = GW * 0.18 + inset, x1 = GW * 0.82 - inset, top = GH * 0.2 + inset, bot = GH * 0.98;
  g.beginPath();
  g.moveTo(x0, bot); g.lineTo(x0, top + (x1 - x0) / 2);
  g.arc(GW / 2, top + (x1 - x0) / 2, (x1 - x0) / 2, Math.PI, 0);
  g.lineTo(x1, bot); g.closePath();
}
function gateLayer(draw) {
  const c = document.createElement('canvas');
  c.width = GW; c.height = GH;
  draw(c.getContext('2d'));
  return c;
}
const GATE = {
  // 틀 + 어두운 안쪽
  frame: gateLayer(g => {
    const frame = g.createLinearGradient(0, 0, GW, 0);
    frame.addColorStop(0, '#3b1d5c'); frame.addColorStop(0.5, '#7c3aed'); frame.addColorStop(1, '#3b1d5c');
    g.fillStyle = frame; gateArch(g, 0); g.fill();
    g.fillStyle = '#120a1c'; gateArch(g, G_IN); g.fill();
  }),
  // 열렸을 때 보이는 축제의 빛 + 호박 얼굴
  light: gateLayer(g => {
    const inside = g.createLinearGradient(0, GH * 0.3, 0, GH);
    inside.addColorStop(0, '#fff3c4'); inside.addColorStop(0.5, '#ffb347'); inside.addColorStop(1, '#ff7a00');
    g.fillStyle = inside; gateArch(g, G_IN); g.fill();
    g.fillStyle = 'rgba(120,40,0,.75)';
    const fx = GW / 2, fy = GH * 0.6;
    for (const s of [-1, 1]) {
      g.beginPath(); g.moveTo(fx + s * 34, fy - 26); g.lineTo(fx + s * 14, fy - 6); g.lineTo(fx + s * 48, fy - 6); g.closePath(); g.fill();
    }
    g.beginPath(); g.moveTo(fx - 46, fy + 18);
    for (let i = 0; i <= 6; i++) g.lineTo(fx - 46 + i * 15.3, fy + 18 + (i % 2 ? 14 : 0));
    g.lineTo(fx + 46, fy + 34); g.lineTo(fx - 46, fy + 34); g.closePath(); g.fill();
  }),
  // 뒤에서 번지는 보랏빛 (열렸을 때만)
  glow: gateLayer(g => {
    const glow = g.createRadialGradient(GW / 2, GH * 0.55, 10, GW / 2, GH * 0.55, GW * 0.62);
    glow.addColorStop(0, 'rgba(190,120,255,.6)'); glow.addColorStop(1, 'rgba(190,120,255,0)');
    g.fillStyle = glow; g.fillRect(0, 0, GW, GH);
  }),
};
// 나무 문짝 (side −1 = 왼쪽, +1 = 오른쪽). 안쪽 아치를 반으로 잘라 그린다
for (const side of [-1, 1]) {
  GATE[side < 0 ? 'left' : 'right'] = gateLayer(g => {
    g.save();
    gateArch(g, G_IN); g.clip();
    g.beginPath(); side < 0 ? g.rect(0, 0, GW / 2, GH) : g.rect(GW / 2, 0, GW / 2, GH); g.clip();
    const wood = g.createLinearGradient(side < 0 ? G_X0 : GW / 2, 0, side < 0 ? GW / 2 : G_X1, 0);
    wood.addColorStop(0, side < 0 ? '#4a2a17' : '#6b3f22'); wood.addColorStop(1, side < 0 ? '#6b3f22' : '#4a2a17');
    g.fillStyle = wood; g.fillRect(0, 0, GW, GH);
    g.strokeStyle = 'rgba(30,14,6,.7)'; g.lineWidth = 2;               // 판자 이음매
    for (let x = G_X0; x < G_X1; x += (G_X1 - G_X0) / 6) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, GH); g.stroke(); }
    g.fillStyle = '#2b2b33';                                            // 쇠띠
    for (const y of [GH * 0.45, GH * 0.82]) g.fillRect(0, y, GW, 9);
    g.fillStyle = '#8a8a99';
    for (const y of [GH * 0.45, GH * 0.82])
      for (let x = G_X0 + 8; x < G_X1; x += 18) { g.beginPath(); g.arc(x, y + 4.5, 2, 0, 7); g.fill(); }
    g.restore();
    g.strokeStyle = '#1a0d05'; g.lineWidth = 3;                         // 가운데 맞닿는 선
    g.beginPath(); g.moveTo(GW / 2, GH * 0.3); g.lineTo(GW / 2, GH * 0.98); g.stroke();
  });
}

// 열리기 시작한 시각(performance.now 기준) → 열린 정도 0~1 (ease-out)
export function gateOpenness(openAt) {
  if (openAt == null) return 0;
  const x = Math.min(1, Math.max(0, (performance.now() - openAt) / GATE_OPEN_MS));
  return 1 - (1 - x) ** 3;
}
// 스프라이트 좌표계에서 탈출문을 합쳐 그린다. 화면 쪽은 호출하는 곳에서 이동·배율을 맞춘다
export function renderGate(g, open, t, candyIds, collected) {
  if (open > 0) { g.globalAlpha = open; g.drawImage(GATE.glow, 0, 0); g.globalAlpha = 1; }
  g.drawImage(GATE.frame, 0, 0);
  if (open > 0) { g.globalAlpha = open; g.drawImage(GATE.light, 0, 0); g.globalAlpha = 1; }
  // 문짝: 경첩을 축으로 가로 폭을 줄여 안쪽으로 젖혀지는 것처럼 보이게
  const squeeze = 1 - 0.9 * open;
  for (const [leaf, hinge] of [[GATE.left, G_X0], [GATE.right, G_X1]]) {
    g.save();
    g.translate(hinge, 0); g.scale(squeeze, 1); g.translate(-hinge, 0);
    g.globalAlpha = 1 - 0.3 * open;
    g.drawImage(leaf, 0, 0);
    g.restore();
  }
  // 자물쇠: 열리면서 사라진다
  if (open < 1) {
    g.save();
    g.globalAlpha = 1 - open;
    g.translate(GW / 2, GH * 0.62 + open * 30);
    g.strokeStyle = '#c9a227'; g.lineWidth = 7;
    g.beginPath(); g.arc(0, -14, 13, Math.PI, 0); g.stroke();
    const body = g.createLinearGradient(0, -14, 0, 22);
    body.addColorStop(0, '#f5d76e'); body.addColorStop(1, '#a37c12');
    g.fillStyle = body; g.fillRect(-20, -14, 40, 34);
    g.fillStyle = '#3a2a05'; g.beginPath(); g.arc(0, 0, 4.5, 0, 7); g.fill(); g.fillRect(-2, 0, 4, 10);
    g.restore();
  }
  // 사탕 홈 3칸 (틀 위쪽): 먹은 사탕마다 불이 들어온다
  const n = candyIds.length;
  candyIds.forEach((id, i) => {
    const x = GW / 2 + (i - (n - 1) / 2) * 38, y = GH * 0.315, on = collected.has(id);
    g.fillStyle = on ? 'rgba(255,200,90,.35)' : '#0b0612';
    g.beginPath(); g.arc(x, y, 15, 0, 7); g.fill();
    g.strokeStyle = on ? '#ffd27a' : '#5b3d82'; g.lineWidth = 3; g.stroke();
    if (on) g.drawImage(candySprite, x - 30, y - 30, 60, 60);
  });
  // EXIT 글자: 잠겨 있을 땐 어둡게
  g.save();
  g.font = 'bold 34px system-ui'; g.textAlign = 'center';
  g.fillStyle = open > 0 ? '#fff' : '#8f7fb0';
  if (open > 0) { g.shadowColor = 'rgba(160,80,255,.9)'; g.shadowBlur = 12 + 6 * Math.sin(t * 3); }
  g.fillText('EXIT', GW / 2, GH * 0.17);
  g.restore();
}
