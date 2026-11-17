"""순위 카운트다운 릴스 (post type "video" + "rank", 운영자 요청 2026-11-17 "AI에게 빠르게 대체 당할 직업 TOP 10",
"마지막에 숨기는 거 너무 오래 끌지 않게", "사람들은 뭔가 움직이는 게 어떻게 변하는가를 은근 계속 봐").

공개 자료의 순위(점수·비율) 또는 발언 목록(인물 예측 TOP 10 등)을 10위 → 1위로 세며 보여 준다. 그림 없이 글자·숫자·막대만.
길이 20~35초 (끝 화면 포함, 기본 약 25초). 화면은 한순간도 멈추지 않는다: 장면 안에서도 무엇이 어떻게 바뀌는지 계속 보이게.

레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 config.json reel_safe 안):
    0~2초       첫 화면: 제목 줄마다 쾅 박힘(listreel과 같은 1.3배 → 0.95 → 1.0, 8분음표 간격) + 강조어 녹색 면 번쩍,
                그 아래 큰 숫자 카운터(rank.hook_count, 예: 785개 직업)가 0부터 올라가고, 아래 순위표 칸이 '?'로 아래에서부터 채워진다.
    순위 장면   위: 순위 카드 (큰 녹색 순위 숫자가 이전 순위에서 굴러 내려와 바뀜 + 이름(검은고딕) + 영어 원문 이름(작게)).
                가운데: 점수 줄 (값 라벨 + 0부터 올라가는 숫자 + 직각 막대가 차오름 + 평균 눈금) 또는 발언(quote, 글자가 차례로 찍힘).
                아래: 순위표 (1위가 맨 위, 아직 안 나온 순위는 'NN ?'). 막대가 다 차면 그 순위 줄이 녹색으로 번쩍 박힌다.
                뒤: 아주 흐린 거대한 순위 숫자가 천천히 흘러간다. 순위 숫자는 박마다 살짝 뛴다(박자 맞춤).
    1위         rank.reveal_beats(기본 1박 = 0.5초) 동안 이름 자리에 '?'(떨림) + 점수 막대는 먼저 차오름 → 박 위에서 이름이 쾅 박힘
                (녹색 면 한 박 + 흔들림 + 쿵). 그 뒤 순위표가 10위 → 1위로 한 줄씩 번쩍 훑고 끝 화면.
    3초~본편 끝 '자료' 안내 띠(dm.banner, 안전 영역 맨 위). rank.intro가 없으면(기본) 아래 '0초부터'로 대신한다.
    작은 출처 줄 rank.source_line (점수 줄 아래, 안전 영역 안)
    끝          dm.cta 끝 화면 2.5초 (video.py append_cta_card)

0초부터(기본, 운영자 결정 2026-11-17: 제목만 있는 첫 화면 → 3초 안 건너뛰기 69%): 위의 '첫 화면'(rank.intro: true일 때만)을 빼고
    0초에 바로 10위 장면. 맨 위에 제목 띠(2줄, 0초에 줄마다 쾅) + 그 아래 안내 한 줄(banner.cta_line, rank.cta_line)이 끝까지 남고,
    순위 카드·순위표는 그 아래. 3초 '자료' 띠는 붙이지 않는다.
그림(선택, rank.items[].src): 순위마다 사진 한 장이 화면 전체 뒤에 깔린다(어둡게 덮어 글자가 읽히게, 장면 안에서 천천히 확대,
    바뀔 때 0.2초 겹쳐 바뀜). 1위는 '?' 동안 흐리게 가렸다가 공개 박에 선명해진다. 출처·라이선스는 items[].credit (캡션 끝 한 줄).
박자: BPM 기본 120 (한 박 = 15프레임, 장면 전환이 박과 0ms 차이). 순위 하나 = rank.beats_per_item(기본 4박 = 2초).
소리: music_gen.make_hook_music(첫 순위에서 비트 드롭, 1위 공개 박에 크래시) + 효과음(코드 합성: 0초 쿵, 제목 줄 타격,
      순위가 바뀔 때마다 휙 + 타격, 순위표 칸이 생기고 박힐 때마다 틱, 1위 앞 스웰 → 공개 쿵) → -14 LUFS.
"""
import asyncio
import html
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)
RAIL_LEFT = _SAFE.get("rail_left", 850)

LENGTH_RANGE = (20.0, 35.0)   # 끝 화면 포함 (STYLE_GUIDE 6장 "순위 카운트다운 릴스", checks.py)
BPM = 120.0                   # 한 박 15프레임
BEATS_PER_ITEM = 4            # 순위 하나 2초
HOOK_BEATS = 4                # 첫 화면 2초
REVEAL_BEATS = 1              # 1위 '?' 시간 (0.5초, "너무 오래 끌지 않게")
TOP_BEATS = 5                 # 1위 장면 전체 (공개 앞 1박 + 뒤 4박)
TITLE_FONT = 104
TOP_FONT = 60                 # 0초부터 위쪽 제목 띠 (rank.intro 없을 때)
HOOK_SCALE = 1.3
STACK_RIGHT = 840             # 순위표 오른쪽 끝 (오른쪽 아래 버튼 줄 x 850~ 안쪽)
LABEL_MAX, LABEL_MIN = 84, 52


def esc(s):
    return html.escape(str(s or ""))


def rank_items(post):
    """rank.items (1위부터). 각 {label, sub, value, quote, desc, source}."""
    return list((post.get("rank") or {}).get("items") or [])


def opts(post):
    R = post.get("rank") or {}
    return {"bpm": float(R.get("bpm", BPM)), "k": int(R.get("beats_per_item", BEATS_PER_ITEM)),
            "hook": int(R.get("hook_beats", HOOK_BEATS)), "reveal": int(R.get("reveal_beats", REVEAL_BEATS)),
            "top": int(R.get("top_beats", TOP_BEATS)), "intro": R.get("intro", False) is True}


def timeline(post):
    """장면 순서와 길이 (checks.py도 이 함수로 길이를 검사한다).
    반환: {"scenes": [{"kind": hook|rank|top, "i": 항목 번호(0=1위), "start", "dur"}], "bpm", "beat", "main", "cta", "total", "reveal"}"""
    if (post.get("rank") or {}).get("mode") == "intro":   # 발언 소개 릴스 (agent/quotereel.py): 순위 없이 날짜 순
        from quotereel import timeline as _qt
        return _qt(post)
    from video import CTA_SECONDS
    o = opts(post)
    n = len(rank_items(post))
    beat = 60.0 / o["bpm"]
    plan = ([("hook", None, o["hook"])] if o["intro"] else []) + [("rank", i, o["k"]) for i in range(n - 1, 0, -1)] + [("top", 0, o["top"])]
    acc, bounds = 0, [0]
    for _, _, b in plan:
        acc += b
        bounds.append(acc)
    frames = [int(round(x * beat * FPS)) for x in bounds]
    scenes = [{"kind": k, "i": i, "start": frames[j] / FPS, "dur": (frames[j + 1] - frames[j]) / FPS, "beat_at": bounds[j]}
              for j, (k, i, _) in enumerate(plan)]
    cta = CTA_SECONDS if (post.get("dm") or {}).get("cta") else 0.0
    main = frames[-1] / FPS
    reveal = round(o["reveal"] * beat * FPS) / FPS
    return {"scenes": scenes, "bpm": o["bpm"], "beat": beat, "main": main, "cta": cta, "total": main + cta,
            "reveal": reveal, "n_frames": frames[-1]}


def hook_starts(post, tl):
    """제목 줄이 박히는 시각 (8분음표 간격, 프레임에 맞춤)."""
    lines = str(post["title"]).split("\n")
    step = tl["beat"] / 2 if 0.15 <= tl["beat"] / 2 <= 0.27 else tl["beat"] / 4
    return [round(i * step * FPS) / FPS for i in range(len(lines))]


def fmt_value(v, dec):
    return f"{float(v):.{dec}f}"


def page_html(post, cfg, tl, folder=None):
    b = cfg["brand"]
    R = post["rank"]
    items = rank_items(post)
    n = len(items)
    fonts = (ROOT / "assets" / "fonts").as_uri()
    from banner import banner_text, banner_height, cta_line
    intro = opts(post)["intro"]
    cl = None if intro else cta_line(post)
    bt = banner_text(post) if (intro or not cl) else None
    card_top = SAFE_TOP + (banner_height(bt) + 26 if bt else 20)   # intro 없으면 JS가 위쪽 제목 띠 아래로 옮긴다
    dec = int(R.get("value_decimals", 1))
    vmax = float(R.get("value_max") or max([float(x["value"]) for x in items if x.get("value") is not None] or [1]))
    hw = post.get("highlight")
    t_lines = str(post["title"]).split("\n")
    spans, used = [], False
    for ln in t_lines:
        t = esc(ln)
        if hw and not used and hw in ln:
            t = t.replace(esc(hw), f'<span class="hl">{esc(hw)}</span>', 1)
            used = True
        spans.append(f'<span class="ln">{t}</span>')
    def _img(it):
        p = (Path(folder) / it["src"]) if (folder and it.get("src")) else None
        return p.resolve().as_uri() if p and p.exists() else None
    data = {
        "intro": intro,
        "items": [{"label": it.get("label", ""), "sub": it.get("sub", ""), "img": _img(it), "imgx": it.get("img_x", 50),
                   "value": (None if it.get("value") is None else float(it["value"])),
                   "quote": it.get("quote") or ""} for it in items],
        "scenes": tl["scenes"], "beat": tl["beat"], "reveal": tl["reveal"], "main": tl["main"],
        "hook": {"starts": hook_starts(post, tl), "scale": HOOK_SCALE,
                 "count": R.get("hook_count"), "count_text": R.get("hook_text", "")},
        "dec": dec, "vmax": vmax, "avg": R.get("avg"), "avg_label": R.get("avg_label", "평균"),
        "unit": R.get("value_unit", ""), "vlabel": R.get("value_label", ""),
        "stack_top": 0, "n": n,
    }
    ht = R.get("hook_text", "")
    count_html = ""
    if R.get("hook_count") is not None:
        pre, _, post_t = ht.partition("{n}") if "{n}" in ht else ("", "", ht)
        count_html = f'<div id="count">{esc(pre)}<b id="cnum">0</b>{esc(post_t)}</div>'
    m_ = __import__("re").search(r"[0-9]+위까지|전체 [0-9]+\S*", cl or "")
    cl_html = esc(cl or "")
    if m_:
        cl_html = cl_html.replace(esc(m_.group(0)), f'<span class="hl">{esc(m_.group(0))}</span>', 1)
    top_html = (f'<div id="top"><div class="t">{"".join(spans)}</div>' + (f'<div class="cl">{cl_html}</div>' if cl else "") + '</div>'
                if not intro else "")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Black.otf');font-weight:900}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};word-break:keep-all}}
.hl{{color:{b['accent']}}}
/* 뒤의 거대한 순위 숫자: 단색(녹색 7%), 글로우·그라데이션 없음 */
#ph{{position:absolute;inset:0;overflow:hidden;background:{b['bg']}}}
#ph img{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;display:none;will-change:transform,opacity,filter}}
#shade{{position:absolute;inset:0;background:rgba(4,5,4,.66)}}
#top{{position:absolute;left:0;right:0;top:{SAFE_TOP}px;padding:18px {SIDE}px 16px;background:rgba(6,7,6,.78);z-index:5}}
#top .t{{font-family:'Black Han Sans';font-size:{TOP_FONT}px;line-height:1.12;letter-spacing:-.01em;text-align:center}}
#top .ln{{display:block;transform-origin:50% 55%;will-change:transform}}
#top .hl.fill{{background:{b['accent']};color:#000;box-shadow:0 0 0 .06em {b['accent']}}}
#top .cl{{font-family:'Wanted';font-weight:700;font-size:36px;line-height:1.2;margin-top:10px;text-align:center;color:{b['text']};white-space:nowrap}}
#f.cp #rowA,#f.cp #rk,#f.cp #lab{{height:180px}} #f.cp .rkn{{font-size:180px;line-height:180px}} #f.cp #rk{{width:220px}} #f.cp #lab{{left:232px}}
#f.cp #val{{margin-top:14px;height:128px}}
#f.cp #lt,#f.cp #ls,#f.cp #vl,#f.cp #src,#f.cp .r{{text-shadow:0 2px 10px rgba(0,0,0,.8)}}
#bg{{position:absolute;right:-40px;top:300px;font-family:'Black Han Sans';font-size:1180px;line-height:1;color:rgba(0,255,102,.07);
  white-space:nowrap;will-change:transform;transform-origin:70% 50%}}
#hook{{position:absolute;left:{SIDE}px;right:{SIDE}px;top:{SAFE_TOP + 15}px;text-align:left}}
#hook .t{{font-family:'Black Han Sans';font-size:{TITLE_FONT}px;line-height:1.12;letter-spacing:-.01em}}
#hook .ln{{display:block;transform-origin:0% 55%;will-change:transform}}
#hook .hl.fill{{background:{b['accent']};color:#000;box-shadow:0 0 0 .06em {b['accent']}}}
#count{{margin-top:34px;font-family:'Wanted';font-weight:800;font-size:50px;color:{b['text']}}}
#count b{{font-family:'Black Han Sans';font-weight:400;font-size:84px;color:{b['accent']};margin-right:.12em;
  display:inline-block;font-variant-numeric:tabular-nums}}
#card{{position:absolute;left:{SIDE}px;right:{SIDE}px;top:{card_top}px;display:none}}
#rowA{{position:relative;height:210px;overflow:hidden}}
#rk{{position:absolute;left:0;top:0;width:250px;height:210px;overflow:hidden}}
.rkn{{position:absolute;left:0;top:0;font-family:'Black Han Sans';font-size:210px;line-height:210px;color:{b['accent']};
  letter-spacing:-.04em;will-change:transform}}
#lab{{position:absolute;left:262px;right:0;top:0;height:210px;display:flex;flex-direction:column;justify-content:center}}
#lt{{font-family:'Black Han Sans';font-size:{LABEL_MAX}px;line-height:1.08;white-space:nowrap;transform-origin:0% 60%;
  will-change:transform;align-self:flex-start;padding:0 .08em;margin-left:-.08em}}
#lt.fill{{background:{b['accent']};color:#000}}
#ls{{font-family:'Pretendard';font-weight:700;font-size:27px;line-height:1.25;color:{b['muted']};letter-spacing:.02em;margin-top:10px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#val{{position:relative;margin-top:26px;height:150px}}
#vl{{position:absolute;left:0;bottom:84px;font-family:'Wanted';font-weight:700;font-size:32px;color:{b['muted']}}}
#vn{{position:absolute;right:0;bottom:78px;font-family:'Black Han Sans';font-size:86px;line-height:1;color:{b['accent']};
  font-variant-numeric:tabular-nums}}
#vn small{{font-size:40px;color:{b['text']};margin-left:6px}}
#track{{position:absolute;left:0;right:0;bottom:30px;height:40px;border-bottom:2px solid #39443F}}
#bar{{position:absolute;left:0;top:0;bottom:0;width:0;background:{b['accent']}}}
#avg{{position:absolute;top:-10px;bottom:-2px;width:4px;background:{b['text']}}}
#axis{{position:absolute;left:0;right:0;bottom:0;height:26px;font-family:'Pretendard';font-weight:700;font-size:22px;color:{b['muted']}}}
#axis span{{position:absolute;top:0;white-space:nowrap}}
#q{{position:absolute;left:0;right:0;top:0;font-family:'Wanted';font-weight:800;font-size:42px;line-height:1.35;color:{b['text']};display:none}}
#src{{margin-top:14px;font-family:'Pretendard';font-weight:700;font-size:23px;color:{b['muted']};white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:{STACK_RIGHT - SIDE}px}}
#stack{{position:absolute;left:{SIDE}px;width:{STACK_RIGHT - SIDE}px;font-family:'Wanted';font-weight:700;white-space:nowrap}}
.r{{position:absolute;left:0;right:0;display:flex;align-items:center}}
.r b{{font-family:'Black Han Sans';font-weight:400;color:rgba(0,255,102,.6);width:2.2em;flex:none}}
.r .nm{{flex:none;color:rgba(242,245,243,.55)}}
.r .mb{{flex:1;margin:0 .6em;height:.34em;position:relative}}
.r .mb i{{position:absolute;left:0;top:0;bottom:0;background:rgba(0,255,102,.35)}}
.r .vv{{flex:none;font-family:'Black Han Sans';font-weight:400;color:rgba(242,245,243,.55);font-variant-numeric:tabular-nums}}
.r.q .nm{{color:rgba(242,245,243,.85)}} .r.q b{{color:rgba(242,245,243,.7)}}
.r.cur .nm,.r.cur b,.r.cur .vv{{color:{b['accent']}}} .r.cur .mb i{{background:{b['accent']}}}
.r.fl{{background:{b['accent']};}} .r.fl .nm,.r.fl b,.r.fl .vv{{color:#000}} .r.fl .mb i{{background:#000}}
</style></head><body><div id="f"{"" if intro else ' class="cp"'}>
<div id="ph"><img id="phB"><img id="phA"><div id="shade"></div></div>
<div id="bg"></div>
{top_html}
<div id="hook"><div class="t">{"".join(spans)}</div>{count_html}</div>
<div id="card">
  <div id="rowA"><div id="rk"><div class="rkn" id="rk0"></div><div class="rkn" id="rk1"></div></div>
    <div id="lab"><div id="lt"></div><div id="ls"></div></div></div>
  <div id="val"><div id="vl">{esc(R.get("value_label", ""))}</div><div id="vn"></div>
    <div id="track"><div id="bar"></div><div id="avg"></div></div><div id="axis"></div>
    <div id="q"></div></div>
  <div id="src">{esc(R.get("source_line", ""))}</div>
</div>
<div id="stack"></div>
</div><script>
const D = {json.dumps(data, ensure_ascii=False)};
const SAFE_BOTTOM = {SAFE_BOTTOM}, SIDE = {SIDE};
const $ = id => document.getElementById(id);
const E3 = x => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const fv = v => v.toFixed(D.dec);
const pct = v => clamp(v / D.vmax, 0, 1) * 100;
let FIT = [], RH = 36, STACK_TOP = 0;
// 레이아웃 재기: 이름 글씨 크기(한 줄), 순위표 자리·줄 높이, 안전 영역 넘침
window.twSetup = () => {{
  const out = [];
  const card = $('card'); card.style.display = 'block';
  if (!D.intro) {{
    $('hook').style.display = 'none';
    const tp = $('top');
    if (tp) {{
      const cl = tp.querySelector('.cl');
      if (cl && cl.scrollWidth > {W} - 2 * SIDE) out.push('제목 아래 안내 줄이 양옆 안전 영역 밖');
      const tl_ = tp.querySelector('.t');
      if (Math.round(tl_.clientHeight / parseFloat(getComputedStyle(tl_).lineHeight)) > 2) out.push('위쪽 제목이 2줄을 넘음');
      card.style.top = Math.round(tp.getBoundingClientRect().bottom + 22) + 'px';
    }}
  }}
  const lt = $('lt'), lab = $('lab');
  D.items.forEach((it, i) => {{
    lt.textContent = it.label; let fs = {LABEL_MAX}; lt.style.fontSize = fs + 'px';
    while (lt.scrollWidth > lab.clientWidth && fs > {LABEL_MIN}) {{ fs -= 2; lt.style.fontSize = fs + 'px'; }}
    if (lt.scrollWidth > lab.clientWidth) out.push('이름이 한 줄에 안 들어감: ' + it.label);
    FIT[i] = fs;
  }});
  const hasVal = D.items.some(x => x.value !== null);
  if (!hasVal) $('val').style.height = '210px';
  const qs = D.items.filter(x => x.quote);
  if (qs.length) {{
    const q = $('q'); q.style.display = 'block';
    qs.forEach(x => {{ q.textContent = x.quote; if (q.scrollHeight > $('val').clientHeight + 2) out.push('발언이 너무 김(3줄 넘음): ' + x.quote.slice(0, 20)); }});
    q.style.display = 'none';
  }}
  const cb = card.getBoundingClientRect().bottom;
  STACK_TOP = Math.round(cb + 26);
  RH = Math.min(46, Math.floor((SAFE_BOTTOM - 10 - STACK_TOP) / D.n));
  if (RH < 28) out.push('순위표 줄 높이가 너무 작음 (' + RH + 'px): 항목 수를 줄이거나 카드를 줄일 것');
  const s = $('stack'); s.style.top = STACK_TOP + 'px'; s.style.height = (RH * D.n) + 'px'; s.style.fontSize = Math.round(RH * 0.7) + 'px';
  let h = '';
  D.items.forEach((it, i) => {{
    const num = String(i + 1).padStart(2, '0');
    h += `<div class="r" id="r${{i}}" style="top:${{i * RH}}px;height:${{RH}}px"><b>${{num}}</b><span class="nm"></span>` +
         `<span class="mb"><i></i></span><span class="vv"></span></div>`;
  }});
  s.innerHTML = h;
  // 축 눈금: 0, 평균(있으면), 최댓값
  if (hasVal) {{
    const ax = $('axis'); let a = `<span style="left:0">0</span><span style="right:0">${{Number.isInteger(D.vmax) ? D.vmax : fv(D.vmax)}}</span>`;
    if (D.avg !== null && D.avg !== undefined) {{
      $('avg').style.left = `calc(${{pct(D.avg)}}% - 2px)`;
      a += `<span style="left:${{pct(D.avg)}}%;transform:translateX(-50%)">${{D.avg_label}} ${{fv(D.avg)}}</span>`;
    }} else $('avg').style.display = 'none';
    ax.innerHTML = a;
  }} else {{ ['vl', 'vn', 'track', 'axis'].forEach(k => $(k).style.display = 'none'); }}
  // 이름 칸 너비를 가장 긴 이름에 맞춰 고정 (미니 막대가 같은 자리에서 시작해 길이를 서로 비교할 수 있게)
  D.items.forEach((it, i) => drawRow(i, 'cur', 1));
  const nmW = Math.max(...D.items.map((it, i) => $('r' + i).querySelector('.nm').getBoundingClientRect().width));
  document.querySelectorAll('#stack .nm').forEach(el => el.style.width = Math.ceil(nmW + 2) + 'px');
  // 가장 긴 순위표 줄이 오른쪽 끝을 넘는지
  D.items.forEach((it, i) => {{ const r = $('r' + i); if (r.scrollWidth > r.clientWidth + 1) out.push('순위표 줄이 넘침: ' + it.label); }});
  if ($('stack').getBoundingClientRect().bottom > SAFE_BOTTOM) out.push('순위표가 안전 영역 밖');
  if (D.intro) {{ const hk = $('hook').getBoundingClientRect(); if (hk.bottom > STACK_TOP - 10) out.push('첫 화면 제목이 순위표와 겹침'); }}
  // 박히는 시작 배율: 줄 너비 x 배율이 양옆 안전 영역 안
  window.hkScale = [...document.querySelectorAll(D.intro ? '#hook .ln' : '#top .ln')].map(el => {{
    const rg = document.createRange(); rg.selectNodeContents(el); const w = rg.getBoundingClientRect().width;
    return Math.max(1, Math.min(D.hook.scale, ({W} - 2 * SIDE) / Math.max(1, w)));
  }});
  card.style.display = 'none';
  return out;
}};
// 순위표 한 줄: mode 'q'(아직, 'NN ?'), 'past'(지난 것), 'cur'(지금), 'fl'(번쩍). g: 미니 막대 진행(0~1)
const drawRow = (i, mode, g) => {{
  const r = $('r' + i), it = D.items[i];
  r.className = 'r' + (mode === 'q' ? ' q' : mode === 'cur' ? ' cur' : mode === 'fl' ? ' fl' : '');
  r.querySelector('.nm').textContent = mode === 'q' ? '?' : it.label;
  const has = it.value !== null && mode !== 'q';
  r.querySelector('.mb i').style.width = has ? (pct(it.value) * g).toFixed(2) + '%' : '0';
  r.querySelector('.vv').textContent = has ? fv(it.value) : '';
  r.style.visibility = 'visible';
}};
const hideRow = i => {{ $('r' + i).style.visibility = 'hidden'; }};
const sceneAt = t => {{ let s = D.scenes[0]; for (const x of D.scenes) if (t + 1e-6 >= x.start) s = x; return s; }};
// 장면 안에서 순위 i가 '박히는' 시각(막대가 다 찬 뒤)
const LAND = 0.95;
const landedBefore = (i, t) => {{
  const s = D.scenes.find(x => x.i === i && x.kind !== 'hook');
  if (!s) return false;
  const at = s.kind === 'top' ? s.start + D.reveal : s.start + LAND;
  return t + 1e-6 >= at;
}};
// 뒤 사진: 순위마다 한 장, 장면 안에서 천천히 확대, 바뀔 때 0.2초 겹침. 1위는 '?' 동안 흐림
const photo = (s, u) => {{
  const A = $('phA'), B = $('phB');
  const it = s.kind === 'hook' ? null : D.items[s.i];
  const want = it && it.img;
  const prevS = D.scenes[D.scenes.indexOf(s) - 1];
  const prev = prevS && prevS.kind !== 'hook' ? D.items[prevS.i].img : null;
  const ps = [];
  const setSrc = (el, src) => {{ if (el.getAttribute('src') !== src) {{ el.setAttribute('src', src); ps.push(el.decode().catch(() => null)); }} }};
  if (!want) {{ A.style.display = 'none'; B.style.display = 'none'; return ps; }}
  setSrc(A, want); A.style.display = 'block';
  A.style.objectPosition = (it.imgx ?? 50) + '% 50%';
  const z = 1.04 + 0.06 * (u / s.dur);
  A.style.transform = `scale(${{z.toFixed(4)}})`;
  const x = Math.min(1, u / 0.2);
  A.style.opacity = prev ? x.toFixed(3) : '1';
  if (s.kind === 'top' && u < D.reveal) A.style.filter = 'blur(38px) brightness(.7)';
  else if (s.kind === 'top' && u < D.reveal + 0.25) A.style.filter = `blur(${{(38 * (1 - (u - D.reveal) / 0.25)).toFixed(1)}}px)`;
  else A.style.filter = '';
  if (prev && x < 1) {{
    setSrc(B, prev); B.style.display = 'block'; B.style.filter = '';
    B.style.objectPosition = (D.items[prevS.i].imgx ?? 50) + '% 50%'; B.style.transform = 'scale(1.1)'; B.style.opacity = '1';
  }} else B.style.display = 'none';
  return ps;
}};
// 위쪽 제목 띠 (rank.intro 없을 때): 0초에 줄마다 쾅 + 강조어 녹색 한 박
const topSlam = (t) => {{
  const tp = $('top'); if (!tp) return;
  let dx = 0, dy = 0;
  tp.querySelectorAll('.ln').forEach((el, i) => {{
    const v = t - D.hook.starts[i] + 1e-6;
    if (v < 0) {{ el.style.opacity = '0'; return; }}
    const S0 = window.hkScale[i]; let k = 1;
    if (v < 0.1) k = S0 - (S0 - 0.95) * Math.pow(v / 0.1, 2);
    else if (v < 0.234) {{ const q = (v - 0.1) / 0.134; k = 0.95 + 0.05 * (1 - Math.pow(1 - q, 2)); }}
    el.style.opacity = '1'; el.style.transform = `scale(${{k.toFixed(4)}})`;
    if (v < 0.3) {{ const a = (i === 0 ? 12 : 8) * Math.exp(-v / 0.07); dx += a * Math.sin(v * 95 + i); dy += a * Math.cos(v * 83 + i * 2); }}
  }});
  tp.style.transform = `translate(${{dx.toFixed(1)}}px, ${{dy.toFixed(1)}}px)`;
  const hs = D.hook.starts, last = hs[hs.length - 1];
  tp.querySelectorAll('.hl').forEach(el => el.classList.toggle('fill', t >= last - 1e-6 && t < last + D.beat - 1e-6 && el.closest('.t')));
}};
window.twFrame = (t) => {{
  const s = sceneAt(t), u = t - s.start;
  const ps = photo(s, u);
  if (!D.intro) topSlam(t);
  const done = () => Promise.all(ps);
  const beatPhase = ((t / D.beat) % 1) * D.beat;     // 박 뒤 지난 초
  // 뒤 숫자
  const bg = $('bg');
  if (s.kind === 'hook') {{
    bg.textContent = String(D.n); bg.style.opacity = '1';
    bg.style.transform = `translateX(${{(-30 * t / 2).toFixed(1)}}px) scale(${{(1 + 0.03 * t).toFixed(4)}})`;
  }} else {{
    bg.textContent = String(s.i + 1);
    const e = E3(u / 0.3);
    bg.style.transform = `translateX(${{((1 - e) * 260 - 40 * u / s.dur).toFixed(1)}}px) scale(${{(1 + 0.05 * u / s.dur).toFixed(4)}})`;
    bg.style.opacity = e.toFixed(3);
  }}
  // 순위표: 첫 화면에서는 아래(10위)에서부터 '?' 칸이 생긴다. 그 뒤 박힌 순위는 이름, 아닌 것은 '?'
  D.items.forEach((it, i) => {{
    if (s.kind === 'hook') {{
      const at = 0.25 + (D.n - 1 - i) * (1.1 / D.n);
      if (u + 1e-6 < at) {{ hideRow(i); return; }}
      drawRow(i, 'q', 0);
      const r = $('r' + i), k = E3((u - at) / 0.12);
      r.style.opacity = k.toFixed(3); r.style.transform = `translateX(${{((1 - k) * -30).toFixed(1)}}px)`;
      return;
    }}
    const r = $('r' + i); r.style.opacity = '1'; r.style.transform = '';
    if (!landedBefore(i, t)) {{ drawRow(i, 'q', 0); return; }}
    const sc = D.scenes.find(x => x.i === i && x.kind !== 'hook');
    const at = sc.kind === 'top' ? sc.start + D.reveal : sc.start + LAND;
    const v = t - at;
    if (v < 0.134) drawRow(i, 'fl', E3(v / 0.2));
    else drawRow(i, s.i === i ? 'cur' : 'past', E3(v / 0.2));
  }});
  // 1위 공개 뒤: 순위표를 10위 → 1위로 한 줄씩 번쩍 훑기 (공개 1박 뒤부터)
  if (s.kind === 'top') {{
    const sw = u - D.reveal - D.beat;
    if (sw >= 0) D.items.forEach((it, i) => {{
      const at = (D.n - 1 - i) * 0.07;
      if (sw >= at && sw < at + 0.1 && i !== 0) drawRow(i, 'fl', 1);
    }});
  }}
  // 첫 화면
  const hook = $('hook'), card = $('card');
  if (s.kind === 'hook') {{
    hook.style.display = 'block'; card.style.display = 'none';
    let dx = 0, dy = 0;
    document.querySelectorAll('#hook .ln').forEach((el, i) => {{
      const v = u - D.hook.starts[i] + 1e-6;
      if (v < 0) {{ el.style.opacity = '0'; return; }}
      const S0 = window.hkScale[i]; let k = 1;
      if (v < 0.1) k = S0 - (S0 - 0.95) * Math.pow(v / 0.1, 2);
      else if (v < 0.234) {{ const q = (v - 0.1) / 0.134; k = 0.95 + 0.05 * (1 - Math.pow(1 - q, 2)); }}
      el.style.opacity = '1'; el.style.transform = `scale(${{k.toFixed(4)}})`;
      if (v < 0.3) {{ const a = (i === 0 ? 18 : 12) * Math.exp(-v / 0.07); dx += a * Math.sin(v * 95 + i); dy += a * Math.cos(v * 83 + i * 2); }}
    }});
    hook.style.transform = `translate(${{dx.toFixed(1)}}px, ${{dy.toFixed(1)}}px)`;
    const hs = D.hook.starts, last = hs[hs.length - 1];
    document.querySelectorAll('#hook .hl').forEach(el => el.classList.toggle('fill', u >= last - 1e-6 && u < last + D.beat - 1e-6));
    if (D.hook.count !== null && D.hook.count !== undefined) {{
      const k = E3((u - 0.3) / 0.9);
      $('cnum').textContent = Math.round(D.hook.count * k).toLocaleString('ko-KR');
      $('count').style.opacity = u < 0.3 ? '0' : '1';
    }}
    return done();
  }}
  hook.style.display = 'none'; card.style.display = 'block';
  const it = D.items[s.i], top = s.kind === 'top';
  // 순위 숫자: 이전 순위(한 칸 아래 숫자)가 위로 빠지고 새 숫자가 아래에서 올라온다 (0.22초), 박마다 살짝 뛴다
  const e = E3(u / 0.22), prev = s.i + 2 > D.n ? '' : String(s.i + 2), cur = String(s.i + 1);
  const r0 = $('rk0'), r1 = $('rk1');
  r0.textContent = prev; r1.textContent = cur;
  const pulse = 1 + 0.06 * Math.exp(-beatPhase / 0.11);
  r0.style.transform = `translateY(${{(-e * 210).toFixed(1)}}px)`; r0.style.opacity = (1 - e).toFixed(3);
  r1.style.transform = `translateY(${{((1 - e) * 210).toFixed(1)}}px) scale(${{(e >= 1 ? pulse : 1).toFixed(4)}})`;
  r1.style.transformOrigin = '30% 60%';
  // 이름: 아래에서 올라오며 나타남. 1위는 공개 전 '?' (떨림), 공개 박에 쾅
  const lt = $('lt'), ls = $('ls');
  lt.classList.remove('fill');
  if (top && u < D.reveal) {{
    lt.textContent = '?'; lt.style.fontSize = '{LABEL_MAX}px'; ls.textContent = '';
    const j = 6 * Math.sin(u * 70);
    lt.style.transform = `translateX(${{j.toFixed(1)}}px) scale(${{(1 + 0.08 * Math.exp(-beatPhase / 0.1)).toFixed(4)}})`;
    lt.style.opacity = '1'; card.style.transform = '';
  }} else {{
    lt.textContent = it.label; ls.textContent = it.sub; lt.style.fontSize = FIT[s.i] + 'px';
    if (top) {{
      const v = u - D.reveal + 1e-6; let k = 1;
      if (v < 0.1) k = 1.35 - 0.4 * Math.pow(v / 0.1, 2); else if (v < 0.234) {{ const q = (v - 0.1) / 0.134; k = 0.95 + 0.05 * (1 - Math.pow(1 - q, 2)); }}
      lt.style.transform = `scale(${{k.toFixed(4)}})`; lt.style.opacity = '1';
      lt.classList.toggle('fill', v < D.beat);
      ls.style.opacity = E3(v / 0.25).toFixed(3);
      const a = 16 * Math.exp(-v / 0.08);
      card.style.transform = v < 0.35 ? `translate(${{(a * Math.sin(v * 90)).toFixed(1)}}px, ${{(a * Math.cos(v * 77)).toFixed(1)}}px)` : '';
    }} else {{
      const k = E3((u - 0.06) / 0.24);
      lt.style.transform = `translateY(${{((1 - k) * 44).toFixed(1)}}px)`; lt.style.opacity = k.toFixed(3);
      ls.style.opacity = E3((u - 0.14) / 0.24).toFixed(3);
      card.style.transform = '';
    }}
  }}
  if (!top) card.style.transform = '';
  // 값: 0부터 올라가는 숫자 + 막대 (1위는 '?' 동안 먼저 차오른다). 발언(quote)이면 글자가 차례로 찍힌다
  const q = $('q');
  if (it.value !== null) {{
    q.style.display = 'none';
    const a0 = top ? 0.0 : 0.15, a1 = top ? Math.max(0.3, D.reveal - 0.02) : LAND;
    const k = E3((u - a0) / (a1 - a0));
    const v = it.value * k;
    $('vn').innerHTML = fv(v) + (D.unit ? `<small>${{D.unit}}</small>` : '');
    $('bar').style.width = pct(v).toFixed(2) + '%';
    ['vl', 'vn', 'track', 'axis'].forEach(id => $(id).style.display = 'block');
  }} else {{
    ['vl', 'vn', 'track', 'axis'].forEach(id => $(id).style.display = 'none');
    if (it.quote) {{
      q.style.display = 'block';
      const k = clamp((u - (top ? D.reveal : 0.15)) / 0.9, 0, 1);
      const nch = Math.round(it.quote.length * k);
      q.textContent = it.quote.slice(0, nch);
    }} else q.style.display = 'none';
  }}
  return done();
}};
</script></body></html>"""


async def shoot(post, cfg, work, tl, folder=None):
    """프레임마다 그린다 (모든 장면이 움직인다). 반환: 문제 목록."""
    from playwright.async_api import async_playwright
    page_file = work / "rank.html"
    page_file.write_text(page_html(post, cfg, tl, folder), encoding="utf-8")
    fr = work / "fr"
    fr.mkdir(exist_ok=True)
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(200)
        problems = await pg.evaluate("twSetup()")
        if problems:
            await browser.close()
            return problems
        for k in range(tl["n_frames"]):
            await pg.evaluate(f"twFrame({k / FPS:.5f})")
            await pg.screenshot(path=str(fr / f"{k:05d}.jpg"), type="jpeg", quality=93)
        await browser.close()
    return []


def sfx_plan(post, tl):
    """효과음 시각 (모두 화면이 바뀌는 프레임 시각)."""
    sc = tl["scenes"]
    n = len(rank_items(post))
    hs = hook_starts(post, tl)
    changes = [s["start"] for s in sc if s["kind"] != "hook"]
    intro = sc[0]["kind"] == "hook"
    rows_in = [0.25 + (n - 1 - i) * (1.1 / n) for i in range(n)]
    lands = [s["start"] + 0.95 for s in sc if s["kind"] == "rank"]
    top = sc[-1]
    if not intro:   # 0초부터 10위: 첫 화면 '?' 칸 틱·상승음·드롭 없음
        rows_in = []
    return {"impacts": [0.0], "hits": hs[1:] + changes[1:], "whooshes": hs[1:] + changes[1:],
            "riser_to": changes[0] if intro else None,
            "riser_len": max(0.4, min(0.8, changes[0] - hs[-1] - 0.25)) if intro else 1.0, "drop": changes[0] if intro else None,
            "ticks": sorted(rows_in + lands), "top": (top["start"], top["start"] + tl["reveal"])}


def make_sfx(post, tl, total):
    import numpy as np
    from music_gen import make_hook_sfx
    p = sfx_plan(post, tl)
    a, info = make_hook_sfx(total, impacts=p["impacts"], hits=p["hits"], whooshes=p["whooshes"], riser_to=p["riser_to"],
                            riser_len=p["riser_len"], drop=p["drop"], ticks=p["ticks"])
    b, _ = make_hook_sfx(total, impacts=[p["top"][1]], flood=p["top"], seed=9)
    mix = a + b * 0.9
    peak = float(np.max(np.abs(mix))) or 1.0
    info["onsets"]["reveal"] = [p["top"][1]]
    return mix / peak, info


def preview_times(tl, total):
    """미리보기: 0.3초, 1초, 카운트다운 중간 두 곳, 1위 공개 직후, 끝 화면."""
    ranks = [s for s in tl["scenes"] if s["kind"] == "rank"]
    top = tl["scenes"][-1]
    ts = [0.3, 1.0]
    for s in (ranks[len(ranks) // 3], ranks[2 * len(ranks) // 3]):
        ts.append(s["start"] + s["dur"] * 0.6)
    ts.append(top["start"] + tl["reveal"] + 0.2)
    ts.append(total - 1.0 if tl["cta"] else tl["main"] - 0.2)
    return ts


def make_rank_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/*.jpg, cover.jpg(첫 화면 제목). 전체 길이(초) 반환."""
    if (post.get("rank") or {}).get("mode") == "intro":
        from quotereel import make_quote_reel
        return make_quote_reel(post, folder, cfg)
    folder = Path(folder)
    work = folder / "_rank"
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
        first = tl["scenes"][1]["start"]
        reveal = tl["scenes"][-1]["start"] + tl["reveal"]
        intro = tl["scenes"][0]["kind"] == "hook"
        first = tl["scenes"][1]["start"] if intro else 0.0
        make_hook_music(music, tl["bpm"], dur, [first, reveal], seed=int(pm.get("seed", 7)), drop_at=first if intro else None)
        print(f"배경음악: 후킹 비트 BPM {tl['bpm']:g} (박 {tl['beat']:.3f}초), 드롭 {first:.2f}초, 1위 공개 크래시 {reveal:.2f}초")
    from listreel import mix_audio
    sfx, info = make_sfx(post, tl, dur)
    mixed = work / "mix.wav"
    st = mix_audio(music, [], dur, mixed, sfx)
    on = info["onsets"]
    print(f"효과음: 쿵 {on['impact']}, 순위 전환 휙+타격 {len(on['hit'])}곳, 틱 {on['ticks']}개, 1위 공개 {on['reveal'][0]:.2f}초 "
          f"(소리 나는 곳 {st.get('sfx_db') or 0:.1f} dB RMS)")
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    from banner import banner_text, make_banner_png, apply_banner, cta_line
    bt = banner_text(post) if (opts(post)["intro"] or not cta_line(post)) else None   # 0초 안내 줄이 있으면 3초 띠는 뺀다
    if bt:
        png = make_banner_png(bt, cfg, W - 2 * SIDE, work / "banner.png")
        apply_banner(out, png, SIDE, SAFE_TOP, dur)
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
    for k, t in enumerate(preview_times(tl, dur), 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    # 커버: 첫 화면 끝(제목이 다 박히고 순위표가 '?'로 찬 순간). thumb가 있으면 render.py가 thumb.py로 덮어쓴다
    hook = tl["scenes"][0]
    cover_t = hook["start"] + hook["dur"] - 2 / FPS if hook["kind"] == "hook" else 0.9
    shutil.copy(work / "fr" / f"{int(round(cover_t * FPS)):05d}.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(f"순위 {len(rank_items(post))}개, 순위당 {tl['scenes'][1]['dur']:.2f}초, 1위 '?' {tl['reveal']:.2f}초, "
          f"본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur
