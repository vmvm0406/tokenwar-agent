// 아래 빈칸: 초록 형광 CRT 터미널. 모든 글자는 고정폭 격자 칸 위에 놓인다 (한글은 2칸).
// render는 결정적: 시각 t만으로 그린다.
const TC = document.getElementById('term'), tx = TC.getContext('2d');
const TW = TC.width, TH = TC.height, PADX = 64, FS = 31, LH = 40;
const G = '#00FF66', GD = '#1FAE5C', GL = 'rgba(0,255,102,0.55)', GLASS = '#0A0B0A';
let CW = 20;
const isWide = c => { const k = c.codePointAt(0); return k >= 0x1100 && !(k >= 0x2500 && k <= 0x259F) && k !== 0x2192 && k !== 0x00B7; };
const cells = s => [...s].reduce((n, c) => n + (isWide(c) ? 2 : 1), 0);
const hash = x => { const s = Math.sin(x * 127.1) * 43758.5453; return s - Math.floor(s); };

function glyphs(s, col, y, fs, color, glow) {
  const cw = CW * fs / FS;
  let c = col;
  for (const ch of s) {
    const w = isWide(ch) ? 2 : 1, x = PADX + c * cw;
    if (ch !== ' ') {
      tx.font = isWide(ch) ? `700 ${fs * 1.16}px Wanted` : `800 ${fs}px JBM`;
      tx.textAlign = 'center'; tx.textBaseline = 'alphabetic';
      const cx0 = x + (w * cw) / 2;
      if (glow) { tx.shadowColor = GL; tx.shadowBlur = fs * 0.45; tx.fillStyle = color; tx.fillText(ch, cx0, y); tx.shadowBlur = 0; }
      tx.fillStyle = color; tx.fillText(ch, cx0, y);
    }
    c += w;
  }
  return c;
}
// 반전 화면(초록 칸 위 검은 글자): 칸 범위에 딱 맞는다
function inverse(s, col, y, fs) {
  const cw = CW * fs / FS, n = cells(s);
  tx.shadowColor = GL; tx.shadowBlur = fs * 0.5; tx.fillStyle = G;
  tx.fillRect(PADX + col * cw - cw * 0.35, y - fs * 1.0, (n + 0.7) * cw, fs * 1.3);
  tx.shadowBlur = 0;
  glyphs(s, col, y, fs, '#031A0B', false);
}
const typed = (s, t, t0, cps = 38) => { const k = Math.max(0, Math.floor((t - t0) * cps)); return [...s].slice(0, k).join(''); };
const typeEnd = (s, t0, cps = 38) => t0 + [...s].length / cps;
const tfmt = n => Math.round(n).toLocaleString("en-US");

function drawBeat(t, b, alpha) {
  tx.globalAlpha = alpha;
  let y = LH + 18, cursor = null, at = b.t0 + 0.05;
  for (const L of b.lines) {
    const [kind] = L;
    if (kind === 'q') {
      const s = typed(L[1], t, at);
      if (t >= at) { glyphs('>', 0, y, FS, GD, false); const e = glyphs(s, 2, y, FS, G, true); cursor = { col: e, y, fs: FS, typing: s.length < [...L[1]].length }; }
      at = typeEnd(L[1], at) + 0.12; y += LH * 1.25;
    } else if (kind === 'd') {
      const s = typed(L[1], t, at);
      if (t >= at) { const e = glyphs(s, 2, y, FS, GD, true); cursor = { col: e, y, fs: FS, typing: s.length < [...L[1]].length }; }
      at = typeEnd(L[1], at) + 0.12; y += LH * 1.25;
    } else if (kind === 'inv') {
      const fs = FS * 1.9, yy = y + fs * 0.62;
      if (t >= at) inverse(typed(L[1], t, at, 30), 1, yy, fs);
      at = typeEnd(L[1], at, 30) + 0.15; y += fs * 1.6;
    } else if (kind === 'bar' || kind === 'pbar') {
      const [, label, v, mx, off] = L, st = b.t0 + off;
      if (t >= st) {
        const p = Math.min(1, (t - st) / 0.7), e = 1 - Math.pow(1 - p, 3);
        const cellsMax = 20, n = Math.max(1, Math.round(cellsMax * (v / mx) * e));
        glyphs(label, 0, y, FS, GD, false);
        const bar = (v / mx < 0.05 ? '▏' : '█'.repeat(n));
        glyphs(bar, 8, y, FS, kind === 'pbar' && label === '2월' ? GD : G, true);
        const val = kind === 'bar' ? '$' + tfmt(v * e) : (v < 1 ? '1% 미만' : Math.round(v * e) + '%');
        glyphs(val, 8 + cellsMax + 1, y, FS, G, true);
      }
      y += LH * 1.3;
    } else if (kind === 'stamp') {
      const st = b.t0 + L[2];
      if (t >= st) { const k = Math.floor((t - st) / 0.12); if (k > 5 || k % 2 === 0) inverse('[ ' + L[1] + ' ]', 8, y + 8, FS * 1.25); }
      y += LH * 1.4;
    }
  }
  if (b.big && t >= b.t0 + b.big.t) {
    const p = Math.min(1, (t - b.t0 - b.big.t) / 0.5), e = 1 - Math.pow(1 - p, 3), fs = FS * 3.3;
    const e2 = glyphs(b.big.fmt + tfmt(b.big.roll * e), 0, y + fs * 0.75, fs, G, true);
    const sfs = FS * 1.6;
    glyphs(b.big.suf, Math.ceil(e2 * fs / sfs) + 1, y + fs * 0.75, sfs, GD, true);
    cursor = null;
  }
  if (cursor && alpha > 0.99) {          // 깜박이는 커서: 치는 동안은 켜져 있다
    const on = cursor.typing || Math.floor(t / 0.53) % 2 === 0;
    if (on) { tx.fillStyle = G; tx.shadowColor = GL; tx.shadowBlur = 10; tx.fillRect(PADX + cursor.col * CW + 2, cursor.y - FS * 0.8, CW * 0.8, FS * 0.95); tx.shadowBlur = 0; }
  }
  tx.globalAlpha = 1;
}

function renderTerm(t, TL) {
  tx.clearRect(0, 0, TW, TH);
  tx.fillStyle = GLASS; tx.fillRect(0, 0, TW, TH);
  // 영상 바로 밑 초록 선 하나로 이어 붙인다 (재생 시간·진행 막대는 인스타가 보여 주므로 넣지 않는다)
  tx.fillStyle = G; tx.fillRect(0, 0, TW, 5);
  // 지금 장면, 그리고 막 끝난 장면의 잔광 (τ≈0.1초)
  const cur = TL.term.find(b => t >= b.t0 && t < b.t1);
  const prev = TL.term.filter(b => t >= b.t1 && t < b.t1 + 0.4).pop();
  if (prev && (!cur || t - cur.t0 < 0.4)) drawBeat(prev.t1 - 0.001, prev, Math.exp(-(t - prev.t1) / 0.1));
  if (cur) drawBeat(t, cur, 1);
  // 유리: 주사선, 약한 깜박임, 가는 테두리
  tx.fillStyle = 'rgba(0,0,0,0.18)';
  for (let yy = 0; yy < TH; yy += 3) tx.fillRect(0, yy, TW, 1);
  const fl = 0.985 + 0.015 * hash(Math.floor(t * 30));
  tx.fillStyle = `rgba(0,0,0,${(1 - fl).toFixed(3)})`; tx.fillRect(0, 0, TW, TH);

}
window.renderTerm = renderTerm;
window.measureTerm = () => { tx.font = `800 ${FS}px JBM`; CW = tx.measureText('M').width; };
