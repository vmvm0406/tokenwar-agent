"""표지 한 장: py -3.12 experiments/minecraft/cover.py <제목> <블록 키(sp3 등)> <출력.jpg> [제목 색 #rrggbb] [제목 크기 px]"""
import functools, http.server, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).resolve().parent
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE)); h.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
title, block, out = sys.argv[1:4]
color = sys.argv[4] if len(sys.argv) > 4 else None
size = int(sys.argv[5]) if len(sys.argv) > 5 else None
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto(f"http://127.0.0.1:{srv.server_port}/scene.html"); pg.evaluate("window.ready")
    pg.evaluate("([t, k, c, z]) => { window.EP = {title: t, coverBlock: k, coverColor: c, coverSize: z, scenes: [{scene: 'cover'}]}; renderAt(0, 0, 1, ''); }", [title, block, color, size])
    png = Path(out).with_suffix(".png"); pg.locator("#c").screenshot(path=str(png)); b.close()
from PIL import Image
Image.open(png).convert("RGB").save(out, quality=92); png.unlink(); print(out)
