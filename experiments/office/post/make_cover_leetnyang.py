"""리트냥이 릴스 썸네일 (운영자 2026-11-18): 끝부분 장면(셋 + 남자가 카메라를 봄, 모니터에 송강호) + 제목 "목요일에 / 말씀드릴게요".
바탕 out/th_base_ln.jpg = leetnyang.json에서 마지막 넓은 컷을 조금 가깝게(dx 0.1, back 0.95)·출처 글자 없이 45.2초 정지 화면.
실행: py -3.12 experiments/office/post/make_cover_leetnyang.py → experiments/office/post/leetnyang_cover.jpg"""
import asyncio
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
b64 = base64.b64encode((ROOT / "experiments/office/out/th_base_ln.jpg").read_bytes()).decode()
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:300px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:150px;line-height:1.1;color:#fff}}
h1 span{{display:block;-webkit-text-stroke:16px #000;paint-order:stroke fill}} .g{{color:#00FF66}}</style></head>
<body><h1><span>목요일에</span><span class="g">말씀드릴게요</span></h1></body></html>"""


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.set_content(html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        ok = await pg.evaluate("document.fonts.check('150px \"Black Han Sans\"')")
        await pg.screenshot(path=str(ROOT / "experiments/office/post/leetnyang_cover.jpg"), type="jpeg", quality=92)
        await b.close()
        print("font ok", ok)

asyncio.run(main())
