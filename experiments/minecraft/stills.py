"""장면 시안: 에피소드 장면마다 한 장씩 → 한 장짜리 모아 보기.
py -3.12 experiments/minecraft/stills.py experiments/minecraft/episodes/sponge.json <출력 폴더> [--at 0.75]"""
import argparse, functools, http.server, json, threading
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("out"); ap.add_argument("--at", type=float, default=0.75)
    a = ap.parse_args()
    ep = json.loads(Path(a.episode).read_text(encoding="utf-8"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for s in ep["scenes"]:
        s["d"] = 3.0
    srv = serve()
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(f"http://127.0.0.1:{srv.server_port}/scene.html")
        pg.evaluate("window.ready")
        pg.evaluate("ep => { window.EP = ep; }", ep)
        for i, s in enumerate(ep["scenes"]):
            pg.evaluate("([i, t, d, sub]) => renderAt(i, t, d, sub)", [i, s["d"] * a.at, s["d"], s["lines"][0][0]])
            f = out / f"{i:02d}_{s['scene']}.png"
            pg.locator("#c").screenshot(path=str(f))
            shots.append(f)
        b.close()
    srv.shutdown()
    cols, tw = 6, 270
    th = tw * 1920 // 1080
    rows = -(-len(shots) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th), "black")
    for k, f in enumerate(shots):
        sheet.paste(Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS), ((k % cols) * tw, (k // cols) * th))
    sheet.save(out / "sheet.jpg", quality=88)
    print(out / "sheet.jpg")


if __name__ == "__main__":
    main()
