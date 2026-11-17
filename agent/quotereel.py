"""발언 소개 릴스 (post type "video" + rank.mode "intro", 운영자 요청 2026-11-17 "예언 릴스는 지루하지 않게").

rankreel.py와 같은 rank 데이터(items: label·sub·quote·desc·source·src·credit)를 쓰되 순위를 세지 않는다.
첫 항목(가장 센 한마디)이 0초에 나오고, 나머지는 날짜 순(오래된 것 → 최근). 순위 숫자·'?' 공개 없음.
화면은 직접 짠 코드(CSS/SVG/canvas)로만 그린다: 외부 화풍 라이브러리(비상업 라이선스) 소재는 쓰지 않는다.

레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 안):
    위        제목 띠(0초에 줄마다 쾅) + 0초 안내 한 줄(banner.cta_line, '댓글 남기시면 전체 N개 DM으로')가 끝까지.
    뒤        항목 사진이 화면 전체(어둡게 덮음). 항목마다 다른 화풍(items[].style: duo 초록 두 톤, halftone 망점,
              scan 주사선, poster 포스터, pixel 픽셀이 풀리며 선명해짐, ink 먹 흑백). 천천히 확대·이동(글자보다 느리게, 시차).
    전환      다음 사진이 대각선으로 쓸려 들어온다(초록 막대가 경계를 따라감, 0.3초) + 휙·타격.
    날짜      큰 초록 날짜(YYYY.MM)가 앞 항목 날짜에서 이번 날짜로 0.35초 동안 째깍째깍 넘어간다(틱 소리).
    이름      인물 이름(검은고딕) + 자리(작게) → 한 줄 제목(label, 녹색 면) 쾅 → 발언이 단어마다 튀어 들어옴(key는 녹색).
    맥락      note(선택): 꼭 알아야 할 단서 한 줄 (원칙 10, 예: "직업 아닌 '업무' 이야기").
    아래      연표 띠: 발언 날짜 자리마다 점, 지금 것 녹색 + 지나온 구간 녹색 선. 작은 출처 줄(rank.source_line).
    끝        dm.cta 끝 화면 2.5초 (video.py append_cta_card).
박자: BPM 120(한 박 15프레임). 첫 항목 rank.first_beats(기본 6박 = 3초), 나머지 rank.beats_per_item(기본 4박 = 2초),
      마지막 rank.last_beats(기본 5박). 소리: music_gen.make_hook_music(music.style, 기본 h5-fm-arp) + 효과음 → -14 LUFS.
"""
import asyncio
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

from rankreel import ROOT, W, H, FPS, SAFE_TOP, SAFE_BOTTOM, SIDE, STACK_RIGHT, TOP_FONT, HOOK_SCALE, esc, rank_items, hook_starts

BPM = 120.0
FIRST_BEATS, ITEM_BEATS, LAST_BEATS = 6, 4, 5
STYLES = ["duo", "halftone", "scan", "poster", "pixel", "ink"]


def is_intro_mode(post):
    return (post.get("rank") or {}).get("mode") == "intro"


def _d(s):
    y, m, d = (str(s) + "-01-01").split("-")[:3]
    return date(int(y), int(m), int(d or 1))


def timeline(post):
    """rankreel.timeline과 같은 모양 (checks.py가 길이를 이 값으로 본다)."""
    from video import CTA_SECONDS
    R = post.get("rank") or {}
    n = len(rank_items(post))
    beat = 60.0 / float(R.get("bpm", BPM))
    beats = [int(R.get("first_beats", FIRST_BEATS))] + [int(R.get("beats_per_item", ITEM_BEATS))] * max(0, n - 2) \
        + ([int(R.get("last_beats", LAST_BEATS))] if n > 1 else [])
    acc, bounds = 0, [0]
    for b in beats:
        acc += b
        bounds.append(acc)
    frames = [int(round(x * beat * FPS)) for x in bounds]
    scenes = [{"kind": "item", "i": j, "start": frames[j] / FPS, "dur": (frames[j + 1] - frames[j]) / FPS} for j in range(n)]
    cta = CTA_SECONDS if (post.get("dm") or {}).get("cta") else 0.0
    main = frames[-1] / FPS
    return {"scenes": scenes, "bpm": float(R.get("bpm", BPM)), "beat": beat, "main": main, "cta": cta, "total": main + cta,
            "reveal": 0.0, "n_frames": frames[-1]}


def target_year(it):
    """items[].target ('2027', '~2030') → 2027.0 / 2030.0. 없으면 None."""
    import re as _re
    m = _re.search(r"(\d{4})", str(it.get("target") or ""))
    return float(m.group(1)) if m else None


def order_problems(post):
    """첫 항목 뒤는 도착 예상 해(target)가 있으면 그 순서(같으면 발언 날짜 순), 없으면 발언 날짜 순."""
    its = rank_items(post)[1:]
    if not all(it.get("date") for it in its):
        return ["rank.mode intro: 항목마다 date(YYYY-MM-DD) 필요"]
    if any(it.get("target") for it in its):
        ks = [(target_year(it) or 0, _d(it["date"])) for it in its]
        return [] if ks == sorted(ks) else ["rank.mode intro: 첫 항목 뒤는 도착 예상 해(target) 오름차순, 같은 해는 발언 날짜 순"]
    ds = [_d(it["date"]) for it in its]
    return [] if ds == sorted(ds) else ["rank.mode intro: 첫 항목 뒤는 오래된 날짜 → 최근 순서"]


def page_html(post, cfg, tl, folder):
    b = cfg["brand"]
    R = post["rank"]
    items = rank_items(post)
    fonts = (ROOT / "assets" / "fonts").as_uri()
    from banner import cta_line
    cl = cta_line(post)
    hw = post.get("highlight")
    spans, used = [], False
    for ln in str(post["title"]).split("\n"):
        t = esc(ln)
        if hw and not used and hw in ln:
            t = t.replace(esc(hw), f'<span class="hl">{esc(hw)}</span>', 1)
            used = True
        spans.append(f'<span class="ln">{t}</span>')
    m_ = re.search(r"(?<=댓글 달고 ).+? 모음집|전체 [0-9]+\S*", cl or "")
    cl_html = esc(cl or "")
    if m_:
        cl_html = cl_html.replace(esc(m_.group(0)), f'<span class="hl">{esc(m_.group(0))}</span>', 1)
    ds = [_d(it["date"]) for it in items]
    tys = [target_year(it) for it in items]
    use_t = any(tys)
    pos = [(ty if use_t else (dd.year + (dd.timetuple().tm_yday - 1) / 366)) for ty, dd in zip(tys, ds)]
    vals = [v for v in pos if v is not None]
    lo, hi = min(vals), max(vals)
    span = max(1e-6, hi - lo)

    def img(it):
        p = Path(folder) / it["src"] if it.get("src") else None
        return p.resolve().as_uri() if p and p.exists() else None
    data = {
        "items": [{"label": it.get("label", ""), "sub": it.get("sub", ""), "who": it.get("who", ""), "quote": it.get("quote", ""),
                   "key": it.get("key", ""), "note": it.get("note", ""), "img": img(it), "pos": it.get("img_pos", "50% 22%"),
                   "style": it.get("style") or STYLES[j % len(STYLES)], "y": ds[j].year, "m": ds[j].month,
                   "target": str(it.get("target") or ""), "ty": tys[j], "srcline": it.get("src_line", ""),
                   "x": (None if pos[j] is None else (pos[j] - lo) / span)} for j, it in enumerate(items)],
        "title_end": tl["scenes"][1]["start"] if len(tl["scenes"]) > 1 and R.get("title_first_only", True) else 1e9,
        "srcline": R.get("source_line", ""),
        "scenes": tl["scenes"], "beat": tl["beat"], "main": tl["main"], "starts": hook_starts(post, tl), "scale": HOOK_SCALE,
        "y0": int(lo), "y1": int(hi),
    }
    years = list(range(int(lo), int(hi) + 1))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Black.otf');font-weight:900}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};word-break:keep-all}}
.hl{{color:{b['accent']}}}
.ph{{position:absolute;inset:0;overflow:hidden;display:none}}
.ph img,.ph canvas{{position:absolute;left:-4%;top:-4%;width:108%;height:108%;object-fit:cover;will-change:transform}}
.ph canvas{{image-rendering:pixelated}}
.ph .fx{{position:absolute;inset:0;pointer-events:none}}
.s-duo img{{filter:url(#duo)}} .s-poster img{{filter:url(#poster)}} .s-ink img{{filter:url(#ink)}}
.s-halftone img{{filter:grayscale(1) contrast(1.35)}}
.s-halftone .fx{{background-image:radial-gradient(circle,rgba(0,0,0,.85) 34%,transparent 36%);background-size:12px 12px}}
.s-scan img{{filter:grayscale(1) contrast(1.5) brightness(.9)}}
.s-scan .fx{{background:repeating-linear-gradient(0deg,rgba(0,0,0,.55) 0 3px,transparent 3px 6px)}}
.s-pixel canvas{{filter:url(#duo)}}
#dim{{position:absolute;inset:0;background:rgba(0,0,0,.6)}}
#edge{{position:absolute;top:-300px;width:26px;height:2600px;background:{b['accent']};display:none;transform-origin:50% 50%}}
#top{{position:absolute;left:0;right:0;top:{SAFE_TOP}px;padding:18px {SIDE}px 16px;background:rgba(6,7,6,.82);z-index:5}}
#top .t{{font-family:'Black Han Sans';font-size:{TOP_FONT}px;line-height:1.12;letter-spacing:-.01em;text-align:center}}
#top .ln{{display:block;transform-origin:50% 55%}}
#top .hl.fill{{background:{b['accent']};color:#000;box-shadow:0 0 0 .06em {b['accent']}}}
#top .cl{{font-family:'Wanted';font-weight:700;font-size:36px;line-height:1.2;margin-top:10px;text-align:center;white-space:nowrap}}
#card{{position:absolute;left:{SIDE}px;right:{SIDE}px;z-index:3}}
#dt{{font-family:'Black Han Sans';font-size:118px;line-height:1;color:{b['accent']};font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
#who{{margin-top:14px;font-family:'Black Han Sans';font-size:62px;line-height:1.1}}
#sub{{margin-top:6px;font-family:'Pretendard';font-weight:700;font-size:28px;color:{b['muted']}}}
#lab{{margin-top:22px;display:inline-block;font-family:'Black Han Sans';font-size:66px;line-height:1.12;background:{b['accent']};color:#000;
  padding:0 .14em;transform-origin:0% 60%;white-space:nowrap}}
#q{{margin-top:22px;font-family:'Wanted';font-weight:800;font-size:46px;line-height:1.36}}
#q span{{display:inline-block;margin-right:.24em;transform-origin:50% 80%}}
#q span.k{{color:{b['accent']}}}
#note{{margin-top:16px;font-family:'Pretendard';font-weight:700;font-size:30px;color:{b['text']};border-left:6px solid {b['accent']};padding-left:14px}}
#strip{{position:absolute;left:{SIDE}px;width:{STACK_RIGHT - SIDE}px;top:{SAFE_BOTTOM - 96}px;height:80px;z-index:3}}
#src{{position:absolute;left:0;right:0;top:0;font-family:'Pretendard';font-weight:700;font-size:23px;color:{b['muted']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#axis{{position:absolute;left:10px;right:10px;top:52px;height:4px;background:#39443F}}
#prog{{position:absolute;left:0;top:0;bottom:0;background:{b['accent']}}}
.dot{{position:absolute;top:-8px;width:20px;height:20px;margin-left:-10px;background:#39443F}}
.dot.on{{background:{b['accent']}}} .dot.cur{{background:{b['accent']};transform:scale(1.5)}}
.yr{{position:absolute;top:18px;font-family:'Pretendard';font-weight:700;font-size:20px;color:{b['muted']};transform:translateX(-50%)}}
</style></head><body><div id="f">
<svg width="0" height="0" style="position:absolute"><defs>
<filter id="duo"><feColorMatrix type="matrix" values="0.25 0.6 0.15 0 0  0.25 0.6 0.15 0 0  0.25 0.6 0.15 0 0  0 0 0 1 0"/>
 <feComponentTransfer><feFuncR type="table" tableValues="0 0.1"/><feFuncG type="table" tableValues="0.02 1"/><feFuncB type="table" tableValues="0.01 0.45"/></feComponentTransfer></filter>
<filter id="poster"><feColorMatrix type="saturate" values="0.15"/><feComponentTransfer><feFuncR type="discrete" tableValues="0 .35 .7 1"/>
 <feFuncG type="discrete" tableValues="0 .4 .75 1"/><feFuncB type="discrete" tableValues="0 .3 .6 .9"/></feComponentTransfer></filter>
<filter id="ink"><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncR type="discrete" tableValues="0 0 .55 1"/>
 <feFuncG type="discrete" tableValues="0 0 .55 1"/><feFuncB type="discrete" tableValues="0 0 .55 1"/></feComponentTransfer></filter>
</defs></svg>
<div id="phs"></div><div id="dim"></div><div id="edge"></div>
<div id="top"><div class="t">{"".join(spans)}</div>{f'<div class="cl">{cl_html}</div>' if cl else ""}</div>
<div id="card"><div id="dt"></div><div id="who"></div><div id="sub"></div><div id="lab"></div><div id="q"></div><div id="note"></div></div>
<div id="strip"><div id="src">{esc(R.get("source_line", ""))}</div><div id="axis"><div id="prog"></div></div></div>
</div><script>
const D = {json.dumps(data, ensure_ascii=False)};
const YEARS = {json.dumps(years)};
const $ = id => document.getElementById(id);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const E3 = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
const PH = [], PX = [];
window.twSetup = async () => {{
  const out = [];
  D.items.forEach((it, i) => {{
    const d = document.createElement('div'); d.className = 'ph s-' + it.style; d.id = 'ph' + i;
    if (it.img) {{
      const im = new Image(); im.src = it.img; im.style.objectPosition = it.pos; d.appendChild(im);
      if (it.style === 'pixel') {{ const c = document.createElement('canvas'); c.width = 108; c.height = 192; d.appendChild(c); im.style.display = 'none'; }}
    }} else out.push('사진 없음: ' + it.label);
    const fx = document.createElement('div'); fx.className = 'fx'; d.appendChild(fx);
    $('phs').appendChild(d); PH.push(d);
  }});
  await Promise.all([...document.images].map(im => im.decode().catch(() => out.push('사진을 못 읽음: ' + im.src))));
  // 연표 띠: 점과 해 눈금
  const ax = $('axis');
  D.items.forEach((it, i) => {{ const d = document.createElement('div'); d.className = 'dot'; d.id = 'dot' + i;
    if (it.x === null) d.style.display = 'none'; else d.style.left = (it.x * 100) + '%'; ax.appendChild(d); }});
  const yspan = D.y1 - D.y0;
  if (yspan > 0) YEARS.forEach(y => {{ const s = document.createElement('div'); s.className = 'yr'; s.textContent = y;
    s.style.left = (((y - D.y0) / yspan) * 100) + '%'; ax.appendChild(s); }});
  const tb = $('top').getBoundingClientRect().bottom;
  $('card').style.top = Math.round(tb + 30) + 'px';   // 가장 좁은 경우(제목 있음)로 넘침을 잰다
  const stripTop = $('strip').getBoundingClientRect().top;
  const card = $('card'), lab = $('lab'), q = $('q');
  window.LABFS = [];
  D.items.forEach((it, i) => {{
    fill(i, 99);
    let fs = 66; lab.style.fontSize = fs + 'px';
    while (lab.getBoundingClientRect().width > card.clientWidth && fs > 44) {{ fs -= 2; lab.style.fontSize = fs + 'px'; }}
    LABFS[i] = fs;
    if (lab.getBoundingClientRect().width > card.clientWidth) out.push('한 줄 제목이 넘침: ' + it.label);
    if (card.getBoundingClientRect().bottom > stripTop - 8) out.push('카드가 연표 띠와 겹침: ' + it.label + ' (' + Math.round(card.getBoundingClientRect().bottom) + 'px)');
  }});
  if ($('top').getBoundingClientRect().width > 0 && $('top').querySelector('.cl') && $('top').querySelector('.cl').scrollWidth > {W - 2 * SIDE}) out.push('안내 줄이 넘침');
  window.hkScale = [...document.querySelectorAll('#top .ln')].map(el => Math.min(D.scale, ({W - 2 * SIDE}) / Math.max(1, el.scrollWidth) * 0.98));
  return out;
}};
const fmt = (y, m) => y + '.' + String(m).padStart(2, '0');
function fill(i, u) {{
  const it = D.items[i];
  $('who').textContent = it.who; $('sub').textContent = (it.target ? fmt(it.y, it.m) + ' · ' : '') + it.sub; $('lab').textContent = it.label;
  $('src').textContent = it.srcline || D.srcline;
  if ($('q').dataset.i != i) {{
    $('q').dataset.i = i;
    const words = it.quote.split(/\\s+/).filter(Boolean);
    $('q').innerHTML = words.map(w => `<span class="${{it.key && it.key.split(' ').some(k => w.includes(k)) ? 'k' : ''}}">${{w.replace(/&/g,'&amp;').replace(/</g,'&lt;')}}</span>`).join('');
  }}
  $('note').textContent = it.note; $('note').style.display = it.note ? 'block' : 'none';
  if (window.LABFS && LABFS[i]) $('lab').style.fontSize = LABFS[i] + 'px';
}}
const sceneAt = t => {{ let s = D.scenes[0]; for (const x of D.scenes) if (t >= x.start - 1e-6) s = x; return s; }};
function topSlam(t) {{
  const tp = $('top'); let dx = 0, dy = 0;
  tp.querySelectorAll('.ln').forEach((el, i) => {{
    const v = t - D.starts[i] + 1e-6;
    if (v < 0) {{ el.style.opacity = '0'; return; }}
    const S0 = Math.max(1.0, window.hkScale[i]); let k = 1;
    if (v < 0.1) k = S0 - (S0 - 0.95) * Math.pow(v / 0.1, 2);
    else if (v < 0.234) {{ const qq = (v - 0.1) / 0.134; k = 0.95 + 0.05 * (1 - Math.pow(1 - qq, 2)); }}
    el.style.opacity = '1'; el.style.transform = `scale(${{k.toFixed(4)}})`;
    if (v < 0.3) {{ const a = (i === 0 ? 12 : 8) * Math.exp(-v / 0.07); dx += a * Math.sin(v * 95 + i); dy += a * Math.cos(v * 83 + i * 2); }}
  }});
  tp.style.transform = `translate(${{dx.toFixed(1)}}px, ${{dy.toFixed(1)}}px)`;
  const last = D.starts[D.starts.length - 1];
  tp.querySelectorAll('.t .hl').forEach(el => el.classList.toggle('fill', t >= last && t < last + D.beat));
}}
function drawPhoto(i, u, dur, wipe) {{
  const d = PH[i]; d.style.display = 'block';
  const k = u / dur, z = 1.04 + 0.08 * k, px = (i % 2 ? -1 : 1) * 18 * k, py = -10 * k;
  const el = d.querySelector('canvas') || d.querySelector('img');
  el.style.transform = `translate(${{px.toFixed(1)}}px, ${{py.toFixed(1)}}px) scale(${{z.toFixed(4)}})`;
  const c = d.querySelector('canvas');
  if (c) {{  // 픽셀: 굵은 칸에서 선명하게 풀린다
    const im = d.querySelector('img'), steps = [12, 18, 27, 40, 60, 90, 135, 200, 300, 540];
    const s = steps[Math.min(steps.length - 1, Math.floor(E3(u / Math.min(1.2, dur * 0.7)) * steps.length))];
    const w = Math.round(s), h = Math.round(s * {H} / {W});
    if (c.width !== w) {{ c.width = w; c.height = h; }}
    const cx = c.getContext('2d'); const r = Math.max(w / im.naturalWidth, h / im.naturalHeight);
    const sw = w / r, sh = h / r, [ox, oy] = D.items[i].pos.split(' ').map(p => parseFloat(p) / 100);
    cx.drawImage(im, (im.naturalWidth - sw) * ox, (im.naturalHeight - sh) * oy, sw, sh, 0, 0, w, h);
  }}
  // 대각선 쓸기 (0~0.3초): 왼쪽에서 오른쪽으로
  if (wipe < 1) {{
    const x = -400 + wipe * ({W} + 800);
    d.style.clipPath = `polygon(0 0, ${{x + 300}}px 0, ${{x - 300}}px 100%, 0 100%)`;
    const e = $('edge'); e.style.display = 'block'; e.style.left = (x - 13) + 'px'; e.style.transform = 'rotate(17deg)';
  }} else {{ d.style.clipPath = 'none'; }}
}}
window.twFrame = (t) => {{
  const s = sceneAt(t), i = s.i, u = t - s.start;
  topSlam(t);
  const showT = t < D.title_end - 1e-6;
  $('top').querySelector('.t').style.display = showT ? 'block' : 'none';
  $('card').style.top = Math.round($('top').getBoundingClientRect().bottom + (showT ? 30 : 46)) + 'px';
  PH.forEach(p => p.style.display = 'none'); $('edge').style.display = 'none';
  const wipe = i === 0 ? 1 : clamp(u / 0.3, 0, 1);
  if (wipe < 1) drawPhoto(i - 1, D.scenes[i - 1].dur, D.scenes[i - 1].dur, 1);
  drawPhoto(i, u, s.dur, wipe);
  fill(i, u);
  const it = D.items[i], pv = i ? D.items[i - 1] : {{y: it.y, m: Math.max(1, it.m - 6)}};
  const k = clamp(u / 0.35, 0, 1);
  if (it.target) {{   // 도착 예상 해: 앞 항목 해(없으면 2025)에서 째깍째깍
    const a = (pv.ty || 2025), bb = it.ty, cur = Math.round(a + (bb - a) * Math.floor(k * 8) / 8);
    $('dt').style.display = 'block'; $('dt').textContent = (it.target.startsWith('~') ? '~' : '') + cur;
  }} else if (D.items.some(x => x.target)) {{ $('dt').style.display = 'none'; }} else {{
    const a = pv.y * 12 + pv.m - 1, bb = it.y * 12 + it.m - 1, cur = Math.round(a + (bb - a) * Math.floor(k * 8) / 8);
    $('dt').style.display = 'block'; $('dt').textContent = fmt(Math.floor(cur / 12), cur % 12 + 1);
  }}
  $('dt').style.transform = k < 1 ? `translateY(${{(Math.sin(u * 90) * 4).toFixed(1)}}px)` : '';
  // 이름 → 한 줄 제목 쾅 → 발언 단어마다
  const kw = E3((u - 0.08) / 0.22);
  $('who').style.opacity = kw; $('who').style.transform = `translateX(${{((1 - kw) * -60).toFixed(1)}}px)`;
  $('sub').style.opacity = E3((u - 0.16) / 0.22);
  const vl = u - 0.32;
  if (vl < 0) {{ $('lab').style.opacity = 0; }} else {{
    let sc = 1; if (vl < 0.1) sc = 1.35 - 0.4 * Math.pow(vl / 0.1, 2); else if (vl < 0.23) sc = 0.95 + 0.05 * E3((vl - 0.1) / 0.13);
    $('lab').style.opacity = 1; $('lab').style.transform = `scale(${{sc.toFixed(4)}})`;
  }}
  const sp = [...$('q').children], q0 = 0.5, per = Math.min(0.09, (s.dur * 0.55) / Math.max(1, sp.length));
  sp.forEach((el, j) => {{ const v = (u - q0 - j * per) / 0.16; const e = E3(v);
    el.style.opacity = clamp(v, 0, 1); el.style.transform = `translateY(${{((1 - e) * 26).toFixed(1)}}px) scale(${{(1.25 - 0.25 * e).toFixed(3)}})`; }});
  const nt = E3((u - q0 - sp.length * per - 0.05) / 0.25);
  $('note').style.opacity = nt; $('note').style.transform = `translateX(${{((1 - nt) * 40).toFixed(1)}}px)`;
  // 연표 띠
  const ix = it.x === null ? 0 : it.x;
  D.items.forEach((x, j) => {{ const d = $('dot' + j); d.className = 'dot' + (j === i ? ' cur' : (x.x !== null && x.x <= ix && j < i ? ' on' : '')); }});
  const pv2 = i ? D.items.slice(0, i).reduce((m, x) => Math.max(m, x.x === null ? 0 : x.x), 0) : 0;
  $('prog').style.width = ((pv2 + (Math.max(ix, pv2) - pv2) * E3(u / 0.35)) * 100).toFixed(2) + '%';
}};
</script></body></html>"""


async def shoot(post, cfg, work, tl, folder):
    from playwright.async_api import async_playwright
    page_file = work / "quote.html"
    page_file.write_text(page_html(post, cfg, tl, folder), encoding="utf-8")
    fr = work / "fr"
    fr.mkdir(exist_ok=True)
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        problems = await pg.evaluate("twSetup()")
        if problems:
            await browser.close()
            return problems
        for k in range(tl["n_frames"]):
            await pg.evaluate(f"twFrame({k / FPS:.5f})")
            await pg.screenshot(path=str(fr / f"{k:05d}.jpg"), type="jpeg", quality=93)
        await browser.close()
    return []


def make_sfx(post, tl, total):
    import numpy as np
    from music_gen import make_hook_sfx
    sc = tl["scenes"]
    hs = hook_starts(post, tl)
    changes = [s["start"] for s in sc[1:]]
    ticks = sorted([s["start"] + k * 0.35 / 8 for s in sc[1:] for k in range(1, 9, 2)] + [s["start"] + 0.34 for s in sc])
    a, info = make_hook_sfx(total, impacts=[0.0], hits=hs[1:] + changes, whooshes=changes, ticks=ticks)
    peak = float(np.max(np.abs(a))) or 1.0
    return a / peak, info


def make_quote_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, -14 LUFS), frames/*.jpg, cover.jpg. 전체 길이(초) 반환."""
    folder = Path(folder)
    probs = order_problems(post)
    if probs:
        raise ValueError("\n".join(probs))
    work = folder / "_quote"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    tl = timeline(post)
    problems = asyncio.run(shoot(post, cfg, work, tl, folder))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(work / "fr" / "%05d.jpg"),
                    "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-r", str(FPS), str(silent)], check=True)
    dur = tl["main"]
    pm = post.get("music") or {}
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    else:
        from music_gen import make_hook_music
        music = work / "music.wav"
        acc = [s["start"] for s in tl["scenes"]][::3]
        make_hook_music(music, tl["bpm"], dur, acc, seed=int(pm.get("seed", 23)), style=pm.get("style", "h5-fm-arp"))
        print(f"배경음악: {pm.get('style', 'h5-fm-arp')} BPM {tl['bpm']:g}, 크래시 {['%.1f' % x for x in acc]}")
    from listreel import mix_audio
    sfx, info = make_sfx(post, tl, dur)
    mixed = work / "mix.wav"
    st = mix_audio(music, [], dur, mixed, sfx)
    print(f"효과음: 전환 {len(tl['scenes']) - 1}곳, 틱 {info['onsets'].get('ticks')}개 (소리 나는 곳 {st.get('sfx_db') or 0:.1f} dB RMS)")
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    from video import dm_cta, append_cta_card
    cta = dm_cta(post)
    if cta:
        dur = append_cta_card(out, cta, cfg, work, dur)
    from loudness import normalize
    normalize(out)
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    sc = tl["scenes"]
    ts = [0.15, 1.6, sc[1]["start"] + 0.15, sc[1]["start"] + 1.6, sc[len(sc) // 2]["start"] + 1.5, sc[-1]["start"] + 2.0, dur - 1.0]
    for k, t in enumerate(ts, 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    cover_t = min(sc[0]["dur"] - 2 / FPS, 2.4)
    shutil.copy(work / "fr" / f"{int(round(cover_t * FPS)):05d}.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(f"발언 {len(sc)}개, 첫 항목 {sc[0]['dur']:.1f}초, 항목당 {sc[1]['dur']:.1f}초, 본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur
