"""3D 대화 릴스 표지 공통 (운영자 2026-11-20 표지 규칙): 흰 글씨 + 검은 테두리, 강조 단어만 초록([대괄호]), 따옴표·마침표 없음.
그리드(3:4로 가운데 잘림)에서 잘리지 않고 오른쪽 위 고정핀·▶ 아이콘에 안 가리게 제목은 y=430부터, 줄마다 너비 860px 안으로 글씨 크기 자동.
실행: py -3.12 experiments/office/post/make_cover.py <out/의 바탕 jpg> <post/에 저장할 이름> "줄1" ["줄2"] [--top 430] [--size 150]
예: make_cover.py th_base_ubi2.jpg ubi_cover3.jpg "[UBI]" "보편적 기본소득" """
import argparse
import asyncio
import base64
import html as H
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def line_html(s, size):
    parts = re.split(r"(\[[^\]]+\])", s)
    inner = "".join(f'<b class="g">{H.escape(p[1:-1])}</b>' if p.startswith("[") else H.escape(p) for p in parts)
    return f'<span style="font-size:{size}px">{inner}</span>'


async def main(a):
    b64 = base64.b64encode((ROOT / "experiments/office/out" / a.base).read_bytes()).decode()
    page = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:{a.top}px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;line-height:1.12;color:#fff}}
h1 span{{display:block;white-space:nowrap;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66;font-weight:400}}</style></head>
<body><h1>{''.join(line_html(s, a.size) for s in a.lines)}</h1></body></html>"""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(page)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        # 줄마다 너비 860px 안으로 (넘으면 그 줄만 글씨를 줄임)
        await pg.evaluate("""() => { for (const s of document.querySelectorAll('h1 span')) { let f = parseFloat(s.style.fontSize);
            const r = document.createRange(); r.selectNodeContents(s);
            while (r.getBoundingClientRect().width > 860 && f > 60) { f -= 4; s.style.fontSize = f + 'px'; } } }""")
        print("font ok", await pg.evaluate("document.fonts.check('150px \"Black Han Sans\"')"))
        await pg.screenshot(path=str(ROOT / "experiments/office/post" / a.out), type="jpeg", quality=92)
        await b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("out"); ap.add_argument("lines", nargs="+")
    ap.add_argument("--top", type=int, default=430); ap.add_argument("--size", type=int, default=150)
    asyncio.run(main(ap.parse_args()))
