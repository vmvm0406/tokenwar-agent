// 막대 경주 릴스 그리기 (agent/racereel.py가 P(계획)·C(색)를 넣고 rcInit() 뒤 프레임마다 rcFrame(t)를 부른다).
// 고전 '바 차트 레이스' (운영자 2026-11-17 "시간에 따라서 연속적으로 숫자가 바뀌어야"): 시간 한 줄, 달마다 이어지는 값,
// 막대 끝 숫자가 계속 올라가고 순위가 바뀌면 막대가 미끄러지며 자리를 바꾼다. 중간 글자 카드 없음.
// 화면 글: 제목·0초 질문 한 줄·작은 단위 라벨·날짜·막대(이름·숫자·작은 사진)·끝 punch 한 줄 (운영자 "쓸데없는 부연설명이 많아").
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const SIDE = P.safe.side, RAIL = P.safe.rail;
const BHS = '"Black Han Sans"';
const TITLE_Y = 380, TITLE_LH = 78, TITLE_PX = 66;
const CTA_Y = 528;
const HEAD_Y = 618;                  // 단위 라벨(왼쪽)·날짜(오른쪽) 줄
const AREA0 = 650, AREA1 = 1138;
const NAME_W = 190, BAR_X = SIDE + NAME_W + 12;
const N = P.ser.length;
const PITCH = Math.min(84, (AREA1 - AREA0) / N);
const BAR_H = Math.round(PITCH * 0.72);
const VAL_PX = Math.min(36, Math.round(BAR_H * 0.62));
const DOT = BAR_H + 10;              // 막대 끝 동그란 사진 지름
let BARMAX = 500;

function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function ease(x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
function lerp(a, b, q) { return a + (b - a) * q; }
function slam(dt) {
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
  g.shadowColor = 'rgba(0,0,0,0.7)'; g.shadowBlur = 8;
  g.fillText(s, x, y);
  g.shadowBlur = 0; g.shadowColor = 'transparent';
  g.globalAlpha = a0;
}
function width(s, px, bhs, w) { g.font = font(px, bhs, w); return g.measureText(s).width; }

// 값 표기 (racereel.py fmt_value와 같음). 단위는 작은 라벨(P.unit)에
function fmtValue(v) {
  if (P.fmt === 'people_m') {
    if (v >= 100) return `${(v / 100).toFixed(1).replace(/\.0$/, '')}억`;
    return `${Math.round(v * 100).toLocaleString('en-US')}만`;
  }
  const eok = v * 10;
  if (eok >= 10000) {
    const r = Math.round(eok), jo = Math.floor(r / 10000), rest = r % 10000;
    return rest ? `${jo}조 ${rest.toLocaleString('en-US')}억` : `${jo}조`;
  }
  if (eok < 10) return `${eok.toFixed(1).replace(/\.0$/, '')}억`;
  return `${Math.round(eok).toLocaleString('en-US')}억`;
}

// 시각 → 날짜(시작부터 일수). 본편 동안 한결같은 속도로 흐른다
function dayAt(t) { return clamp(t / P.race_len, 0, 1) * P.span; }
// 회사 값: 발표 사이는 비율로 이어 그린다(기하 보간), 첫 발표 때 0에서 짧게 자라 들어온다, 마지막 발표 뒤는 그대로
function valueAt(i, day) {
  const pts = P.ser[i].pts;
  if (day < pts[0].d) return null;
  if (P.step) {        // 기업가치: 다음 발표까지 유지, 발표 때 짧게 늘어남
    let k = 0;
    for (let j = 0; j < pts.length; j++) if (pts[j].d <= day) k = j;
    if (k === 0 && pts[0].d <= 0) return pts[0].v;
    const a = k > 0 ? pts[k - 1].v : 0;
    const td = Math.max(1, Math.min(P.entry_days, P.span - pts[k].d));   // 끝 날짜 전에 다 늘어나게
    return a + (pts[k].v - a) * ease((day - pts[k].d) / td);
  }
  if (pts[0].d > 0 && day < pts[0].d + P.entry_days) return pts[0].v * ease((day - pts[0].d) / P.entry_days);
  for (let k = 0; k < pts.length - 1; k++) {
    const a = pts[k], b = pts[k + 1];
    if (day < b.d) {
      const f = (day - a.d) / (b.d - a.d);
      return a.v > 0 && b.v > 0 ? a.v * Math.pow(b.v / a.v, f) : lerp(a.v, b.v, f);
    }
  }
  return pts[pts.length - 1].v;
}
function vals(t) { const d = dayAt(t); return P.ser.map((_, i) => valueAt(i, d)); }
// 순위용 값: 막 들어오는 회사는 첫 발표 값으로 (0에서 자라는 동안 아래 줄을 가로지르지 않게)
function rankVals(t) {
  const d = dayAt(t);
  return P.ser.map((s, i) => {
    const v = valueAt(i, d);
    return v !== null && s.pts[0].d > 0 && d < s.pts[0].d + P.entry_days ? Math.max(v, s.pts[0].v) : v;
  });
}
function ranks(vs) {
  return vs.map((v, i) => v === null ? N : vs.filter((w, j) => w !== null && (w > v || (w === v && j < i))).length);
}
function smoothRank(i, t) {          // 0.3초 동안 미끄러지며 자리를 바꾼다
  let s = 0, ws = 0;
  for (let k = 0; k < 12; k++) {
    const w = Math.sin(Math.PI * (k + 0.5) / 12);
    const tt = Math.max(0, t - k * 0.026);
    let r = ranks(rankVals(tt))[i];
    if (r === N) r = ranks(rankVals(Math.max(t, 0)))[i];
    s += w * r; ws += w;
  }
  return s / ws;
}
function dateLabel(t) {
  const d = new Date(Date.UTC(P.start[0], P.start[1] - 1, P.start[2]) + dayAt(t) * 86400000);
  return `${d.getUTCFullYear()}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

// ---------- 사진 ----------
const IMG = {};
function cover(im, x, y, w, h, fx, fy, zoom) {
  const s = Math.max(w / im.width, h / im.height) * (zoom || 1);
  const dw = im.width * s, dh = im.height * s;
  g.drawImage(im, x + (w - dw) * fx / 100, y + (h - dh) * fy / 100, dw, dh);
}
// 배경: 1위 회사 사진을 흐리게, 어둡게 (1위가 바뀌면 0.5초 겹쳐 바뀜)
function drawBG(t) {
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const L = P.lead || [];
  let k = -1;
  for (let j = 0; j < L.length; j++) if (L[j][0] <= t) k = j;
  const draw = (i, a) => {
    const e = IMG[i]; if (!e || a <= 0) return;
    g.save(); g.globalAlpha = a; g.filter = 'blur(16px)';
    cover(e.im, -40, -40, W + 80, H + 80, e.x, e.y, 1.05 + 0.03 * Math.sin(t * 0.3));
    g.restore();
  };
  if (k >= 0) {
    const q = ease((t - L[k][0]) / 0.5);
    if (k > 0 && q < 1) draw(L[k - 1][1], 1);
    draw(L[k][1], k > 0 ? q : 1);
  }
  g.globalAlpha = 0.74; g.fillStyle = C.bg; g.fillRect(0, 0, W, H); g.globalAlpha = 1;
}
function dot(i, cx, cy, d) {        // 막대 끝 동그란 사진
  const e = IMG[i];
  g.save();
  g.beginPath(); g.arc(cx, cy, d / 2, 0, Math.PI * 2); g.closePath();
  g.fillStyle = P.ser[i].color; g.fill();
  if (e) { g.clip(); cover(e.im, cx - d / 2, cy - d / 2, d, d, e.x, e.fy, 1); }
  g.restore();
  g.strokeStyle = C.text; g.lineWidth = 3;
  g.beginPath(); g.arc(cx, cy, d / 2, 0, Math.PI * 2); g.stroke();
}

function drawHL(ln, cx, y, px) {
  const hl = P.hl && ln.includes(P.hl) ? P.hl : '';
  const parts = hl ? [ln.slice(0, ln.indexOf(hl)), hl, ln.slice(ln.indexOf(hl) + hl.length)] : [ln];
  let x = cx - width(ln, px, true) / 2;
  parts.forEach((s, k) => {
    if (!s) return;
    text(s, x, y, px, (hl && k === 1) ? C.accent : C.text, { bhs: true });
    x += width(s, px, true);
  });
}
function drawHead(t) {
  P.title.forEach((ln, i) => {
    const st = i * 0.25;
    if (t < st) return;
    const sc = slam(t - st);
    const y = TITLE_Y + i * TITLE_LH;
    g.save(); g.translate(W / 2, y - TITLE_PX * 0.35); g.scale(sc, sc); g.translate(-W / 2, -(y - TITLE_PX * 0.35));
    drawHL(ln, W / 2, y, TITLE_PX);
    g.restore();
  });
  if (P.cta && t >= 0.5) text(P.cta, W / 2, CTA_Y, 36, C.accent, { w: 700, align: 'center', alpha: ease((t - 0.5) / 0.2) });
  if (P.unit) text(P.unit, SIDE, HEAD_Y, 24, C.text, { w: 600, alpha: 0.8 });
  const out = t >= P.race_end ? 1 - ease((t - P.race_end) / 0.3) : 1;
  text(dateLabel(Math.min(t, P.race_len)), W - SIDE, HEAD_Y + 4, 56, C.text, { bhs: true, align: 'right', alpha: out });
}

function drawBars(t) {
  const win = t >= P.race_end ? ease((t - P.race_end) / 0.35) : 0;
  const vs = vals(t);
  const m = Math.max(...vs.map(v => v || 0)) || 1;
  P.ser.forEach((s, i) => {
    const v = vs[i];
    if (v === null) return;
    const y = AREA0 + smoothRank(i, t) * PITCH;
    const isW = i === P.winner;
    const enter = clamp((dayAt(t) - s.pts[0].d) / P.entry_days, 0, 1);
    const a = (s.pts[0].d > 0 ? ease(enter) : 1) * (isW ? 1 : 1 - 0.65 * win);
    g.globalAlpha = a;
    const nl = nameLines(s.name);
    const nc = isW && win > 0 ? C.accent : C.text;
    nl.lines.forEach((ln, j) => text(ln, SIDE, y + BAR_H / 2 + nl.px * 0.36 + (j - (nl.lines.length - 1) / 2) * nl.px * 1.05,
                                     nl.px, nc, { w: 700 }));
    const len = Math.max(DOT / 2, v / m * BARMAX);
    g.fillStyle = isW && win > 0 ? C.accent : s.color;
    g.fillRect(BAR_X, y, len, BAR_H);
    dot(i, BAR_X + len, y + BAR_H / 2, DOT);
    text(fmtValue(v), BAR_X + len + DOT / 2 + 12, y + BAR_H / 2 + VAL_PX * 0.36, VAL_PX, nc, { bhs: true });
    g.globalAlpha = 1;
  });
}

function drawPunch(t) {
  P.punch.forEach((ln, i) => {
    const st = P.race_end + 0.1 + i * 0.3;
    if (t < st || !ln) return;
    const sc = slam(t - st) * (1 + 0.03 * ease((t - st) / 3));
    const px = punchPx();
    const y = 1190 + i * (px + 12) - (P.punch.length - 1) * (px + 12) / 2;
    g.save(); g.translate(SIDE, y - px * 0.35); g.scale(sc, sc); g.translate(-SIDE, -(y - px * 0.35));
    text(ln, SIDE, y, px, i === P.punch.length - 1 ? C.accent : C.text, { bhs: true });
    g.restore();
  });
}
function punchPx() {
  let px = 56;
  while (px > 40 && P.punch.some(l => SIDE + width(l, px, true) * 1.04 > RAIL - 8)) px -= 2;
  return px;
}
function nameLines(name) {
  let px = 32;
  while (px > 26 && width(name, px, false, 700) > NAME_W) px -= 1;
  if (width(name, px, false, 700) <= NAME_W || !name.includes(' ')) {
    while (px > 18 && width(name, px, false, 700) > NAME_W) px -= 1;
    return { lines: [name], px };
  }
  const k = name.lastIndexOf(' ');
  const lines = [name.slice(0, k), name.slice(k + 1)];
  px = Math.min(28, Math.floor(BAR_H / 2.15));
  while (px > 18 && lines.some(l => width(l, px, false, 700) > NAME_W)) px -= 1;
  return { lines, px };
}

const IMPACTS = [0.0, P.race_end + 0.1].concat((P.lead || []).slice(1).map(x => x[0]));
function shake(t) {
  let x = 0, y = 0;
  for (const s of IMPACTS) {
    const d = t - s;
    if (d >= 0 && d < 0.35) { const a = 8 * Math.exp(-d * 12); x += a * Math.sin(d * 83); y += a * 0.6 * Math.cos(d * 71); }
  }
  return [x, y];
}

async function rcInit() {
  await Promise.all(Object.entries(P.imgs || {}).map(([k, v]) => new Promise(res => {
    const im = new Image();
    im.onload = () => { IMG[+k] = { im, x: v.x, y: v.y, fy: v.fy }; res(); };
    im.onerror = res; im.src = v.uri;
  })));
  let vw = 0;
  P.ser.forEach(s => s.pts.forEach(p => { vw = Math.max(vw, width(fmtValue(p.v), VAL_PX, true)); }));
  BARMAX = Math.floor(W - SIDE - BAR_X - DOT / 2 - 12 - vw * 1.05);
  return BARMAX;
}

function rcFrame(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawBG(t);
  const [sx, sy] = shake(t);
  g.translate(sx, sy);
  drawBars(t);
  drawPunch(t);
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawHead(t);
  return cv.toDataURL('image/jpeg', 0.93);
}

// 썸네일 바탕: 1위 회사 사진 + 아래쪽 끝 순위 막대 (글자 없음, thumb.py가 제목을 얹는다)
function rcThumb() {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const top = P.ser.map((s, i) => [s.pts[s.pts.length - 1].v, i]).sort((a, b) => b[0] - a[0]).slice(0, 4);
  if (IMG[P.winner]) { const e = IMG[P.winner]; cover(e.im, 0, 0, W, H, e.x, e.y, 1); }
  top.forEach(([v, i], r) => {
    g.fillStyle = i === P.winner ? C.accent : P.ser[i].color;
    g.fillRect(0, 1400 + r * 115, Math.max(80, v / top[0][0] * (W - 160)), 90);
  });
  return cv.toDataURL('image/jpeg', 0.93);
}

function rcProblems() {
  const out = [];
  const full = W - 2 * SIDE;
  P.title.forEach(l => { if (width(l, TITLE_PX, true) > full) out.push(`제목 줄이 화면 폭을 넘음: ${l}`); });
  if (P.cta && width(P.cta, 36, false, 700) > full) out.push(`cta_line이 화면 폭을 넘음: ${P.cta}`);
  if (P.unit && SIDE + width(P.unit, 24, false, 600) + 30 > W - SIDE - width('2026.12', 56, true)) out.push(`단위 라벨이 날짜와 겹침: ${P.unit}`);
  if (BARMAX < 300) out.push(`값 글자가 길어 막대 자리가 ${BARMAX}px뿐 (300px 이상 필요)`);
  if (P.punch.some(l => SIDE + width(l, 40, true) * 1.04 > RAIL - 8)) out.push(`punch 줄이 버튼 줄(x ${RAIL})에 닿음`);
  P.ser.forEach(s => { if (nameLines(s.name).px < 20) out.push(`이름이 너무 김: ${s.name}`); });
  return out;
}
