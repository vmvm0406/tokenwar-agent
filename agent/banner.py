"""참여형 '자료' 릴스의 앞쪽 안내 띠 (dm.banner, 선택, 운영자 결정 2026-11-16).

평균 시청 비율이 12%라 대부분이 끝 화면(dm.cta)까지 보지 않는다. 그래서 3초에 작은 띠가 나타나
본편이 끝날 때까지 남는다. 끝 화면(dm.cta)은 따로 그대로 붙는다 (띠는 끝 화면 위에는 없다).

- 모양: 검정 띠(살짝 비침) + 왼쪽 형광 초록 막대, 흰 글씨, 따옴표 안('자료')은 초록. 모서리 각짐 (STYLE_GUIDE 1-1).
- 자리: 영상 릴스(video.py)는 영상 창 위쪽 테두리 안쪽(자막은 바닥이라 반대쪽),
        카드형 모션 릴스(motion.py)는 안전 영역 맨 위(세로 285px부터, 본문은 그만큼 아래로 밀림, render.py).
- dm.banner가 없으면 아무것도 하지 않는다 (예전과 같음).
"""
import html as _html
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
BANNER_START = 3.0   # 첫 3~5초 안에 나타난다
BANNER_FADE = 0.3
BANNER_H = 64        # 한 줄 띠 높이(px). motion은 본문을 띠 높이 + 여백만큼 아래로 민다
BANNER_LINE = 40     # 줄이 늘 때마다 더하는 높이(px). 두 줄 띠는 104px
BANNER_GAP = 20


def banner_height(text):
    """띠 높이: 한 줄 64px, 두 줄 104px (dm.banner는 두 줄까지)."""
    n = max(1, len([l for l in (text or "").splitlines() if l.strip()]))
    return BANNER_H + BANNER_LINE * (n - 1)


def cta_line(post):
    """0초부터 제목 띠 바로 아래에 남는 한 줄 안내 (목록형·순위 릴스, 운영자 결정 2026-11-17: 제목만 있는 첫 화면에서
    3초 안 건너뛰기 69% → 첫 화면부터 내용 + 안내). dm.cta가 있을 때만. list/rank.cta_line: 문자열이면 그대로, false면 없음.
    기본 "댓글 달고 {list.topic} 모음집 받아가세요" (운영자 결정 2026-11-17, topic 없으면 "댓글 달고 전체 N개 모음집 받아가세요"). 이 줄이 있으면 3초 '자료' 띠(dm.banner)는 붙이지 않는다."""
    d = post.get("dm") or {}
    sec = post.get("list") or post.get("rank") or {}
    v = sec.get("cta_line")
    if v is False or sec.get("intro") is True:
        return None
    if isinstance(v, str) and v.strip():
        return v.strip()          # dm 없이도 됨: 소식·이야기 릴스의 양자택일 질문·팔로우 한 줄 (STYLE_GUIDE 0 원칙 8)
    if not d.get("cta"):
        return None
    topic = (sec.get("topic") or "").strip()
    if topic:
        return f"댓글 달고 {topic} 모음집 받아가세요"
    n = len(sec.get("items") or []) + len((d.get("page") or {}).get("more") or [])
    return f"댓글 달고 전체 {n}개 모음집 받아가세요"


def banner_text(post):
    d = post.get("dm") or {}
    return (d.get("banner") or "").strip() or None


def banner_html(text, cfg, width):
    b = cfg["brand"]
    h = banner_height(text)
    fonts_uri = (ROOT / "assets" / "fonts").as_uri()
    body = "<br>".join(_html.escape(l.strip()) for l in text.splitlines() if l.strip())
    body = re.sub(r"(?:'|&#x27;|‘)(.+?)(?:'|&#x27;|’)", lambda m: f"<span class=\"hl\">'{m.group(1)}'</span>", body)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@font-face{{font-family:'Wanted';src:url('{fonts_uri}/WantedSans-ExtraBold.otf');font-weight:800}}
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent}}
#b{{width:{width}px;height:{h}px;display:flex;align-items:center;gap:18px;padding:0 24px 0 0;
  background:rgba(10,11,10,.86);border-left:10px solid {b['accent']};border-radius:0;
  font-family:'Wanted',sans-serif;font-weight:800;font-size:31px;letter-spacing:-.01em;color:#fff;line-height:1.3;white-space:nowrap;overflow:hidden}}
#b .t{{padding-left:18px}}
.hl{{color:{b['accent']}}}
</style></head><body><div id="b"><span class="t">{body}</span></div></body></html>"""


async def make_banner_png_async(text, cfg, width, out_png):
    """띠 그림(투명 배경 PNG, width x banner_height(text)). 글이 띠보다 길면 ValueError. (motion.py처럼 이미 async 안에서 부를 때)"""
    from playwright.async_api import async_playwright

    out_png = Path(out_png)
    page_file = out_png.with_suffix(".html")
    page_file.write_text(banner_html(text, cfg, width), encoding="utf-8")
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": width, "height": banner_height(text)})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        over = await pg.evaluate("() => { const b = document.getElementById('b'); return b.scrollWidth > b.clientWidth + 1; }")
        await (await pg.query_selector("#b")).screenshot(path=str(out_png), omit_background=True)
        await browser.close()
    page_file.unlink()
    if over:
        raise ValueError(f"dm.banner 글이 띠({width}px)보다 김 → 줄일 것: {text}")
    return out_png


def make_banner_png(text, cfg, width, out_png):
    """make_banner_png_async의 동기 판 (video.py)."""
    import asyncio
    return asyncio.run(make_banner_png_async(text, cfg, width, out_png))


def apply_banner(mp4, png, x, y, end, start=BANNER_START):
    """다 만든 mp4에 띠를 start초부터 end초까지 얹는다 (0.3초 페이드인). 소리는 그대로."""
    mp4 = Path(mp4)
    tmp = mp4.with_name(mp4.stem + "_banner.mp4")
    end = max(start + 0.5, float(end))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(mp4),
                    "-loop", "1", "-framerate", str(FPS), "-t", f"{end:.3f}", "-i", str(png),
                    "-filter_complex",
                    f"[1:v]format=rgba,fade=t=in:st={start:.3f}:d={BANNER_FADE}:alpha=1[bn];"
                    f"[0:v][bn]overlay={int(x)}:{int(y)}:enable='between(t,{start:.3f},{end:.3f})':eof_action=pass,format=yuv420p[v]",
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                    "-c:a", "copy", "-movflags", "+faststart", str(tmp)], check=True)
    shutil.move(str(tmp), str(mp4))
    print(f"안내 띠: {start:g}~{end:.1f}초, x={int(x)} y={int(y)}")
