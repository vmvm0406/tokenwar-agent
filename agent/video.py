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


def page_html(post, cfg, box_h, fonts_uri):
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
.sub{{position:absolute;left:70px;right:70px;text-align:center;font-size:50px;font-weight:800;line-height:1.35;letter-spacing:-.02em;
  color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);white-space:pre-line}}
.sub .hl{{color:{b['accent']}}}
</style></head><body><div id="frame">
<div class="head"><div class="brand">TOKEN WAR</div>
<h1 class="title">{hl(post['title'], post.get('highlight'))}</h1>
<div class="en">{esc(post.get('title_en', ''))}</div></div>
<div class="box" id="box"></div>{credit_html}
<div class="sub" id="sub"></div>
</div></body></html>"""


async def render_layers(post, cfg, folder, box_h, work):
    """틀(PNG), 자막(PNG 여러 장), 미리보기용 배경을 만든다. 영상 창 위치를 돌려준다."""
    from playwright.async_api import async_playwright

    fonts_uri = (ROOT / "assets" / "fonts").as_uri()
    tmp = work / "frame.html"
    tmp.write_text(page_html(post, cfg, box_h, fonts_uri), encoding="utf-8")
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
            if (inside && capAt > 0) {{
              // 원본에 박힌 자막 바로 위에 우리 자막을 둔다 (자막 아래쪽 끝 기준)
              sub.style.top = 'auto';
              sub.style.bottom = ({H} - (top + 6 + capAt * ({box_h} - 12) - 14)) + 'px';
            }} else if (inside) sub.style.top = (bottom - 230) + 'px'; else sub.style.top = (bottom + credH + 40) + "px";
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
MAX_SHIFT = 60          # 우리 자막을 이만큼(px)까지만 위로 옮겨 피한다. 더 옮기면 얼굴을 덮을 수 있어 뒤에 띠를 깐다
BAR_ALPHA = 0.97        # 원본 글자를 가리는 띠의 불투명도 (브랜드 배경색)


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


def avoid_burned(post, src, start, dur, subs, geo, box_h, scale_info, bg_hex):
    """우리 자막이 원본에 박힌 글자와 겹치면 위로 조금 옮기거나(MAX_SHIFT 이하), 뒤에 띠를 깔아 원본 글자를 가린다.
    subs: [(png, a, z)] → [(png, a, z, dy)]. 결정 내용을 출력한다."""
    from PIL import Image, ImageDraw
    v = post.get("video") or {}
    if v.get("captions_at") or v.get("avoid_burned") is False or not geo.get("inside"):
        return [(p, a, z, 0) for p, a, z in subs]
    crop = (float(v["crop"].get("top", 0)), float(v["crop"].get("bottom", 1))) if v.get("crop") else None
    times, frames = sample_gray(src, start, dur, crop)
    box_top = geo["top"] + 6
    scaled_h, off_y = scale_info            # 영상 창 안에서 원본 높이(px)와 위쪽 잘린 양(px, 음수면 여백)

    def to_px(fr):
        return box_top + fr * scaled_h - off_y

    out = []
    for i, (path, a, z) in enumerate(subs):
        rows = alpha_rows(path)
        if not rows:
            out.append((path, a, z, 0))
            continue
        y0, y1 = rows
        bands = []
        for tt, fr in zip(times, frames):
            if a - 0.25 <= tt <= z + 0.25:
                bands += [(to_px(b0), to_px(b1)) for b0, b1 in text_bands(fr)]
        hit = [b for b in bands if b[1] > y0 - 10 and b[0] < y1 + 10]
        if not hit:
            out.append((path, a, z, 0))
            continue
        dy = int(min(b[0] for b in hit) - 12 - y1)
        moved = (y0 + dy, y1 + dy)
        clear = all(not (b[1] > moved[0] - 10 and b[0] < moved[1] + 10) for b in bands)
        if -MAX_SHIFT <= dy < 0 and clear and moved[0] >= box_top:
            print(f"  자막 {i + 1}: 원본 글자를 피해 {-dy}px 위로")
            out.append((path, a, z, dy))
            continue
        # 많이 옮겨야 하면 얼굴을 덮을 수 있다 → 제자리에서 뒤에 띠를 깔아 원본 글자를 가린다
        top = int(min([y0] + [b[0] for b in hit]) - 14)
        bot = int(max([y1] + [b[1] for b in hit]) + 14)
        top, bot = max(top, box_top), min(bot, box_top + box_h - 12)
        im = Image.open(path).convert("RGBA")
        bar = Image.new("RGBA", im.size, (0, 0, 0, 0))
        r, g, b_ = (int(bg_hex[k:k + 2], 16) for k in (1, 3, 5))
        ImageDraw.Draw(bar).rectangle([26, top, 26 + 1028 - 1, bot], fill=(r, g, b_, int(255 * BAR_ALPHA)))
        Image.alpha_composite(bar, im).save(path)
        print(f"  자막 {i + 1}: 원본 글자와 겹쳐 뒤에 띠를 깖 ({top}~{bot}px)")
        out.append((path, a, z, 0))
    return out


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


def make_video_reel(post, folder, cfg):
    v = post["video"]
    src = folder / v["src"]
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
    geo, subs = asyncio.run(render_layers(post, cfg, folder, box_h, work))
    top = geo["top"]
    inner_w, inner_h = 1028, box_h - 12  # 테두리 안쪽
    tall = 1040 / aspect > 1170
    s = min(inner_w / vw, inner_h / vh) if tall else max(inner_w / vw, inner_h / vh)
    scaled_h = vh * s
    subs = avoid_burned(post, src, start, dur, subs, geo, box_h, (scaled_h, (scaled_h - inner_h) / 2), cfg["brand"]["bg"])
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
        fc.append("[1:a]aresample=44100,aformat=channel_layouts=stereo[aout]")
        amap = ["-map", "[aout]"]
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", f"{3 + len(subs)}:a"]
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
                    "-map", "[vout]", *amap, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                    str(out)], check=True)
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
