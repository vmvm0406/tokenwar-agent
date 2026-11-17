"""발언 소개 릴스 (post type "video" + rank.mode "intro", 운영자 요청 2026-11-17 "예언 릴스는 지루하지 않게").

rankreel.py와 같은 rank 데이터(items: label·sub·quote·desc·source·src·credit)를 쓰되 순위를 세지 않는다.
첫 항목(가장 센 한마디)이 0초에 나오고, 나머지는 날짜 순(오래된 것 → 최근). 순위 숫자·'?' 공개 없음.
화면은 직접 짠 코드(CSS/SVG/canvas)로만 그린다: 외부 화풍 라이브러리(비상업 라이선스) 소재는 쓰지 않는다.

레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 안). 모션 그래픽 (운영자 2026-11-17 "카드 뉴스 붙여놓은 느낌 말고 애니메이션 느낌으로,
스무스하게 이어지게", "글에 효과음"): 멈춘 화면 없이 계속 움직인다.
    위        제목 띠(0초에 줄마다 쾅) → 첫 이동 때 위로 접히며 사라짐. 0초 안내 한 줄(banner.cta_line)은 끝까지.
    세계      항목들이 가로로 한 화면씩 놓여 있고 카메라가 흘러간다: 경계 앞뒤 0.35초 smootherstep 패닝(HALF) +
              머무는 동안에도 카드가 천천히 흐름(DRIFT). 층마다 속도가 달라 시차(사진 0.35배, 이름 1.1, 발언 1.25, 단서 1.4).
    사진      항목마다 다른 화풍(items[].style: duo, halftone, scan, poster, pixel, ink). 다음 사진이 확대된 채 밀려 들어오며
              겹쳐 바뀌고(뚝 끊는 전환 없음), 늘 천천히 확대·이동.
    숫자판    큰 초록 연도(도착 예상 해 target, 없으면 발언 해)가 자리마다 주행 거리계처럼 굴러 넘어간다(카메라와 같은 곡선).
    글        이름·자리 미끄러져 들어옴 → 한 줄 제목(녹색 면) 부드럽게 커졌다 자리 → 발언이 단어마다 떠오름(key는 녹색) → note.
    아래      연표 띠: 항목 점·해 이름·눈금이 카메라와 같이 흐르고 가운데 삼각이 지금 자리, 지나온 구간 녹색.
    소리      0초 쿵 + 제목 줄 타격, 이동마다 부드러운 휙, 한 줄 제목 톡, 단어마다 작은 뽁, 숫자판 째깍 (음악 아래, 높은 소리 깎음).
    끝        dm.cta 끝 화면 2.5초 (video.py append_cta_card).
박자: BPM 120(한 박 0.5초). 첫 항목 rank.first_beats(기본 4박 = 2초), 나머지 rank.beats_per_item(기본 6박 = 3초),
      마지막 rank.last_beats(기본 6박). 음악 music_gen.make_hook_music(music.style, 기본 h5-fm-arp) → -14 LUFS.
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
FIRST_BEATS, ITEM_BEATS, LAST_BEATS = 4, 6, 6
SFX_UNDER_MUSIC_DB = 2.0   # 효과음은 음악보다 이만큼 작게 (원칙 1: 음악 아래, 거슬리는 높은 소리 없음)
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
    cta = CTA_SECONDS if ((post.get("dm") or {}).get("cta") or post.get("end_cta")) else 0.0
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


HALF = 0.35      # 항목 사이 이동(카메라 패닝) 반쪽 길이(초): 경계 앞뒤 0.35초씩
DRIFT = 26.0     # 머무는 동안에도 카드가 흐르는 속도(px/초): 멈춘 화면이 없게
TRACK_GAP = 300  # 아래 연표 띠에서 항목 사이 간격(px)


def s5(x):
    """smootherstep: 속도·가속도가 양 끝에서 0 (끊김 없는 이어짐)."""
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def item_year(it):
    """연도 숫자판 값: 도착 예상 해(target), 없으면 발언 해."""
    ty = target_year(it)
    return ty if ty is not None else float(_d(it["date"]).year)


def motion_plan(post, tl):
    """화면(JS)과 효과음이 같이 쓰는 시각: 카메라 이동 중심, 항목 도착, 단어 시각, 숫자판 틱."""
    items = rank_items(post)
    sc = tl["scenes"]
    cuts = [s["start"] for s in sc[1:]]
    arrive = [0.0] + [c - HALF for c in cuts]
    leave = [c - HALF for c in cuts] + [tl["main"]]
    words, per = [], []
    for j, it in enumerate(items):
        n = max(1, len(str(it.get("quote", "")).split()))
        p = min(0.09, 1.1 / n)
        per.append(p)
        words.append([arrive[j] + 0.55 + k * p for k in range(n)])
    ys = [item_year(it) for it in items]

    def yv(t):
        return ys[0] + sum((ys[k] - ys[k - 1]) * s5((t - cuts[k - 1] + HALF) / (2 * HALF)) for k in range(1, len(ys)))
    ticks, prev = [], int(yv(0.0) + 1e-6)
    for i in range(1, int(tl["main"] * 1000)):
        v = int(yv(i / 1000) + 1e-6)
        if v != prev:
            ticks.append(i / 1000)
            prev = v
    return {"cuts": cuts, "arrive": arrive, "leave": leave, "per": per, "words": words, "years": ys, "ticks": ticks,
            "slams": [a + 0.4 for a in arrive]}


def page_html(post, cfg, tl, folder):
    """모션 그래픽 화면 (운영자 2026-11-17 "카드 뉴스 붙여놓은 느낌 말고 애니메이션 느낌으로", "스무스하게 이어지게").
    항목들이 가로로 놓인 세계를 카메라가 계속 흘러간다(경계에서 smootherstep 패닝 + 머무는 동안에도 천천히 흐름).
    층마다 속도가 달라(사진 0.35, 이름 1.1, 발언 1.25배) 시차가 생기고, 사진은 다음 사진이 확대된 채 밀려 들어오며 겹쳐 바뀐다.
    큰 연도 숫자판은 자리마다 굴러 넘어가고(주행 거리계), 아래 연표 띠는 해 눈금이 카메라와 함께 지나간다."""
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
    mp = motion_plan(post, tl)

    def img(it):
        p = Path(folder) / it["src"] if it.get("src") else None
        return p.resolve().as_uri() if p and p.exists() else None
    data = {
        "items": [{"label": it.get("label", ""), "sub": it.get("sub", ""), "who": it.get("who", ""), "quote": it.get("quote", ""),
                   "key": it.get("key", ""), "note": it.get("note", ""), "img": img(it), "pos": it.get("img_pos", "50% 22%"),
                   "style": it.get("style") or STYLES[j % len(STYLES)], "y": ds[j].year, "m": ds[j].month,
                   "target": str(it.get("target") or ""), "yv": mp["years"][j], "tilde": 1 if str(it.get("target") or "").startswith("~") else 0,
                   "srcline": it.get("src_line", ""), "per": mp["per"][j]} for j, it in enumerate(items)],
        "title_end": tl["scenes"][1]["start"] if len(tl["scenes"]) > 1 and R.get("title_first_only", True) else 1e9,
        "srcline": R.get("source_line", ""), "cuts": mp["cuts"], "arrive": mp["arrive"], "leave": mp["leave"],
        "half": HALF, "drift": DRIFT, "tg": TRACK_GAP,
        "beat": tl["beat"], "main": tl["main"], "starts": hook_starts(post, tl), "scale": HOOK_SCALE,
    }
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Black.otf');font-weight:900}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};word-break:keep-all}}
.hl{{color:{b['accent']}}}
.ph{{position:absolute;inset:0;overflow:hidden;display:none;will-change:transform,opacity}}
.ph img,.ph canvas{{position:absolute;left:-6%;top:-4%;width:112%;height:108%;object-fit:cover}}
.ph canvas{{image-rendering:pixelated}}
.ph .fx{{position:absolute;inset:0;pointer-events:none}}
.s-duo img{{filter:url(#duo)}} .s-poster img{{filter:url(#poster)}} .s-ink img{{filter:url(#ink)}}
.s-halftone img{{filter:grayscale(1) contrast(1.35)}}
.s-halftone .fx{{background-image:radial-gradient(circle,rgba(0,0,0,.85) 34%,transparent 36%);background-size:12px 12px}}
.s-scan img{{filter:grayscale(1) contrast(1.5) brightness(.9)}}
.s-scan .fx{{background:repeating-linear-gradient(0deg,rgba(0,0,0,.55) 0 3px,transparent 3px 6px)}}
.s-pixel canvas{{filter:url(#duo)}}
#dim{{position:absolute;inset:0;background:rgba(0,0,0,.6)}}
#top{{position:absolute;left:0;right:0;top:{SAFE_TOP}px;padding:18px {SIDE}px 16px;background:rgba(6,7,6,.82);z-index:5}}
#top .t{{font-family:'Black Han Sans';font-size:{TOP_FONT}px;line-height:1.12;letter-spacing:-.01em;text-align:center;overflow:hidden}}
#top .ln{{display:block;transform-origin:50% 55%}}
#top .hl.fill{{background:{b['accent']};color:#000;box-shadow:0 0 0 .06em {b['accent']}}}
#top .cl{{font-family:'Wanted';font-weight:700;font-size:36px;line-height:1.2;margin-top:10px;text-align:center;white-space:nowrap}}
#yc{{position:absolute;left:{SIDE}px;z-index:4;font-family:'Black Han Sans';font-size:118px;line-height:1;color:{b['accent']};display:flex;height:1em;overflow:hidden}}
#yc .tl{{display:inline-block;width:.5em}}
#yc .dg{{display:inline-block;width:.6em;height:1em;overflow:hidden;text-align:center}}
#yc .col{{display:flex;flex-direction:column;will-change:transform}} #yc .col span{{height:1em;display:block}}
.cd{{position:absolute;left:{SIDE}px;width:{W - 2 * SIDE}px;z-index:3;display:none;will-change:transform}}
.cd .who{{font-family:'Black Han Sans';font-size:62px;line-height:1.1}}
.cd .sub{{margin-top:6px;font-family:'Pretendard';font-weight:700;font-size:28px;color:{b['muted']}}}
.cd .lab{{margin-top:22px;display:inline-block;font-family:'Black Han Sans';font-size:66px;line-height:1.12;background:{b['accent']};color:#000;
  padding:0 .14em;transform-origin:0% 60%;white-space:nowrap}}
.cd .q{{margin-top:22px;font-family:'Wanted';font-weight:800;font-size:46px;line-height:1.36}}
.cd .q span{{display:inline-block;margin-right:.24em;transform-origin:50% 80%}}
.cd .q span.k{{color:{b['accent']}}}
.cd .note{{margin-top:16px;font-family:'Pretendard';font-weight:700;font-size:30px;color:{b['text']};border-left:6px solid {b['accent']};padding-left:14px}}
#strip{{position:absolute;left:{SIDE}px;width:{STACK_RIGHT - SIDE}px;top:{SAFE_BOTTOM - 96}px;height:84px;z-index:3;overflow:hidden}}
#src{{position:absolute;left:0;right:0;top:0;font-family:'Pretendard';font-weight:700;font-size:23px;color:{b['muted']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#rail{{position:absolute;left:50%;top:54px;height:4px;will-change:transform}}
#rbg{{position:absolute;left:0;top:0;height:4px;background:#39443F}}
#rfill{{position:absolute;left:0;top:0;height:4px;background:{b['accent']}}}
.dot{{position:absolute;top:-8px;width:20px;height:20px;margin-left:-10px;background:#39443F}}
.dot.on{{background:{b['accent']}}}
.yr{{position:absolute;top:-36px;font-family:'Pretendard';font-weight:700;font-size:21px;color:{b['muted']};transform:translateX(-50%);white-space:nowrap}}
.mt{{position:absolute;top:-3px;width:2px;height:10px;background:#39443F}}
#ph{{position:absolute;left:50%;top:44px;width:0;height:0;margin-left:-11px;border-left:11px solid transparent;border-right:11px solid transparent;border-top:12px solid {b['accent']}}}
</style></head><body><div id="f">
<svg width="0" height="0" style="position:absolute"><defs>
<filter id="duo"><feColorMatrix type="matrix" values="0.25 0.6 0.15 0 0  0.25 0.6 0.15 0 0  0.25 0.6 0.15 0 0  0 0 0 1 0"/>
 <feComponentTransfer><feFuncR type="table" tableValues="0 0.1"/><feFuncG type="table" tableValues="0.02 1"/><feFuncB type="table" tableValues="0.01 0.45"/></feComponentTransfer></filter>
<filter id="poster"><feColorMatrix type="saturate" values="0.15"/><feComponentTransfer><feFuncR type="discrete" tableValues="0 .35 .7 1"/>
 <feFuncG type="discrete" tableValues="0 .4 .75 1"/><feFuncB type="discrete" tableValues="0 .3 .6 .9"/></feComponentTransfer></filter>
<filter id="ink"><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncR type="discrete" tableValues="0 0 .55 1"/>
 <feFuncG type="discrete" tableValues="0 0 .55 1"/><feFuncB type="discrete" tableValues="0 0 .55 1"/></feComponentTransfer></filter>
</defs></svg>
<div id="phs"></div><div id="dim"></div>
<div id="top"><div class="t">{"".join(spans)}</div>{f'<div class="cl">{cl_html}</div>' if cl else ""}</div>
<div id="yc"><span class="tl">~</span></div><div id="cds"></div>
<div id="strip"><div id="src">{esc(R.get("source_line", ""))}</div><div id="rail"><div id="rbg"></div><div id="rfill"></div></div><div id="ph"></div></div>
</div><script>
const D = {json.dumps(data, ensure_ascii=False)};
const $ = id => document.getElementById(id);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const E3 = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
const S5 = x => {{ x = clamp(x, 0, 1); return x * x * x * (x * (x * 6 - 15) + 10); }};
const BK = x => {{ x = clamp(x, 0, 1); const c = 1.2; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }};  // 살짝 넘쳤다 돌아오는 부드러운 끝
const N = D.items.length, H2 = D.half, W = {W};
const camP = t => {{ let p = 0; D.cuts.forEach(c => p += S5((t - c + H2) / (2 * H2))); return p; }};
const yearV = t => {{ let v = D.items[0].yv; for (let k = 1; k < N; k++) v += (D.items[k].yv - D.items[k - 1].yv) * S5((t - D.cuts[k - 1] + H2) / (2 * H2)); return v; }};
const tildeV = t => {{ let v = D.items[0].tilde; for (let k = 1; k < N; k++) v += (D.items[k].tilde - D.items[k - 1].tilde) * S5((t - D.cuts[k - 1] + H2) / (2 * H2)); return v; }};
const CEN = D.arrive.map((a, j) => (a + (D.leave[j] || D.main)) / 2);
const PH = [], CD = [], COLS = [];
let T0H = 0, YCH = 0;
window.twSetup = async () => {{
  const out = [];
  D.items.forEach((it, i) => {{
    const d = document.createElement('div'); d.className = 'ph s-' + it.style;
    if (it.img) {{
      const im = new Image(); im.src = it.img; im.style.objectPosition = it.pos; d.appendChild(im);
      if (it.style === 'pixel') {{ const c = document.createElement('canvas'); c.width = 108; c.height = 192; d.appendChild(c); im.style.display = 'none'; }}
    }} else out.push('사진 없음: ' + it.label);
    const fx = document.createElement('div'); fx.className = 'fx'; d.appendChild(fx);
    $('phs').appendChild(d); PH.push(d);
    const c = document.createElement('div'); c.className = 'cd';
    const words = it.quote.split(/\\s+/).filter(Boolean);
    const esc_ = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
    c.innerHTML = `<div class="who">${{esc_(it.who)}}</div><div class="sub">${{esc_((it.target ? it.y + '.' + String(it.m).padStart(2, '0') + ' · ' : '') + it.sub)}}</div>` +
      `<div class="lab">${{esc_(it.label)}}</div><div class="q">` +
      words.map(w => `<span class="${{it.key && it.key.split(' ').some(k => w.includes(k)) ? 'k' : ''}}">${{esc_(w)}}</span>`).join('') + '</div>' +
      (it.note ? `<div class="note">${{esc_(it.note)}}</div>` : '');
    $('cds').appendChild(c); CD.push(c);
  }});
  await Promise.all([...document.images].map(im => im.decode().catch(() => out.push('사진을 못 읽음: ' + im.src))));
  // 연도 숫자판: 네 자리, 자리마다 0~9,0 세로 띠
  for (let k = 0; k < 4; k++) {{ const dg = document.createElement('span'); dg.className = 'dg'; const col = document.createElement('span'); col.className = 'col';
    col.innerHTML = [0,1,2,3,4,5,6,7,8,9,0].map(x => `<span>${{x}}</span>`).join(''); dg.appendChild(col); $('yc').appendChild(dg); COLS.unshift(col); }}
  YCH = $('yc').getBoundingClientRect().height;
  // 연표 띠: 항목 점 + 해 이름 + 사이 눈금
  const rail = $('rail');
  $('rbg').style.width = ((N - 1) * D.tg) + 'px';
  D.items.forEach((it, j) => {{
    const d = document.createElement('div'); d.className = 'dot'; d.id = 'dot' + j; d.style.left = (j * D.tg) + 'px'; rail.appendChild(d);
    const y = document.createElement('div'); y.className = 'yr'; y.style.left = (j * D.tg) + 'px';
    y.textContent = it.target || String(it.y); rail.appendChild(y);
    if (j < N - 1) for (let s = 1; s < 4; s++) {{ const m = document.createElement('div'); m.className = 'mt'; m.style.left = (j * D.tg + s * D.tg / 4) + 'px'; rail.appendChild(m); }}
  }});
  // 넘침 검사: 첫 항목은 제목이 있을 때, 나머지는 제목이 접힌 뒤
  T0H = $('top').querySelector('.t').getBoundingClientRect().height;
  const stripTop = $('strip').getBoundingClientRect().top;
  D.items.forEach((it, i) => {{
    $('top').querySelector('.t').style.height = (i === 0 ? T0H : 0) + 'px';
    const c = CD[i]; c.style.display = 'block';
    c.style.top = Math.round($('top').getBoundingClientRect().bottom + 26 + YCH + 10) + 'px';
    const lab = c.querySelector('.lab'); let fs = 66; lab.style.fontSize = fs + 'px';
    while (lab.getBoundingClientRect().width > c.clientWidth && fs > 44) {{ fs -= 2; lab.style.fontSize = fs + 'px'; }}
    if (lab.getBoundingClientRect().width > c.clientWidth) out.push('한 줄 제목이 넘침: ' + it.label);
    if (c.getBoundingClientRect().bottom > stripTop - 8) out.push('카드가 연표 띠와 겹침: ' + it.label + ' (' + Math.round(c.getBoundingClientRect().bottom) + 'px)');
    c.style.display = 'none';
  }});
  $('top').querySelector('.t').style.height = T0H + 'px';
  if ($('top').querySelector('.cl') && $('top').querySelector('.cl').scrollWidth > {W - 2 * SIDE}) out.push('안내 줄이 넘침');
  window.hkScale = [...document.querySelectorAll('#top .ln')].map(el => Math.min(D.scale, ({W - 2 * SIDE}) / Math.max(1, el.scrollWidth) * 0.98));
  return out;
}};
function topBand(t) {{
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
  // 제목은 첫 이동과 함께 위로 접히며 사라진다 (뚝 끊지 않음)
  const k = S5((t - (D.title_end - H2)) / (2 * H2)), tt = tp.querySelector('.t');
  tt.style.height = (T0H * (1 - k)).toFixed(1) + 'px'; tt.style.opacity = (1 - k).toFixed(3);
  tt.style.transform = `translateY(${{(-30 * k).toFixed(1)}}px)`;
}}
function odo(v, tl) {{
  COLS.forEach((col, k) => {{
    const pw = Math.pow(10, k), val = Math.floor(v / pw + 1e-9), dg = val % 10;
    const f = k === 0 ? v - Math.floor(v + 1e-9) : Math.max(0, (v % pw) - (pw - 1));
    col.style.transform = `translateY(${{(-(dg + clamp(f, 0, 1)) * 100 / 11).toFixed(3)}}%)`;
  }});
  const te = $('yc').querySelector('.tl'); te.style.opacity = tl.toFixed(3); te.style.width = (0.5 * tl).toFixed(3) + 'em';
}}
function drawPhoto(j, t, p) {{
  const d = PH[j], e = clamp(p - j + 1, 0, 1), ee = S5(e);
  if (e <= 0 || (j < N - 1 && p - j >= 1)) {{ d.style.display = 'none'; return; }}
  d.style.display = 'block';
  const x = (j - p) * W * 0.35 - 14 * (t - CEN[j]), z = 1.04 + 0.16 * (1 - ee) + 0.012 * (t - D.arrive[j]);
  d.style.opacity = ee.toFixed(3);
  const el = d.querySelector('canvas') || d.querySelector('img');
  el.style.transform = `translateX(${{x.toFixed(1)}}px) scale(${{z.toFixed(4)}})`;
  const c = d.querySelector('canvas');
  if (c) {{  // 픽셀: 들어오면서 굵은 칸에서 선명하게 풀린다
    const im = d.querySelector('img'), steps = [12, 18, 27, 40, 60, 90, 135, 200, 300, 540];
    const s = steps[Math.min(steps.length - 1, Math.floor(E3((t - D.arrive[j]) / 1.2) * steps.length))];
    const w = Math.round(s), h = Math.round(s * {H} / {W});
    if (c.width !== w) {{ c.width = w; c.height = h; }}
    const cx = c.getContext('2d'); const r = Math.max(w / im.naturalWidth, h / im.naturalHeight);
    const sw = w / r, sh = h / r, [ox, oy] = D.items[j].pos.split(' ').map(q => parseFloat(q) / 100);
    cx.drawImage(im, (im.naturalWidth - sw) * ox, (im.naturalHeight - sh) * oy, sw, sh, 0, 0, w, h);
  }}
}}
window.twFrame = (t) => {{
  const p = camP(t);
  topBand(t);
  const top = $('top').getBoundingClientRect().bottom + 26;
  $('yc').style.top = top.toFixed(1) + 'px';
  odo(yearV(t), tildeV(t));
  $('yc').style.transform = `translateX(${{(-DRIFT_YC(t)).toFixed(1)}}px)`;
  const ctop = top + YCH + 10;
  for (let j = 0; j < N; j++) {{
    drawPhoto(j, t, p);
    const c = CD[j], d = j - p;
    if (Math.abs(d) > 1.3) {{ c.style.display = 'none'; continue; }}
    c.style.display = 'block'; c.style.top = ctop.toFixed(1) + 'px';
    const a = t - D.arrive[j];
    c.style.transform = `translateX(${{(d * W - D.drift * (t - CEN[j])).toFixed(1)}}px)`;
    const it = D.items[j];
    const kw = E3((a - 0.12) / 0.4), ks = E3((a - 0.22) / 0.4);
    const who = c.querySelector('.who'), sub = c.querySelector('.sub'), lab = c.querySelector('.lab');
    who.style.opacity = kw; who.style.transform = `translateX(${{(d * W * 0.1 + (1 - kw) * 70).toFixed(1)}}px)`;
    sub.style.opacity = ks; sub.style.transform = `translateX(${{(d * W * 0.1 + (1 - ks) * 70).toFixed(1)}}px)`;
    const vl = (a - 0.4) / 0.38;
    lab.style.opacity = clamp(vl * 3, 0, 1);
    lab.style.transform = `translateX(${{(d * W * 0.05).toFixed(1)}}px) scale(${{(1.22 - 0.22 * BK(vl)).toFixed(4)}})`;
    const sp = [...c.querySelector('.q').children];
    sp.forEach((el, w) => {{ const v = (a - 0.55 - w * it.per) / 0.3; const e = E3(v);
      el.style.opacity = clamp(v * 1.6, 0, 1);
      el.style.transform = `translate(${{(d * W * (0.25 + 0.02 * w) + (1 - e) * 40).toFixed(1)}}px, ${{((1 - e) * 28).toFixed(1)}}px) scale(${{(1.18 - 0.18 * e).toFixed(3)}})`; }});
    const nt = c.querySelector('.note');
    if (nt) {{ const v = E3((a - 0.6 - sp.length * it.per - 0.1) / 0.35); nt.style.opacity = v;
      nt.style.transform = `translateX(${{(d * W * 0.4 + (1 - v) * 50).toFixed(1)}}px)`; }}
  }}
  // 연표 띠: 카메라와 같이 흐른다 (가운데 삼각 표시가 지금 자리)
  $('rail').style.transform = `translateX(${{(-p * D.tg - 6 * Math.sin(t * 0.9)).toFixed(1)}}px)`;
  $('rfill').style.width = (p * D.tg).toFixed(1) + 'px';
  for (let j = 0; j < N; j++) $('dot' + j).className = 'dot' + (j <= p + 0.5 ? ' on' : '');
  const ni = clamp(Math.round(p), 0, N - 1);
  $('src').textContent = D.items[ni].srcline || D.srcline;
}};
const DRIFT_YC = t => 4 * Math.sin(t * 1.3);
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


def _soft(sig, lo, hi):
    """부드러운 대역 통과 (FFT, 완만한 경계): 거슬리는 높은 소리를 뺀다 (STYLE_GUIDE 0 원칙 1)."""
    import numpy as np
    from music_gen import SR
    F = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1 / SR) + 1e-6
    F *= (1 / (1 + (f / hi) ** 4)) * (1 - 1 / (1 + (f / lo) ** 4))
    return np.fft.irfft(F, len(sig))


def make_sfx(post, tl, total):
    """효과음: 0초 쿵 + 제목 줄 타격, 항목 이동마다 부드러운 휙(높은 소리 깎음, 왼→오 이동), 한 줄 제목 톡,
    발언 단어마다 작은 뽁, 연도 숫자판이 넘어갈 때마다 작은 째깍. 피크 1 기준."""
    import numpy as np
    from music_gen import make_hook_sfx, SR
    mp = motion_plan(post, tl)
    hs = hook_starts(post, tl)
    base, info = make_hook_sfx(total, impacts=[0.0], hits=hs[1:])
    n = base.shape[0] if base.ndim == 2 else len(base)
    L = np.zeros(n)
    R = np.zeros(n)
    rng = np.random.default_rng(11)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(round(t0 * SR))
        if i >= n:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr
    # 휙: 이동 구간(0.7초) 전체에 걸친 띠 잡음, 가운데가 가장 크고 왼쪽에서 오른쪽으로
    m = int(2 * HALF * SR)
    for c in mp["cuts"]:
        w = _soft(rng.standard_normal(m), 250, 2200)
        x = np.linspace(0, 1, m)
        e = np.sin(np.pi * x) ** 2
        w = w / (np.max(np.abs(w)) or 1) * e * 0.32
        add(w * (1 - 0.5 * x), c - HALF, 1.0, 1.0)
        add(w * 0.5 * x, c - HALF, 0.0, 1.0)
    # 한 줄 제목 톡: 낮은 사인 탁
    tt = np.arange(int(0.12 * SR)) / SR
    tok = np.sin(2 * np.pi * (220 * tt + 300 * 0.02 * (1 - np.exp(-tt / 0.02)))) * (1 - np.exp(-tt / 0.002)) * np.exp(-tt / 0.04) * 0.3
    for s in mp["slams"]:
        add(tok, s)
    # 단어 뽁: 520→330Hz 짧은 사인, 아주 작게
    tp = np.arange(int(0.06 * SR)) / SR
    fr = 330 + 190 * np.exp(-tp / 0.012)
    pop = np.sin(2 * np.pi * np.cumsum(fr) / SR) * (1 - np.exp(-tp / 0.002)) * np.exp(-tp / 0.016) * 0.11
    for ws in mp["words"]:
        for k, t0 in enumerate(ws):
            add(pop, t0, 1.0 - 0.3 * (k % 2), 0.7 + 0.3 * (k % 2))
    # 숫자판 째깍: 1.1kHz 아주 짧게
    tk = np.arange(int(0.025 * SR)) / SR
    tick = _soft(np.sin(2 * np.pi * 1100 * tk) * np.exp(-tk / 0.005), 300, 2500) * 0.12
    for t0 in mp["ticks"]:
        add(tick, t0)
    extra = np.stack([L, R], axis=1)
    a = (base if base.ndim == 2 else np.stack([base, base], axis=1)) + extra
    peak = float(np.max(np.abs(a))) or 1.0
    info.setdefault("onsets", {})["ticks"] = mp["ticks"]
    info["onsets"]["pops"] = sum(len(w) for w in mp["words"])
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
    mix_audio(music, [], dur, mixed, None)
    # 효과음은 음악 아래로 (소리 나는 곳 RMS = 음악 RMS - SFX_UNDER_MUSIC_DB)
    import numpy as np
    from listreel import _read_audio, _write_wav, _db
    m = _read_audio(mixed)
    s = np.zeros_like(m)
    k = min(len(s), len(sfx))
    s[:k] = sfx[:k]
    act = np.abs(s).max(axis=1) > 0.12
    g = 10 ** ((_db(m) - SFX_UNDER_MUSIC_DB - _db(s[act])) / 20) if act.any() else 0.0
    _write_wav(mixed, m + s * g)
    print(f"효과음: 이동 {len(tl['scenes']) - 1}곳, 숫자판 째깍 {len(info['onsets'].get('ticks') or [])}개, 단어 뽁 {info['onsets'].get('pops')}개 (음악보다 {SFX_UNDER_MUSIC_DB:g} dB 아래)")
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
    ts = [0.15, 1.6, sc[1]["start"], sc[1]["start"] + 1.6, sc[2]["start"] - 0.1, sc[len(sc) // 2]["start"] + 1.5, sc[-1]["start"] + 2.0, dur - 1.0]
    for k, t in enumerate(ts, 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    cover_t = min(sc[0]["dur"] - HALF - 0.1, 2.4)   # 제목이 접히기 전
    shutil.copy(work / "fr" / f"{int(round(cover_t * FPS)):05d}.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(f"발언 {len(sc)}개, 첫 항목 {sc[0]['dur']:.1f}초, 항목당 {sc[1]['dur']:.1f}초, 본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur
