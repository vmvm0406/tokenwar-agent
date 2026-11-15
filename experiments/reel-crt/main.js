// v3: 영상 위에는 평범한 자막, 아래 빈칸에만 모션. render(t)는 결정적.
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const eo = x => 1 - Math.pow(1 - x, 3);
const back = (x, s = 1.6) => { x -= 1; return x * x * ((s + 1) * x + s) + 1; };
const $ = s => document.querySelector(s);
const fmt = n => Math.round(n).toLocaleString('en-US');
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
let TL; const cache = new Map();
const cv = $('#cv'), cx = cv.getContext('2d');

function img(i) {
  i = clamp(i, 1, TL.frames);
  if (cache.has(i)) return cache.get(i);
  const im = new Image(); im.src = `frames/${String(i).padStart(5, '0')}.jpg`;
  const p = im.decode().then(() => im); cache.set(i, p);
  if (cache.size > 12) cache.delete(cache.keys().next().value);
  return p;
}
const shotAt = t => TL.shots.find(s => t >= s.t0 && t < s.t1) || TL.shots[TL.shots.length - 1];

async function footage(t) {
  const im = await img(Math.floor(t * TL.fps) + 1), s = shotAt(t), W = 1080, H = 608;
  cx.save(); cx.fillStyle = '#161616'; cx.fillRect(0, 0, W, H);
  cx.filter = 'contrast(1.06) saturate(0.94)';
  // 16:9 원본을 화면 폭 그대로 (자르지 않음), 아주 천천히 다가감
  const z = 1 + (s.kind === 'head' ? 0.03 : 0.035) * seg(t, s.t0, s.t1), w = W * z, h = H * z;
  cx.drawImage(im, (W - w) / 2, (H - h) * (s.kind === 'head' ? 0.35 : 0.5), w, h);
  cx.restore();
}

function subtitle(t) {
  const c = TL.cues.find(c => t >= c.t0 && t < c.t1);
  $('#sub').textContent = c ? c.sub : '';
}

function motion(t) {
  const b = TL.beats.find(b => t >= b.t0 && t < b.t1);
  if (!b) { $('#mo').innerHTML = ''; return; }
  const inP = seg(t, b.t0, b.t0 + 0.25), outP = seg(t, b.t1 - 0.2, b.t1);
  const wrap = h => `<div style="opacity:${inP * (1 - outP)};transform:translateY(${(1 - eo(inP)) * 40 - outP * 20}px)">${h}</div>`;
  let h = '';
  if (b.kind === 'hook') {
    const n = b.num * eo(seg(t, b.t0 + 0.1, b.t0 + 0.6));
    h = `<div class="kk">${esc(b.kicker)}</div>
      <div style="display:flex;align-items:flex-end;gap:22px;margin-top:22px"><span class="blk" style="font-size:170px">${b.fmt}${fmt(n)}</span><span class="d" style="font-size:64px;padding-bottom:12px">${esc(b.pre)}</span></div>`;
  } else if (b.kind === 'word') {
    const p = seg(t, b.t0 + 0.08, b.t0 + 0.3);
    h = `<div class="eb">${esc(b.eyebrow)}</div>
      <div style="margin-top:22px"><span class="blk" style="font-size:150px;transform-origin:0 100%;transform:scale(${1.25 - 0.25 * back(p)})">${esc(b.word)}</span></div>
      <div class="lab">${esc(b.label)}</div>`;
  } else if (b.kind === 'vs') {
    const na = b.a.num * eo(seg(t, b.a.t, b.a.t + 0.5)), pb = seg(t, b.b.t, b.b.t + 0.25);
    const nb = b.b.num * eo(seg(t, b.b.t, b.b.t + 0.6));
    const st = seg(t, b.stamp_t, b.stamp_t + 0.16);
    h = `<div class="eb">${esc(b.eyebrow)}</div>
      <div class="vs"><div class="c"><div class="l">${esc(b.a.label)}</div><div class="n">$${fmt(na)}</div></div>
        <div class="arr" style="opacity:${pb}">→</div>
        <div class="c" style="opacity:${pb};transform:translateX(${(1 - eo(pb)) * 40}px)"><div class="l">${esc(b.b.label)}</div><div class="n"><span class="blk">$${fmt(nb)}</span></div></div></div>
      ${st > 0 ? `<div class="stamp" style="transform:rotate(-8deg) scale(${1.9 - 0.9 * eo(st)});opacity:${st}">${esc(b.stamp)}</div>` : ''}`;
  } else if (b.kind === 'bars') {
    h = `<div class="eb">${esc(b.eyebrow)}</div>` + b.bars.map(r => {
      const p = seg(t, r.t, r.t + 0.6), w = Math.max(r.num, 0.8) / 30 * 100 * eo(p);
      const dim = r.label !== '현재';
      return `<div class="br${dim ? ' dim' : ''}" style="opacity:${seg(t, r.t, r.t + 0.15)}"><div class="l">${esc(r.label)}</div>
        <div class="tr"><i style="width:${w.toFixed(2)}%"></i></div><div class="v">${p > 0.6 ? esc(r.show) : ''}</div></div>`;
    }).join('');
  }
  $('#mo').innerHTML = wrap(h);
}

window.render = async function (t) {
  await footage(t);
  subtitle(t);
  window.renderTerm(t, TL);
};

(async () => {
  TL = await (await fetch('timeline.json')).json();
  window.DUR = TL.dur;
  $('#title').innerHTML = esc(TL.title.replace('|', ' ')).replace(/\{(.+?)\}/g, '<i>$1</i>');
  $('#credit').textContent = TL.credit;
  const all = JSON.stringify(TL) + '0123456789$,%→';
  await document.fonts.load('400 80px "Black Han Sans"', all);
  await document.fonts.load('800 44px Wanted', all);
  await document.fonts.load('700 30px Wanted', all);
  await document.fonts.load('800 33px JBM', '0123456789$%,>TOKENWAR.LOG[]');
  await document.fonts.ready;
  window.measureTerm();
  await window.render(0);
  window.READY = true;
})();
