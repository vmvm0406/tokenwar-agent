"""GTA 6 편 모니터 화면 (운영자 2026-11-18 확정 대본 gta6.md): 우리가 그린 화면만 (게임 실제 화면·로고 안 씀).
countdown(출시 카운트다운) / calendar(팀 캘린더, 내일 칸에 연차 다섯) / ladder(사다리 타기 → 주인공 얼굴이 '출근') / shorts(긴 방송 → 쇼츠 3개).
얼굴: out/faces/me.jpg(남자 캐릭터 렌더) + p1~p4_lp.jpg(같은 그림체 다른 생김새, 허깅페이스 Kontext + 면 쪼개기).
실행: py -3.12 experiments/office/post/gta6_screens.py [이름…] → out/clips/gta6_<이름>.mp4 (1920x1080, 15fps)"""
import asyncio
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "office" / "out"
FPS = 15
LEN = {"countdown": 8, "calendar": 6, "ladder": 6.5, "shorts": 6.5}
FACES = ["p1_lp", "p2_lp", "me", "p3_lp", "p4_lp"]   # 사다리·캘린더 순서 (주인공은 가운데)


def uri(p):
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


JS = r"""
const W = 1920, H = 1080, G = '#00FF66', FACES = ['p1_lp', 'p2_lp', 'me', 'p3_lp', 'p4_lp'];
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (u) => { u = cl(u); return u * u * (3 - 2 * u); };
const back = (u) => { u = cl(u); const c = 1.7; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
const cv = document.getElementById('c'), g = cv.getContext('2d');
const face = (k, x, y, r, ring) => {   // 동그란 얼굴
  g.save(); g.beginPath(); g.arc(x, y, r, 0, 7); g.clip(); g.drawImage(IM[k], x - r, y - r, 2 * r, 2 * r); g.restore();
  g.lineWidth = r * 0.08; g.strokeStyle = ring || '#fff'; g.beginPath(); g.arc(x, y, r, 0, 7); g.stroke();
};
const txt = (s, x, y, size, col, font, align) => { g.font = `${size}px ${font || 'Wanted'}`; g.fillStyle = col; g.textAlign = align || 'center'; g.textBaseline = 'middle'; g.fillText(s, x, y); };

const DRAW = {
  countdown(t) {
    g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
    txt('GTA 6 출시까지', W / 2, 250, 96, '#fff');
    const s = 13 * 3600 + 59 * 60 + 58 - Math.floor(t), p = (n) => String(n).padStart(2, '0');
    const pulse = 1 + 0.03 * Math.exp(-(t % 1) * 6);
    g.save(); g.translate(W / 2, 560); g.scale(pulse, pulse);
    txt(`${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}`, 0, 0, 330, G, "'Black Han Sans'"); g.restore();
    txt('11월 19일 출시', W / 2, 860, 64, '#9a9a9a');
  },
  calendar(t) {
    g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    txt('팀 캘린더', 110, 110, 76, '#fff', 'Wanted', 'left'); txt('2026년 11월', 1810, 110, 54, '#9a9a9a', 'Wanted', 'right');
    const days = ['16 월', '17 화', '18 수', '19 목', '20 금'], cw = 340, x0 = 110, y0 = 200;
    days.forEach((d, i) => {
      const x = x0 + i * cw, hot = i === 3;
      g.fillStyle = hot ? '#06210f' : '#141414'; g.fillRect(x + 6, y0, cw - 12, 820);
      if (hot) { g.lineWidth = 8; g.strokeStyle = G; g.strokeRect(x + 6, y0, cw - 12, 820); }
      txt(d, x + cw / 2, y0 + 60, 56, hot ? G : '#ddd');
      if (i === 2) txt('오늘', x + cw / 2, y0 + 120, 40, '#9a9a9a');
      if (hot) txt('내일', x + cw / 2, y0 + 120, 40, G);
    });
    FACES.forEach((k, j) => {   // 내일 칸에 연차가 하나씩 쌓임
      const u = back((t - 0.5 - j * 0.45) / 0.35); if (u <= 0) return;
      const x = x0 + 3 * cw + 24, y = y0 + 180 + j * 124, w = cw - 48;
      g.save(); g.translate(x + w / 2, y + 52); g.scale(u, u); g.translate(-(x + w / 2), -(y + 52));
      g.fillStyle = G; g.fillRect(x, y, w, 104);
      face(k, x + 58, y + 52, 40, '#000'); txt('연차', x + 190, y + 54, 58, '#000');
      g.restore();
    });
  },
  ladder(t) {
    g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
    const n = 5, xs = [...Array(n)].map((_, i) => 260 + i * 350), top = 250, bot = 860;
    const rungs = [[0, 360], [2, 400], [1, 470], [3, 500], [2, 560], [0, 600], [3, 640], [1, 700], [2, 760], [3, 800]];   // [왼쪽 줄, 높이]
    g.lineWidth = 12; g.strokeStyle = '#555'; g.lineCap = 'round';
    xs.forEach((x) => { g.beginPath(); g.moveTo(x, top); g.lineTo(x, bot); g.stroke(); });
    rungs.forEach(([i, y]) => { g.beginPath(); g.moveTo(xs[i], y); g.lineTo(xs[i + 1], y); g.stroke(); });
    // 주인공(가운데 2번) 길 따라가기
    let col = 2, path = [[xs[2], top]];
    for (const [i, y] of [...rungs].sort((a, b) => a[1] - b[1])) {
      if (i === col) { path.push([xs[col], y]); col++; path.push([xs[col], y]); }
      else if (i + 1 === col) { path.push([xs[col], y]); col--; path.push([xs[col], y]); }
    }
    path.push([xs[col], bot]);
    const end = col;
    xs.forEach((x, i) => {   // 아래 칸: 출근 하나, 나머지 연차
      const w = 250, y = 900, isWork = i === end;
      g.fillStyle = isWork ? '#fff' : '#1c1c1c'; g.fillRect(x - w / 2, y, w, 120);
      txt(isWork ? '출근' : '연차', x, y + 62, 70, isWork ? '#000' : '#888', "'Black Han Sans'");
    });
    const L = path.reduce((a, p, i) => a + (i ? Math.hypot(p[0] - path[i - 1][0], p[1] - path[i - 1][1]) : 0), 0);
    let left = L * ease((t - 0.7) / 3.2);
    g.lineWidth = 18; g.strokeStyle = G; g.beginPath(); g.moveTo(...path[0]);
    let tip = path[0];
    for (let i = 1; i < path.length && left > 0; i++) {
      const [ax, ay] = path[i - 1], [bx, by] = path[i], d = Math.hypot(bx - ax, by - ay), u = Math.min(1, left / d);
      tip = [ax + (bx - ax) * u, ay + (by - ay) * u]; g.lineTo(...tip); left -= d;
    }
    g.stroke();
    FACES.forEach((k, i) => face(k, xs[i], 150, 88, i === 2 ? G : '#fff'));
    if (t > 0.7 && t < 4.0) face('me', tip[0], tip[1], 46, G);   // 내려가는 얼굴
    const u = back((t - 4.0) / 0.45);
    if (u > 0) { g.save(); g.translate(xs[end], 790); g.scale(u, u); face('me', 0, 0, 120, G); g.restore(); }   // '출근' 칸에 박힘
  },
  shorts(t) {
    g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
    txt('GTA 6 생방송 다시보기 · 10:00:00', W / 2, 110, 66, '#fff');
    const x0 = 120, x1 = 1800, y = 300, h = 150;
    g.fillStyle = '#161616'; g.fillRect(x0, y, x1 - x0, h);
    for (let k = 0; k < 140; k++) {   // 소리 막대 (방송 길이)
      const v = 0.25 + 0.7 * Math.abs(Math.sin(k * 1.7) * Math.cos(k * 0.37));
      g.fillStyle = '#3a3a3a'; g.fillRect(x0 + 6 + k * 12, y + h / 2 - v * h * 0.42, 7, v * h * 0.84);
    }
    const segs = [[0.18, 0.05], [0.52, 0.05], [0.81, 0.05]];   // 잘라 낼 구간 (가로 비율)
    const scan = cl((t - 0.3) / 2.1);
    segs.forEach(([s, w], i) => {
      const lit = scan > s + w, X = x0 + s * (x1 - x0), Wd = w * (x1 - x0);
      if (!lit) return;
      const fly = ease((t - 2.8 - i * 0.18) / 0.7);
      const cw = 300, ch = 534, cx = W / 2 + (i - 1) * 380 - cw / 2, cy = 470;
      const bx = X + (cx - X) * fly, by = y + (cy - y) * fly, bw = Wd + (cw - Wd) * fly, bh = h + (ch - h) * fly;
      if (fly < 1) { g.fillStyle = 'rgba(0,255,102,0.25)'; g.fillRect(X, y, Wd, h); g.lineWidth = 6; g.strokeStyle = G; g.strokeRect(X, y, Wd, h); }
      if (fly > 0) {
        g.fillStyle = '#121212'; g.fillRect(bx, by, bw, bh); g.lineWidth = 8; g.strokeStyle = G; g.strokeRect(bx, by, bw, bh);
        if (fly >= 1) {
          g.fillStyle = G; g.beginPath(); g.moveTo(cx + cw / 2 - 40, cy + ch / 2 - 55); g.lineTo(cx + cw / 2 + 55, cy + ch / 2); g.lineTo(cx + cw / 2 - 40, cy + ch / 2 + 55); g.fill();
          txt(`쇼츠 ${i + 1}`, cx + cw / 2, cy + 70, 52, '#fff'); txt('0:30', cx + cw / 2, cy + ch - 60, 46, '#9a9a9a');
        }
      } else txt('0:30', X + Wd / 2, y - 36, 40, G);
    });
    if (scan < 1) { const sx = x0 + scan * (x1 - x0); g.fillStyle = '#fff'; g.fillRect(sx - 3, y - 20, 6, h + 40); }
  },
};
window.frame = (name, t) => { DRAW[name](t); return cv.toDataURL('image/jpeg', 0.95); };
"""


async def main(names):
    from playwright.async_api import async_playwright
    fonts = (ROOT / "assets" / "fonts").as_uri()
    imgs = ",".join(f"'{k}':'{uri(OUT / 'faces' / (k + '.jpg'))}'" for k in FACES)
    html = f"""<html><head><meta charset=utf-8><link rel=stylesheet href='{fonts}/black-han-sans/index.css'><style>
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:400}}
body{{margin:0;background:#000}}</style></head><body><canvas id=c width=1920 height=1080></canvas>
<script>const IM={{}};const SRC={{{imgs}}};
window.ready=Promise.all(Object.entries(SRC).map(([k,s])=>{{const im=new Image();im.src=s;IM[k]=im;return im.decode();}}))
.then(()=>Promise.all([document.fonts.load('80px Wanted','가'),document.fonts.load("80px 'Black Han Sans'",'출근연차0123456789:')]));
{JS}</script></body></html>"""
    page = OUT / "gta6_screens.html"
    page.write_text(html, encoding="utf-8")
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
            mp4 = OUT / "clips" / f"gta6_{name}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"),
                            "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(mp4)], check=True)
            shutil.copy(fd / f"{int(LEN[name] * FPS) - 1:04d}.jpg", OUT / f"scr_{name}_last.jpg")
            shutil.rmtree(fd)
            print(mp4)
        await b.close()
    page.unlink()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(LEN)))
