"""목록형 자료 릴스 (post type "video" + "list", 운영자 결정 2026-11-16, 참고 형식 '34가지 조명 코드').

결과 그림이 화면을 가로 꽉 채우고(1080x1350, 4:5), 항목마다 그림과 '번호 + 이름' 띠가 함께 바뀐다
(운영자 수정 2026-11-17: "그림은 꽉차게", 화면 속 전체 목록은 뺌). 길이 20~35초 (끝 화면 포함).

레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 config.json reel_safe 안):
    그림        세로 0~1350px, 가로 꽉 (위 285px까지는 인스타 머리말에 덮여도 되는 자리)
    0~2초       첫 화면: 가장 눈에 띄는 결과 그림(list.hook) + 제목 띠(2줄, 아래쪽)
    2초~        항목 화면: 그림 + 이름 띠 "07 스플릿 조명" (아래쪽, 오른쪽 아래 버튼 줄 위 1138px에서 끝남)
    3초~본편 끝 '자료' 안내 띠(dm.banner, 안전 영역 맨 위 285px)
    끝          dm.cta 끝 화면 2.5초 (video.py append_cta_card)

소리: 코드로 만든 음악(music_gen.py, 항목 전환에 박자, 목록 시작·11줄마다 강한 박자) → -14 LUFS (loudness.py).
전체 목록·영어 용어·추가 용어는 화면에 쓰지 않고 DM 자료 페이지(dm.py)에 둔다.
그림은 마스코트 슬라임 AI 그림 (list.items[].prompt + "mascot": true → render.yml의 gen_images가 만든다).
그림이 아직 없으면 render.py가 회색 자리표시(번호만)로 틀만 렌더링한다 (with_placeholders, Actions에서는 멈춤).
"""
import asyncio
import html
import json
import math
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

HOOK_SECONDS = 2.0      # 첫 화면 (가장 눈에 띄는 결과 + 제목)
END_HOLD = 0.6          # 마지막 항목을 조금 더 보여 준다
BASE_FACTOR = 1.3       # 원본(list.base) 줄은 항목보다 조금 길게
TARGET_TOTAL = 29.0     # 기본 목표 길이(끝 화면 포함). 항목 시간은 이 값에 맞춰 0.9~1.6초 사이로 정한다
ITEM_RANGE = (0.9, 1.6)
LENGTH_RANGE = (20.0, 35.0)   # 끝 화면 포함 (STYLE_GUIDE 6장 "목록형 자료 릴스", checks.py)
MAX_ROWS = 11           # 음악 강한 박자 묶음 크기 (예전 한 화면 목록 줄 수). 이 줄 수마다 박자를 세게
RAIL_TOP = _SAFE.get("rail_top", 1150)   # 오른쪽 아래 버튼 줄 시작. 이름 띠는 이 위에 둔다 (가로 꽉 채워도 안 가려짐)
IMG_TOP = 0             # 그림(1080x1350) 위 끝. 위 285px는 인스타 머리말에 덮이는 벽 부분이고, 마스코트가 이름 띠(아래쪽) 위에 오게 화면 맨 위부터
LABEL_FONT = 96         # 번호 + 이름 띠 글씨 (검은고딕)
LABEL_MIN = 64
TITLE_FONT = 78         # 첫 화면 제목 띠


def esc(s):
    return html.escape(str(s or ""))


def hl(text, word):
    t = esc(text)
    if word:
        t = t.replace(esc(word), f'<span class="hl">{esc(word)}</span>', 1)
    return t.replace("\n", "<br>")


def rows_of(post):
    """목록 줄: [원본(list.base, 선택)] + 항목들. 각 줄 {num, name, src, base}."""
    L = post.get("list") or {}
    rows = []
    if L.get("base"):
        b = L["base"]
        rows.append({"num": "00", "name": b.get("name", "원본 사진"), "src": b.get("src"), "base": True})
    for i, it in enumerate(L.get("items") or [], 1):
        rows.append({"num": f"{i:02d}", "name": it.get("name", ""), "src": it.get("src"), "base": False})
    return rows


def _frames(sec):
    return max(1, int(round(sec * FPS)))


def timeline(post):
    """장면 순서와 길이(초, 프레임 단위로 맞춤). checks.py도 이 함수로 길이를 검사한다.
    반환: {"states": [(종류, 줄 번호), ...], "durs": [...], "main": 본편 길이, "cta": 끝 화면, "total": 전체, "item": 항목 하나}"""
    from video import CTA_SECONDS
    L = post.get("list") or {}
    rows = rows_of(post)
    n_items = sum(1 for r in rows if not r["base"])
    n_base = len(rows) - n_items
    hook = float(L.get("hook_seconds", HOOK_SECONDS))
    cta = CTA_SECONDS if (post.get("dm") or {}).get("cta") else 0.0
    if L.get("seconds"):
        item = float(L["seconds"])
    else:
        units = n_items + BASE_FACTOR * n_base
        item = (TARGET_TOTAL - cta - hook - END_HOLD) / max(1.0, units)
        item = min(ITEM_RANGE[1], max(ITEM_RANGE[0], item))
    item = _frames(item) / FPS
    states, durs = [("hook", _hook_row(post, rows))], [_frames(hook) / FPS]
    for r, row in enumerate(rows):
        d = item * (BASE_FACTOR if row["base"] else 1.0)
        if r == len(rows) - 1:
            d += END_HOLD
        states.append(("row", r))
        durs.append(_frames(d) / FPS)
    main = sum(durs)
    return {"states": states, "durs": durs, "main": main, "cta": cta, "total": main + cta, "item": item}


def _hook_row(post, rows):
    """첫 화면에 크게 보여 줄 줄 번호 (list.hook = 항목 번호 1부터, 기본 1)."""
    h = int((post.get("list") or {}).get("hook", 1))
    idx = [i for i, r in enumerate(rows) if not r["base"]]
    if not idx:
        return 0
    return idx[min(max(h, 1), len(idx)) - 1]


def pages(n, per=None):
    """n줄을 페이지로 고르게 나눈다: 한 화면 per(기본 MAX_ROWS)줄까지. [(시작, 끝), ...]"""
    per = int(per or MAX_ROWS)
    k = max(1, math.ceil(n / per))
    size = math.ceil(n / k)
    return [(i, min(n, i + size)) for i in range(0, n, size)]


def layout(post):
    """그림을 가로 꽉 차게(1080x1350, 4:5) 두고, 읽을 글(이름 띠·제목 띠)은 안전 영역 아래쪽,
    오른쪽 아래 버튼 줄(rail_top) 위에 둔다. 위쪽 '자료' 안내 띠(dm.banner)는 그림 위 안전 영역 맨 위."""
    img_h = int(W * 1.25)
    return {"img": (0, IMG_TOP, W, img_h), "label_bottom": RAIL_TOP - 12, "label_w": W - 2 * SIDE}


def page_html(post, folder, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    L = post["list"]
    rows = rows_of(post)
    lo = layout(post)
    pos = L.get("position", "center 40%")
    imgs = [(Path(folder) / r["src"]).resolve().as_uri() for r in rows]
    ix, iy, iw, ih = lo["img"]
    js_rows = json.dumps([{"num": r["num"], "name": r["name"], "img": u} for r, u in zip(rows, imgs)], ensure_ascii=False)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};
  font-family:'Wanted',sans-serif;word-break:keep-all}}
.hl{{color:{b['accent']}}}
.pic{{position:absolute;left:{ix}px;top:{iy}px;width:{iw}px;height:{ih}px;background:#1d2420}}
.pic img{{width:100%;height:100%;object-fit:cover;object-position:{pos};display:block}}
.band{{position:absolute;left:{SIDE}px;bottom:{H - lo['label_bottom']}px;max-width:{lo['label_w']}px;
  background:rgba(10,11,10,.88);border-left:10px solid {b['accent']};padding:20px 30px 18px 26px;
  font-family:'Black Han Sans';font-weight:400;letter-spacing:-.02em;display:none}}
#label{{white-space:nowrap;font-size:{LABEL_FONT}px;line-height:1}}
#label .n{{color:{b['accent']};margin-right:24px}}
#title{{font-size:{TITLE_FONT}px;line-height:1.14}}
</style></head><body><div id="f">
<div class="pic"><img id="img" src=""></div>
<div class="band" id="title">{hl(post['title'], post.get('highlight'))}</div>
<div class="band" id="label"><span class="n" id="ln"></span><span id="lt"></span></div>
</div><script>
const ROWS = {js_rows};
const small = [];
const lab = document.getElementById('label');
// 이름 띠는 글씨 하나 크기로 통일하되, 띠 너비를 넘는 이름만 그 장에서 줄인다 (최소 {LABEL_MIN}px)
window.twFit = () => {{}};
const fit = (row) => {{
  lab.style.fontSize = '{LABEL_FONT}px';
  let fs = {LABEL_FONT};
  while (lab.scrollWidth > lab.clientWidth + 1 && fs > {LABEL_MIN}) {{ fs -= 2; lab.style.fontSize = fs + 'px'; }}
  if (lab.scrollWidth > lab.clientWidth + 1) small.push(row.name);
}};
window.twProblems = () => {{
  const out = [];
  lab.style.display = 'block';
  ROWS.forEach(r => {{ document.getElementById('ln').textContent = r.num; document.getElementById('lt').textContent = r.name; fit(r); }});
  lab.style.display = 'none';
  small.forEach(s => out.push('이름이 띠 한 줄에 안 들어감: ' + s));
  const t = document.getElementById('title'); t.style.display = 'block';
  // 제목은 2줄 안에 들어갈 때까지 글씨를 줄인다 (최소 56px). 줄 나눔은 post.title 그대로
  let tfs = {TITLE_FONT};
  const lines = () => Math.round((t.clientHeight - 38) / parseFloat(getComputedStyle(t).lineHeight));
  while (lines() > 2 && tfs > 56) {{ tfs -= 2; t.style.fontSize = tfs + 'px'; }}
  if (lines() > 2) out.push('제목이 2줄을 넘음');
  if (t.getBoundingClientRect().top < {SAFE_TOP}) out.push('제목 띠가 안전 영역 위로 나감');
  t.style.display = 'none';
  return out;
}};
window.twState = (kind, r) => {{
  const row = ROWS[r];
  document.getElementById('img').src = row.img;
  document.getElementById('title').style.display = kind === 'hook' ? 'block' : 'none';
  lab.style.display = kind === 'row' ? 'block' : 'none';
  if (kind === 'row') {{
    document.getElementById('ln').textContent = row.num;
    document.getElementById('lt').textContent = row.name;
    fit(row);
  }}
  return Promise.all([...document.images].filter(i => i.src).map(i => i.decode().catch(() => null)));
}};
</script></body></html>"""


async def shoot_states(post, folder, cfg, work):
    """장면마다 PNG 한 장. [(png, 초), ...]와 레이아웃 문제 목록."""
    from playwright.async_api import async_playwright
    tl = timeline(post)
    page_file = work / "list.html"
    page_file.write_text(page_html(post, folder, cfg), encoding="utf-8")
    shots = []
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(200)
        await pg.evaluate("twFit()")
        problems = await pg.evaluate("twProblems()")
        el = await pg.query_selector("#f")
        for i, ((kind, r), d) in enumerate(zip(tl["states"], tl["durs"])):
            await pg.evaluate(f"twState('{kind}', {r})")
            png = work / f"s{i:03d}.png"
            await el.screenshot(path=str(png))
            shots.append((png, d))
        await browser.close()
    return shots, problems, tl


def _page_bounds(post, tl):
    """음악의 강한 박자 자리: 첫 화면 → 목록, 페이지가 넘어가는 순간."""
    rows = rows_of(post)
    pg = pages(len(rows), (post.get("list") or {}).get("per_page"))
    starts = {s for s, _ in pg[1:]}
    out, t = [], 0.0
    for (kind, r), d in zip(tl["states"], tl["durs"]):
        if kind == "row" and (r == 0 or r in starts):
            out.append(t)
        t += d
    return out


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


def make_list_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/01.jpg·cover.jpg(썸네일이 덮어씀). 전체 길이(초) 반환."""
    folder = Path(folder)
    missing = [r["src"] for r in rows_of(post) if not r.get("src") or not (folder / r["src"]).exists()]
    if missing:
        raise FileNotFoundError("목록 이미지 없음: " + ", ".join(map(str, missing[:5]))
                                + " → list.items[].prompt·mascot 확인 (그림은 render.yml이 만든다)")
    work = folder / "_list"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    shots, problems, tl = asyncio.run(shoot_states(post, folder, cfg, work))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    # 1) 장면 이어 붙이기 (컷 전환)
    lst = work / "list.txt"
    lines = []
    for png, d in shots:
        lines += [f"file '{png.name}'", f"duration {d:.4f}"]
    lines.append(f"file '{shots[-1][0].name}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps={FPS},scale={W}:{H},setsar=1,format=yuv420p", "-t", f"{tl['main']:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), str(silent)],
                   check=True, cwd=str(work))
    # 2) 음악 (소리 없는 릴스 금지, STYLE_GUIDE 6장): post.music.src → assets/music → 코드로 생성
    pm = post.get("music") or {}
    files = sorted((ROOT / "assets" / "music").glob("*.mp3")) + sorted((ROOT / "assets" / "music").glob("*.m4a"))
    vol = float(pm.get("volume", 0.8))
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    elif files and not pm.get("generate"):
        music = random.choice(files)
    else:
        from music_gen import make_music
        music = work / "music.wav"
        info = make_music(music, tl["durs"], 0.0, seed=int(pm.get("seed", 7)), hit_at=_page_bounds(post, tl))
        print(f"배경음악: 코드로 생성 (BPM {info['bpm']}, 목록 시작·페이지 넘김 {len(info['hits'])}곳에 강한 박자)")
    out = folder / "reel.mp4"
    dur = tl["main"]
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent),
                    "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex", f"[1:a]volume={vol},atrim=duration={dur:.3f},aresample=44100,"
                                       f"aformat=channel_layouts=stereo,afade=t=in:d=0.05[a]",
                    "-map", "0:v:0", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    # 3) 앞쪽 '자료' 안내 띠 (dm.banner): 안전 영역 맨 위, 3초부터 본편 끝까지. 목록 화면은 그만큼 아래에서 시작한다
    from banner import banner_text, make_banner_png, apply_banner, banner_height
    bt = banner_text(post)
    if bt:
        png = make_banner_png(bt, cfg, W - 2 * SIDE, work / "banner.png")
        apply_banner(out, png, SIDE, SAFE_TOP, dur)
        print(f"  안내 띠 자리: 안전 영역 맨 위 (세로 {SAFE_TOP}~{SAFE_TOP + banner_height(bt)}px)")
    # 4) 끝 화면 (dm.cta 2.5초, 음악은 그 앞에서 페이드아웃)
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
    # 미리보기: 첫 화면(1초), 목록 첫 줄, 페이지마다 가운데, 끝 화면
    for k, t in enumerate(preview_times(post, tl, dur), 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    rows = rows_of(post)
    print(f"목록 {len(rows)}줄 ({', '.join(f'{e - s}줄' for s, e in pages(len(rows), post['list'].get('per_page')))}), "
          f"항목당 {tl['item']:.2f}초, 본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur


def preview_times(post, tl, total):
    ts = [1.0]
    rows = rows_of(post)
    pg = pages(len(rows), (post.get("list") or {}).get("per_page"))
    t, starts = 0.0, {}
    for (kind, r), d in zip(tl["states"], tl["durs"]):
        if kind == "row":
            starts[r] = t + d / 2
        t += d
    ts.append(max(starts[0], 3.4))   # 안내 띠가 들어온 뒤
    for s, e in pg:
        ts.append(starts[(s + e) // 2])
    ts.append(starts[len(rows) - 1])
    if tl["cta"]:
        ts.append(total - 1.0)
    return ts
