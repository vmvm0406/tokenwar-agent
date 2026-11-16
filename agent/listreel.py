"""목록형 자료 릴스 (post type "video" + "list", 운영자 결정 2026-11-16, 참고 형식 '34가지 조명 코드').

결과 그림이 세로 화면 전체(1080x1920)를 꽉 채우고, 항목마다 그림과 영화 자막 같은 이름 띠가 박자에 맞춰 바뀐다
(운영자 수정 2026-11-17: "아래 하단이 비어있잖아", "썸네일처럼 화면 가득", "있어 보이게", "노래도 후킹되게").
길이 20~35초 (끝 화면 포함).

그림: 4:5(1088x1360)로 만든 그림에서 슬라임(마스코트) 중심을 찾아 세로 9:16(약 765x1360)만 잘라
      1080x1920으로 Lanczos 확대한다 (fill_frame). 그림 생성 크기는 4:5 그대로.
레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 config.json reel_safe 안):
    0초~        첫 화면: 가장 눈에 띄는 결과 그림(list.hook) + 제목(2줄, 위쪽 띠, 안전 영역 맨 위)
    항목 화면   그림 + 이름 띠: 작은 녹색 번호 / 큰 영어 이름(대문자, 자간 넓게). 한국어 이름은 DM 자료 페이지에만
                (운영자 결정 2026-11-17). list.label "ko"면 한국어 크게 + 영어 작게, "both"면 영어 크게 + 한국어 작게.
                띠는 단색 반투명 검정, 위쪽('자료' 안내 띠 바로 아래). 마스코트(화면 가운데~아래)를 가리지 않게.
                voice/<번호>.wav가 있으면 그림이 바뀌는 박에 맞춰 그 영어 용어 읽는 목소리를 넣는다 (agent/tts.py, Kokoro-82M).
                나타날 때 0.27초 동안 아래에서 올라오며 자간이 좁혀진다.
    3초~본편 끝 '자료' 안내 띠(dm.banner, 안전 영역 맨 위 285px)
    끝          dm.cta 끝 화면 2.5초 (video.py append_cta_card)

박자: 항목 길이 = 박자 간격의 정수배(기본 2박). BPM은 전체 길이가 29초 안팎이 되게 96~128에서 고른다.
      장면이 바뀌는 시각은 박 위에 오도록 프레임(30fps)으로 맞춘다(오차 1/60초 이하).
소리: music_gen.make_hook_music (0초부터 킥·스네어, 2마디 멜로디 훅, 목록 시작·8개마다 크래시) → -14 LUFS.
전체 목록·영어 용어·추가 용어는 화면에 다 쓰지 않고 DM 자료 페이지(dm.py)에 둔다.
그림은 마스코트 슬라임 AI 그림 (list.items[].prompt + "mascot": true → render.yml의 gen_images가 만든다).
그림이 아직 없으면 render.py가 회색 자리표시(번호만)로 틀만 렌더링한다 (with_placeholders, Actions에서는 멈춤).
"""
import asyncio
import html
import json
import random
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
RAIL_TOP = _SAFE.get("rail_top", 1150)   # 오른쪽 아래 버튼 줄 시작. 이름 띠는 이 위에서 끝난다

TARGET_TOTAL = 29.0     # 기본 목표 길이(끝 화면 포함)
ITEM_RANGE = (0.9, 1.7)  # 항목 하나 길이(초)
BPM_RANGE = (94, 129)  # 실제 후보: 128.6·120·112.5·105.9·100·94.7 (한 박 = 14~19프레임)
HOOK_BEATS = 4          # 첫 화면 박 수
END_BEATS = 2           # 마지막 항목에 더 주는 박 수
LENGTH_RANGE = (20.0, 35.0)   # 끝 화면 포함 (STYLE_GUIDE 6장 "목록형 자료 릴스", checks.py)
ACCENT_EVERY = 8        # 크래시(강한 박자) 넣는 항목 간격
ANIM_FRAMES = 8         # 이름 띠 등장 모션 (8프레임 = 0.27초)
EN_FONT, EN_MIN = 92, 52        # 큰 영어 이름 (Pretendard Black, 대문자)
KO_BIG, KO_BIG_MIN = 96, 60     # list.label "ko"일 때 큰 한국어 이름 (검은고딕)
TITLE_FONT = 80         # 첫 화면 제목
CROP_W = 765            # 1360 높이에서 9:16로 남길 너비 (1360 x 9/16)


def esc(s):
    return html.escape(str(s or ""))


def hl(text, word):
    t = esc(text)
    if word:
        t = t.replace(esc(word), f'<span class="hl">{esc(word)}</span>', 1)
    return t.replace("\n", "<br>")


def rows_of(post):
    """목록 줄: [원본(list.base, 선택)] + 항목들. 각 줄 {num, name, en, src, base}."""
    L = post.get("list") or {}
    rows = []
    if L.get("base"):
        b = L["base"]
        rows.append({"num": "00", "name": b.get("name", "원본 사진"), "en": b.get("en", "ORIGINAL"), "src": b.get("src"), "base": True})
    for i, it in enumerate(L.get("items") or [], 1):
        rows.append({"num": f"{i:02d}", "name": it.get("name", ""), "en": it.get("en", ""), "src": it.get("src"), "base": False})
    return rows


def _hook_row(post, rows):
    """첫 화면에 크게 보여 줄 줄 번호 (list.hook = 항목 번호 1부터, 기본 1)."""
    h = int((post.get("list") or {}).get("hook", 1))
    idx = [i for i, r in enumerate(rows) if not r["base"]]
    if not idx:
        return 0
    return idx[min(max(h, 1), len(idx)) - 1]


def _beats(rows, k):
    """장면마다 박 수: 첫 화면 HOOK_BEATS, 원본 줄 k+1, 항목 k, 마지막 항목 k+END_BEATS."""
    out = [HOOK_BEATS]
    for r, row in enumerate(rows):
        b = k + 1 if row["base"] else k
        if r == len(rows) - 1:
            b += END_BEATS
        out.append(b)
    return out


def timeline(post):
    """장면 순서와 길이. 항목 길이는 박자 간격의 정수배, 장면이 바뀌는 시각은 박 위(프레임 단위로 맞춤).
    checks.py도 이 함수로 길이를 검사한다.
    반환: {"states", "durs", "starts"(장면 시작 초), "beat_at"(장면 시작 박 번호), "bpm", "beat", "k",
           "main", "cta", "total", "item"}"""
    from video import CTA_SECONDS
    L = post.get("list") or {}
    rows = rows_of(post)
    cta = CTA_SECONDS if (post.get("dm") or {}).get("cta") else 0.0
    if L.get("bpm"):
        cands = [(float(L["bpm"]), int(L.get("beats_per_item", 2)))]
    else:
        ks = [int(L["beats_per_item"])] if L.get("beats_per_item") else [2, 3, 4]
        # 한 박이 정확히 정수 프레임(30fps)이 되는 BPM만: 1800/f (f = 한 박 프레임 수) → 전환이 박과 0ms 차이
        cands = [(1800.0 / f, k) for k in ks for f in range(14, 20) if BPM_RANGE[0] <= 1800.0 / f <= BPM_RANGE[1]]
    best = None
    for bpm, k in cands:
        beat = 60.0 / bpm
        item = k * beat
        total = sum(_beats(rows, k)) * beat + cta
        bad = 0 if ITEM_RANGE[0] <= item <= ITEM_RANGE[1] else 100
        score = bad + abs(total - TARGET_TOTAL) + (k - 2) * 0.5   # 2박을 먼저
        if best is None or score < best[0]:
            best = (score, bpm, k)
    _, bpm, k = best
    beat = 60.0 / bpm
    beats = _beats(rows, k)
    states = [("hook", _hook_row(post, rows))] + [("row", r) for r in range(len(rows))]
    # 장면 경계(박 번호 누적)를 프레임으로 반올림: 쌓이는 오차 없이 각 경계가 박 시각에서 1/60초 안
    acc, bounds = 0, [0]
    for b in beats:
        acc += b
        bounds.append(acc)
    frames = [int(round(x * beat * FPS)) for x in bounds]
    durs = [(frames[i + 1] - frames[i]) / FPS for i in range(len(beats))]
    starts = [f / FPS for f in frames[:-1]]
    main = frames[-1] / FPS
    return {"states": states, "durs": durs, "starts": starts, "beat_at": bounds[:-1], "bpm": bpm, "beat": beat, "k": k,
            "main": main, "cta": cta, "total": main + cta, "item": k * beat}


# ---------- 그림: 4:5 → 세로 9:16 꽉 채우기 ----------

def subject_x(img):
    """마스코트(연두 젤리)의 가로 중심 비율(0~1). 초록 기운이 있는 화소를 그림 가운데 세로 띠(20~85%)에서 찾고,
    가장 넓게 뭉친 열 구간의 가운데를 쓴다. 못 찾으면 0.5 (가운데)."""
    import numpy as np
    small = img.convert("RGB").resize((272, 340))
    a = np.asarray(small).astype(np.int16)
    a = a[int(340 * 0.2):int(340 * 0.85)]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mask = (g > 70) & (g > r + 12) & (g > b + 18)
    col = mask.sum(axis=0).astype(float)
    if col.sum() < 60:
        return 0.5
    # 열 밀도를 부드럽게 해서 가장 큰 덩어리(슬라임)를 고른다 (왼쪽 화분 같은 작은 초록은 무시)
    k = np.ones(15) / 15
    sm = np.convolve(col, k, mode="same")
    thr = sm.max() * 0.35
    best, cur, start = (0, 0, 0), 0, 0
    for i, v in enumerate(list(sm) + [0]):
        if v >= thr and cur == 0:
            start = i
        if v >= thr:
            cur += sm[i] if i < len(sm) else 0
        elif cur:
            if cur > best[0]:
                best = (cur, start, i)
            cur = 0
    _, s0, s1 = best
    xs = np.arange(s0, s1)
    w = sm[s0:s1]
    return float((xs * w).sum() / w.sum() / len(sm)) if w.sum() else 0.5


def fill_frame(src, out, x_center=None):
    """4:5 그림에서 세로 9:16 부분을 잘라 1080x1920 Lanczos 확대. 가로 기준은 마스코트 중심(x_center, 없으면 찾음).
    반환: (중심 비율, 확대 배율)."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    cw = min(w, int(round(h * 9 / 16)))
    cx = subject_x(im) if x_center is None else float(x_center)
    left = int(round(cx * w - cw / 2))
    left = max(0, min(w - cw, left))
    crop = im.crop((left, 0, left + cw, h))
    crop.resize((W, H), Image.LANCZOS).save(out, "JPEG", quality=94)
    return cx, H / h


def prepare_images(post, folder, work):
    """줄마다 세로 꽉 찬 그림 파일. list.items[].center(선택, 0~1)로 가로 기준을 손으로 정할 수 있다.
    반환: [(경로, 중심, 배율)]."""
    L = post.get("list") or {}
    centers = ([L["base"].get("center")] if L.get("base") else []) + [it.get("center") for it in L.get("items") or []]
    out = []
    for i, (row, c) in enumerate(zip(rows_of(post), centers)):
        dst = work / f"img{i:02d}.jpg"
        cx, scale = fill_frame(Path(folder) / row["src"], dst, c)
        out.append((dst, cx, scale))
    return out


def page_html(post, imgs, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    L = post["list"]
    rows = rows_of(post)
    mode = L.get("label", "en")        # "en": 영어 이름만 크게(기본), "ko": 한국어 크게 + 영어 작게, "both": 영어 크게 + 한국어 작게
    ko_big = mode == "ko"
    cls = {"ko": "big-ko", "both": ""}.get(mode, "en-only")
    js_rows = json.dumps([{"num": r["num"], "name": r["name"], "en": (r["en"] or "").upper(), "img": p.resolve().as_uri()}
                          for r, (p, _, _) in zip(rows, imgs)], ensure_ascii=False)
    from banner import banner_text, banner_height
    bt = banner_text(post)
    label_top = SAFE_TOP + (banner_height(bt) + 16 if bt else 15)   # 이름 띠: '자료' 안내 띠 바로 아래
    title_top = SAFE_TOP + 15                                       # 제목 띠: 첫 화면(안내 띠는 3초부터)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Black.otf');font-weight:900}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Bold.otf');font-weight:700}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:#fff;word-break:keep-all}}
#img{{position:absolute;inset:0;width:{W}px;height:{H}px;display:block}}
.hl{{color:{b['accent']}}}
/* 위쪽 띠: 단색 반투명 검정(그라데이션 금지, STYLE_GUIDE 1-1). 글은 양옆 {SIDE}px 안. 마스코트는 화면 가운데~아래라 가리지 않는다 */
#title{{top:{title_top}px}} #label{{top:{label_top}px}}
.band{{position:absolute;left:0;right:0;background:rgba(6,7,6,.62);
  padding:30px {SIDE}px 28px;text-align:center;display:none;text-shadow:0 2px 12px rgba(0,0,0,.55)}}
.inner{{will-change:transform,opacity}}
#title .t{{font-family:'Black Han Sans';font-weight:400;font-size:{TITLE_FONT}px;line-height:1.16;letter-spacing:-.01em}}
.num{{font-family:'Black Han Sans';font-size:40px;line-height:1;color:{b['accent']};letter-spacing:.18em;margin-bottom:16px}}
.en{{font-family:'Pretendard';font-weight:900;font-size:{EN_FONT}px;line-height:1.04;white-space:nowrap}}
.ko{{font-family:'Wanted';font-weight:700;font-size:46px;line-height:1.2;margin-top:14px;color:#E8EDEA}}
.big-ko .en{{font-family:'Pretendard';font-weight:700;font-size:34px;letter-spacing:.24em;margin-top:14px;color:#E8EDEA;order:3}}
.big-ko .ko{{font-family:'Black Han Sans';font-weight:400;font-size:{KO_BIG}px;line-height:1.05;margin-top:0;color:#fff;white-space:nowrap}}
.big-ko .inner{{display:flex;flex-direction:column;align-items:center}}
.en-only .ko{{display:none}}
</style></head><body><div id="f">
<img id="img" src="">
<div class="band" id="title"><div class="inner"><div class="t">{hl(post['title'], post.get('highlight'))}</div></div></div>
<div class="band {cls}" id="label"><div class="inner">
  <div class="num" id="ln"></div><div class="en" id="le"></div><div class="ko" id="lk"></div></div></div>
</div><script>
const ROWS = {js_rows};
const KO_BIG = {'true' if ko_big else 'false'};
const lab = document.getElementById('label'), ttl = document.getElementById('title');
const maxW = {W - 2 * SIDE};
const fits = {{}};   // 줄마다 큰 이름 글씨 크기 (한 줄에 들어가게)
const set = (r) => {{
  const row = ROWS[r];
  document.getElementById('ln').textContent = row.num;
  document.getElementById('le').textContent = row.en;
  document.getElementById('lk').textContent = row.name;
}};
const bigEl = () => document.getElementById(KO_BIG ? 'lk' : 'le');
window.twProblems = () => {{
  const out = [];
  lab.style.display = 'block';
  ROWS.forEach((row, r) => {{
    set(r);
    const el = bigEl(); let fs = KO_BIG ? {KO_BIG} : {EN_FONT}; const min = KO_BIG ? {KO_BIG_MIN} : {EN_MIN};
    el.style.letterSpacing = KO_BIG ? '-.01em' : '.12em'; el.style.fontSize = fs + 'px';
    while (el.scrollWidth > maxW && fs > min) {{ fs -= 2; el.style.fontSize = fs + 'px'; }}
    let wrap = false;
    if (el.scrollWidth > maxW) {{
      // 가장 작게 해도 한 줄에 안 들어가는 긴 이름은 두 줄로 (글씨는 처음 크기에서 다시 줄여 맞춘다)
      wrap = true; el.style.whiteSpace = 'normal'; el.style.maxWidth = maxW + 'px'; el.style.margin = '0 auto';
      fs = KO_BIG ? {KO_BIG} : {EN_FONT}; el.style.fontSize = fs + 'px';
      const ln = () => Math.round(el.clientHeight / parseFloat(getComputedStyle(el).lineHeight));
      while ((ln() > 2 || el.scrollWidth > maxW) && fs > min) {{ fs -= 2; el.style.fontSize = fs + 'px'; }}
      if (ln() > 2) out.push('이름이 두 줄에도 안 들어감: ' + (KO_BIG ? row.name : row.en));
      el.style.whiteSpace = ''; el.style.maxWidth = ''; el.style.margin = '';
    }}
    fits[r] = [fs, wrap];
  }});
  if (lab.getBoundingClientRect().bottom > {SAFE_BOTTOM}) out.push('이름 띠가 안전 영역 밖');
  lab.style.display = 'none';
  ttl.style.display = 'block';
  const t = ttl.querySelector('.t'); let tfs = {TITLE_FONT};
  const lines = () => Math.round(t.clientHeight / parseFloat(getComputedStyle(t).lineHeight));
  while (lines() > 2 && tfs > 56) {{ tfs -= 2; t.style.fontSize = tfs + 'px'; }}
  if (lines() > 2) out.push('제목이 2줄을 넘음');
  if (ttl.getBoundingClientRect().bottom > {SAFE_BOTTOM}) out.push('제목 띠가 안전 영역 밖');
  ttl.style.display = 'none';
  return out;
}};
// p: 등장 진행(0~1). 0.27초 동안 아래에서 36px 올라오며 나타나고, 큰 영어 이름은 자간이 .3em → .12em로 좁혀진다
window.twState = (kind, r, p) => {{
  const e = 1 - Math.pow(1 - p, 3);
  document.getElementById('img').src = ROWS[r].img;
  ttl.style.display = kind === 'hook' ? 'block' : 'none';
  lab.style.display = kind === 'row' ? 'block' : 'none';
  const band = kind === 'hook' ? ttl : lab;
  const inner = band.querySelector('.inner');
  inner.style.transform = `translateY(${{(1 - e) * 36}}px)`;
  inner.style.opacity = String(e);
  if (kind === 'row') {{
    set(r);
    const el = bigEl(); el.style.fontSize = fits[r][0] + 'px';
    el.style.whiteSpace = fits[r][1] ? 'normal' : ''; el.style.maxWidth = fits[r][1] ? maxW + 'px' : ''; el.style.margin = fits[r][1] ? '0 auto' : '';
    if (!KO_BIG) el.style.letterSpacing = (0.12 + 0.18 * (1 - e)).toFixed(3) + 'em';
  }}
  return Promise.all([...document.images].filter(i => i.src).map(i => i.decode().catch(() => null)));
}};
</script></body></html>"""


async def shoot_states(post, imgs, cfg, work):
    """장면마다 등장 모션 프레임(ANIM_FRAMES장, 1/30초씩) + 정지 화면 한 장. [(png, 초), ...], 문제 목록, timeline."""
    from playwright.async_api import async_playwright
    tl = timeline(post)
    page_file = work / "list.html"
    page_file.write_text(page_html(post, imgs, cfg), encoding="utf-8")
    shots = []
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(200)
        problems = await pg.evaluate("twProblems()")
        el = await pg.query_selector("#f")
        for i, ((kind, r), d) in enumerate(zip(tl["states"], tl["durs"])):
            n_anim = min(ANIM_FRAMES, int(round(d * FPS)) - 1)
            for k in range(n_anim):
                await pg.evaluate(f"twState('{kind}', {r}, {(k + 1) / (n_anim + 1):.4f})")
                png = work / f"s{i:03d}_{k}.png"
                await el.screenshot(path=str(png))
                shots.append((png, 1 / FPS))
            await pg.evaluate(f"twState('{kind}', {r}, 1)")
            png = work / f"s{i:03d}.png"
            await el.screenshot(path=str(png))
            shots.append((png, d - n_anim / FPS))
        await browser.close()
    return shots, problems, tl


def accents(post, tl):
    """크래시(강한 박자) 자리: 목록 시작, 그 뒤 ACCENT_EVERY 항목마다."""
    out = []
    for (kind, r), t in zip(tl["states"], tl["starts"]):
        if kind == "row" and r % ACCENT_EVERY == 0:
            out.append(t)
    return out


def beat_check(tl):
    """장면 전환 시각과 박 시각의 차이(초). 최대값을 보고용으로."""
    return max(abs(t - b * tl["beat"]) for t, b in zip(tl["starts"], tl["beat_at"]))


PH_DIR = "_ph"


def with_placeholders(post, folder):
    """그림이 아직 없는 줄(AI 그림은 render.yml이 만든다)을 회색 자리표시(번호만)로 바꾼 사본.
    자리표시는 게시물 폴더의 _ph/에 만들고 렌더링 뒤 지운다 (img/ 자리에는 넣지 않는다: 넣으면 Actions가 그림을 안 만든다).
    반환: (사본 post, 자리표시 수)."""
    import copy
    from PIL import Image, ImageDraw, ImageFont
    folder = Path(folder)
    p = copy.deepcopy(post)
    L = p.get("list") or {}
    cells = ([("00", L["base"])] if L.get("base") else []) + [(f"{i:02d}", it) for i, it in enumerate(L.get("items") or [], 1)]
    ph = folder / PH_DIR
    made = {}
    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Pretendard-Black.otf"), 380)
    for num, it in cells:
        src = it.get("src")
        if src and (folder / src).exists():
            continue
        ph.mkdir(exist_ok=True)
        out = ph / f"{num}.jpg"
        im = Image.new("RGB", (1080, 1350), (58, 63, 60))
        dr = ImageDraw.Draw(im)
        bx = dr.textbbox((0, 0), num, font=font)
        dr.text(((1080 - bx[2] - bx[0]) / 2, (1350 - bx[3] - bx[1]) / 2), num, font=font, fill=(150, 158, 153))
        im.save(out, "JPEG", quality=85)
        made[src] = str(out.resolve())
        it["src"] = made[src]
    t = (p.get("thumb") or {}).get("image") or {}
    if t.get("src") in made:
        t["src"] = made[t["src"]]
    return p, len(made)


def clear_placeholders(folder):
    shutil.rmtree(Path(folder) / PH_DIR, ignore_errors=True)



# ---------- 소리: 음악 + 목소리(선택) ----------
SR = 44100
VOICE_DIR = "voice"
VOICE_OVER_MUSIC_DB = 17.0   # 말하는 동안 말이 음악보다 이만큼 크게 (15~20dB)
MUSIC_GAP_DB = 6.0           # 말이 없을 때 음악은 말보다 이만큼만 작게 (비트가 살게)


def _read_audio(path):
    """아무 소리 파일 → 44.1kHz 스테레오 float32 (ffmpeg)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768.0


def _write_wav(path, x):
    import wave
    import numpy as np
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _db(x):
    import numpy as np
    r = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    return 20 * np.log10(max(r, 1e-9))


def voice_files(post, folder, tl):
    """[(시작 초, 파일)]: 항목 장면마다 voice/<번호>.wav가 있으면 그 장면이 시작하는 박에."""
    rows = rows_of(post)
    out = []
    for (kind, r), t in zip(tl["states"], tl["starts"]):
        if kind != "row":
            continue
        f = Path(folder) / VOICE_DIR / f"{rows[r]['num']}.wav"
        if f.exists():
            out.append((t, f))
    return out


def mix_audio(music_wav, voices, total, out_wav):
    """음악 + 목소리. 말하는 동안 음악을 줄여(덕킹) 말이 음악보다 VOICE_OVER_MUSIC_DB 크게,
    말이 없을 때는 음악을 말보다 MUSIC_GAP_DB 작게 둔다. 반환: 측정값 dict (RMS 기준 dB)."""
    import numpy as np
    n = int(round(total * SR))
    m = _read_audio(music_wav)[:n]
    if len(m) < n:
        m = np.pad(m, ((0, n - len(m)), (0, 0)))
    if not voices:
        _write_wav(out_wav, m)
        return {"voices": 0}
    v = np.zeros_like(m)
    for t, f in voices:
        x = _read_audio(f)
        i = int(round(t * SR))
        k = min(len(x), n - i)
        if k > 0:
            v[i:i + k] += x[:k]
    # 말소리 있는 곳 (10ms 창 RMS) → 부드러운 덕킹 곡선 (올라갈 때 20ms, 내려갈 때 250ms)
    mono = np.abs(v).mean(axis=1)
    win = int(0.01 * SR)
    pad = (-len(mono)) % win
    blocks = np.pad(mono, (0, pad)).reshape(-1, win).max(axis=1)
    on = (blocks > 0.02).astype(float)
    env = np.zeros_like(on)
    a_up, a_dn = 1 - np.exp(-1 / 2), 1 - np.exp(-1 / 25)
    e = 0.0
    for i, x in enumerate(on):
        e += (x - e) * (a_up if x > e else a_dn)
        env[i] = e
    env = np.repeat(env, win)[:n]
    speech = env > 0.9
    lv = _db(v[speech])
    lm = _db(m)
    base_db = (lv - MUSIC_GAP_DB) - lm                       # 말 없을 때 음악 크기
    duck_db = -(VOICE_OVER_MUSIC_DB - MUSIC_GAP_DB)          # 말하는 동안 더 줄이는 양
    gain = 10 ** ((base_db + duck_db * env) / 20)
    mm = m * gain[:, None]
    mix = v + mm
    _write_wav(out_wav, mix)
    return {"voices": len(voices), "voice_db": lv, "music_in_speech_db": _db(mm[speech]),
            "music_between_db": _db(mm[~speech]), "diff_in_speech_db": lv - _db(mm[speech])}


def make_list_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/*.jpg·cover.jpg(썸네일이 덮어씀). 전체 길이(초) 반환."""
    folder = Path(folder)
    missing = [r["src"] for r in rows_of(post) if not r.get("src") or not (folder / r["src"]).exists()]
    if missing:
        raise FileNotFoundError("목록 이미지 없음: " + ", ".join(map(str, missing[:5]))
                                + " → list.items[].prompt·mascot 확인 (그림은 render.yml이 만든다)")
    work = folder / "_list"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    imgs = prepare_images(post, folder, work)
    for (p_, cx, sc), row in zip(imgs, rows_of(post)):
        print(f"  그림 {row['num']}: 가로 중심 {cx:.2f}, 확대 {sc:.2f}배")
    shots, problems, tl = asyncio.run(shoot_states(post, imgs, cfg, work))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    # 1) 장면 이어 붙이기 (등장 모션 프레임 + 정지 화면)
    lst = work / "list.txt"
    lines = []
    for png, d in shots:
        lines += [f"file '{png.name}'", f"duration {d:.5f}"]
    lines.append(f"file '{shots[-1][0].name}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps={FPS},scale={W}:{H},setsar=1,format=yuv420p", "-t", f"{tl['main']:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(silent)],
                   check=True, cwd=str(work))
    # 2) 음악 (소리 없는 릴스 금지, STYLE_GUIDE 6장): post.music.src → assets/music → 코드로 만든 후킹 비트
    pm = post.get("music") or {}
    files = sorted((ROOT / "assets" / "music").glob("*.mp3")) + sorted((ROOT / "assets" / "music").glob("*.m4a"))
    dur = tl["main"]
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    elif files and not pm.get("generate"):
        music = random.choice(files)
    else:
        from music_gen import make_hook_music
        music = work / "music.wav"
        acc = accents(post, tl)
        make_hook_music(music, tl["bpm"], dur, acc, seed=int(pm.get("seed", 7)))
        print(f"배경음악: 후킹 비트 BPM {tl['bpm']:g} (박 {tl['beat']:.4f}초, 항목 {tl['k']}박 = {tl['item']:.3f}초), "
              f"크래시 {len(acc)}곳, 장면 전환과 박의 최대 차이 {beat_check(tl) * 1000:.1f}ms")
    # 3) 목소리 (선택, voice/<번호>.wav, agent/tts.py로 이 컴퓨터에서 미리 만든다)
    mixed = work / "mix.wav"
    st = mix_audio(music, voice_files(post, folder, tl), dur, mixed)
    if st.get("voices"):
        print(f"목소리 {st['voices']}개: 말하는 동안 말 {st['voice_db']:.1f} dB / 음악 {st['music_in_speech_db']:.1f} dB "
              f"(차이 {st['diff_in_speech_db']:.1f} dB), 말 없을 때 음악 {st['music_between_db']:.1f} dB (RMS)")
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    # 4) 앞쪽 '자료' 안내 띠 (dm.banner): 안전 영역 맨 위, 3초부터 본편 끝까지
    from banner import banner_text, make_banner_png, apply_banner, banner_height
    bt = banner_text(post)
    if bt:
        png = make_banner_png(bt, cfg, W - 2 * SIDE, work / "banner.png")
        apply_banner(out, png, SIDE, SAFE_TOP, dur)
        print(f"  안내 띠 자리: 안전 영역 맨 위 (세로 {SAFE_TOP}~{SAFE_TOP + banner_height(bt)}px)")
    # 5) 끝 화면 (dm.cta 2.5초, 음악은 그 앞에서 페이드아웃)
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
    for k, t in enumerate(preview_times(post, tl, dur), 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(f"목록 {len(rows_of(post))}줄, 항목당 {tl['item']:.2f}초, 본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur


def preview_times(post, tl, total):
    """미리보기: 첫 화면 1초, 안내 띠가 들어온 뒤 항목, 중간 항목 몇 개, 마지막 항목, 끝 화면."""
    rows = [(r, t + d * 0.6) for (kind, r), t, d in zip(tl["states"], tl["starts"], tl["durs"]) if kind == "row"]
    ts = [1.0]
    after = [x for x in rows if x[1] > 3.4]
    picks = [after[0]] + [rows[len(rows) * k // 4] for k in (1, 2, 3)] + [rows[-1]]
    ts += [t for _, t in picks]
    if tl["cta"]:
        ts.append(total - 1.0)
    return ts
