"""영상 프레임 릴스 (post type = "video").

레이아웃 (1080x1920):
    ▌TOKEN WAR
    한국어 제목 2줄 (강조 녹색)
    영어 부제
    ┌──────── 영상 (네온 테두리) ────────┐
    └────────────────────────────────────┘
    영상 · @원작자
    자막 (시간에 맞춰 바뀜)

영상은 권리가 확인된 것만 쓴다: 직접 만든 것(own), 원작자 허락(permission), 이용 허락 라이선스(license).
"""
import asyncio
import html
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_SAFE = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("reel_safe", {})
UI_SAFE_TOP = _SAFE.get("top", 285)        # 이보다 위는 인스타 머리말(릴스·카메라)에 가려진다
UI_SAFE_BOTTOM = _SAFE.get("bottom", 1250)  # 이보다 아래는 인스타 캡션·음악·버튼에 가려진다


def esc(s):
    return html.escape(str(s or ""))


def hl(text, word):
    t = esc(text)
    if word:
        t = t.replace(esc(word), f'<span class="hl">{esc(word)}</span>', 1)
    return t.replace("\n", "<br>")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    return st["width"], st["height"], float(d["format"]["duration"])


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return bool(out)


CTA_SECONDS = 2.5


def dm_cta(post):
    """참여형(dm 있음) 게시물 화면 안 '자료' 안내 문구 (운영자 결정 2026-11-16). dm.cta 또는 없으면 None."""
    d = post.get("dm") or {}
    return (d.get("cta") or "").strip() or None


def cta_html(text, cfg, fonts_uri):
    b = cfg["brand"]
    import re as _re
    body = esc(text).replace("\n", "<br>")
    body = _re.sub(r"(?:'|&#x27;|‘)(.+?)(?:'|&#x27;|’)", lambda m: f"<span class=\"hl\">'{m.group(1)}'</span>", body)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts_uri}/black-han-sans/index.css');
*{{box-sizing:border-box}}html,body{{margin:0}}
#frame{{width:{W}px;height:{H}px;position:relative;background:{b['bg']};color:{b['text']};word-break:keep-all}}
.wrap{{position:absolute;left:90px;right:90px;top:{UI_SAFE_TOP + 120}px;bottom:{H - UI_SAFE_BOTTOM + 60}px;display:flex;flex-direction:column;
  justify-content:center;align-items:center;gap:44px;text-align:center}}
.brand{{font-family:'Black Han Sans';font-size:44px;color:{b['accent']}}}
.t{{font-family:'Black Han Sans';font-size:82px;line-height:1.25;letter-spacing:-.02em;text-wrap:balance}}
.hl{{color:{b['accent']}}}
.bar{{width:160px;height:8px;background:{b['accent']}}}
</style></head><body><div id="frame"><div class="wrap"><div class="brand">TOKEN WAR</div><div class="t">{body}</div><div class="bar"></div></div></div></body></html>"""


def append_cta_card(mp4, text, cfg, work, dur):
    """다 만든 릴스 끝에 '자료' 안내 화면(CTA_SECONDS초)을 붙인다. 소리는 앞 영상 끝에서 이어 작게 페이드."""
    import asyncio
    from playwright.async_api import async_playwright

    fonts_uri = (ROOT / "assets" / "fonts").as_uri()
    html = work / "cta.html"
    html.write_text(cta_html(text, cfg, fonts_uri), encoding="utf-8")
    png = work / "cta.png"

    async def shoot():
        async with async_playwright() as p:
            exe = shutil.which("google-chrome") or shutil.which("chromium")
            browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
            pg = await browser.new_page(viewport={"width": W, "height": H})
            await pg.goto(html.as_uri())
            await pg.evaluate("document.fonts.ready")
            await (await pg.query_selector("#frame")).screenshot(path=str(png))
            await browser.close()
    asyncio.run(shoot())
    tmp = work / "with_cta.mp4"
    total = dur + CTA_SECONDS
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(mp4),
                    "-loop", "1", "-t", f"{CTA_SECONDS}", "-framerate", str(FPS), "-i", str(png),
                    "-f", "lavfi", "-t", f"{CTA_SECONDS}", "-i", "anullsrc=r=44100:cl=stereo",
                    "-filter_complex",
                    f"[1:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p,fade=t=in:d=0.25[cv];"
                    f"[0:v]setsar=1,fps={FPS},format=yuv420p[mv];"
                    f"[0:a]aresample=44100,aformat=channel_layouts=stereo[ma];"
                    f"[mv][ma][cv][2:a]concat=n=2:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)], check=True)
    shutil.move(str(tmp), str(mp4))
    return total


def page_html(post, cfg, box_h, fonts_uri, size=50):
    b = cfg["brand"]
    credit = post.get("credit")
    credit_html = (f'<div class="credit"><span>출처</span><b>{esc(credit)}</b></div>' if credit
                   else '<div class="credit"></div>')
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts_uri}/black-han-sans/index.css');
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-SemiBold.otf');font-weight:600}}
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Wanted';src:url('{fonts_uri}/WantedSans-SemiBold.otf');font-weight:600}}
@font-face{{font-family:'Wanted';src:url('{fonts_uri}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts_uri}/WantedSans-ExtraBold.otf');font-weight:800}}
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent}}
#frame{{width:{W}px;height:{H}px;position:relative;color:{b['text']};font-family:'Wanted',sans-serif;word-break:keep-all}}
#frame.bg{{background:{b['bg']}}}
.head{{position:absolute;left:65px;right:65px;top:{UI_SAFE_TOP}px;display:flex;flex-direction:column;align-items:center;gap:22px;text-align:center}}
.brand{{font-family:'Black Han Sans';font-size:40px;color:{b['accent']}}}
.title{{margin:6px 0 0;font-family:'Black Han Sans';font-weight:400;font-size:88px;line-height:1.18;letter-spacing:-.02em;text-wrap:balance}}
.hl{{color:{b['accent']}}}
.en{{font-size:34px;font-weight:600;color:#9AA59F;letter-spacing:-.005em}}
.box{{position:absolute;left:20px;width:1040px;height:{box_h}px;border:6px solid {b['accent']}}}
.credit{{position:absolute;left:0;right:0;display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center}}
.credit span{{font-size:26px;font-weight:700;color:#9AA59F}}
.credit b{{font-size:34px;font-weight:800;color:{b['accent']};letter-spacing:-.01em}}
.sub{{position:absolute;left:70px;right:70px;text-align:center;font-size:{size}px;font-weight:800;line-height:1.35;letter-spacing:-.02em;
  color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);white-space:pre-line}}
.sub .hl{{color:{b['accent']}}}
</style></head><body><div id="frame">
<div class="head"><div class="brand">TOKEN WAR</div>
<h1 class="title">{hl(post['title'], post.get('highlight'))}</h1>
<div class="en">{esc(post.get('title_en', ''))}</div></div>
<div class="box" id="box"></div>{credit_html}
<div class="sub" id="sub"></div>
</div></body></html>"""


async def render_layers(post, cfg, folder, box_h, work, size=50, lift=0):
    """틀(PNG), 자막(PNG 여러 장), 미리보기용 배경을 만든다. 영상 창 위치를 돌려준다.
    size: 자막 글씨(px). 자막은 항상 영상 창 바닥. lift: 원본 글자 띠를 피해 바닥에서 올린 만큼(px)."""
    from playwright.async_api import async_playwright

    fonts_uri = (ROOT / "assets" / "fonts").as_uri()
    tmp = work / "frame.html"
    tmp.write_text(page_html(post, cfg, box_h, fonts_uri, size), encoding="utf-8")
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(tmp.as_uri())
        await pg.evaluate("document.fonts.ready")
        geo = await pg.evaluate(f"""() => {{
            const head = document.querySelector('.head').getBoundingClientRect();
            const box = document.getElementById('box');
            let top = Math.max(head.bottom + 56, 600);
            top = Math.round(top / 2) * 2;
            box.style.top = top + 'px';
            const cr = document.querySelector('.credit');
            cr.style.top = (top + {box_h} + 20) + 'px';
            const bottom = top + {box_h};
            const credH = cr.getBoundingClientRect().height ? 84 : 0;
            const inside = bottom + credH + 40 + 136 > {UI_SAFE_BOTTOM};
            const sub = document.getElementById('sub');
            const capAt = {float((post.get("video") or {}).get("captions_at") or 0)};
            // 2줄 자막 높이 기준으로 위치를 고정한다 (자막 PNG는 아래 끝 기준이라 1줄이어도 아래 끝선이 같다)
            const twoLine = 2 * {size} * 1.35;
            sub.style.top = 'auto';
            if (inside && capAt > 0) {{
              // 예전 방식: 원본에 박힌 자막 바로 위 (자막 아래쪽 끝 기준)
              sub.style.bottom = ({H} - (top + 6 + capAt * ({box_h} - 12) - 14)) + 'px';
            }} else if (inside) {{
              // 영상 창 맨 아래: 자막 아래 끝이 안쪽 테두리 위 24px (lift만큼 올림)
              sub.style.bottom = ({H} - (bottom - 6 - 24 - {int(lift)})) + 'px';
            }} else {{
              // 영상 아래 빈칸이 안전 영역 안이면 영상 아래 (2줄 기준 위 끝)
              sub.style.bottom = ({H} - (bottom + credH + 40 + twoLine)) + 'px';
            }}
            const headOver = head.bottom > top - 20;
            return {{top, inside, headOver, titleH: document.querySelector('.title').getBoundingClientRect().height}};
        }}""")
        if geo["headOver"] or geo["titleH"] > 88 * 1.18 * 2.4:
            await browser.close()
            raise SystemExit("제목이 너무 길어 영상과 겹침 → 2줄 안으로 줄일 것")
        frame = await pg.query_selector("#frame")
        await frame.screenshot(path=str(work / "frame.png"), omit_background=True)
        subs = []
        await pg.evaluate("""() => { document.querySelector('.head').style.visibility='hidden';
            document.getElementById('box').style.visibility='hidden'; document.querySelector('.credit').style.visibility='hidden'; }""")
        for i, s in enumerate(post.get("subtitles", [])):
            await pg.evaluate("([t]) => { document.getElementById('sub').innerHTML = t; }",
                              [hl(s["text"], s.get("highlight"))])
            path = work / f"sub_{i:02d}.png"
            await frame.screenshot(path=str(path), omit_background=True)
            subs.append((path, float(s["start"]), float(s["end"])))
        await browser.close()
    return geo, subs


# ---------- 원본에 박힌 글자(이름 자막·하단 자막) 피하기 ----------
# 원본 화면의 가로줄마다 '세게 바뀌는 점'의 밀도를 잰다. 글자 줄은 밀도가 0.1 이상이고 짧은 획이 많다
# (머스크 대담 영상: 이름 자막 0.12~0.28, 옷·배경 잡음 0.07 이하).
BURN_DENSITY, BURN_RUNS, BURN_W = 0.10, 50, 480
# 원본 글자를 띠로 가리지 않는다 (운영자 결정: 자막만 보이게). 자막은 항상 영상 창 바닥 (2026-11-16 운영자 결정: 위에 다는 것 없앰).
# 바닥에서 겹치면 글씨를 줄여 보고(SUB_SIZES), 그래도 겹치면 원본 글자 띠 바로 위로 조금 올린다(영상 창 아래쪽 1/3 안에서만,
# 얼굴 검출이 없어 턱·입을 가리지 않게 보수적으로). 그래도 안 되면 바닥에 두고 겹침 감수. 한 릴스 안에서는 크기·위치 하나로 통일.
SUB_SIZES = (50, 44, 40)   # 40px 아래로는 줄이지 않는다
LIFT_ZONE = 1 / 3          # 올린 자막의 위 끝이 영상 창 안쪽 높이의 아래 1/3 안에 있어야 한다


def sample_gray(src, start, dur, crop=None, fps=2):
    """[start, start+dur] 구간을 초당 fps장 회색 프레임으로. (시각 목록, 프레임 배열[N,h,w]) 원본 비율 유지, 폭 480."""
    import numpy as np
    vw, vh, _ = probe(src)
    if crop:
        t0, t1 = crop
        ch = int(vh * (t1 - t0)) // 2 * 2
        vf = f"crop={vw}:{ch}:0:{int(vh * t0)},"
        vh = ch
    else:
        vf = ""
    h = max(2, int(round(BURN_W * vh / vw / 2)) * 2)
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{start}", "-t", f"{dur:.3f}", "-i", str(src),
                          "-vf", f"{vf}fps={fps},scale={BURN_W}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    n = len(raw) // (BURN_W * h)
    frames = np.frombuffer(raw[: n * BURN_W * h], np.uint8).reshape(n, h, BURN_W).astype(np.int16)
    times = [start + (i + 0.5) / fps for i in range(n)]
    return times, frames


def text_bands(frame):
    """한 프레임에서 글자 줄 띠 [(위, 아래)] (프레임 높이 비율)."""
    import numpy as np
    gx = np.abs(np.diff(frame, axis=1)) > 40
    dens = gx.mean(axis=1)
    runs = np.count_nonzero(np.diff(gx.astype(np.int8), axis=1), axis=1)
    rows = np.where((dens > BURN_DENSITY) & (runs > BURN_RUNS))[0]
    bands, h = [], frame.shape[0]
    for y in rows:
        if bands and y - bands[-1][1] <= 3:
            bands[-1][1] = y
        else:
            bands.append([y, y])
    return [(a / h, (b + 1) / h) for a, b in bands if b - a + 1 >= max(3, h // 90)]


def alpha_rows(path):
    """자막 PNG에서 글자(그림자 포함)가 있는 세로 범위."""
    from PIL import Image
    box = Image.open(path).getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    return (box[1], box[3]) if box else None


def burned_bands(post, src, start, dur, geo, scale_info):
    """원본에 박힌 글자 줄을 프레임마다 찾아 [(시각, [(위px, 아래px)])]로. 영상 창 밖이면 None."""
    v = post.get("video") or {}
    if v.get("captions_at") or v.get("avoid_burned") is False or not geo.get("inside"):
        return None
    crop = (float(v["crop"].get("top", 0)), float(v["crop"].get("bottom", 1))) if v.get("crop") else None
    times, frames = sample_gray(src, start, dur, crop)
    box_top = geo["top"] + 6
    scaled_h, off_y = scale_info
    return [(tt, [(box_top + b0 * scaled_h - off_y, box_top + b1 * scaled_h - off_y) for b0, b1 in text_bands(fr)])
            for tt, fr in zip(times, frames)]


def _overlaps(subs, burned, i, shift=0, rows=None):
    """자막 i와 겹치는 (시각, 띠위px) 목록. shift: 자막을 위로 올린 만큼(px), rows: 미리 잰 글자 세로 범위."""
    path, a, z = subs[i]
    rows = rows or alpha_rows(path)
    if not rows:
        return []
    y0, y1 = rows[0] - shift, rows[1] - shift
    return [(tt, b0) for tt, bands in burned if a - 0.25 <= tt <= z + 0.25
            for b0, b1 in bands if b1 > y0 - 10 and b0 < y1 + 10]


def clashing(subs, burned, shift=0, rows=None):
    """원본 글자와 겹치는 자막 번호 목록. subs: [(png, a, z)]."""
    return [i + 1 for i in range(len(subs)) if _overlaps(subs, burned, i, shift, rows and rows[i])]


def clash_spans(subs, burned, start, shift=0, rows=None):
    """겹치는 구간을 릴스 시각(초)으로 [(a, z)] 묶어서."""
    spans = []
    for i in range(len(subs)):
        ts = [tt for tt, _ in _overlaps(subs, burned, i, shift, rows and rows[i])]
        if ts:
            _, a, z = subs[i]
            spans.append((max(a, min(ts) - 0.25) - start, min(z, max(ts) + 0.25) - start))
    spans.sort()
    merged = []
    for a, z in spans:
        if merged and a <= merged[-1][1] + 0.1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], z))
        else:
            merged.append((a, z))
    return merged


def _clash_secs(spans):
    return sum(z - a for a, z in spans)


def place_subs(post, cfg, folder, box_h, work, src, start, dur, scale_info):
    """자막 크기·자리를 정하고 그린다. 자막은 항상 영상 창 바닥. 순서: 바닥 50px → 겹치면 44px → 40px
    → 그래도 겹치면 원본 글자 띠 바로 위로 조금 올림(올린 자막 위 끝이 영상 창 아래쪽 1/3 안일 때만)
    → 남는 겹침은 감수(띠로 가리지 않음)하고 "겹침 감수: a~b초"로 알린다. 겹치는 시간이 가장 짧은 자리를 고른다.
    video.captions_size(px)를 적으면 그 크기만 쓴다. captions_pos: "top"은 더 쓰지 않는다(경고 후 바닥)."""
    v = post.get("video") or {}
    pos_fix, size_fix = v.get("captions_pos"), v.get("captions_size")
    if pos_fix and pos_fix != "bottom":
        print(f"  경고: video.captions_pos '{pos_fix}'는 더 쓰지 않는다 → 자막은 영상 창 바닥 (post.json에서 지울 것)")
    sizes = [int(size_fix)] if size_fix else list(SUB_SIZES)
    geo, subs = asyncio.run(render_layers(post, cfg, folder, box_h, work, sizes[0]))
    if not geo.get("inside"):
        return geo, subs
    burned = burned_bands(post, src, start, dur, geo, scale_info)
    if burned is None:
        print(f"  자막: 영상 창 맨 아래, {sizes[0]}px")
        return geo, subs
    inner_top = geo["top"] + 6
    zone_top = inner_top + (box_h - 12) * (1 - LIFT_ZONE)
    cands = []  # (겹친 시간, 올림, 크기 순번, 크기, 겹친 자막)
    first_bad = None
    for k, size in enumerate(sizes):
        if k:
            geo, subs = asyncio.run(render_layers(post, cfg, folder, box_h, work, size))
        rows = [alpha_rows(p_) for p_, _, _ in subs]
        bad = clashing(subs, burned, 0, rows)
        if not bad:
            if k:
                print(f"  자막 크기 {size}px로 줄여 바닥 유지 ({sizes[0]}px에서 원본 글자와 겹쳤던 자막: {first_bad})")
            else:
                print(f"  자막: 영상 창 맨 아래, {size}px")
            return geo, subs
        first_bad = first_bad or bad
        cands.append((_clash_secs(clash_spans(subs, burned, start, 0, rows)), 0, k, size, bad))
        # 올림 후보: 겹치는 원본 글자 띠마다 '그 띠 위 끝 - 10px'에 자막 아래 끝이 오게
        y1 = max(r[1] for r in rows if r)
        top0 = min(r[0] for r in rows if r)
        lifts = sorted({int(round((y1 - (b0 - 10)) / 2) * 2) for i in range(len(subs))
                        for _, b0 in _overlaps(subs, burned, i, 0, rows[i])})
        for lift in lifts:
            if lift <= 0 or top0 - lift < zone_top:
                continue
            spans = clash_spans(subs, burned, start, lift, rows)
            cands.append((_clash_secs(spans), lift, k, size, clashing(subs, burned, lift, rows)))
    secs, lift, k, size, bad = min(cands)
    geo, subs = asyncio.run(render_layers(post, cfg, folder, box_h, work, size, lift))
    where = f"영상 창 바닥에서 {lift}px 올림 (원본 글자 띠 바로 위, 영상 창 아래쪽 1/3 안)" if lift else "영상 창 맨 아래"
    print(f"  자막: {where}, {size}px" + (". 얼굴(턱·입)을 덮지 않는지 장면 시트로 확인" if lift else ""))
    if bad:
        spans = ", ".join(f"{a:.1f}~{z:.1f}초" for a, z in clash_spans(subs, burned, start))
        print(f"  겹침 감수: {spans} 원본 글자와 겹침 (릴스 시각, 자막 {bad})")
    return geo, subs


# ---------- 구간 경계를 말소리에 맞추기 (나델라 릴스 끝 "rejected"가 잘린 일 이후) ----------
# 받아쓰기 단어 시각만 믿지 않고 원본 소리 크기로 '첫 소리 시작'과 '마지막 소리 끝'을 찾는다.
# 소리 기준은 클립마다 상대적으로: 20ms 조각 dB의 아래 10%(무음·숨) ~ 위 10%(말소리) 사이 EDGE_RATIO 지점.
# 이보다 작은 조각이 EDGE_GAP초 이상 이어지면 '소리 틈'(단어·문장 사이)으로 본다.
# - end: 마지막 소리 끝 + EDGE_TAIL(0.3초)보다 앞이면 '마지막 소리 끝 + 0.4초'로 늘린다.
#        그 사이 다음 말 첫소리가 들어오면 '마지막 소리 끝 + 0.05초'부터 0.12초 동안 소리를 줄여 무음으로 (화면은 end까지).
# - start: 첫 소리 - 0.2초보다 뒤면 앞으로 당긴다. 그 앞에 앞 문장 꼬리가 있으면 소리만 무음 → 첫 소리 직전 0.12초 페이드인.
# - 말이 EDGE_MAX초 넘게 끊김 없이 이어지면(문장 한가운데) 자동으로 못 고치므로 오류.
EDGE_HOP, EDGE_RATIO, EDGE_GAP = 0.02, 0.3, 0.06
EDGE_TAIL, EDGE_END_PAD, EDGE_HEAD = 0.3, 0.4, 0.2
FADE_AFTER, FADE_LEN, EDGE_MAX = 0.05, 0.12, 1.2


class EdgeCutError(Exception):
    pass


def _db_frames(src, a, z, sr=16000):
    """[a, z] 구간 소리를 EDGE_HOP초 조각으로 나눈 dB 목록. (조각 시작 시각 배열, dB 배열)"""
    import numpy as np
    # -ss를 -i 앞에만 두면 일부 원본(yt-dlp로 일부만 받은 것 등)에서 소리가 0.1~0.7초 어긋난다.
    # 5초 앞까지 빠르게 건너뛴 뒤 원래 시각(-copyts)으로 정확히 자른다.
    pre = max(0.0, a - 5)
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{pre:.3f}", "-i", str(src), "-copyts",
                          "-ss", f"{a:.3f}", "-t", f"{z - a:.3f}", "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw[: len(raw) // 2 * 2], np.int16).astype(np.float32) / 32768
    hop = int(sr * EDGE_HOP)
    n = len(x) // hop
    if n == 0:
        return np.zeros(0), np.zeros(0)
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-10)
    return a + np.arange(n) * EDGE_HOP, 20 * np.log10(rms)


def fit_edges(src, start, end):
    """start/end를 말소리에 맞춘다. {"start", "end", "fade_in", "fade_out", "notes", "errors"}
    fade_in/fade_out: 소리를 줄이기 시작하는 원본 시각 (없으면 None)."""
    import numpy as np
    plan = {"start": start, "end": end, "fade_in": None, "fade_out": None, "notes": [], "errors": []}
    if not has_audio(src):
        return plan
    _, _, vdur = probe(src)
    a, z = max(0.0, start - EDGE_MAX - 0.5), min(vdur, end + EDGE_MAX + 0.5)
    t, db = _db_frames(src, a, z)
    body = db[(t >= start) & (t < end)]
    if len(body) < 50:
        return plan
    lo, hi = np.percentile(body, 10), np.percentile(body, 90)
    if hi - lo < 10:  # 소리 크기 차이가 거의 없으면(음악·잡음) 판단하지 않는다
        return plan
    loud = db > lo + EDGE_RATIO * (hi - lo)
    gap_n = int(round(EDGE_GAP / EDGE_HOP))
    n = len(t)

    def idx(x):
        return int(min(max(np.searchsorted(t, x, side="right") - 1, 0), n - 1))

    def run_end(i):
        """i에서 시작하는 소리가 끝나는 조각 번호(소리 틈 직전 마지막 조각 + 1). 틈이 없으면 None."""
        quiet = 0
        for j in range(i, n):
            quiet = quiet + 1 if not loud[j] else 0
            if quiet >= gap_n:
                return j - gap_n + 1
        return None

    def run_start(i):
        """i에서 거꾸로 가서, 이 소리가 시작한 조각 번호. 틈이 없으면 None."""
        quiet = 0
        for j in range(i, -1, -1):
            quiet = quiet + 1 if not loud[j] else 0
            if quiet >= gap_n:
                return j + gap_n
        return None

    # ----- 끝 -----
    ie = idx(end - 1e-6)
    if loud[ie]:            # end가 소리 한가운데: 그 소리가 끝나는 곳까지
        k = run_end(ie)
        last = t[k] if k is not None else None
    else:                   # end가 조용한 곳: 바로 앞 마지막 소리 끝
        j = ie
        while j >= 0 and not loud[j]:
            j -= 1
        last = t[j] + EDGE_HOP if j >= 0 else None
    if last is None or last - end > EDGE_MAX:
        plan["errors"].append(f"video.end={end:g}: 말이 {EDGE_MAX}초 넘게 이어지는 문장 한가운데 → 문장이 끝나는 곳으로 옮길 것 "
                              "(받아쓰기 단어 [w, 시작, 끝]의 '끝' + 0.4초)")
    elif end < last + EDGE_TAIL:
        new_end = round(min(vdur, last + EDGE_END_PAD), 2)
        k = idx(last + FADE_AFTER)
        nxt = bool(loud[k:idx(new_end - 1e-6) + 1].any())
        if nxt:
            plan["fade_out"] = last + FADE_AFTER
        plan["end"] = new_end
        plan["notes"].append(f"끝: 마지막 소리 {last:.2f} → end {end:g}에서 {new_end:g}로"
                             + (f" (뒤 {FADE_LEN}초 소리 줄임, 다음 말 첫소리 막기)" if nxt else ""))
    else:
        k = idx(last + FADE_AFTER)
        if loud[k:ie + 1].any():   # 늘리지 않아도 다음 말 첫소리가 끝에 걸려 있으면 줄인다
            plan["fade_out"] = last + FADE_AFTER
            plan["notes"].append(f"끝: 마지막 소리 {last:.2f}, end {end:g} (뒤 {FADE_LEN}초 소리 줄임, 다음 말 첫소리 막기)")

    # ----- 시작 -----
    i0 = idx(start)
    tail_end = None
    if loud[i0]:            # start가 소리 한가운데: 앞 문장 꼬리로 보고, 그 꼬리가 끝난 뒤 첫 소리를 찾는다
        k = run_end(i0)
        if k is None or t[k] - start > EDGE_MAX:
            plan["errors"].append(f"video.start={start:g}: 말이 이어지는 문장 한가운데 → 첫 단어 '시작' - 0.2초로 옮길 것")
            return plan
        tail_end = t[k]
        j = k
    else:
        j = i0
    while j < n and not loud[j]:
        j += 1
    if j >= n:
        return plan
    first = t[j]
    if start > first - EDGE_HEAD or tail_end is not None:
        new_start = round(max(0.0, first - EDGE_HEAD), 2) if tail_end is None else start
        # 새 시작 ~ 첫 소리 사이에 앞 문장 꼬리가 있으면 소리만 무음 → 첫 소리 직전 페이드인
        pre = loud[idx(new_start):j - gap_n + 1]
        if tail_end is not None or pre.any():
            plan["fade_in"] = max(new_start, first - FADE_AFTER - FADE_LEN)
        plan["start"] = new_start
        plan["notes"].append(f"시작: 첫 소리 {first:.2f} → start {start:g}" + (f"에서 {new_start:g}로" if new_start != start else " 그대로")
                             + (f" (앞 문장 꼬리 소리 줄임, {FADE_LEN}초 페이드인)" if plan["fade_in"] is not None else ""))
    return plan


def remap(t, keep):
    """원본 시각 t → 빠른 전환으로 이어 붙인 영상의 시각."""
    acc = 0.0
    for a, z in keep:
        if t < a:
            return acc
        if t <= z:
            return acc + (t - a)
        acc += z - a
    return acc


def make_cut(src, keep, punch, work):
    """keep 구간들만 이어 붙인다 (말 사이 쉬는 틈 없애기). punch면 컷마다 살짝 확대/원래 크기를 번갈아."""
    parts, n = [], len(keep)
    vw, vh, _ = probe(src)
    zw, zh = int(vw * 1.08) // 2 * 2, int(vh * 1.08) // 2 * 2
    for i, (a, z) in enumerate(keep):
        zoom = f",scale={zw}:{zh},crop={vw}:{vh}" if punch and i % 2 == 1 else ""
        parts.append(f"[0:v]trim={a:.3f}:{z:.3f},setpts=PTS-STARTPTS{zoom},setsar=1[v{i}]")
        parts.append(f"[0:a]atrim={a:.3f}:{z:.3f},asetpts=PTS-STARTPTS[a{i}]")
    parts.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    out = work / "_cut.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", ";".join(parts),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                    "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def make_video_reel(post, folder, cfg, soft_edges=False):
    """soft_edges: 구간 끝 검사(edge_check)를 오류 대신 경고로만 (예시 폴더용)."""
    v = post["video"]
    src = folder / v["src"]
    fade_in = fade_out = None
    if not v.get("keep") and v.get("avoid_edge_check", True) is not False and v.get("edge_check", True) is not False:
        # 구간 경계를 원본 말소리에 맞춘다 (fit_edges): 끝이 말 중간이면 늘리고, 다음·앞 말 소리는 줄인다
        _, _, vd = probe(src)
        plan = fit_edges(src, float(v.get("start", 0)), float(v.get("end") or vd))
        if plan["errors"] and not soft_edges:
            raise EdgeCutError("\n".join(plan["errors"]))
        for e in plan["errors"]:
            print("경고:", e)
        for line in plan["notes"]:
            print(" ", line)
        v = dict(v, start=plan["start"], end=plan["end"])
        fade_in, fade_out = plan["fade_in"], plan["fade_out"]
    # 손으로 정한 경계(avoid_edge_check: false)에서도 쓰는 소리 페이드 (원본 시각, 선택):
    # video.fade_out = 마지막 소리 끝 + 0.05초 → 그때부터 FADE_LEN초 줄이고 그 뒤 무음 (다음 말 첫소리 막기)
    # video.fade_in  = 첫 소리 - 0.17초 → 그 앞(앞 문장 꼬리)은 무음, 첫 소리 직전 페이드인
    if v.get("fade_out") is not None:
        fade_out = float(v["fade_out"])
        print(f"  끝: 손으로 정한 소리 페이드 {fade_out:g}부터 {FADE_LEN}초, end {float(v['end']):g}")
    if v.get("fade_in") is not None:
        fade_in = float(v["fade_in"])
    work = folder / "_video"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    if v.get("keep"):
        # 빠른 전환: 말 사이 틈을 잘라 이어 붙이고, 자막 시각도 거기에 맞춘다
        keep = [(float(a), float(z)) for a, z in v["keep"]]
        src = make_cut(src, keep, v.get("punch", False), work)
        post = dict(post)
        post["subtitles"] = [dict(s, start=remap(float(s["start"]), keep), end=remap(float(s["end"]), keep))
                             for s in post.get("subtitles", [])]
        v = dict(v, start=0, end=sum(z - a for a, z in keep))
    vw, vh, vdur = probe(src)
    start = float(v.get("start", 0))
    end = float(v.get("end") or vdur)
    dur = end - start
    # 원본에 자막이 박혀 있거나 이름표가 있으면 그 부분을 잘라낸다: "crop": {"top": 0, "bottom": 0.7} (원본 높이 비율)
    crop = ""
    if v.get("crop"):
        t0, t1 = float(v["crop"].get("top", 0)), float(v["crop"].get("bottom", 1))
        ch = int(vh * (t1 - t0)) // 2 * 2
        crop = f"crop={vw}:{ch}:0:{int(vh * t0)},"
        vh = ch
    aspect = vw / vh
    box_h = int(round(min(max(1040 / aspect, 400), 1170) / 2) * 2)
    tall = 1040 / aspect > 1170
    inner_w, inner_h = 1028, box_h - 12  # 테두리 안쪽
    s = min(inner_w / vw, inner_h / vh) if tall else max(inner_w / vw, inner_h / vh)
    scaled_h = vh * s
    geo, subs = place_subs(post, cfg, folder, box_h, work, src, start, dur, (scaled_h, (scaled_h - inner_h) / 2))
    top = geo["top"]
    subs = [(p_, a_, z_, 0) for p_, a_, z_ in subs]
    bg = cfg["brand"]["bg"].replace("#", "0x")

    inputs = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"color=c={bg}:s={W}x{H}:r={FPS}",
              "-ss", f"{start}", "-t", f"{dur:.3f}", "-i", str(src),
              "-i", str(work / "frame.png")]
    # 틀·자막 그림은 한 번만 읽는다 (overlay가 마지막 장면을 유지). -loop 1로 넣으면 1080x1920 PNG를
    # 매 프레임 다시 읽어(자막 13장 x 1,700프레임) 윈도우에서 인코딩이 멈추곤 했다.
    for path, _, _, _ in subs:
        inputs += ["-i", str(path)]
    if tall:  # 세로가 긴 영상은 자르지 않고 양옆을 채운다
        fit = (f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
               f"pad={inner_w}:{inner_h}:(ow-iw)/2:(oh-ih)/2:color={bg}")
    else:
        fit = f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=increase,crop={inner_w}:{inner_h}"
    fc = [f"[1:v]{crop}{fit},setsar=1,fps={FPS}[vid]",
          f"[0:v][vid]overlay=26:{top + 6}[b0]", "[b0][2:v]overlay=0:0[b1]"]
    last = "[b1]"
    for i, (_, a, z, dy) in enumerate(subs):
        a, z = a - start, z - start
        fc.append(f"{last}[{3 + i}:v]overlay=0:{dy}:enable='between(t,{a:.3f},{z:.3f})'[s{i}]")
        last = f"[s{i}]"
    fc.append(f"{last}format=yuv420p[vout]")
    if has_audio(src):
        fades = ""
        if fade_in is not None:   # 앞 문장 꼬리: 그 앞은 무음, 첫 소리 직전 페이드인
            fades += f",afade=t=in:st={max(0.0, fade_in - start):.3f}:d={FADE_LEN}"
        if fade_out is not None:  # 다음 말 첫소리: 마지막 소리 끝 + 0.05초부터 줄이고 그 뒤 무음 (화면은 end까지)
            fades += f",afade=t=out:st={max(0.0, fade_out - start):.3f}:d={FADE_LEN}"
        # 소리는 따로 읽는다: -ss를 -i 앞에 두면 일부 원본에서 소리만 0.1~0.7초 어긋나(입 모양과 안 맞음)
        # 처음부터 읽어 원본 시각 그대로 자른다
        inputs += ["-i", str(src)]
        ai = 3 + len(subs)
        fc.append(f"[{ai}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                  f"aresample=44100,aformat=channel_layouts=stereo{fades}[aout]")
        amap = ["-map", "[aout]"]
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", f"{3 + len(subs)}:a"]
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
                    "-map", "[vout]", *amap, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                    str(out)], check=True)
    cta = dm_cta(post)
    if cta:
        dur = append_cta_card(out, cta, cfg, work, dur)
    # 표지와 미리보기: 1초 지점 화면
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    t = min(1.0, dur / 2)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(out), "-frames:v", "1",
                    "-q:v", "2", str(frames / "01.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    return dur
