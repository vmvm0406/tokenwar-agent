"""릴스 썸네일(cover.jpg) 만들기. 1080x1920.

post.json의 "thumb":
    {
      "title": "AI 피싱 시대,\n2중 보안은 필수다",   # 2줄, 줄당 12자 안팎
      "highlight": "2중 보안",                      # 녹색 강조 (선택)
      "person": {"name": "Jensen Huang", "desc": "엔비디아 전 CEO"},  # 사진 속 인물 표기 (선택)
      "image": {"type": "image", "src": "img/thumb.jpg",
                "url": "https://... 실물 이미지 주소",       # 1순위: 실물 이미지 (Actions가 내려받음)
                "prompt": "a giant glowing padlock ..."}     # 2순위: 실물이 없을 때 AI로 만듦
    }

배치: 그림이 화면을 빈칸 없이 꽉 채우고 (위아래 검은 띠가 있는 그림은 검사에서 막는다), 아래가 어두워지며 가운데 정렬 제목 2줄.
프로필 격자에서는 가운데 3:4(위아래 240px씩 잘림)만 보인다. 릴스 화면에서는 아래쪽이 캡션·버튼에 가리므로
제목·인물 표기·TOKEN WAR는 인스타 안전 영역(config.json reel_safe, 세로 285~1250px) 안에 둔다.
"""
import asyncio
import shutil
from pathlib import Path

from checks import CONFIG
from render import FONTS, br, esc, hl

B = CONFIG["brand"]
W, H = 1080, 1920
SAFE = CONFIG.get("reel_safe", {"top": 285, "bottom": 1250})
BOT = H - SAFE["bottom"]            # 안전 영역 아래 끝에서 화면 바닥까지 (670px)


def page(post, folder):
    t = post["thumb"]
    img = (folder / t["image"]["src"]).resolve()
    if not img.exists():
        raise FileNotFoundError(f"썸네일 그림 없음: {t['image']['src']}")
    pos = t["image"].get("position", "center 30%")
    person = ""
    if t.get("person"):
        p = t["person"]
        person = (f'<div class="person"><b>{esc(p["name"])}</b>'
                  f'{"<span>" + esc(p["desc"]) + "</span>" if p.get("desc") else ""}</div>')
    sub = f'<p class="sub">{esc(t["sub"])}</p>' if t.get("sub") else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@import url('{FONTS}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{FONTS}/WantedSans-SemiBold.otf');font-weight:600}}
@font-face{{font-family:'Wanted';src:url('{FONTS}/WantedSans-Bold.otf');font-weight:700}}
*{{box-sizing:border-box}} html,body{{margin:0;background:#000}}
#t{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:#000;color:#fff;
  font-family:'Wanted',sans-serif;word-break:keep-all}}
#t img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:{pos}}}
.shade{{position:absolute;left:0;right:0;bottom:0;height:60%;
  background:linear-gradient(to bottom,rgba(0,0,0,0) 0%,rgba(0,0,0,.5) 35%,rgba(0,0,0,.78) 70%,rgba(0,0,0,.85) 100%)}}
.txt{{position:absolute;left:60px;right:60px;bottom:{BOT + 60}px;text-align:center}}
.person{{position:absolute;left:60px;bottom:{BOT + 330}px;text-align:left;font-size:30px;line-height:1.3;
  text-shadow:0 2px 10px rgba(0,0,0,.8)}}
.person b{{display:block;font-weight:700}} .person span{{opacity:.75;font-weight:600}}
h1{{margin:0;font-family:'Black Han Sans';font-weight:400;font-size:96px;line-height:1.18;letter-spacing:-.01em;
  text-shadow:0 3px 18px rgba(0,0,0,.6)}}
.hl{{color:{B['accent']}}}
.sub{{margin:26px 0 0;font-size:34px;font-weight:600;color:#cfd6d2}}
.brand{{position:absolute;left:0;right:0;bottom:{BOT + 8}px;text-align:center;font-family:'Black Han Sans';
  font-size:32px;color:{B['accent']};letter-spacing:.02em}}
</style></head><body><div id="t"><img src="{img.as_uri()}"><div class="shade"></div>{person}
<div class="txt"><h1>{br(hl(t['title'], t.get('highlight')))}</h1>{sub}</div>
<div class="brand">TOKEN WAR</div></div></body></html>"""


async def _shoot(html_text, folder, out):
    from playwright.async_api import async_playwright
    tmp = folder / "_thumb.html"
    tmp.write_text(html_text, encoding="utf-8")
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(tmp.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(300)
        info = await pg.evaluate("""() => { const h = document.querySelector('h1');
            const lh = parseFloat(getComputedStyle(h).lineHeight);
            const r = h.getBoundingClientRect();
            const b = document.querySelector('.brand').getBoundingClientRect();
            return {lines: Math.round(r.height / lh), top: r.top, wide: h.scrollWidth > h.clientWidth + 2,
                    bottom: b.bottom}; }""")
        problems = []
        if info["lines"] > 2:
            problems.append(f"썸네일 제목이 {info['lines']}줄 (2줄까지)")
        if info["top"] < SAFE["top"] or info["bottom"] > SAFE["bottom"] + 2:
            problems.append(f"썸네일 글자가 안전 영역({SAFE['top']}~{SAFE['bottom']}px) 밖")
        if info["wide"]:
            problems.append("썸네일 제목이 가로로 넘침")
        if not problems:
            await (await pg.query_selector("#t")).screenshot(path=str(out), type="jpeg", quality=92)
        await browser.close()
    tmp.unlink()
    return problems


def letterbox(path):
    """그림 위나 아래에 검은 띠(빈칸)가 있는지. 영상 화면을 줄여 넣은 그림에서 자주 생긴다."""
    from PIL import Image, ImageStat
    im = Image.open(path).convert("L")
    w, h = im.size
    band = max(8, h // 12)
    out = []
    for name, box in (("위", (0, 0, w, band)), ("아래", (0, h - band, w, h))):
        st = ImageStat.Stat(im.crop(box))
        if st.mean[0] < 20 and st.stddev[0] < 0.6:  # 영상 여백(완전히 고른 검정)만. 검은 옷은 조금이라도 결이 있다
            out.append(name)
    return out


def make_thumb(post, folder):
    """썸네일을 cover.jpg로 저장. 문제가 있으면 문제 목록을 돌려준다."""
    folder = Path(folder).resolve()
    src = folder / post["thumb"]["image"]["src"]
    if src.exists():
        bands = letterbox(src)
        if bands:
            return [f"썸네일 그림 {'·'.join(bands)}쪽에 검은 빈칸이 있음 → 인물·상징이 화면을 꽉 채우게 9:16으로 잘라 다시 만들 것 "
                    "(영상 장면이면 ffmpeg crop으로 인물 쪽을 세로로 잘라 1080x1920)"]
    return asyncio.run(_shoot(page(post, folder), folder, folder / "cover.jpg"))
