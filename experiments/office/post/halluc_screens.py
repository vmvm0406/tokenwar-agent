"""할루시네이션 편 모니터 화면 (운영자 2026-11-19 확정 대본 scripts/halluc.md): 우리가 그린 화면만, 가게 이름은 지어낸 것.
fake(맛집 물었더니 없는 가게를 지어냄 → '없는 가게' 도장) / nomore(그림·노래 가사·이름 짓기에 차례로 X).
실행: py -3.12 experiments/office/post/halluc_screens.py [이름…] → out/clips/halluc_<이름>.mp4 (1920x1080, 15fps)"""
import asyncio
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "office" / "out"
FPS = 15
LEN = {"fake": 20.0, "nomore": 12.0}

JS = r"""
const W = 1920, H = 1080, G = '#00FF66', R = '#ff3b3b';
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const back = (u) => { u = cl(u); const c = 1.7; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
const cv = document.getElementById('c'), g = cv.getContext('2d');
const txt = (s, x, y, size, col, font, align) => { g.font = `${size}px ${font || 'Wanted'}`; g.fillStyle = col; g.textAlign = align || 'center'; g.textBaseline = 'middle'; g.fillText(s, x, y); };
const stamp = (s, x, y, size, col, t0, t) => { if (t < t0) return; const u = back((t - t0) / 0.22), sc = 1 + 1.2 * (1 - cl((t - t0) / 0.15));
  g.save(); g.translate(x, y); g.rotate(-0.12); g.scale(sc * Math.max(0.001, u), sc * Math.max(0.001, u)); g.font = `${size}px 'Black Han Sans'`;
  const w = g.measureText(s).width + 80; g.lineWidth = 16; g.strokeStyle = col; g.strokeRect(-w / 2, -size * 0.78, w, size * 1.56); txt(s, 0, 6, size, col, "'Black Han Sans'"); g.restore(); };
const bubble = (s, right, y, col, tc, t0, t) => { if (t < t0) return; const u = back((t - t0) / 0.3);
  g.save(); g.globalAlpha = Math.min(1, u); g.translate(0, (1 - Math.min(1, u)) * 40);
  g.font = '58px Wanted'; const w = g.measureText(s).width + 80, x = right ? W - 140 - w : 140;
  g.fillStyle = col; g.fillRect(x, y, w, 120); txt(s, x + 40, y + 62, 58, tc, 'Wanted', 'left'); g.restore(); };
const DRAW = {
  fake(t) { g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    g.fillStyle = '#161616'; g.fillRect(0, 0, W, 120); txt('클로드', 960, 62, 50, '#fff', "'Black Han Sans'");
    bubble('우리 동네 맛집 추천해 줘', true, 200, '#2a2a2a', '#fff', 0.0, t);
    const a = '\'토큰 국밥\' 추천해요! 1987년에 문 연 노포예요.';
    if (t > 0.3) { const n = Math.floor(cl((t - 0.3) / 0.7) * a.length);
      g.fillStyle = '#141414'; g.fillRect(140, 380, 1640, 300); g.fillStyle = G; g.fillRect(140, 380, 10, 300);
      txt(a.slice(0, n), 200, 470, 58, '#fff', 'Wanted', 'left');
      if (t > 1.0) txt('별점 4.9 · 리뷰 2,318개', 200, 580, 50, G, 'Wanted', 'left'); }
    if (t > 1.3) { g.fillStyle = '#f2f2f2'; const u = cl((t - 1.3) / 0.2); g.fillRect(140, 760, 1640 * u, 140);
      if (u >= 1) { txt('지도 검색: 토큰 국밥', 200, 830, 52, '#222', 'Wanted', 'left'); if (t > 1.6) txt('검색 결과 없음', 1720, 830, 52, R, 'Wanted', 'right'); } }
    stamp('없는 가게', 1450, 625, 115, R, 2.0, t); },
  nomore(t) { g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    [['그림', 0.35], ['노래 가사', 0.83], ['이름 짓기', 1.45]].forEach(([s, t0], i) => { const x = 340 + i * 620;
      g.fillStyle = '#161616'; g.fillRect(x - 270, 240, 540, 600); g.strokeStyle = t > t0 ? '#3a3a3a' : G; g.lineWidth = 6; g.strokeRect(x - 270, 240, 540, 600);
      txt(s, x, 540, 92, t > t0 ? '#555' : '#fff', "'Black Han Sans'");
      if (t > t0) { const u = back((t - t0) / 0.2); g.save(); g.translate(x, 540); g.scale(u || 0.001, u || 0.001); g.strokeStyle = R; g.lineWidth = 22; g.lineCap = 'round';
        g.beginPath(); g.moveTo(-190, -190); g.lineTo(190, 190); g.moveTo(190, -190); g.lineTo(-190, 190); g.stroke(); g.restore();
        txt(s, x, 540, 92, '#8a8a8a', "'Black Han Sans'"); } });
    if (t > 1.9) txt('창작 기능 꺼짐', 960, 960, 64, R, "'Black Han Sans'"); },
};
window.frame = (name, t) => { DRAW[name](t); return cv.toDataURL('image/jpeg', 0.95); };
"""


async def main(names):
    from playwright.async_api import async_playwright
    fonts = (ROOT / "assets" / "fonts").as_uri()
    html = f"""<html><head><meta charset=utf-8><link rel=stylesheet href='{fonts}/black-han-sans/index.css'><style>
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:400}}
body{{margin:0;background:#000}}</style></head><body><canvas id=c width=1920 height=1080></canvas>
<script>window.ready=Promise.all([document.fonts.load('80px Wanted','가'),document.fonts.load("80px 'Black Han Sans'",'클로드없는가게그림노래가사이름짓기창작기능꺼짐')]);
{JS}</script></body></html>"""
    page = OUT / "halluc_screens.html"
    page.write_text(html, encoding="utf-8")
    (OUT / "clips").mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.goto(page.as_uri())
        await pg.evaluate("window.ready")
        for name in names:
            fd = OUT / f"scr_{name}"
            shutil.rmtree(fd, ignore_errors=True); fd.mkdir()
            for k in range(int(LEN[name] * FPS)):
                d = await pg.evaluate(f"window.frame('{name}', {k / FPS})")
                (fd / f"{k:04d}.jpg").write_bytes(base64.b64decode(d.split(",", 1)[1]))
            mp4 = OUT / "clips" / f"halluc_{name}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"),
                            "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(mp4)], check=True)
            shutil.copy(fd / f"{int((LEN[name] - 0.1) * FPS):04d}.jpg", OUT / f"scr_{name}_end.jpg")   # 확인용 마지막 장면
            shutil.rmtree(fd)
            print(mp4)
        await b.close()
    page.unlink()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(LEN)))
