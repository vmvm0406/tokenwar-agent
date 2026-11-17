// 연표 릴스 그리기 (agent/timeline_reel.py가 P(계획)·C(색)를 넣고 프레임마다 twFrame(t)를 부른다).
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
// 한 가지 생각만: 새 모델이 점점 빨리 나온다. 결과 숫자는 끝 정리 화면에만.
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const SIDE = P.safe.side;
const X0 = 255, X1 = W - SIDE;            // 점 가로 범위
const TITLE_Y = [384, 482], TITLE_PX = 92;
const CTA_Y = 548;
const ROW0 = 640, ROWSTEP = 54;           // 회사 줄 (6줄: 640~910)
const AXIS = 948, YEAR_Y = 984, NOTE_Y = 1022;
const NOW_Y = 1100;
const CLABEL_Y = 1150, CVAL_Y = 1232;
const BHS = '"Black Han Sans"';
const N = P.ev.length;
const LOGO = {}, BIMG = {};
// 그림 멈춤 카드: 그림 640x518 (1344x1088 비율), 아래 이름·특징 한 줄
const CARD_X = (W - 640) / 2, CARD_Y = 592, CARD_W = 640, CARD_H = 518;
const CAP_NAME_Y = 1166, CAP_TEXT_Y = 1230;

function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function ease(x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
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

function loadImg(src) {
  return new Promise(res => { const im = new Image(); im.onload = () => res(im); im.onerror = () => res(null); im.src = src; });
}
// 로고·그림 불러오기 (timeline_reel.py가 twReady()를 기다린 뒤 프레임을 찍는다)
async function twReady() {
  for (const [k, v] of Object.entries(P.lab_info)) if (v.logo) { const im = await loadImg(v.logo); if (im) LOGO[k] = im; }
  for (const b of P.beats) if (b.img) { const im = await loadImg(b.img); if (im) BIMG[b.i] = im; }
  return Object.keys(LOGO).length + Object.keys(BIMG).length;
}
// 회사 표시: 로고(있으면), 없으면 같은 자리에 회사 색 점
function drawMark(lab, x, y, size, alpha) {
  g.globalAlpha = alpha;
  if (LOGO[lab]) g.drawImage(LOGO[lab], x, y - size, size, size);
  else { g.fillStyle = labOf(lab).color; g.beginPath(); g.arc(x + size / 2, y - size / 2, size * 0.28, 0, Math.PI * 2); g.fill(); }
  g.globalAlpha = 1;
}

const TL_END = P.tl_end;
const ROWS_T = P.rows_t;
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
    const parts = P.cta.split('댓글로');
    const px = 34;
    let x = W / 2 - width(P.cta, px, false, 700) / 2;
    text(parts[0], x, CTA_Y, px, C.text, { w: 700 });
    if (parts.length > 1) { x += width(parts[0], px, false, 700); text('댓글로' + parts.slice(1).join('댓글로'), x, CTA_Y, px, C.accent, { w: 700 }); }
  }
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

function dotPop(dt) { return dt >= 0 && dt < 0.2 ? 1 + 1.4 * (1 - ease(dt / 0.2)) : 1; }
function beatAt(t) { return P.beats.find(b => t >= b.t0 && t < b.t0 + P.beat_len) || null; }
const RH = P.rehook;
function inRehook(t) { return RH && t >= RH.t0 && t < RH.t0 + P.rehook_len; }
// 멈춤(그림·리후킹): 재생선이 멈추는 구간 [시작 점 번호, 다시 움직이는 시각]
const PAUSES = P.beats.map(b => ({ i: b.i, until: b.t0 + P.beat_len })).concat(RH ? [{ i: RH.i, until: RH.t0 + P.rehook_len }] : []);

function playheadU(t) {
  if (t < P.ev[0].t) return lerp(0, P.ev[0].u, clamp((t - P.tl_start) / (P.ev[0].t - P.tl_start), 0, 1));
  for (let i = 0; i < N - 1; i++) {
    if (t < P.ev[i + 1].t) {
      const ps = PAUSES.filter(x => x.i === i);
      const t0 = ps.length ? Math.max(...ps.map(x => x.until)) : P.ev[i].t;   // 멈춤 동안 재생선도 멈춘다
      return lerp(P.ev[i].u, P.ev[i + 1].u, clamp((t - t0) / (P.ev[i + 1].t - t0), 0, 1));
    }
  }
  return P.ev[N - 1].u + 0.012 * clamp((t - P.ev[N - 1].t) / 0.6, 0, 1);
}
function lastIdx(t) {
  let k = -1;
  for (let i = 0; i < N; i++) if (P.ev[i].t <= t) k = i;
  return k;
}
function dateOfU(u) {
  const d = new Date(Date.UTC(P.x0year, 0, 1) + u * P.span * 86400000);
  return `${d.getUTCFullYear()}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

function drawAxis() {
  g.fillStyle = C.muted; g.fillRect(X0 - 12, AXIS, X1 - X0 + 12, 2);
  P.years.forEach(y => {
    const u = (Date.UTC(y, 0, 1) - Date.UTC(P.x0year, 0, 1)) / 86400000 / P.span;
    const a = g.globalAlpha; g.globalAlpha = a * 0.6; g.fillRect(xOf(u), AXIS - 6, 2, 12); g.globalAlpha = a;
    g.font = font(24, false, 600); g.fillStyle = C.muted; g.textAlign = 'left'; g.fillText(String(y), xOf(u) + 4, YEAR_Y);
  });
  if (P.note) { g.font = font(24, false, 600); g.fillText(P.note, SIDE, NOTE_Y); }
}
function drawLabs() {
  P.labs.forEach((l, r) => {
    const y = rowY(r) + 12;
    const a = g.globalAlpha;
    if (LOGO[l]) g.drawImage(LOGO[l], SIDE, y + 3 - 30, 30, 30);
    else { g.fillStyle = labOf(l).color; g.beginPath(); g.arc(SIDE + 15, y + 3 - 15, 8.4, 0, Math.PI * 2); g.fill(); }
    g.font = font(26, false, 700); g.fillStyle = labOf(l).color; g.textAlign = 'left'; g.fillText(labOf(l).short, SIDE + 40, y);
    g.globalAlpha = a;
  });
}
function drawDots(t) {
  const li = lastIdx(t);
  for (let i = 0; i <= li; i++) {
    const e = P.ev[i];
    const s = dotPop(t - e.t), ring = t - e.t >= 0 && t - e.t < 0.2;
    const x = xOf(e.u), y = rowY(e.row), r = 11 * s;
    g.fillStyle = labOf(e.lab).color;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
    if (ring) { g.strokeStyle = C.text; g.lineWidth = 3; g.beginPath(); g.arc(x, y, r + 5, 0, Math.PI * 2); g.stroke(); }
  }
}
function drawPlayhead(t) {
  const x = xOf(playheadU(t));
  const top = ROW0 - 34;
  const a = g.globalAlpha;
  g.globalAlpha = a * 0.85; g.fillStyle = C.accent; g.fillRect(x - 1.5, top, 3, AXIS - top); g.globalAlpha = a;
  const tag = dateOfU(playheadU(t));
  g.font = font(26, false, 700);
  const w = g.measureText(tag).width;
  g.fillStyle = C.accent; g.textAlign = 'left'; g.fillText(tag, clamp(x - w / 2, X0 - 40, W - SIDE - w), top - 12);
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
  const q = ease((t - e.t) / 0.12);
  const off = (1 - q) * 40;
  const px = namePx(e);
  drawMark(e.lab, SIDE + off, NOW_Y + 2, 44, q);
  const nx = SIDE + 56 + off;
  text(e.name, nx, NOW_Y, px, labOf(e.lab).color, { bhs: true, alpha: q });
  text(e.date, nx + width(e.name, px, true) + 20, NOW_Y - 2, 28, C.muted, { w: 600, alpha: q });
}
// 재생 중 아래: 지금까지 나온 모델 수 (결과 숫자 아님)
function drawCount(t) {
  const li = lastIdx(t);
  if (li < 0) return;
  const pop = t - P.ev[li].t;
  const sc = pop >= 0 && pop < 0.14 ? 1 + 0.12 * (1 - pop / 0.14) : 1;
  text('출시된 주요 모델', SIDE, CLABEL_Y + 10, 28, C.muted, { w: 600 });
  scaleAt(SIDE, CVAL_Y - 30, sc, () => text(`${li + 1}개`, SIDE, CVAL_Y + 6, 76, C.text, { bhs: true }));
}

// 대표 모델 그림: 점에서 튀어나와 가운데 카드로, 천천히 확대, 끝에 다시 점으로
function drawBeat(t, b) {
  const d = t - b.t0, L = P.beat_len;
  const qi = ease(d / 0.2), qo = d > L - 0.16 ? ease((d - (L - 0.16)) / 0.16) : 0;
  const q = qi * (1 - qo);
  const e = P.ev[b.i];
  const dx = xOf(e.u), dy = rowY(e.row);
  const cx = lerp(dx, CARD_X + CARD_W / 2, q), cy = lerp(dy, CARD_Y + CARD_H / 2, q);
  const s = lerp(0.04, 1, q);
  const w = CARD_W * s, h = CARD_H * s;
  const col = labOf(b.lab).color;
  g.save();
  g.globalAlpha = Math.min(1, q * 1.5);
  g.fillStyle = '#000'; g.fillRect(cx - w / 2, cy - h / 2, w, h);
  const im = BIMG[b.i];
  if (im) {
    g.save(); g.beginPath(); g.rect(cx - w / 2, cy - h / 2, w, h); g.clip();
    const z = 1 + 0.07 * clamp(d / L, 0, 1);
    const iw = w * z, ih = iw * im.height / im.width;
    g.drawImage(im, cx - iw / 2, cy - ih / 2, iw, Math.max(ih, h * z));
    g.restore();
  }
  g.strokeStyle = col; g.lineWidth = 5; g.strokeRect(cx - w / 2, cy - h / 2, w, h);
  g.restore();
  // 이름 + 특징 한 줄 (그림 왼쪽 끝에 맞춤)
  const ta = ease((d - 0.12) / 0.15) * (1 - qo);
  if (ta > 0) {
    const off = (1 - ta) * 30;
    drawMark(b.lab, CARD_X + off, CAP_NAME_Y + 2, 46, ta);
    text(b.name, CARD_X + 58 + off, CAP_NAME_Y, 52, col, { bhs: true, alpha: ta });
    text(b.text, CARD_X + off, CAP_TEXT_Y, 42, C.text, { w: 700, alpha: ta });
  }
}

// 리후킹 (5박자 3번째): 어두워진 연표 위 가운데에 작은 줄 + 큰 줄 쾅 (결과 숫자는 아직 아님)
function drawRehook(t) {
  const d = t - RH.t0, L = P.rehook_len;
  const out = d > L - 0.18 ? ease((d - (L - 0.18)) / 0.18) : 0;
  const a = ease(d / 0.12) * (1 - out);
  text(RH.small, W / 2, 790, 40, C.text, { w: 700, align: 'center', alpha: a });
  const px = 96, y = 900;
  scaleAt(W / 2, y - 34, slam(d - 0.15) || (d < 0.15 ? 0.001 : 1), () => {
    g.globalAlpha = 1 - out;
    const hl = RH.hl && RH.big.includes(RH.hl) ? RH.hl : '';
    const parts = hl ? [RH.big.slice(0, RH.big.indexOf(hl)), hl, RH.big.slice(RH.big.indexOf(hl) + hl.length)] : [RH.big];
    let x = W / 2 - width(RH.big, px, true) / 2;
    parts.forEach((p, k) => { if (!p) return; text(p, x, y, px, hl && k === 1 ? C.accent : C.text, { bhs: true, alpha: 1 - out }); x += width(p, px, true); });
    g.globalAlpha = 1;
  });
}

// 끝 정리: 새 모델 하나 나오는 데 걸린 시간 (같은 눈금 막대)
const BAR_Y0 = 712, BAR_STEP = 96, BAR_MAXW = W - 2 * SIDE;
function drawSummary(t) {
  if (t < TL_END + 0.25) return;
  const a = ease((t - TL_END - 0.25) / 0.2);
  text('새 모델 하나 나오는 데 걸린 시간', SIDE, 636, 34, C.text, { w: 700, alpha: a });
  const last = P.rows.length - 1;
  const maxD = Math.max(...P.rows.map(r => r.days));
  P.rows.forEach((r, i) => {
    const d = t - ROWS_T[i];
    if (d < 0) return;
    const q = ease(d / 0.35), qa = ease(d / 0.15);
    const y = BAR_Y0 + i * BAR_STEP;
    const isLast = i === last;
    text(r.name, SIDE, y, 40, isLast ? C.text : C.muted, { bhs: true, alpha: qa });
    let sc = isLast ? (slam(d) || 1) : 1;
    if (isLast && d > 0.24) sc = 1 + 0.04 * ease((d - 0.24) / 3);   // 끝까지 천천히 커짐 (정지 화면 없음)
    scaleAt(W - SIDE, y - 20, sc, () => text(r.value, W - SIDE, y, isLast ? 56 : 44, isLast ? C.accent : C.text, { bhs: true, align: 'right', alpha: qa }));
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
  const b = t < TL_END ? beatAt(t) : null;
  let dim = 1;
  if (b) { const d = t - b.t0; dim = 1 - 0.8 * ease(d / 0.2) * (1 - (d > P.beat_len - 0.16 ? ease((d - P.beat_len + 0.16) / 0.16) : 0)); }
  const rh = t < TL_END && inRehook(t);
  if (rh) { const d = t - RH.t0; dim = 1 - 0.85 * ease(d / 0.12) * (1 - (d > P.rehook_len - 0.18 ? ease((d - P.rehook_len + 0.18) / 0.18) : 0)); }
  const chartA = (t < TL_END ? 1 : 1 - ease((t - TL_END) / 0.25)) * dim;
  if (chartA > 0) {
    g.save(); g.globalAlpha = chartA;
    drawLabs(); drawAxis(); drawDots(t);
    if (t < TL_END) drawPlayhead(t);
    g.restore();
    if (t < TL_END && dim > 0.6) { g.save(); g.globalAlpha = 1; drawNow(t); drawCount(t); g.restore(); }
  }
  if (b) drawBeat(t, b);
  if (rh) drawRehook(t);
  drawSummary(t);
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
  P.beats.forEach(b => {   // 그림 아래 글은 버튼 줄(x 850~) 왼쪽에서 끝나야 한다
    if (CARD_X + 58 + width(b.name, 52, true) > 850) out.push(`그림 이름이 버튼 줄에 닿음: ${b.name}`);
    if (CARD_X + width(b.text, 42, false, 700) > 850) out.push(`그림 특징 줄이 버튼 줄에 닿음: ${b.text}`);
  });
  if (RH && width(RH.big, 96, true) > W - 2 * SIDE) out.push(`리후킹 줄이 화면 폭을 넘음: ${RH.big}`);
  const lastY = BAR_Y0 + (P.rows.length - 1) * BAR_STEP;
  if (lastY + 34 > 1150) out.push(`정리 마지막 줄이 버튼 줄에 닿음 (y ${lastY + 34})`);
  P.rows.forEach(r => { if (SIDE + width(r.name, 40, true) + 30 + width(r.value, 56 * 1.05, true) > W - SIDE) out.push(`정리 줄이 화면 폭을 넘음: ${r.name} ${r.value}`); });
  if (P.note && width(P.note, 24, false, 600) > W - 2 * SIDE) out.push(`출처 줄이 화면 폭을 넘음: ${P.note}`);
  return out;
}
