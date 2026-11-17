// 연표 릴스 그리기 (agent/timeline_reel.py가 P(계획)·C(색)를 넣고 프레임마다 twFrame(t)를 부른다).
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
// 한 가지 생각만: 새 모델이 점점 빨리 나온다. 제목 + 0초 한 줄은 끝까지 그대로, 그 아래 연표 → 기간별 평균 간격 막대.
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const SIDE = P.safe.side;
const X0 = 255, X1 = W - SIDE;            // 점 가로 범위
const TITLE_Y = [384, 482], TITLE_PX = 92;
const CTA_Y = 548;
const ROW0 = 640, ROWSTEP = 54;           // 회사 줄 (6줄: 640~910)
const AXIS = 948, YEAR_Y = 984, NOTE_Y = 1022;
const NOW_Y = 1092;
const CLABEL_Y = 1146, CVAL_Y = 1232;
const BHS = '"Black Han Sans"';
const N = P.ev.length;
const LOGO = {};

function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function ease(x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
function easeIO(x) { x = clamp(x, 0, 1); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
function lerp(a, b, q) { return a + (b - a) * q; }
function slam(dt) {               // 1.3배에서 쾅 박힘 (0.95 넘침 → 1)
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
  g.globalAlpha = opt.alpha === undefined ? 1 : opt.alpha;
  g.fillText(s, x, y);
  g.globalAlpha = 1;
}
function width(s, px, bhs, w) { g.font = font(px, bhs, w); return g.measureText(s).width; }
function xOf(u) { return X0 + (X1 - X0) * u; }
function rowY(r) { return ROW0 + ROWSTEP * r; }
function labOf(name) { return P.lab_info[name] || { color: C.text, short: name }; }
function scaleAt(cx, cy, s, fn) { g.save(); g.translate(cx, cy); g.scale(s, s); g.translate(-cx, -cy); fn(); g.restore(); }

// 로고 그림 불러오기 (timeline_reel.py가 twReady()를 기다린 뒤 프레임을 찍는다)
async function twReady() {
  await Promise.all(Object.entries(P.lab_info).map(([k, v]) => new Promise(res => {
    if (!v.logo) return res();
    const im = new Image(); im.onload = () => { LOGO[k] = im; res(); }; im.onerror = () => res(); im.src = v.logo;
  })));
  return Object.keys(LOGO).length;
}
// 회사 표시: 로고(있으면) + 회사 색 이름. 로고가 없는 회사는 같은 자리에 회사 색 점
function drawMark(lab, x, y, size, alpha) {
  const li = labOf(lab);
  g.globalAlpha = alpha;
  if (LOGO[lab]) g.drawImage(LOGO[lab], x, y - size, size, size);
  else { g.fillStyle = li.color; g.beginPath(); g.arc(x + size / 2, y - size / 2, size * 0.28, 0, Math.PI * 2); g.fill(); }
  g.globalAlpha = 1;
}

// 효과음과 같은 시각 (timeline_reel.py sfx_times)
const PULSES = P.hook_pulse.map((_, j, a) => 0.75 + j * (P.hook - 0.95) / Math.max(1, a.length - 1));
const TL_END = P.tl_end;
const BARS0 = TL_END + 0.3;
const ROWS_T = P.rows.map((_, i) => P.bars_t[i]);
const SHAKES = [0.0, 0.3].concat(ROWS_T.length ? [ROWS_T[ROWS_T.length - 1]] : []);

function shake(t) {
  let x = 0, y = 0;
  for (const s of SHAKES) {
    const d = t - s;
    if (d >= 0 && d < 0.4) { const a = 12 * Math.exp(-d * 12); x += a * Math.sin(d * 83); y += a * 0.6 * Math.cos(d * 71); }
  }
  return [x, y];
}

// 제목 두 줄 (0초·0.3초에 줄마다 쾅) + 0초 한 줄 안내: 끝까지 같은 자리
function drawTitle(t) {
  P.title.forEach((ln, i) => {
    const st = i * 0.3;
    if (t < st) return;
    const y = TITLE_Y[i];
    scaleAt(W / 2, y - TITLE_PX * 0.35, slam(t - st) || 1, () => drawHL(ln, W / 2, y, TITLE_PX));
  });
  if (P.cta) {
    const a = ease(t / 0.2);
    const parts = P.cta.split('댓글로');
    const px = 34;
    const full = width(P.cta, px, false, 700);
    let x = W / 2 - full / 2;
    text(parts[0], x, CTA_Y, px, C.text, { w: 700, alpha: a });
    if (parts.length > 1) { x += width(parts[0], px, false, 700); text('댓글로' + parts.slice(1).join('댓글로'), x, CTA_Y, px, C.accent, { w: 700, alpha: a }); }
  }
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

function dotPop(dt) { return dt >= 0 && dt < 0.2 ? 1 + 1.4 * (1 - ease(dt / 0.2)) : 1; }

function playheadU(t) {
  if (t < P.hook) return P.ev[N - 1].u;
  if (t < P.tl_start) return lerp(P.ev[N - 1].u, 0, ease((t - P.hook) / P.rewind));
  if (t < P.ev[0].t) return lerp(0, P.ev[0].u, (t - P.tl_start) / (P.ev[0].t - P.tl_start));
  for (let i = 0; i < N - 1; i++) {
    if (t < P.ev[i + 1].t) return lerp(P.ev[i].u, P.ev[i + 1].u, (t - P.ev[i].t) / (P.ev[i + 1].t - P.ev[i].t));
  }
  return P.ev[N - 1].u + 0.012 * clamp((t - P.ev[N - 1].t) / 0.6, 0, 1);
}
function lastIdx(t) {          // 지금까지 찍힌 마지막 점
  if (t < P.tl_start) return N - 1;
  let k = -1;
  for (let i = 0; i < N; i++) if (P.ev[i].t <= t) k = i;
  return k;
}
function dateOfU(u) {
  const d = new Date(Date.UTC(P.x0year, 0, 1) + u * P.span * 86400000);
  return `${d.getUTCFullYear()}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}
function fmtGap(days) {
  if (days >= 60) return `${Math.round(days / 30.44)}개월`;
  if (days >= 28) return `${Math.round(days / 7)}주`;
  return `${Math.round(days)}일`;
}

function drawAxis() {
  g.fillStyle = C.muted; g.fillRect(X0 - 12, AXIS, X1 - X0 + 12, 2);
  P.years.forEach(y => {
    const u = (Date.UTC(y, 0, 1) - Date.UTC(P.x0year, 0, 1)) / 86400000 / P.span;
    g.globalAlpha = 0.6; g.fillRect(xOf(u), AXIS - 6, 2, 12); g.globalAlpha = 1;
    text(String(y), xOf(u) + 4, YEAR_Y, 24, C.muted, { w: 600 });
  });
  if (P.note) text(P.note, SIDE, NOTE_Y, 24, C.muted, { w: 600 });
}
function drawLabs() {
  P.labs.forEach((l, r) => {
    const y = rowY(r) + 12;
    drawMark(l, SIDE, y + 3, 30, 1);
    text(labOf(l).short, SIDE + 40, y, 26, labOf(l).color, { w: 700 });
  });
}

function drawDots(t) {
  const li = lastIdx(t);
  const inHook = t < P.hook;
  const rew = t >= P.hook && t < P.tl_start;
  const uc = rew ? 1.02 - 1.04 * ease((t - P.hook) / P.rewind) : 2;
  for (let i = 0; i < N; i++) {
    const e = P.ev[i];
    if (rew && e.u > uc) continue;
    if (!inHook && !rew && i > li) continue;
    let s = 1, ring = false;
    if (inHook) {
      const j = P.hook_pulse.indexOf(i);
      if (j >= 0) { s = dotPop(t - PULSES[j]); ring = t - PULSES[j] >= 0 && t - PULSES[j] < 0.2; }
    } else if (!rew) {
      s = dotPop(t - e.t); ring = t - e.t >= 0 && t - e.t < 0.2;
    }
    const x = xOf(e.u), y = rowY(e.row);
    const r = 11 * s;
    g.fillStyle = labOf(e.lab).color;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
    if (ring) { g.strokeStyle = C.text; g.lineWidth = 3; g.beginPath(); g.arc(x, y, r + 5, 0, Math.PI * 2); g.stroke(); }
  }
}

function drawPlayhead(t) {
  const u = playheadU(t);
  const x = xOf(u);
  const top = ROW0 - 34;
  g.globalAlpha = 0.85; g.fillStyle = C.accent; g.fillRect(x - 1.5, top, 3, AXIS - top); g.globalAlpha = 1;
  const tag = dateOfU(u);
  const w = width(tag, 26, false, 700);
  const tx = clamp(x - w / 2, X0 - 40, W - SIDE - w);
  text(tag, tx, top - 12, 26, C.accent, { w: 700 });
}

function namePx(e) {           // 로고 + 이름 + 날짜가 한 줄에 들어가게 이름 글씨를 줄인다 (40px까지)
  const rest = 56 + 20 + width(e.date, 28, false, 600);
  for (let px = 56; px > 40; px -= 2) if (SIDE + rest + width(e.name, px, true) <= W - SIDE) return px;
  return 40;
}
function drawNow(t) {
  const li = lastIdx(t);
  if (li < 0) return;
  const e = P.ev[li];
  const since = t < P.tl_start ? 1 : t - e.t;
  let q = ease(since / 0.12);
  if (t >= P.hook && t < P.tl_start) q = 1 - ease((t - P.hook) / 0.25);   // 되감기 동안 사라짐
  if (q <= 0) return;
  const off = (1 - q) * 40;
  const px = namePx(e);
  drawMark(e.lab, SIDE + off, NOW_Y + 2, 44, q);
  const nx = SIDE + 56 + off;
  text(e.name, nx, NOW_Y, px, labOf(e.lab).color, { bhs: true, alpha: q });
  text(e.date, nx + width(e.name, px, true) + 20, NOW_Y - 2, 28, C.muted, { w: 600, alpha: q });
}

function drawCounter(t) {
  let label, value, sc = 1, a = 1;
  if (t < P.hook) {
    if (t < 0.62) return;
    const c = P.counters[N - 1];
    label = c.label; value = c.value; sc = slam(t - 0.62);
  } else if (t < P.tl_start) {
    const c = P.counters[N - 1];
    label = c.label; value = c.value; a = 1 - ease((t - P.hook) / 0.25);
  } else {
    const li = lastIdx(t);
    if (li < 0) return;
    if (li === 0) {   // 첫 모델 뒤: 다음 모델까지 걸린 날을 실시간으로
      label = '다음 모델까지'; value = fmtGap(Math.max(1, (playheadU(t) - P.ev[0].u) * P.span));
    } else {
      const c = P.counters[li];
      label = c.label; value = c.value;
      const pop = (P.counters[li - 1] === null || P.counters[li - 1].value !== value) ? t - P.ev[li].t : -1;
      sc = pop >= 0 && pop < 0.16 ? 1 + 0.16 * (1 - pop / 0.16) : 1;
    }
  }
  text(label, SIDE, CLABEL_Y, 28, C.muted, { w: 600, alpha: a });
  scaleAt(SIDE, CVAL_Y - 30, sc, () => text(value, SIDE, CVAL_Y, 88, C.accent, { bhs: true, alpha: a }));
}

// 끝: 기간별 평균 간격 막대 (같은 눈금, 막대가 줄어드는 것이 그대로 보인다)
const BAR_Y0 = 712, BAR_STEP = 96, BAR_MAXW = W - 2 * SIDE;
function drawBars(t) {
  if (t < BARS0) return;
  const a = ease((t - BARS0) / 0.2);
  text('새 모델 사이 평균 간격', SIDE, 636, 32, C.muted, { w: 700, alpha: a });
  const last = P.rows.length - 1;
  const maxD = Math.max(...P.rows.map(r => r.days));
  P.rows.forEach((r, i) => {
    const d = t - ROWS_T[i];
    if (d < 0) return;
    const q = ease(d / 0.35);
    const y = BAR_Y0 + i * BAR_STEP;
    const isLast = i === last;
    const col = isLast ? C.accent : C.text;
    text(r.name, SIDE, y, 40, isLast ? C.text : C.muted, { bhs: true, alpha: ease(d / 0.15) });
    let sc = isLast ? (slam(d) || 1) : 1;
    if (isLast && d > 0.24) sc = 1 + 0.05 * ease((d - 0.24) / 1.8);   // 끝까지 천천히 커짐 (정지 화면 없음)
    scaleAt(W - SIDE, y - 20, sc, () => text(r.value, W - SIDE, y, isLast ? 60 : 44, col, { bhs: true, align: 'right', alpha: ease(d / 0.15) }));
    const bw = Math.max(8, BAR_MAXW * r.days / maxD) * q;
    g.fillStyle = isLast ? C.accent : C.muted; g.globalAlpha = isLast ? 1 : 0.75;
    g.fillRect(SIDE, y + 16, bw, 18); g.globalAlpha = 1;
  });
  if (P.note) text(P.note, SIDE, 1214, 24, C.muted, { w: 600, alpha: a });
}

function twFrame(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const [sx, sy] = shake(t);
  g.translate(sx, sy);
  const chartA = t < TL_END ? 1 : 1 - ease((t - TL_END) / 0.3);
  if (chartA > 0) {
    g.globalAlpha = chartA;
    g.save();
    drawLabs(); drawAxis(); drawDots(t);
    if (t < TL_END) drawPlayhead(t);
    g.restore();
    g.globalAlpha = 1;
    if (t < TL_END) { drawNow(t); drawCounter(t); }
  }
  drawBars(t);
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawTitle(t);
  return cv.toDataURL('image/jpeg', 0.93);
}

// 썸네일 바탕 (글자 없음, thumb.py가 가운데 제목을 얹는다): 화면을 꽉 채운 회사 색 점 무늬.
// 가로 = 시간(실제 출시일 위치), 줄마다 회사 하나씩 되풀이 → 오른쪽으로 갈수록 점이 빽빽해진다. 제목 자리(가운데)는 흐리게.
function twThumb() {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const ax0 = 30, ax1 = 1050, step = 48;
  for (let r = 0, y = 30; y < H; r++, y += step) {
    const lab = P.labs[r % P.labs.length];
    const mid = y > 640 && y < 1300;
    P.ev.filter(e => e.lab === lab).forEach(e => {
      g.fillStyle = labOf(lab).color; g.globalAlpha = mid ? 0.22 : 0.9;
      g.beginPath(); g.arc(ax0 + (ax1 - ax0) * e.u, y, 13, 0, Math.PI * 2); g.fill();
    });
  }
  g.globalAlpha = 1;
  return cv.toDataURL('image/jpeg', 0.93);
}

function twProblems() {
  const out = [];
  P.title.forEach(l => { if (width(l, TITLE_PX, true) > W - 2 * SIDE) out.push(`제목 줄이 화면 폭을 넘음: ${l}`); });
  if (P.cta && width(P.cta, 34, false, 700) > W - 2 * SIDE) out.push(`0초 안내 줄이 화면 폭을 넘음: ${P.cta}`);
  P.ev.forEach(e => {
    const w = 56 + width(e.name, namePx(e), true) + 20 + width(e.date, 28, false, 600);
    if (SIDE + w > W - SIDE) out.push(`모델 이름 줄이 화면 폭을 넘음: ${e.name}`);
  });
  P.counters.filter(c => c).forEach(c => { if (SIDE + width(c.value, 88 * 1.16, true) > 840) out.push(`큰 숫자가 오른쪽 아래 버튼 줄에 닿음: ${c.value}`); });
  // 막대 숫자(오른쪽 정렬)는 버튼 줄(y 1150~) 위에 있어야 한다
  const lastY = BAR_Y0 + (P.rows.length - 1) * BAR_STEP;
  if (lastY + 34 > 1150) out.push(`막대 마지막 줄이 버튼 줄에 닿음 (y ${lastY + 34})`);
  if (P.note && width(P.note, 24, false, 600) > W - 2 * SIDE) out.push(`출처 줄이 화면 폭을 넘음: ${P.note}`);
  return out;
}
