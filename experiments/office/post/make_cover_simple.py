"""3D 대화 릴스 썸네일 (운영자 2026-11-19): 바탕 장면(정지 화면 1080x1920) + 위쪽 제목 두 줄(흰색 / 초록, 검은고딕, 검은 테두리).
실행: py -3.12 experiments/office/post/make_cover_simple.py <바탕.jpg> <첫 줄> <둘째 줄> <결과.jpg>
바탕은 render.py --stills로 자막·출처 없이 뽑은 장면 (리트냥이 편과 같은 방식)."""
import asyncio
import base64
import sys
from pathlib import Path

base, l1, l2, out = sys.argv[1:5]
b64 = base64.b64encode(Path(base).read_bytes()).decode()
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:300px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:150px;line-height:1.1;color:#fff}}
h1 span{{display:block;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66}}</style></head>
<body><h1><span>{l1}</span><span class="g">{l2}</span></h1></body></html>"""


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=out, type="jpeg", quality=92)
        await b.close()

asyncio.run(main())
print(out)
