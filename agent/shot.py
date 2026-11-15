"""웹페이지 화면 캡처 → 카드뉴스용 JPEG.

다른 AI 정보 계정처럼 본문 장 위쪽에 '실제 화면'(서비스 화면, 공식 발표 페이지, 논문 그림, X 게시물)을 넣을 때 쓴다.

사용법 (명령줄):
    py -3.12 agent/shot.py <주소> <저장할 파일.jpg> [--selector "CSS 선택자"] [--width 1280] [--height 1000]
                           [--scroll 600] [--wait 2500] [--dark]
post.json에서 (gen_images.py가 파일이 없을 때 자동으로 찍는다):
    {"type": "image", "src": "img/02.jpg", "credit": "Lovable 공식 문서",
     "shot": {"url": "https://...", "selector": "article", "scroll": 0, "width": 1280, "height": 1000}}

- selector가 있으면 그 요소만 찍는다(본문, 그림, 표). 없으면 화면(viewport) 그대로.
- 쿠키 동의창·고정 머리말은 숨긴다. 로그인이 필요한 페이지나 봇을 막는 사이트는 실패할 수 있다 → 다른 출처를 찾는다.
- 찍은 뒤에는 꼭 이미지를 열어 보고, 알아볼 수 있는지·광고나 팝업이 가리지 않는지 확인한다.
"""
import argparse
import sys
from pathlib import Path

HIDE_CSS = """
[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],
[id*="onetrust" i],[class*="onetrust" i],[aria-label*="cookie" i],
[class*="newsletter" i][class*="popup" i],[class*="modal" i][class*="signup" i]{display:none!important}
html{scroll-behavior:auto!important}
"""


def capture(url, out, selector=None, width=1280, height=1000, scroll=0, wait=2500, dark=False):
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".shot.png")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=2,
                            color_scheme="dark" if dark else "light", locale="en-US",
                            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"))
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.add_style_tag(content=HIDE_CSS)
        # 화면 위에 붙는 고정 머리말은 캡처를 가리므로 숨긴다
        page.evaluate("""() => { for (const el of document.querySelectorAll('body *')) {
            const s = getComputedStyle(el);
            if ((s.position === 'fixed' || s.position === 'sticky') && el.getBoundingClientRect().height < 220)
                el.style.setProperty('display', 'none', 'important'); } }""")
        page.wait_for_timeout(wait)
        if selector:
            el = page.locator(selector).first
            el.scroll_into_view_if_needed(timeout=10000)
            el.screenshot(path=str(png))
        else:
            if scroll:
                page.evaluate(f"window.scrollTo(0, {int(scroll)})")
                page.wait_for_timeout(600)
            page.screenshot(path=str(png))
        b.close()
    from PIL import Image
    img = Image.open(png).convert("RGB")
    if max(img.size) > 2400:
        img.thumbnail((2400, 2400))
    img.save(out, "JPEG", quality=90)
    png.unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--selector")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--scroll", type=int, default=0)
    ap.add_argument("--wait", type=int, default=2500)
    ap.add_argument("--dark", action="store_true")
    a = ap.parse_args()
    out = capture(a.url, a.out, a.selector, a.width, a.height, a.scroll, a.wait, a.dark)
    print(f"저장: {out}")


if __name__ == "__main__":
    sys.exit(main())
