"""2판(돈 모으는 클로드, 운영자 2026-11-19): py -3.12 experiments/office/post/make_cover_ubi.py th_base_ubi2.jpg ubi_cover2.jpg (base = scripts/ubi_cover.json 2.4초 still)
기본소득 편 썸네일 (2026-11-19): 끝 장면(쉬지 않고 일하는 클로드 옆 멍한 남자, 19.15초) + 제목 '클로드, "돈 벌어와."' (운영자 2026-11-19).
out/th_base_ubi.jpg = out/ubi.mp4 19.15초. 실행: py -3.12 experiments/office/post/make_cover_ubi.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
b64 = base64.b64encode((ROOT / "experiments/office/out" / (sys.argv[1] if len(sys.argv) > 1 else "th_base_ubi.jpg")).read_bytes()).decode()
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:310px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:150px;line-height:1.1;color:#fff}}
h1 span{{display:block;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66}}</style></head>
<body><h1><span style="font-size:150px">클로드,</span><span style="font-size:150px"><b class="g" style="font-weight:400">“돈 벌어와.”</b></span></h1></body></html>"""


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        ok = await pg.evaluate("document.fonts.check('150px \"Black Han Sans\"')")
        await pg.screenshot(path=str(ROOT / "experiments/office/post" / (sys.argv[2] if len(sys.argv) > 2 else "ubi_cover.jpg")), type="jpeg", quality=92)
        await b.close()
        print("font ok", ok)

asyncio.run(main())
