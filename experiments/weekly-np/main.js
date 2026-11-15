// 주간 "이번 주 AI 4가지" — News Package 문법을 세로 릴스(검정 + #00FF66)로. render(t)는 결정적.
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const eo = x => 1 - Math.pow(1 - x, 3);
const eio = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const back = (x, s = 1.7) => { x -= 1; return x * x * ((s + 1) * x + s) + 1; };
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const S = document.getElementById('s');
let TL;

function el(html) { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }

// 띠 지우개(장면 전환): 초록 84 + 검정 5 + 민트 14
function band(p) {
  if (p <= 0 || p >= 1) return '';
  const x = -120 + 1320 * eio(p);
  return `<div class="band" style="left:${x}px"><i style="width:84px;background:var(--g)"></i><i style="width:5px;background:var(--ink)"></i><i style="width:14px;background:var(--mint)"></i></div>`;
}

function plate(cx, cy, sc, opacity, sub) {
  return `<div class="plate" style="left:${cx - 400}px;top:${cy - 100}px;width:800px;height:200px;transform:skewX(-14deg) scale(${sc});opacity:${opacity}">
    <div class="in d" style="font-size:118px;line-height:1;white-space:nowrap">TOKEN WAR</div></div>` +
    (sub ? `<div class="abs d" style="left:0;right:0;top:${cy + 130}px;text-align:center;font-size:84px;opacity:${sub.o};transform:scaleX(${sub.sx})">${esc(sub.text)}</div>` : '');
}

function bug(t) {
  // 표지 판이 오른쪽 위로 날아가 채널 표시가 된다
  const p = eio(seg(t, 1.15, 1.6));
  if (t < 1.15 || t >= TL.end[0]) return '';
  return `<div class="plate" style="right:56px;top:96px;width:300px;height:64px;transform:skewX(-14deg);opacity:${p}">
     <div class="in d" style="font-size:40px;white-space:nowrap">TOKEN WAR</div></div>
     <div class="abs m" style="right:56px;top:172px;font-size:20px;color:var(--mint);opacity:${p}">AI NEWS · ${esc(TL.week.label)}</div>`;
}

function sting(t) {
  if (t >= 1.6) return '';
  let h = '';
  [[.04, 260], [.10, 420]].forEach(([a, x0]) => {
    const p = seg(t, a, a + .22);
    if (p > 0 && p < 1) h += `<div class="slash" style="left:${x0 + 900 * eo(p) - 300}px;top:${510}px;opacity:${1 - p}"></div>`;
  });
  const sl = seg(t, .16, .42), fly = eio(seg(t, 1.15, 1.6));
  const sc = (1.9 - .9 * back(sl)) * (1 - .62 * fly);
  const cx = 540 + fly * (1080 - 56 - 150 - 540), cy = 860 + fly * (128 - 860);
  const shake = (t > .42 && t < .55) ? Math.sin(t * 120) * 6 * (1 - seg(t, .42, .55)) : 0;
  const sub = { text: '이번 주 AI 소식 4가지', o: seg(t, .55, .7) * (1 - seg(t, 1.0, 1.15)), sx: eo(seg(t, .55, .8)) };
  if (sl > 0) h += `<div style="position:absolute;inset:0;transform:translateX(${shake}px)">${plate(cx, cy, sc, fly > .98 ? 0 : 1, sub)}</div>`;
  if (t > .42 && t < .7) { const r = seg(t, .42, .7); h += `<div class="abs" style="left:${540 - 400 * r}px;top:${860 - 160 * r}px;width:${800 * r}px;height:${320 * r}px;border:4px solid var(--g);border-radius:50%;opacity:${1 - r}"></div>`; }
  return h;
}

function rundown(t, recap) {
  const [a, z] = recap ? TL.recap : TL.rundown_in;
  if (t < a || t >= z) return '';
  const out = seg(t, z - .25, z);
  let h = `<div class="abs" style="left:56px;top:300px;opacity:${seg(t, a, a + .2) * (1 - out)}">
    <div class="m" style="font-size:26px;color:var(--g)">${recap ? 'RECAP · 정리' : 'THIS WEEK · 이번 주'}</div>
    <div class="d" style="font-size:150px;line-height:1;margin-top:14px;letter-spacing:-.02em">${esc(TL.week.range)}</div>
    <div class="d" style="font-size:54px;margin-top:10px;color:var(--mint)">${esc(TL.week.label)} AI 소식 4가지</div></div>`;
  TL.stories.forEach((s, i) => {
    const st = a + .35 + .28 * i, p = seg(t, st, st + .3);
    const rot = 90 * (1 - back(p, 1.4)), op = p > 0 ? 1 : 0;
    const ck = recap ? seg(t, a + 1.3 + .4 * i, a + 1.5 + .4 * i) : 0;
    h += `<div class="row" style="top:${690 + 156 * i}px;transform:perspective(900px) rotateX(${rot}deg);opacity:${op * (1 - out)}">
      <div class="n d">${String(i + 1).padStart(2, '0')}${ck > 0 ? `<div class="ck d" style="transform:scale(${1.6 - .6 * back(ck)})">✓</div>` : ''}</div>
      <div class="t d" style="${ck > 0 ? 'color:#7d8781' : ''}">${esc(s.row)}</div></div>`;
  });
  return h;
}

function story(t, s) {
  const a = s.t0, p = x => seg(t, a + x, a + x + .3);
  let h = `<div class="abs m" style="left:56px;top:380px;font-size:28px;color:var(--g);opacity:${p(.25)}">${esc(s.eyebrow)}</div>`;
  if (s.kind !== 'money') {
    const up = eo(p(.35));
    h += `<div class="abs" style="left:56px;right:56px;top:430px;height:140px;overflow:hidden">
      <div class="d" style="font-size:${/[A-Za-z]{8}/.test(s.big) && s.big.length > 16 ? 76 : 108}px;line-height:1.2;transform:translateY(${(1 - up) * 130}px);white-space:nowrap">${esc(s.big)}</div></div>`;
  }
  if (s.kind === 'spec') {
    s.lines.forEach((l, i) => { const q = p(1.0 + .45 * i);
      h += `<div class="line" style="position:absolute;left:56px;right:56px;top:${680 + 150 * i}px;opacity:${q};transform:translateX(${(1 - eo(q)) * -40}px)"><i></i><span>${esc(l)}</span></div>`; });
  }
  if (s.kind === 'checks') {
    h += `<div class="abs" style="left:56px;right:56px;top:670px">` + s.lines.map((l, i) => {
      const q = p(.9 + .35 * i), tk = seg(t, a + 2.2 + .7 * i, a + 2.38 + .7 * i);
      return `<div class="chk" style="opacity:${q}"><div class="box">${tk > 0 ? `<b style="transform:scale(${1.5 - .5 * back(tk)})">✓</b>` : ''}</div><span>${esc(l)}</span></div>`;
    }).join('') + `</div>`;
    h += `<div class="abs m" style="left:56px;top:1180px;font-size:30px;color:var(--mint);opacity:${p(3.0)}">${esc(s.note)}</div>`;
  }
  if (s.kind === 'cards') {
    s.lines.forEach((l, i) => { const q = p(.9 + .3 * i), col = i % 2, r = Math.floor(i / 2);
      h += `<div class="card abs" style="left:${56 + col * 494}px;width:474px;top:${670 + r * 270}px;height:246px;opacity:${q};transform:translateY(${(1 - eo(q)) * 40}px)">${esc(l)}</div>`; });
  }
  if (s.kind === 'money') {
    const roll = eo(seg(t, a + .5, a + 1.3));
    h += `<div class="abs d" style="left:56px;top:440px;font-size:64px;opacity:${p(.35)}">${esc(s.pre)}</div>
      <div class="abs d" style="left:40px;top:500px;font-size:330px;line-height:1;color:var(--g);letter-spacing:-.04em;opacity:${p(.4)}">${Math.round(s.num * roll)}<span style="font-size:110px;color:var(--pa);margin-left:16px">${esc(s.unit)}</span></div>`;
    s.chips.forEach((c, i) => { const q = p(1.6 + .35 * i);
      h += `<div class="card abs" style="left:${56 + i * 494}px;width:474px;top:910px;opacity:${q};transform:translateX(${(1 - eo(q)) * (i ? 60 : -60)}px)">${esc(c)}</div>`; });
    h += `<div class="abs" style="left:56px;right:56px;top:1100px;font-size:42px;font-weight:700;color:#DDE3DF;opacity:${p(2.8)}">${esc(s.note)}</div>`;
  }
  if (s.stamp) {
    const q = seg(t, a + 2.6, a + 2.76);
    if (q > 0) h += `<div class="stamp d" style="right:70px;top:1150px;transform:rotate(-8deg) scale(${1.9 - .9 * eo(q)});opacity:${q}">${esc(s.stamp)}</div>`;
  }
  return h;
}

function strap(t) {
  const first = TL.stories[0].t0, last = TL.recap[0];
  if (t < first - .05 || t >= last + .3) return '';
  const cur = TL.stories.findIndex(s => t >= s.t0 && t < s.t1);
  const i = cur < 0 ? TL.stories.length - 1 : cur, s = TL.stories[i];
  const inP = eo(seg(t, first, first + .3)), outP = eio(seg(t, last, last + .3));
  const dx = (1 - inP) * -1100 + outP * -1100;
  // 이야기가 바뀔 때 세로로 뒤집힌다 (새 글은 아래에서 위로)
  const f = i > 0 ? seg(t, s.t0, s.t0 + .32) : 1, prev = i > 0 ? TL.stories[i - 1] : null;
  const flash = i > 0 && t >= s.t0 && t < s.t0 + .08;
  let words = `<div class="sw" style="transform:translateY(${(1 - eio(f)) * 168}px)"><div class="h d">${esc(s.head)}</div><div class="e">${esc(s.en)}</div></div>`;
  if (prev && f < 1) words += `<div class="sw" style="transform:translateY(${-eio(f) * 168}px)"><div class="h d">${esc(prev.head)}</div><div class="e">${esc(prev.en)}</div></div>`;
  return `<div id="tab" style="transform:translateX(${dx}px);background:${flash ? '#fff' : 'var(--g)'}"><span class="k d">${esc(s.tab)}</span><span class="e m">${esc(s.tab_en)}</span></div>
    <div id="strap" style="transform:translateX(${dx}px)">${words}<div class="end"></div></div>
    <div id="src" class="m" style="opacity:${inP * (1 - outP) * .9}">${esc(s.src)}</div>`;
}

function endCard(t) {
  const [a] = TL.end; if (t < a) return '';
  const p = seg(t, a, a + .35);
  return plate(540, 760, 1.9 - .9 * back(p), 1, null) +
    `<div class="abs d" style="left:0;right:0;top:960px;text-align:center;font-size:62px;opacity:${seg(t, a + .3, a + .6)}">매일 AI 소식은</div>
     <div class="abs d" style="left:0;right:0;top:1050px;text-align:center;font-size:86px;color:var(--g);opacity:${seg(t, a + .45, a + .75)}">@tokenwar_ai</div>`;
}

window.render = function (t) {
  let h = sting(t) + bug(t) + rundown(t, false);
  TL.stories.forEach(s => { if (t >= s.t0 - .05 && t < s.t1) h += story(t, s); });
  h += rundown(t, true) + strap(t) + endCard(t);
  // 이야기와 순서 사이에는 띠 지우개
  [TL.rundown_in[0], ...TL.stories.map(s => s.t0), TL.recap[0], TL.end[0]].forEach(c => { h += band(seg(t, c - .15, c + .15)); });
  S.innerHTML = h;
  window.__t = t;
};

(async () => {
  TL = await (await fetch('timeline.json')).json();
  window.DUR = TL.dur;
  await document.fonts.load('400 80px "Black Han Sans"', JSON.stringify(TL) + '0123456789✓→TOKENWAR이번주소식가지매일은정리');
  await document.fonts.load('700 30px Wanted', JSON.stringify(TL));
  await document.fonts.load('700 26px Mono', 'AINEWS SOURCE RECAP THIS WEEK 0123456789');
  await document.fonts.ready;
  window.render(0);
  window.READY = true;
})();
