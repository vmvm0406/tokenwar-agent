"""GTA 6 릴스 썸네일 (운영자 2026-11-18 "올리자 gta"): 사다리 결과(주인공 얼굴이 출근 칸) 장면 + 제목 "GTA 6 나오는 날 / 나만 출근한다".
바탕 out/th_base_gta6.jpg = out/gta6.mp4 28.8초 정지 화면.
실행: py -3.12 experiments/office/post/make_cover_gta6.py → experiments/office/post/gta6_cover.jpg"""
import asyncio
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
b64 = base64.b64encode((ROOT / "experiments/office/out/th_base_gta6.jpg").read_bytes()).decode()
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:300px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:128px;line-height:1.1;color:#fff}}
h1 span{{display:block;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66}}</style></head>
<body><h1><span>GTA 6 나오는 날</span><span class="g">나만 출근한다</span></h1></body></html>"""


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        ok = await pg.evaluate("document.fonts.check('150px \"Black Han Sans\"')")
        await pg.screenshot(path=str(ROOT / "experiments/office/post/gta6_cover.jpg"), type="jpeg", quality=92)
        await b.close()
        print("font ok", ok)

asyncio.run(main())
