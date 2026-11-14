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
UI_SAFE_BOTTOM = 1510  # 이보다 아래는 인스타 버튼·캡션에 가려진다


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
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-SemiBold.otf');font-weight:600}}
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts_uri}/Pretendard-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'JBM';src:url('{fonts_uri}/jetbrains-mono-latin-800-normal.woff2');font-weight:800}}
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent}}
#frame{{width:{W}px;height:{H}px;position:relative;color:{b['text']};font-family:'Pretendard',sans-serif;word-break:keep-all}}
#frame.bg{{background:{b['bg']}}}
.head{{position:absolute;left:60px;right:60px;top:170px;display:flex;flex-direction:column;align-items:center;gap:22px;text-align:center}}
.brand{{font-family:'JBM',monospace;font-weight:800;font-size:40px;letter-spacing:.16em;color:{b['accent']};display:flex;align-items:center;gap:12px}}
.brand i{{display:inline-block;width:13px;height:32px;background:{b['accent']}}}
.title{{margin:6px 0 0;font-size:84px;font-weight:800;line-height:1.24;letter-spacing:-.035em;text-wrap:balance}}
.hl{{color:{b['accent']}}}
.en{{font-size:34px;font-weight:600;color:#9AA59F;letter-spacing:-.005em}}
.box{{position:absolute;left:20px;width:1040px;height:{box_h}px;border:6px solid {b['accent']};border-radius:8px}}
.credit{{position:absolute;left:0;right:0;display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center}}
.credit span{{font-size:24px;font-weight:700;color:#7E8A83;letter-spacing:.2em}}
.credit b{{font-size:34px;font-weight:800;color:{b['accent']};letter-spacing:-.01em}}
.sub{{position:absolute;left:70px;right:70px;text-align:center;font-size:50px;font-weight:800;line-height:1.35;letter-spacing:-.02em;
  color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);white-space:pre-line}}
.sub .hl{{color:{b['accent']}}}
</style></head><body><div id="frame">
<div class="head"><div class="brand"><i></i>TOKEN WAR</div>
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
            if (inside) sub.style.top = (bottom - 230) + 'px'; else sub.style.top = (bottom + credH + 40) + "px";
            const headOver = head.bottom > top - 20;
            return {{top, inside, headOver, titleH: document.querySelector('.title').getBoundingClientRect().height}};
        }}""")
        if geo["headOver"] or geo["titleH"] > 84 * 1.24 * 2.4:
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


def make_video_reel(post, folder, cfg):
    v = post["video"]
    src = folder / v["src"]
    vw, vh, vdur = probe(src)
    start = float(v.get("start", 0))
    end = float(v.get("end") or vdur)
    dur = end - start
    aspect = vw / vh
    box_h = int(round(min(max(1040 / aspect, 400), 1170) / 2) * 2)
    work = folder / "_video"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    geo, subs = asyncio.run(render_layers(post, cfg, folder, box_h, work))
    top = geo["top"]
    inner_w, inner_h = 1028, box_h - 12  # 테두리 안쪽
    bg = cfg["brand"]["bg"].replace("#", "0x")

    inputs = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"color=c={bg}:s={W}x{H}:r={FPS}",
              "-ss", f"{start}", "-t", f"{dur:.3f}", "-i", str(src),
              "-loop", "1", "-t", f"{dur:.3f}", "-i", str(work / "frame.png")]
    for path, _, _ in subs:
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(path)]
    if 1040 / aspect > 1170:  # 세로가 긴 영상은 자르지 않고 양옆을 채운다
        fit = (f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
               f"pad={inner_w}:{inner_h}:(ow-iw)/2:(oh-ih)/2:color={bg}")
    else:
        fit = f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=increase,crop={inner_w}:{inner_h}"
    fc = [f"[1:v]{fit},setsar=1,fps={FPS}[vid]",
          f"[0:v][vid]overlay=26:{top + 6}[b0]", "[b0][2:v]overlay=0:0[b1]"]
    last = "[b1]"
    for i, (_, a, z) in enumerate(subs):
        a, z = a - start, z - start
        fc.append(f"{last}[{3 + i}:v]overlay=0:0:enable='between(t,{a:.3f},{z:.3f})'[s{i}]")
        last = f"[s{i}]"
    fc.append(f"{last}format=yuv420p[vout]")
    if has_audio(src):
        fc.append("[1:a]aresample=44100,aformat=channel_layouts=stereo[aout]")
        amap = ["-map", "[aout]"]
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", f"{3 + len(subs)}:a"]
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
                    "-map", "[vout]", *amap, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                    str(out)], check=True)
    # 표지와 미리보기: 1초 지점 화면
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    t = min(1.0, dur / 2)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(out), "-frames:v", "1",
                    "-q:v", "2", str(frames / "01.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    return dur
