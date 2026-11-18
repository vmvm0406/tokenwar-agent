import asyncio, base64, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
ROOT=Path.cwd()
base=Image.open('experiments/office/out/th_base.jpg').convert('RGB')
reel=Image.open('experiments/office/out/th_reel.jpg').convert('RGB')
pw,ph=330,587
reel=ImageOps.fit(reel,(pw,ph))
phone=Image.new('RGBA',(pw+36,ph+70),(0,0,0,0)); d=ImageDraw.Draw(phone)
d.rounded_rectangle([0,0,pw+35,ph+69],radius=52,fill=(14,15,18,255))
mask=Image.new('L',(pw,ph),0); ImageDraw.Draw(mask).rounded_rectangle([0,0,pw-1,ph-1],radius=38,fill=255)
phone.paste(reel,(18,35),mask)
phone=phone.rotate(-6,expand=True,resample=Image.BICUBIC)
base.paste(phone,(1080-phone.width-30,1240),phone)
base.save('experiments/office/out/th_comp.jpg',quality=95)
b64=base64.b64encode(open('experiments/office/out/th_comp.jpg','rb').read()).decode()
html=f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>body{{margin:0;width:1080px;height:1920px;background:url(data:image/jpeg;base64,{b64}) no-repeat;background-size:cover}}
h1{{position:absolute;top:300px;left:0;right:0;margin:0;text-align:center;font-family:'Black Han Sans';font-weight:400;font-size:170px;line-height:1.08;
color:#fff;-webkit-text-stroke:0;text-shadow:0 0 0 #000;paint-order:stroke fill;}}
h1 span{{display:block}} .g{{color:#00FF66}}
h1 span{{-webkit-text-stroke:16px #000;paint-order:stroke fill}} .name{{position:absolute;left:60px;top:780px;font-family:"Black Han Sans";font-size:84px;color:#fff;-webkit-text-stroke:12px #000;paint-order:stroke fill}} .name:after{{content:"";display:block;height:10px;background:#00FF66;margin-top:6px;border:4px solid #000}}</style></head>
<body><h1><span>실시간</span><span class="g">젠슨황</span></h1><div class="name">젠슨 황</div></body></html>"""
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1080,"height":1920})
        await pg.set_content(html); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(500)
        ok=await pg.evaluate("document.fonts.check('170px \"Black Han Sans\"')")
        await pg.screenshot(path='experiments/office/post/jensen_cover.jpg',type='jpeg',quality=92); await b.close(); print('font ok',ok)
asyncio.run(main())
