// 막대 경주 릴스 그리기 (agent/racereel.py가 P(계획)·C(색)를 넣고 rcInit() 뒤 프레임마다 rcFrame(t)를 부른다).
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const SIDE = P.safe.side, RAIL = P.safe.rail;
const BHS = '"Black Han Sans"';
const TITLE_Y = 362, TITLE_LH = 76, TITLE_PX = 64;
const CTA_Y = 506, BASIS_Y = 556;
const AREA0 = 596, AREA1 = 1124;
const NAME_W = 190, BAR_X = SIDE + NAME_W + 12;
const TICK_Y = 1236, TICK_PX = 104;
const N = P.ser.length;
const PITCH = Math.min(92, (AREA1 - AREA0) / N);
const BAR_H = Math.round(PITCH * 0.7);
const VAL_PX = Math.min(36, Math.round(BAR_H * 0.62));
let BARMAX = 500;

function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function ease(x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
function easeIO(x) { x = clamp(x, 0, 1); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
function lerp(a, b, q) { return a + (b - a) * q; }
function slam(dt) {               // 1.3배에서 쾅 박힘
  if (dt < 0) return 0;
  if (dt < 0.12) return 1.3 - 0.35 * (dt / 0.12);
  if (dt < 0.24) return 0.95 + 0.05 * ((dt - 0.12) / 0.12);
  return 1;
}
function font(px, bhs, w) { return bhs ? `${px}px ${BHS}` : `${w || 700} ${px}px Wanted`; }
function text(s, x, y, px, color, opt) {
  opt = opt || {};
  g.font = font(px, opt.bhs, opt.w);
  g.fillStyle = color;
  g.textAlign = opt.align || 'left';
  g.textBaseline = 'alphabetic';
  const a0 = g.globalAlpha;
  g.globalAlpha = a0 * (opt.alpha === undefined ? 1 : opt.alpha);
  g.shadowColor = 'rgba(0,0,0,0.75)'; g.shadowBlur = 10;   // 사진 위에서 읽히게
  g.fillText(s, x, y);
  g.shadowBlur = 0; g.shadowColor = 'transparent';
  g.globalAlpha = a0;
}
function width(s, px, bhs, w) { g.font = font(px, bhs, w); return g.measureText(s).width; }
function lum(hex) {
  const n = parseInt(hex.slice(1), 16);
  return (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255;
}

// 값 표기 (racereel.py fmt_value와 같은 규칙)
function fmtValue(v) {
  if (P.fmt === 'people_m') {
    if (v >= 100) return `${+(v / 100).toFixed(1)}억 명`;
    return `${Math.round(v * 100).toLocaleString('en-US')}만 명`;
  }
  const eok = v * 10;
  if (eok >= 10000) {
    const r = Math.round(eok), jo = Math.floor(r / 10000), rest = r % 10000;
    return rest ? `${jo}조 ${rest.toLocaleString('en-US')}억 달러` : `${jo}조 달러`;
  }
  if (eok < 10) return `${+eok.toFixed(1)}억 달러`;
  return `${Math.round(eok).toLocaleString('en-US')}억 달러`;
}
function valueW(i, v) {
  const s = P.ser[i];
  return width(fmtValue(v), VAL_PX, true) + (s.tag ? 10 + width(s.tag, Math.round(VAL_PX * 0.66), false, 700) : 0);
}

// 발표가 나온 시각에만 값이 바뀌고, TWEEN초 동안 부드럽게 늘어난다
function cur(i, t) {
  const pts = P.ser[i].pts;
  let k = -1;
  for (let j = 0; j < pts.length; j++) if (pts[j].t <= t) k = j;
  if (k < 0) return null;
  const q = pts[k].t === 0 ? 1 : easeIO((t - pts[k].t) / P.tween);
  const prev = k > 0 ? pts[k - 1].v : 0;
  return { v: lerp(prev, pts[k].v, q), q, k, alpha: k === 0 && pts[0].t > 0 ? ease((t - pts[0].t) / 0.3) : 1 };
}
function rankAt(i, t) {
  const a = cur(i, t);
  if (!a) return N;
  let r = 0;
  for (let j = 0; j < N; j++) {
    if (j === i) continue;
    const b = cur(j, t);
    if (b && (b.v > a.v || (b.v === a.v && j < i))) r++;
  }
  return r;
}
function smoothRank(i, t) {         // 막대가 미끄러지며 자리를 바꾼다 (0.25초, 양끝 부드럽게)
  let s = 0, wsum = 0;
  for (let k = 0; k < 12; k++) {
    const w = Math.sin(Math.PI * (k + 0.5) / 12);
    const tt = Math.max(0, t - k * 0.021);
    // 새로 들어오는 막대는 아래에서 올라오지 않고 제자리에서 나타난다 (질문 글자를 가로지르지 않게)
    const r = cur(i, tt) ? rankAt(i, tt) : rankAt(i, P.ser[i].pts[0].t + P.tween + 0.01);
    s += w * r; wsum += w;
  }
  return s / wsum;
}
function axisMax(t) {
  let m = 0;
  for (let i = 0; i < N; i++) { const c = cur(i, t); if (c) m = Math.max(m, c.v); }
  return m || 1;
}

function dateAt(t) {
  const K = P.keys;
  let days = K[K.length - 1][1];
  for (let i = 0; i < K.length - 1; i++) {
    if (t < K[i + 1][0]) { days = lerp(K[i][1], K[i + 1][1], (t - K[i][0]) / (K[i + 1][0] - K[i][0])); break; }
  }
  if (t < K[0][0]) days = K[0][1];
  const d = new Date(Date.UTC(P.start[0], P.start[1] - 1, P.start[2]) + days * 86400000);
  return `${d.getUTCFullYear()}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

const IMPACTS = [0.0, P.race_end + 0.05].concat(P.rehook_t ? [P.rehook_t] : []);
function shake(t) {
  let x = 0, y = 0;
  for (const s of IMPACTS.concat(P.overtakes.map(o => o.t + 0.12))) {
    const d = t - s;
    const big = IMPACTS.includes(s) ? 13 : 6;
    if (d >= 0 && d < 0.4) { const a = big * Math.exp(-d * 12); x += a * Math.sin(d * 83); y += a * 0.6 * Math.cos(d * 71); }
  }
  return [x, y];
}

function drawHL(ln, cx, y, px) {
  const hl = P.hl && ln.includes(P.hl) ? P.hl : '';
  const parts = hl ? [ln.slice(0, ln.indexOf(hl)), hl, ln.slice(ln.indexOf(hl) + hl.length)] : [ln];
  const total = width(ln, px, true);
  let x = cx - total / 2;
  parts.forEach((s, k) => {
    if (!s) return;
    text(s, x, y, px, (hl && k === 1) ? C.accent : C.text, { bhs: true });
    x += width(s, px, true);
  });
}
function drawTitle(t) {
  P.title.forEach((ln, i) => {
    const st = i * 0.25;
    if (t < st) return;
    const sc = slam(t - st);
    const y = TITLE_Y + i * TITLE_LH;
    g.save(); g.translate(W / 2, y - TITLE_PX * 0.35); g.scale(sc, sc); g.translate(-W / 2, -(y - TITLE_PX * 0.35));
    drawHL(ln, W / 2, y, TITLE_PX);
    g.restore();
  });
  if (P.cta && t >= 0.5) text(P.cta, W / 2, CTA_Y, 34, C.accent, { w: 700, align: 'center', alpha: ease((t - 0.5) / 0.2) });
  if (P.basis) text(P.basis, W / 2, BASIS_Y, 24, C.muted, { w: 600, align: 'center' });
}

function drawBars(t) {
  const win = t >= P.race_end ? ease((t - P.race_end) / 0.35) : 0;
  const m = axisMax(t);
  const order = [];
  for (let i = 0; i < N; i++) { const c = cur(i, t); if (c) order.push([i, c]); }
  // 앞지르는 막대를 맨 위에 그린다
  const up = P.overtakes.filter(o => t - o.t >= 0 && t - o.t < 1).map(o => o.i);
  order.sort((a, b) => (up.includes(a[0]) ? 1 : 0) - (up.includes(b[0]) ? 1 : 0));
  order.forEach(([i, c]) => {
    const s = P.ser[i];
    const y = AREA0 + smoothRank(i, t) * PITCH;
    const isW = i === P.winner;
    const a = c.alpha * (isW ? 1 : 1 - 0.7 * win);
    g.globalAlpha = a;
    // 이름 (왼쪽 칸에 맞게 줄이고, 26px 아래로 가야 하면 띄어쓰기에서 두 줄)
    const nc = isW && win > 0 ? C.accent : C.text;
    const nl = nameLines(s.name);
    nl.lines.forEach((ln, j) => text(ln, SIDE, y + BAR_H / 2 + nl.px * 0.36 + (j - (nl.lines.length - 1) / 2) * nl.px * 1.05,
                                     nl.px, nc, { w: 700 }));
    // 막대: 회사 색 단색 직각. 끝 장면에서 1위는 녹색
    const len = Math.max(4, c.v / m * BARMAX);
    g.fillStyle = s.color; g.fillRect(BAR_X, y, len, BAR_H);
    if (isW && win > 0) { g.globalAlpha = a * win; g.fillStyle = C.accent; g.fillRect(BAR_X, y, len, BAR_H); g.globalAlpha = a; }
    // 순위가 오른 순간 번쩍
    for (const o of P.overtakes) {
      const d = t - o.t;
      if (o.i === i && d >= 0 && d < 0.55) {
        g.globalAlpha = a * 0.75 * (1 - d / 0.55); g.fillStyle = '#FFFFFF'; g.fillRect(BAR_X, y, len, BAR_H); g.globalAlpha = a;
      }
    }
    // 값 (바뀐 직후 살짝 튐)
    const pop = c.k > 0 && c.q < 1 ? 1 + 0.16 * Math.sin(Math.PI * c.q) : 1;
    const vx = BAR_X + len + 14, vy = y + BAR_H / 2 + VAL_PX * 0.36;
    g.save(); g.translate(vx, vy - VAL_PX * 0.35); g.scale(pop, pop); g.translate(-vx, -(vy - VAL_PX * 0.35));
    const vs = fmtValue(c.v);
    text(vs, vx, vy, VAL_PX, isW && win > 0 ? C.accent : C.text, { bhs: true });
    if (s.tag) text(s.tag, vx + width(vs, VAL_PX, true) + 10, vy, Math.round(VAL_PX * 0.66), C.muted, { w: 700 });
    g.restore();
    g.globalAlpha = 1;
  });
}

// 후킹 질문 (0~hook_until초): 막대 칸 아래 빈 자리에 크게. 끝 1위는 아직 보이지 않는다
function hookY() {
  let n = 0;
  for (let i = 0; i < N; i++) if (cur(i, P.hook_until)) n++;
  return Math.max(920, AREA0 + n * PITCH + 90);
}
function drawHook(t) {
  if (!P.hook.length || t >= P.hook_until) return;
  const a = t > P.hook_until - 0.3 ? 1 - ease((t - P.hook_until + 0.3) / 0.3) : 1;
  const y0 = hookY();
  P.hook.forEach((ln, i) => {
    const st = 0.15 + i * 0.25;
    if (t < st) return;
    const sc = slam(t - st) * (1 + 0.04 * Math.sin(t * 6));
    const y = y0 + i * 84;
    g.save(); g.globalAlpha = a; g.translate(W / 2, y - 25); g.scale(sc, sc); g.translate(-W / 2, -(y - 25));
    text(ln, W / 2, y, 74, i === P.hook.length - 1 ? C.accent : C.text, { bhs: true, align: 'center' });
    g.restore();
  });
}
// 두 번째 질문 (ask.from ~ 답): 날짜 옆에, 띠가 없을 때만. 박마다 살짝 뛴다
function drawAsk(t, tw) {
  const A = P.ask;
  if (!A || t < A.from || t >= A.to) return;
  if (P.overtakes.some(o => t - o.t >= 0 && t - o.t < 1.3)) return;
  const a = ease((t - A.from) / 0.2) * (t > A.to - 0.15 ? 1 - (t - A.to + 0.15) / 0.15 : 1);
  const x = SIDE + tw + 30;
  const px = askPx(tw);
  const sc = 1 + 0.05 * Math.max(0, Math.sin((t - A.from) * Math.PI * 2 / 0.5));
  A.lines.forEach((ln, i) => {
    const y = TICK_Y - 14 - (A.lines.length - 1 - i) * (px + 8);
    g.save(); g.translate(x, y - px * 0.35); g.scale(sc, sc); g.translate(-x, -(y - px * 0.35));
    text(ln, x, y, px, i === A.lines.length - 1 ? C.accent : C.text, { bhs: true, alpha: a });
    g.restore();
  });
}
function askPx(tw) {
  let px = 44;
  while (px > 28 && P.ask.lines.some(l => SIDE + tw + 30 + width(l, px, true) * 1.05 > RAIL - 8)) px -= 2;
  return px;
}

function drawTicker(t) {
  const out = t >= P.race_end ? 1 - ease((t - P.race_end) / 0.2) : 1;
  if (out > 0) {
    const ds = dateAt(Math.min(t, P.race_end));
    text(ds, SIDE, TICK_Y, TICK_PX, C.text, { bhs: true, alpha: out });
    // 1·2위로 올라선 순간: 날짜 옆 녹색 띠 (1.3초, 반전은 1.8초)
    const tw = width(ds, TICK_PX, true);
    drawAsk(t, tw);
    P.overtakes.forEach((o, k) => {
      const d = t - o.t;
      const nxt = k + 1 < P.overtakes.length ? P.overtakes[k + 1].t - o.t : 99;   // 다음 띠가 나오면 바로 비킨다
      const life = Math.min(o.rehook ? 1.8 : 1.3, nxt);
      if (d < 0 || d >= life) return;
      const q = ease(d / 0.15) * (d > life - 0.2 ? 1 - (d - life + 0.2) / 0.2 : 1);
      const px = labelPx(o.label, tw);
      const lw = width(o.label, px, true) + 28;
      const x = SIDE + tw + 26 - (1 - q) * 40;
      g.globalAlpha = q * out; g.fillStyle = C.accent; g.fillRect(x, TICK_Y - 66, lw, 76); g.globalAlpha = 1;
      text(o.label, x + 14, TICK_Y - 14, px, C.bg, { bhs: true, alpha: q * out });
    });
  }
  // 끝: punch 한 줄 쾅
  P.punch.forEach((ln, i) => {
    const st = P.race_end + 0.05 + i * 0.3;
    if (t < st || !ln) return;
    const sc = slam(t - st) * (1 + 0.03 * ease((t - st) / 3));
    const px = punchPx();
    const y = (P.punch.length > 1 ? TICK_Y - 64 : TICK_Y - 20) + i * (px + 12);
    g.save(); g.translate(SIDE, y - px * 0.35); g.scale(sc, sc); g.translate(-SIDE, -(y - px * 0.35));
    text(ln, SIDE, y, px, i === P.punch.length - 1 ? C.accent : C.text, { bhs: true });
    g.restore();
  });
}
function labelPx(label, tw) {
  let px = 44;
  while (px > 28 && SIDE + tw + 26 + width(label, px, true) + 28 > RAIL - 8) px -= 2;
  return px;
}
function punchPx() {
  let px = 58;
  while (px > 40 && P.punch.some(l => SIDE + width(l, px, true) * 1.04 > RAIL - 8)) px -= 2;
  return px;
}

function nameLines(name) {
  let px = 34;
  while (px > 26 && width(name, px, false, 700) > NAME_W) px -= 1;
  if (width(name, px, false, 700) <= NAME_W || !name.includes(' ')) {
    while (px > 18 && width(name, px, false, 700) > NAME_W) px -= 1;
    return { lines: [name], px };
  }
  const k = name.lastIndexOf(' ');
  const lines = [name.slice(0, k), name.slice(k + 1)];
  px = Math.min(30, Math.floor(BAR_H / 2.15));
  while (px > 18 && lines.some(l => width(l, px, false, 700) > NAME_W)) px -= 1;
  return { lines, px };
}

// ---------- 사진 배경 (STYLE_GUIDE 0장 원칙 0: 막대는 사진 위에) ----------
const IMG = {};
const SPOT = P.spot || [];
const DIM = 0.6;           // 사진 위 단색 어둡게 (그라데이션 없이)
function cover(im, x, y, w, h, fx, fy, zoom) {
  const s = Math.max(w / im.width, h / im.height) * zoom;
  const dw = im.width * s, dh = im.height * s;
  const ox = x + (w - dw) * fx / 100, oy = y + (h - dh) * fy / 100;
  g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
  g.drawImage(im, ox, oy, dw, dh);
  g.restore();
}
function drawPhoto(i, alpha, since) {
  const e = IMG[i];
  if (!e || alpha <= 0) return;
  g.globalAlpha = alpha;
  cover(e.im, 0, 0, W, H, e.x, e.y, 1.04 + 0.05 * clamp(since / 6, 0, 1));   // 천천히 다가감
  g.globalAlpha = alpha * Math.max(0, e.dim - DIM) / (1 - DIM);   // 밝은 화면 캡처는 더 어둡게 (아래 공통 DIM과 합쳐 e.dim)
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  g.globalAlpha = 1;
}
function drawBG(t) {
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const hookOn = P.hook_strip && P.hook_strip.length && P.hook.length && t < P.hook_until + 0.35;
  if (SPOT.length && t >= SPOT[0][0]) {
    let k = 0;
    for (let j = 0; j < SPOT.length; j++) if (SPOT[j][0] <= t) k = j;
    const q = ease((t - SPOT[k][0]) / 0.35);
    if (k > 0 && q < 1) drawPhoto(SPOT[k - 1][1], 1, t - SPOT[k - 1][0]);
    drawPhoto(SPOT[k][1], (k > 0 || hookOn) ? q : 1, t - SPOT[k][0]);
  }
  if (hookOn) {     // 후킹: 경쟁 회사 사진 세로 세 칸 (누가 1위일까?)
    const a = t < P.hook_until ? 1 : 1 - ease((t - P.hook_until) / 0.35);
    const n = P.hook_strip.length, sw = W / n;
    g.globalAlpha = a;
    P.hook_strip.forEach((i, j) => {
      const e = IMG[i];
      if (!e) return;
      cover(e.im, j * sw, 0, sw, H, e.x, e.y, 1.0 + 0.06 * clamp(t / 3, 0, 1));
      if (j > 0) { g.fillStyle = C.bg; g.fillRect(j * sw - 3, 0, 6, H); }
    });
    g.globalAlpha = 1;
  }
  g.globalAlpha = DIM; g.fillStyle = C.bg; g.fillRect(0, 0, W, H); g.globalAlpha = 1;
}

async function rcInit() {
  await Promise.all(Object.entries(P.imgs || {}).map(([k, v]) => new Promise(res => {
    const im = new Image(); im.onload = () => { IMG[+k] = { im, x: v.x, y: v.y, dim: v.dim === undefined ? DIM : v.dim }; res(); }; im.onerror = res; im.src = v.uri;
  })));
  // 막대 최대 길이: 가장 넓은 값 글자가 오른쪽 여백(W - SIDE) 안에 들어가게
  let vw = 0;
  P.ser.forEach((s, i) => s.pts.forEach(p => { vw = Math.max(vw, valueW(i, p.v)); }));
  BARMAX = Math.floor(W - SIDE - BAR_X - 14 - vw * 1.16);
  return BARMAX;
}

function rcFrame(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawBG(t);
  const [sx, sy] = shake(t);
  g.translate(sx, sy);
  drawBars(t);
  drawTicker(t);
  drawHook(t);
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawTitle(t);
  return cv.toDataURL('image/jpeg', 0.93);
}

// 썸네일 바탕: 끝 순위의 큰 막대 (글자 없음, thumb.py가 제목을 얹는다). 1위는 녹색
function rcThumb() {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  if (IMG[P.winner]) {   // 1위 회사 사진 + 아래쪽 끝 순위 막대
    const e = IMG[P.winner];
    cover(e.im, 0, 0, W, H, e.x, e.y, 1.0);
    const top = P.ser.map((s, i) => [s.pts[s.pts.length - 1].v, i]).sort((a, b) => b[0] - a[0]).slice(0, 4);
    top.forEach(([v, i], r) => {
      g.fillStyle = i === P.winner ? C.accent : P.ser[i].color;
      g.fillRect(0, 1400 + r * 115, Math.max(80, v / top[0][0] * (W - 160)), 90);
    });
    return cv.toDataURL('image/jpeg', 0.93);
  }
  const last = P.ser.map((s, i) => [s.pts[s.pts.length - 1].v, i]).sort((a, b) => b[0] - a[0]);
  const pitch = H / last.length, bh = pitch * 0.82, top = (pitch - bh) / 2;
  last.forEach(([v, i], r) => {
    const len = Math.max(140, v / last[0][0] * W);
    g.fillStyle = i === P.winner ? C.accent : P.ser[i].color;
    g.fillRect(0, top + r * pitch, len, bh);
  });
  return cv.toDataURL('image/jpeg', 0.93);
}

function rcProblems() {
  const out = [];
  const full = W - 2 * SIDE;
  P.title.forEach(l => { if (width(l, TITLE_PX, true) * 1.0 > full) out.push(`제목 줄이 화면 폭을 넘음: ${l}`); });
  if (P.cta && width(P.cta, 34, false, 700) > full) out.push(`cta_line이 화면 폭을 넘음: ${P.cta}`);
  if (P.basis && width(P.basis, 24, false, 600) > full) out.push(`basis_line이 화면 폭을 넘음: ${P.basis}`);
  if (BARMAX < 300) out.push(`값 글자가 길어 막대 자리가 ${BARMAX}px뿐 (300px 이상 필요)`);
  if (P.punch.some(l => SIDE + width(l, 40, true) * 1.04 > RAIL - 8)) out.push(`punch 줄이 버튼 줄(x ${RAIL})에 닿음`);
  const tw = width('2026.12', TICK_PX, true);
  P.overtakes.forEach(o => {
    if (SIDE + tw + 26 + width(o.label, labelPx(o.label, tw), true) + 28 > RAIL - 8) out.push(`띠가 버튼 줄에 닿음: ${o.label}`);
  });
  P.hook.forEach(l => { if (width(l, 74, true) * 1.3 > full) out.push(`후킹 줄이 화면 폭을 넘음: ${l}`); });
  if (P.hook.length && hookY() + (P.hook.length - 1) * 84 > P.safe.bottom - 10) out.push('후킹 질문이 안전 영역 아래로 내려감');
  if (P.ask && askPx(tw) < 30) out.push(`질문(ask)이 날짜 옆에 들어가지 않음: ${P.ask.lines.join(' ')}`);
  P.ser.forEach(s => { if (nameLines(s.name).px < 20) out.push(`이름이 너무 김: ${s.name}`); });
  return out;
}
