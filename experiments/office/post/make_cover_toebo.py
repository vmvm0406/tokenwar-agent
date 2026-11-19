"""퇴보 vs 퇴화 편 썸네일 (운영자 2026-11-19 "썸네일은 AI 안 쓰면 퇴보, AI 쓰면 퇴화"): 시험장에서 모두 쳐다보는 장면(44.1초).
out/th_base_toebo.jpg = out/toebo.mp4 44.1초. 실행: py -3.12 experiments/office/post/make_cover_toebo.py"""
import asyncio
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
b64 = base64.b64encode((ROOT / "experiments/office/out/th_base_toebo.jpg").read_bytes()).decode()
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:310px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:150px;line-height:1.1;color:#fff}}
h1 span{{display:block;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66}}</style></head>
<body><h1><span style="font-size:132px">AI 안 쓰면 <b class="g" style="font-weight:400">퇴보</b></span><span style="font-size:132px">AI 쓰면 <b class="g" style="font-weight:400">퇴화</b></span></h1></body></html>"""


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        ok = await pg.evaluate("document.fonts.check('150px \"Black Han Sans\"')")
        await pg.screenshot(path=str(ROOT / "experiments/office/post/toebo_cover.jpg"), type="jpeg", quality=92)
        await b.close()
        print("font ok", ok)

asyncio.run(main())
