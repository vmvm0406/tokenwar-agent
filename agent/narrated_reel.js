// 내레이션 모션 릴스 그리기 (agent/narrated_reel.py가 P(계획)·C(색)를 넣고 프레임마다 nrFrame(t)를 부른다).
// 캔버스 1080x1920. 읽을 것은 모두 안전 영역 안 (위 285, 아래 1250, 양옆 65, 오른쪽 아래 버튼 줄 x 850~/y 1150~).
// 위: 제목 질문 2줄 + 0초 한 줄 (끝까지 같은 자리) / 가운데: 그림 칸 / 아래: 말에 맞춰 박히는 화면 글 + 작은 출처 줄.
const cv = document.getElementById('c');
const g = cv.getContext('2d');
const W = 1080, H = 1920;
const SIDE = P.safe.side;
const RAIL_X = 850, RAIL_Y = 1150;
const TITLE_Y = [380, 470], TITLE_PX = 84;
const CTA_Y = 536, CTA_PX = 32;
const PX = SIDE, PY = 580, PW = W - 2 * SIDE, PH = 470;       // 그림 칸 950x470 (그림 1344x672 비율)
const LINE_Y = [1126, 1202], LINE_PX = 68;
const SRC_Y = 1240, SRC_PX = 24;
const BHS = '"Black Han Sans"';
const IMG = {};

function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
function ease(x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); }
function lerp(a, b, q) { return a + (b - a) * q; }
function slam(dt) {               // 1.28배에서 쾅 박힘
  if (dt < 0) return 0;
  if (dt < 0.11) return 1.28 - 0.33 * (dt / 0.11);
  if (dt < 0.22) return 0.95 + 0.05 * ((dt - 0.11) / 0.11);
  return 1;
}
function font(px, bhs, w) { return bhs ? `${px}px ${BHS}` : `${w || 700} ${px}px Wanted`; }
function width(s, px, bhs, w) { g.font = font(px, bhs, w); return g.measureText(s).width; }
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
function scaleAt(cx, cy, s, fn) { g.save(); g.translate(cx, cy); g.scale(s, s); g.translate(-cx, -cy); fn(); g.restore(); }
// 한 줄에서 hl 부분만 초록
function drawHL(ln, x, y, px, hl, align) {
  const has = hl && ln.includes(hl);
  const parts = has ? [ln.slice(0, ln.indexOf(hl)), hl, ln.slice(ln.indexOf(hl) + hl.length)] : [ln];
  let cx = align === 'center' ? x - width(ln, px, true) / 2 : x;
  parts.forEach((s, k) => {
    if (!s) return;
    text(s, cx, y, px, (has && k === 1) ? C.accent : C.text, { bhs: true });
    cx += width(s, px, true);
  });
}
function loadImg(src) {
  return new Promise(res => { const im = new Image(); im.onload = () => res(im); im.onerror = () => res(null); im.src = src; });
}
const POPIMG = {};
async function nrReady() {
  for (const s of P.scenes) if (s.img) { const im = await loadImg(s.img); if (im) IMG[s.k] = im; }
  for (const s of P.scenes) for (const [i, q] of (s.pops || []).entries()) {
    const src = q.logo_svg || q.photo_data;
    if (src) { const im = await loadImg(src); if (im) POPIMG[s.k + '_' + i] = im; }
  }
  return Object.keys(IMG).length;
}
function sceneAt(t) {
  let cur = P.scenes[0];
  for (const s of P.scenes) if (t >= s.t0) cur = s;
  return cur;
}
const ANS = P.scenes.find(s => s.beat === 'answer');
const SHAKES = [[0.0, 12]].concat(ANS ? [[ANS.t0 + (ANS.lt[0] || 0), 12]] : []);
P.scenes.forEach(s => (s.pops || []).forEach(q => SHAKES.push([s.t0 + q.t, 5])));   // 로고·숫자가 박힐 때 살짝 흔들림
function shake(t) {
  let x = 0, y = 0;
  for (const [s, amp] of SHAKES) {
    const d = t - s;
    if (d >= 0 && d < 0.4) { const a = amp * Math.exp(-d * 12); x += a * Math.sin(d * 83); y += a * 0.6 * Math.cos(d * 71); }
  }
  return [x, y];
}
function lineFit(ln, maxW) {
  let px = LINE_PX;
  while (px > 40 && width(ln, px, true) > maxW) px -= 2;
  return px;
}
function lineMax(i) { return i === 0 ? PW : RAIL_X - SIDE - 10; }   // 둘째 줄은 버튼 줄(x 850~) 왼쪽에서 끝

function drawTitle(t) {
  P.title.forEach((ln, i) => {
    const st = i * 0.22;
    if (t < st) return;
    scaleAt(W / 2, TITLE_Y[i] - TITLE_PX * 0.35, slam(t - st) || 1, () => drawHL(ln, W / 2, TITLE_Y[i], TITLE_PX, P.hl, 'center'));
  });
  if (P.cta) {
    const parts = P.cta.split('댓글로');
    let x = W / 2 - width(P.cta, CTA_PX, false, 700) / 2;
    text(parts[0], x, CTA_Y, CTA_PX, C.muted, { w: 700 });
    if (parts.length > 1) { x += width(parts[0], CTA_PX, false, 700); text('댓글로' + parts.slice(1).join('댓글로'), x, CTA_Y, CTA_PX, C.accent, { w: 700 }); }
  }
}

function drawImage(s, d, alpha) {
  const im = IMG[s.k];
  if (!im) return;
  const zoom = 1.0 + 0.07 * clamp(d / Math.max(1, s.dur), 0, 1);
  const enter = ease(d / 0.2);
  g.save();
  g.beginPath(); g.rect(PX, PY, PW, PH); g.clip();
  g.globalAlpha = alpha * enter;
  const r = Math.max(PW / im.width, PH / im.height) * zoom;
  const w = im.width * r, h = im.height * r;
  g.drawImage(im, PX + (PW - w) / 2 + (1 - enter) * 50, PY + (PH - h) / 2, w, h);
  g.restore();
  g.globalAlpha = 1;
}

function drawBars(s, d) {
  if (IMG[s.k]) drawImage(s, d, 0.36);          // 사진은 늘 깐다 (운영자 2026-11-17 "사진은 무조건 넣어"), 막대는 그 위에
  const n = s.bars.length;
  const step = Math.min(84, PH / n);
  const y0 = PY + (PH - step * n) / 2 + step * 0.5;
  const LX = PX + 10, BX = PX + 300, BMAX = PW - 300 - 170;
  const vmax = s.bar_max || Math.max(...s.bars.map(b => Math.abs(b.value))) || 1;
  s.bars.forEach((b, i) => {
    const y = y0 + i * step;
    const q = b.instant ? 1 : ease((d - b.t) / 0.35);
    if (!b.instant && d < b.t) {
      text(b.label, LX, y + 13, 38, C.muted, { w: 700, alpha: 0.35 });
      return;
    }
    const col = b.win ? C.accent : C.text;
    text(b.label, LX, y + 13, 38, b.win ? C.accent : C.text, { w: 700 });
    if (b.hidden) {
      g.fillStyle = C.muted; g.globalAlpha = 0.5; g.fillRect(BX, y - 20, 60, 40); g.globalAlpha = 1;
      text('?', BX + 80, y + 18, 52, C.muted, { bhs: true });
      return;
    }
    const bw = Math.max(6, BMAX * Math.abs(b.value) / vmax * q);
    g.fillStyle = col; g.globalAlpha = b.win ? 1 : 0.85;
    g.fillRect(BX, y - 20, bw, 40); g.globalAlpha = 1;
    const shown = b.shown;
    scaleAt(BX + bw + 20, y, b.instant ? 1 : (slam(d - b.t - 0.3) || 0.0001), () => {
      if (d - b.t >= 0.3 || b.instant) text(shown, BX + bw + 20, y + 18, 52, col, { bhs: true });
    });
  });
}

function parseBig(s) {
  const m = s.match(/^([^0-9]*)([0-9][0-9,]*\.?[0-9]*)(.*)$/);
  if (!m) return null;
  const num = parseFloat(m[2].replace(/,/g, ''));
  const dec = (m[2].split('.')[1] || '').length;
  return { pre: m[1], num, dec, suf: m[3], comma: m[2].includes(',') };
}
function fmtNum(v, b) {
  let s = v.toFixed(b.dec);
  if (b.comma) s = Number(s).toLocaleString('en-US', { minimumFractionDigits: b.dec, maximumFractionDigits: b.dec });
  return b.pre + s + b.suf;
}
function drawBig(s, d) {
  if (IMG[s.k]) { drawImage(s, d, 0.32); }   // 숫자는 사진 위에
  if (d < s.big_t) return;
  const b = parseBig(s.big);
  const q = ease((d - s.big_t) / 0.6);
  const str = b ? fmtNum(b.num * q, b) : s.big;
  let px = 220;
  while (px > 80 && width(s.big, px, true) > PW - 40) px -= 6;
  scaleAt(W / 2, PY + PH / 2, d - s.big_t > 0.6 ? (slam(d - s.big_t - 0.6) || 1) : 1, () => {
    text(str, W / 2, PY + PH / 2 + px * 0.36, px, C.accent, { bhs: true, align: 'center' });
  });
}

function drawLines(s, d) {
  s.lines.forEach((ln, i) => {
    const st = s.lt[i];
    if (d < st) return;
    const px = lineFit(ln, lineMax(i));
    scaleAt(SIDE + width(ln, px, true) / 2, LINE_Y[i] - px * 0.35, slam(d - st) || 1,
      () => drawHL(ln, SIDE, LINE_Y[i], px, s.hl, 'left'));
  });
  if (s.source) text(s.source, SIDE, SRC_Y, SRC_PX, C.muted, { w: 600 });
}

// 끝 화면 (post.end_cta): 본편이 끝나면 페이드 없이 컷으로 들어와 글이 쾅 박힌다 (운영자 2026-11-17 "페이드 아웃할 필요 없을듯")
function drawEnd(t) {
  const d = t - P.end;
  const cy = 780, px = 84;
  const n = P.cta_end.length;
  text('TOKEN WAR', W / 2, cy - 70 - (n - 1) * px * 0.62, 44, C.accent, { bhs: true, align: 'center' });
  P.cta_end.forEach((ln, i) => {
    const y = cy + (i - (n - 1) / 2) * px * 1.25 + px * 0.35;
    scaleAt(W / 2, y - px * 0.35, slam(d - i * 0.12) || 0.0001, () => {
      if (d >= i * 0.12) text(ln, W / 2, y, px, C.text, { bhs: true, align: 'center' });
    });
  });
  g.fillStyle = C.accent; g.fillRect(W / 2 - 80, cy + n * px * 0.7 + 40, 160, 8);
}

// 아래 칸 움직임 (화면 아래 절반이 비지 않게): 말 속 낱말에 맞춰 로고·숫자·말·사진이 하나씩 쾅 박히며 격자로 쌓인다.
// 운영자 2026-11-17 "AI이름 나열할 때는 로고를 빡 빡 빡 박을 수 있잖아". 읽어야 할 글은 위 안전 영역에 있고 이 칸은 보조.
const POP_Y0 = 1290, POP_H = 380;
function popSlam(dt) {            // 1.6배에서 쾅
  if (dt < 0) return 0;
  if (dt < 0.13) return 1.6 - 0.68 * (dt / 0.13);
  if (dt < 0.24) return 0.92 + 0.08 * ((dt - 0.13) / 0.11);
  return 1;
}
function drawPops(s, d) {
  const ps = s.pops || [];
  if (!ps.length) return;
  const n = ps.length, cols = Math.min(n, 3), rows = Math.ceil(n / 3);
  const cw = PW / cols, ch = Math.min(190, POP_H / rows);
  const y0 = POP_Y0 + (POP_H - ch * rows) / 2;
  ps.forEach((q, i) => {
    const dt = d - q.t;
    if (dt < 0) return;
    const r = Math.floor(i / cols), c = i % cols;
    const inRow = Math.min(cols, n - r * cols);
    const cx = PX + (PW - cw * inRow) / 2 + cw * (c + 0.5), cy = y0 + ch * (r + 0.5);
    const im = POPIMG[s.k + '_' + i];
    scaleAt(cx, cy, popSlam(dt), () => {
      if (q.logo_svg && im) {
        const sz = Math.min(ch * 0.58, 120);
        g.drawImage(im, cx - sz / 2, cy - ch * 0.42, sz, sz);
        if (q.label) text(q.label, cx, cy + ch * 0.36, Math.min(42, ch * 0.24), q.label_color || C.text, { bhs: true, align: 'center' });
      } else if (q.photo_data && im) {
        const w = cw * 0.86, h = ch * 0.7;
        const rr = Math.max(w / im.width, h / im.height);
        g.save(); g.beginPath(); g.rect(cx - w / 2, cy - ch * 0.45, w, h); g.clip();
        g.drawImage(im, cx - im.width * rr / 2, cy - ch * 0.45 + h / 2 - im.height * rr / 2, im.width * rr, im.height * rr);
        g.restore();
        if (q.label) text(q.label, cx, cy + ch * 0.42, Math.min(36, ch * 0.2), C.text, { bhs: true, align: 'center' });
      } else if (q.num) {
        let px = Math.min(120, ch * 0.62);
        while (px > 40 && width(q.num, px, true) > cw - 24) px -= 4;
        text(q.num, cx, cy + px * 0.28 - (q.label ? 14 : 0), px, q.color || C.accent, { bhs: true, align: 'center' });
        if (q.label) text(q.label, cx, cy + ch * 0.42, Math.min(32, ch * 0.18), C.muted, { w: 700, align: 'center' });
      } else {
        const ln = q.word || q.label || '';
        let px = Math.min(72, ch * 0.4);
        while (px > 34 && width(ln, px, true) > cw - 24) px -= 4;
        text(ln, cx, cy + px * 0.35, px, q.color || C.text, { bhs: true, align: 'center' });
      }
    });
  });
}

function nrFrame(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  if (P.cta_end.length && t >= P.end) { drawEnd(t); return cv.toDataURL('image/jpeg', 0.92); }
  const [sx, sy] = shake(t);
  g.translate(sx, sy);
  const s = sceneAt(t);
  const d = t - s.t0;
  g.fillStyle = C.accent; g.fillRect(PX, PY - 14, 140, 8);             // 그림 칸 위 녹색 선
  if (s.kind === 'bars') drawBars(s, d);
  else if (s.kind === 'big') drawBig(s, d);
  else drawImage(s, d, 1);
  drawLines(s, d);
  drawPops(s, d);
  g.setTransform(1, 0, 0, 1, 0, 0);
  drawTitle(t);
  return cv.toDataURL('image/jpeg', 0.92);
}

function nrProblems() {
  const out = [];
  P.title.forEach(l => { if (width(l, TITLE_PX, true) > W - 2 * SIDE) out.push(`제목 줄이 화면 폭을 넘음: ${l}`); });
  if (P.cta && width(P.cta, CTA_PX, false, 700) > W - 2 * SIDE) out.push(`0초 안내 줄이 화면 폭을 넘음: ${P.cta}`);
  P.scenes.forEach(s => {
    s.lines.forEach((ln, i) => { if (lineFit(ln, lineMax(i)) < 52) out.push(`장면 ${s.k} 화면 글이 길어 글씨가 너무 작아짐: ${ln}`); });
    if (s.source && SIDE + width(s.source, SRC_PX, false, 600) > RAIL_X - 10) out.push(`장면 ${s.k} 출처 줄이 버튼 줄(x 850~)에 닿음: ${s.source}`);
    s.bars.forEach(b => {
      if (width(b.label, 38, false, 700) > 280) out.push(`장면 ${s.k} 막대 이름이 김: ${b.label}`);
    });
    if (s.lines.length > 2) out.push(`장면 ${s.k} 화면 글은 2줄까지`);
  });
  return out;
}
