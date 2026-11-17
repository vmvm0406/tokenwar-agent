// 연표 릴스 그리기 (agent/timeline_reel.py가 P(계획)·C(색)를 넣고 프레임마다 twFrame(t)를 부른다).
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const X0 = 230, X1 = 1010;                 // 점 가로 범위
const ROW0 = 628, ROWSTEP = 58;            // 회사 줄
const AXIS = 965;
const TAG_Y = 590;
const NOTE_Y = 1036;
const NOW_Y = 1102;
const CLABEL_Y = 1152, CVAL_Y = 1240;
const SIDE = P.safe.side;
const BHS = '"Black Han Sans"';
const N = P.ev.length;

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

// 효과음과 같은 시각 (timeline_reel.py sfx_times)
const PULSES = P.hook_pulse.map((_, j, a) => 0.75 + j * (P.hook - 0.95) / Math.max(1, a.length - 1));
const TL_END = P.tl_end;
const MORPH0 = TL_END, MORPH1 = TL_END + 0.8, LINE1 = TL_END + 1.3;
const METR_ON = TL_END + 1.45, PEN0 = TL_END + 1.75, PEN1 = TL_END + 4.45;
const ROWS_T = P.rows.map((_, i) => P.curve_end + 0.15 + 0.22 * i);
const SHAKES = [0.0, 0.3, 0.62, PEN1].concat(ROWS_T.length ? [ROWS_T[ROWS_T.length - 1]] : []);

function shake(t) {
  let x = 0, y = 0;
  for (const s of SHAKES) {
    const d = t - s;
    if (d >= 0 && d < 0.4) { const a = 13 * Math.exp(-d * 12); x += a * Math.sin(d * 83); y += a * 0.6 * Math.cos(d * 71); }
  }
  return [x, y];
}

// 제목: 첫 화면은 크게(줄마다 쾅), 2.4~2.9초에 작아져 위쪽 자리(안내 띠 아래)로
function drawTitle(t) {
  const q = easeIO((t - P.hook) / P.rewind);
  const px = lerp(98, 62, q);
  const lh = lerp(112, 74, q);
  const base = lerp(400, 468, q);
  P.title.forEach((ln, i) => {
    const st = i * 0.3;
    if (t < st) return;
    const sc = t < P.hook ? slam(t - st) : 1;
    const y = base + i * lh;
    g.save();
    g.translate(W / 2, y - px * 0.35);
    g.scale(sc, sc);
    g.translate(-W / 2, -(y - px * 0.35));
    drawHL(ln, W / 2, y, px);
    g.restore();
  });
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

function dotPop(dt) { return dt >= 0 && dt < 0.2 ? 1 + 1.5 * (1 - ease(dt / 0.2)) : 1; }

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

function drawAxis(alpha, metr) {
  g.globalAlpha = alpha;
  g.fillStyle = C.muted;
  g.fillRect(X0 - 12, AXIS, X1 - X0 + 24, 2);
  g.globalAlpha = 1;
  if (metr) {
    const y0 = P.x0year - 1, y1 = P.last_year;
    for (let y = y0; y <= y1; y++) {
      const u = (y - y0) / (y1 - y0 + 10.5 / 12);
      text(String(y), xOf(u), 1000, 22, C.muted, { align: 'center', alpha, w: 600 });
    }
    return;
  }
  P.years.forEach(y => {
    const u = (Date.UTC(y, 0, 1) - Date.UTC(P.x0year, 0, 1)) / 86400000 / P.span;
    g.globalAlpha = alpha * 0.6; g.fillStyle = C.muted; g.fillRect(xOf(u), AXIS - 6, 2, 12); g.globalAlpha = 1;
    text(String(y), xOf(u) + 4, 1000, 22, C.muted, { align: 'left', alpha, w: 600 });
  });
}
function drawLabs(alpha) {
  P.labs.forEach((l, r) => text(l, SIDE, rowY(r) + 8, 24, C.muted, { w: 600, alpha }));
}

function cumY(i) { return AXIS - 12 - (i + 1) / N * (AXIS - 12 - 640); }

function drawDots(t) {
  const li = lastIdx(t);
  const inHook = t < P.hook;
  const rew = t >= P.hook && t < P.tl_start;
  const uc = rew ? 1.02 - 1.04 * ease((t - P.hook) / P.rewind) : 2;
  const morph = clamp((t - MORPH0) / (MORPH1 - MORPH0), 0, 1);
  const mq = easeIO(morph);
  const fadeCum = t >= METR_ON ? lerp(1, 0.22, ease((t - METR_ON) / 0.3)) : 1;
  // 누적 곡선 선 (점이 모인 뒤)
  if (t >= MORPH1) {
    const q = clamp((t - MORPH1) / (LINE1 - MORPH1), 0, 1);
    const upto = q * (N - 1);
    g.save(); g.globalAlpha = fadeCum; g.strokeStyle = C.accent; g.lineWidth = 4; g.beginPath();
    for (let i = 0; i <= Math.floor(upto); i++) {
      const x = xOf(P.ev[i].u), y = cumY(i);
      i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    const f = upto - Math.floor(upto), i = Math.floor(upto);
    if (i < N - 1) g.lineTo(lerp(xOf(P.ev[i].u), xOf(P.ev[i + 1].u), f), lerp(cumY(i), cumY(i + 1), f));
    g.stroke(); g.restore();
  }
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
    const x = xOf(e.u);
    const y = lerp(rowY(e.row), cumY(i), mq);
    const r = 9 * s;
    g.globalAlpha = fadeCum;
    g.fillStyle = C.accent;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
    if (ring) { g.strokeStyle = C.text; g.lineWidth = 3; g.beginPath(); g.arc(x, y, r + 5, 0, Math.PI * 2); g.stroke(); }
    g.globalAlpha = 1;
  }
}

function drawPlayhead(t) {
  if (t >= TL_END) return;
  const u = playheadU(t);
  const x = xOf(u);
  g.globalAlpha = 0.85; g.fillStyle = C.accent; g.fillRect(x - 1.5, TAG_Y + 12, 3, AXIS - TAG_Y - 12); g.globalAlpha = 1;
  let tag = dateOfU(u);
  const li = lastIdx(t);
  if (t >= P.tl_start && li >= 0 && li < N - 1) {
    const el = Math.round((u - P.ev[li].u) * P.span);
    if (el >= 7) tag += `  +${el}일`;
  }
  const w = width(tag, 26, false, 700);
  const tx = clamp(x - w / 2, SIDE, W - SIDE - w);
  text(tag, tx, TAG_Y, 26, C.accent, { w: 700 });
}

function namePx(e) {           // 이름 + 회사·날짜가 한 줄에 들어가게 이름 글씨를 줄인다 (40px까지)
  const rest = 20 + width(`${e.lab} · ${e.date}`, 26, false, 600);
  for (let px = 52; px > 40; px -= 2) if (SIDE + width(e.name, px, true) + rest <= W - SIDE) return px;
  return 40;
}
function drawNow(t) {
  if (t >= TL_END) return;
  const li = lastIdx(t);
  if (li < 0) return;
  const e = P.ev[li];
  const since = t < P.tl_start ? 1 : t - e.t;
  let q = ease(since / 0.12);
  if (t >= P.hook && t < P.tl_start) q = 1 - ease((t - P.hook) / 0.25);   // 되감기 동안 사라짐
  if (q <= 0) return;
  const off = (1 - q) * 40;
  const nm = e.name;
  const px = namePx(e);
  const nw = width(nm, px, true);
  text(nm, SIDE + off, NOW_Y, px, C.accent, { bhs: true, alpha: q });
  text(`${e.lab} · ${e.date}`, SIDE + nw + 20 + off, NOW_Y - 2, 26, C.muted, { w: 600, alpha: q });
}

function drawCounter(t) {
  if (t >= TL_END) return;
  let label, value, pop = 0;
  if (t < P.hook) {
    if (t < 0.62) return;
    const c = P.counters[N - 1];
    label = c.label; value = c.value;
    const sc = slam(t - 0.62);
    g.save(); g.translate(SIDE, CVAL_Y - 30); g.scale(sc, sc); g.translate(-SIDE, -(CVAL_Y - 30));
    text(label, SIDE, CLABEL_Y, 26, C.muted, { w: 600 });
    text(value, SIDE, CVAL_Y, 84, C.text, { bhs: true });
    g.restore();
    return;
  }
  if (t < P.tl_start) {
    const a = 1 - ease((t - P.hook) / 0.25);
    const c = P.counters[N - 1];
    text(c.label, SIDE, CLABEL_Y, 26, C.muted, { w: 600, alpha: a });
    text(c.value, SIDE, CVAL_Y, 84, C.text, { bhs: true, alpha: a });
    return;
  }
  const li = lastIdx(t);
  if (li <= 0) {   // 첫 모델 뒤: 다음 모델까지 걸린 날을 실시간으로
    if (li < 0) return;
    const el = (playheadU(t) - P.ev[0].u) * P.span;
    label = '다음 모델까지'; value = fmtGap(Math.max(1, el));
  } else {
    const c = P.counters[li];
    label = c.label; value = c.value;
    if (P.counters[li - 1] === null || P.counters[li - 1].value !== value) pop = t - P.ev[li].t;
  }
  const sc = pop > 0 && pop < 0.16 ? 1 + 0.14 * (1 - pop / 0.16) : 1;
  text(label, SIDE, CLABEL_Y, 26, C.muted, { w: 600 });
  g.save(); g.translate(SIDE, CVAL_Y - 30); g.scale(sc, sc); g.translate(-SIDE, -(CVAL_Y - 30));
  text(value, SIDE, CVAL_Y, 84, C.text, { bhs: true });
  g.restore();
}

// 누적 출시 수 (점이 곡선으로 모일 때)
function drawCum(t) {
  if (t < MORPH0 || t >= METR_ON + 0.3) return;
  const a = t < METR_ON ? 1 : 1 - ease((t - METR_ON) / 0.3);
  const n = Math.round(N * ease((t - MORPH0) / (MORPH1 - MORPH0)));
  text('주요 모델 누적 출시 수', SIDE, CLABEL_Y, 26, C.muted, { w: 600, alpha: a });
  text(`${n}개`, SIDE, CVAL_Y, 84, C.text, { bhs: true, alpha: a });
}

// METR 추세선: 2배 되는 기간 long_months, recent_from년부터 recent_months
function metrV(mo) {
  const m = P.metr, cut = (m.recent_from - (P.x0year - 1)) * 12;
  return mo < cut ? mo / m.long_months : cut / m.long_months + (mo - cut) / m.recent_months;   // log2 값
}
function drawMetr(t) {
  if (!P.metr || t < METR_ON) return { done: false };
  const m = P.metr;
  const a = ease((t - METR_ON) / 0.3);
  const endMo = (P.last_year - (P.x0year - 1)) * 12 + 10.5;
  const top = metrV(endMo);
  const prog = clamp((t - PEN0) / (PEN1 - PEN0), 0, 1);
  const u = prog * prog;                 // 끝으로 갈수록 빨라짐
  const fade = t > PEN1 + 0.25 ? 1 - ease((t - PEN1 - 0.25) / 0.35) : 1;
  if (u > 0) {
    g.save(); g.globalAlpha = fade; g.strokeStyle = C.accent; g.lineWidth = 8; g.lineJoin = 'round'; g.beginPath();
    const steps = 240;
    let px = 0, py = 0;
    for (let k = 0; k <= steps; k++) {
      const uu = u * k / steps;
      const mo = uu * endMo;
      const v = Math.pow(2, metrV(mo) - top);       // 끝 = 1
      px = xOf(uu); py = AXIS - 12 - v * (AXIS - 12 + 90);
      k === 0 ? g.moveTo(px, py) : g.lineTo(px, py);
    }
    g.stroke();
    if (prog < 1) { g.fillStyle = C.text; g.beginPath(); g.arc(px, py, 11, 0, Math.PI * 2); g.fill(); }
    g.restore();
  }
  // 아래 글: 이름 → 2배 되는 기간 (최근 구간에 들어서면 바뀜)
  const cutU = Math.sqrt(((m.recent_from - (P.x0year - 1)) * 12) / endMo);
  const recent = prog >= cutU;
  const fa = t > P.curve_end - 0.3 ? 1 - ease((t - P.curve_end + 0.3) / 0.3) : 1;
  text(m.label, SIDE, NOW_Y, 36, C.text, { w: 700, alpha: a * fa });
  const val = recent ? m.recent : m.long;
  const sw = recent ? t - (PEN0 + (PEN1 - PEN0) * cutU) : t - METR_ON;
  const sc = sw >= 0 && sw < 0.24 ? slam(sw) : 1;
  g.save(); g.translate(SIDE, CVAL_Y - 30); g.scale(sc, sc); g.translate(-SIDE, -(CVAL_Y - 30));
  text(val, SIDE, CVAL_Y - 8, 76, C.accent, { bhs: true, alpha: a * fa });
  g.restore();
  return { done: true };
}

function drawRows(t) {
  if (t < P.curve_end) return;
  const a = ease((t - P.curve_end) / 0.2);
  text('새 모델 사이 평균 간격', SIDE, 610, 30, C.muted, { w: 600, alpha: a });
  const last = P.rows.length - 1;
  P.rows.forEach((r, i) => {
    const d = t - ROWS_T[i];
    if (d < 0) return;
    const q = ease(d / 0.15);
    const y = 690 + i * 70;
    const off = (1 - q) * 60;
    g.globalAlpha = q * 0.7; g.fillStyle = C.muted; g.fillRect(SIDE, y + 18, W - 2 * SIDE, 2); g.globalAlpha = 1;
    const isLast = i === last;
    text(r.name, SIDE + off, y, isLast ? 52 : 44, isLast ? C.text : C.muted, { bhs: true, alpha: q });
    let sc = isLast ? slam(d) || 1 : 1;
    if (isLast && d > 0.24) sc = 1 + 0.05 * ease((d - 0.24) / 1.8);   // 끝까지 천천히 커짐 (정지 화면 없음)
    g.save(); g.translate(W - SIDE, y - 20); g.scale(sc, sc); g.translate(-(W - SIDE), -(y - 20));
    text(r.value, W - SIDE + off, y, isLast ? 64 : 48, isLast ? C.accent : C.text, { bhs: true, align: 'right', alpha: q });
    g.restore();
  });
}

// 아래 빈칸(안전 영역 밖, 읽을 글 없음): 점이 찍힐 때마다 뛰는 심전도 선. 오른쪽에서 왼쪽으로 흐르고,
// 점이 빨라지면 박동도 빨라진다 (효과음 심장 박동과 같은 시각)
const BEATS = PULSES.concat(P.ev.map(e => e.t)).concat(SHAKES.slice(3));
const ECG_Y = 1560, ECG_SPAN = 2.4;
function beatShape(d) {
  if (d < 0 || d > 0.22) return 0;
  if (d < 0.03) return -40 * (d / 0.03);
  if (d < 0.07) return lerp(-40, 300, (d - 0.03) / 0.04);
  if (d < 0.11) return lerp(300, -140, (d - 0.07) / 0.04);
  if (d < 0.15) return lerp(-140, 0, (d - 0.11) / 0.04);
  return 26 * Math.sin(Math.PI * (d - 0.15) / 0.07);
}
function drawECG(t) {
  const a = t < P.end - 0.5 ? 1 : 1 - ease((t - P.end + 0.5) / 0.5);
  g.save(); g.globalAlpha = 0.9 * a; g.strokeStyle = C.accent; g.lineWidth = 5; g.lineJoin = 'round'; g.beginPath();
  for (let x = 0; x <= W; x += 3) {
    const tau = t - (W - x) / W * ECG_SPAN;
    let y = 0;
    for (const b of BEATS) { const d = tau - b; if (d >= 0 && d <= 0.22) y += beatShape(d); }
    x === 0 ? g.moveTo(x, ECG_Y - y) : g.lineTo(x, ECG_Y - y);
  }
  g.stroke();
  g.fillStyle = C.text; g.beginPath();
  let yy = 0; for (const b of BEATS) { const d = t - b; if (d >= 0 && d <= 0.22) yy += beatShape(d); }
  g.arc(W, ECG_Y - yy, 9, 0, Math.PI * 2); g.fill();
  g.restore();
}

function drawNote(t) {
  const metr = P.metr && t >= METR_ON && t < P.curve_end;
  const s = metr ? `출처: ${P.metr.source}` : P.note;
  if (s) text(s, SIDE, NOTE_Y, 22, C.muted, { w: 600 });
}

function twFrame(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const [sx, sy] = shake(t);
  g.translate(sx, sy);
  const chartA = t < P.curve_end ? 1 : 1 - ease((t - P.curve_end) / 0.2);
  const metrMode = P.metr && t >= METR_ON;
  if (chartA > 0) {
    g.globalAlpha = chartA;
    if (t < MORPH1) drawLabs(1 - clamp((t - MORPH0) / 0.4, 0, 1));
    drawAxis(t < METR_ON ? 1 : 1, metrMode);
    drawDots(t);
    drawPlayhead(t);
    g.globalAlpha = 1;
  }
  drawMetr(t);
  drawNow(t); drawCounter(t); drawCum(t);
  drawRows(t);
  drawNote(t);
  drawECG(t);
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawTitle(t);
  return cv.toDataURL('image/jpeg', 0.93);
}

// 썸네일 바탕: 위로 뚫고 나가는 곡선 + 아래쪽 촘촘한 점 (글자 없음, thumb.py가 제목을 얹는다)
function twThumb() {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const ax0 = 65, ax1 = 1015;
  P.ev.forEach(e => {
    const x = ax0 + (ax1 - ax0) * e.u, y = 1330 + e.row * 92;
    g.fillStyle = C.accent; g.beginPath(); g.arc(x, y, 15, 0, Math.PI * 2); g.fill();
  });
  g.strokeStyle = C.accent; g.lineWidth = 16; g.lineJoin = 'round'; g.beginPath();
  for (let k = 0; k <= 300; k++) {
    const u = k / 300, v = Math.pow(2, (u - 1) * 9);
    const x = ax0 + (ax1 - ax0) * u, y = 1200 - v * 1300;
    k === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
  }
  g.stroke();
  return cv.toDataURL('image/jpeg', 0.93);
}

function twProblems() {
  const out = [];
  P.title.forEach(l => { if (width(l, 62, true) > W - 2 * SIDE) out.push(`제목 줄이 화면 폭을 넘음: ${l}`); });
  P.title.forEach(l => { if (width(l, 98, true) > W - 2 * SIDE + 40) out.push(`첫 화면 제목 줄이 너무 김: ${l}`); });
  P.ev.forEach(e => {
    const w = width(e.name, namePx(e), true) + 20 + width(`${e.lab} · ${e.date}`, 26, false, 600);
    if (SIDE + w > W - SIDE) out.push(`모델 이름 줄이 화면 폭을 넘음: ${e.name}`);
  });
  const vals = P.counters.filter(c => c).map(c => c.value).concat(P.metr ? [P.metr.long, P.metr.recent] : []);
  vals.forEach(v => { if (SIDE + width(v, 84, true) > 840) out.push(`큰 숫자가 오른쪽 아래 버튼 줄에 닿음: ${v}`); });
  return out;
}
