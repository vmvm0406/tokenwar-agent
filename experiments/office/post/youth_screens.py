"""신입 자리 편 모니터 화면 (운영자 2026-11-19 확정 대본 youth_newbie.md): 우리가 그린 화면만, 회사 이름은 지어낸 것.
inbox(불합격 메일 5→6) / posting(신입 공고, '경력 2년 이상' 강조) / stamp(신입 업무에 'AI 처리' 도장) / docs(사람들이 쓴 글이 클로드로 흘러가다 끊김).
실행: py -3.12 experiments/office/post/youth_screens.py [이름…] → out/clips/youth_<이름>.mp4 (1920x1080, 15fps)"""
import asyncio
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "office" / "out"
FPS = 15
LEN = {"inbox": 5, "posting": 7, "stamp": 6}
DOCS_STOP = 5.0   # docs: 이 시각부터 글이 더 안 들어옴 (클로드 '사람이 일을 못 배우면')

JS = r"""
const W = 1920, H = 1080, G = '#00FF66', STOP = %STOP%;
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (u) => { u = cl(u); return u * u * (3 - 2 * u); };
const back = (u) => { u = cl(u); const c = 1.7; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
const cv = document.getElementById('c'), g = cv.getContext('2d');
const txt = (s, x, y, size, col, font, align) => { g.font = `${size}px ${font || 'Wanted'}`; g.fillStyle = col; g.textAlign = align || 'center'; g.textBaseline = 'middle'; g.fillText(s, x, y); };
const rnd = (k) => { const x = Math.sin(k * 127.1) * 43758.5453; return x - Math.floor(x); };

const DRAW = {
  inbox(t) {
    g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    txt('받은편지함', 110, 110, 76, '#fff', 'Wanted', 'left');
    const NEW = 0.35, n = t >= NEW ? 6 : 5, pop = 1 + 0.25 * Math.exp(-Math.max(0, t - NEW) * 6) * (t >= NEW ? 1 : 0);
    g.save(); g.translate(1640, 110); g.scale(pop, pop);
    txt('불합격', -40, 0, 54, '#9a9a9a', 'Wanted', 'right'); txt(String(n), 70, 0, 120, G, "'Black Han Sans'"); g.restore();
    const co = ['한빛상사', '누리테크', '다온물산', '새봄전자', '바른유통', '가람에너지'];
    const rows = co.slice(0, 5).map((c, i) => ({ c, d: `11월 ${18 - i}일` }));
    const u = ease((t - NEW) / 0.45);
    if (t >= NEW) rows.unshift({ c: co[5], d: '방금', hot: true });
    rows.forEach((r, i) => {
      const y = 230 + (i - (t >= NEW ? 1 - u : 0)) * 140;
      if (r.hot && u <= 0) return;
      g.globalAlpha = r.hot ? u : 1;
      g.fillStyle = r.hot ? '#06210f' : '#141414'; g.fillRect(110, y, 1700, 120);
      if (r.hot) { g.lineWidth = 6; g.strokeStyle = G; g.strokeRect(110, y, 1700, 120); }
      txt(`${r.c} 채용팀`, 160, y + 42, 44, r.hot ? '#fff' : '#bbb', 'Wanted', 'left');
      txt('[서류 전형 결과] 지원해 주셔서 감사합니다. 아쉽게도…', 160, y + 88, 36, r.hot ? G : '#777', 'Wanted', 'left');
      txt(r.d, 1770, y + 42, 36, '#777', 'Wanted', 'right');
      g.globalAlpha = 1;
    });
  },
  posting(t) {
    g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    txt('채용 공고 검색: 신입', 110, 100, 52, '#9a9a9a', 'Wanted', 'left');
    g.fillStyle = '#141414'; g.fillRect(110, 170, 1700, 820);
    txt('[신입] 사무직 채용', 180, 260, 84, '#fff', 'Wanted', 'left');
    txt('누리테크 · 서울 · 정규직', 180, 350, 44, '#9a9a9a', 'Wanted', 'left');
    const rows = [['모집 부문', '사무 지원 (신입)'], ['담당 업무', '회의록 정리, 자료 조사, 엑셀 정리'], ['자격 요건', '경력 2년 이상']];
    rows.forEach(([k, v], i) => { txt(k, 180, 500 + i * 140, 48, '#777', 'Wanted', 'left'); txt(v, 520, 500 + i * 140, 56, '#fff', 'Wanted', 'left'); });
    const u = ease((t - 2.4) / 0.5);   // '경력 2년 이상' 강조
    if (u > 0) {
      g.font = '56px Wanted'; const w = g.measureText('경력 2년 이상').width;
      g.fillStyle = G; g.fillRect(500, 780 - 46, (w + 40) * u, 92);
      g.save(); g.beginPath(); g.rect(500, 0, (w + 40) * u, H); g.clip(); txt('경력 2년 이상', 520, 780, 56, '#000', 'Wanted', 'left'); g.restore();
    }
  },
  stamp(t) {
    g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H);
    txt('신입이 하던 일', 110, 110, 76, '#fff', 'Wanted', 'left');
    const jobs = ['회의록 정리', '자료 조사', '엑셀 정리', '보고서 초안'];
    jobs.forEach((j, i) => {
      const x = 110 + (i % 2) * 860, y = 220 + Math.floor(i / 2) * 400;
      g.fillStyle = '#141414'; g.fillRect(x, y, 840, 370);
      txt(j, x + 60, y + 90, 64, '#ddd', 'Wanted', 'left');
      for (let k = 0; k < 3; k++) { g.fillStyle = '#2a2a2a'; g.fillRect(x + 60, y + 170 + k * 52, 620 - k * 120, 22); }
      const s = 0.6 + i * 0.55, u = back((t - s) / 0.25);
      if (t < s) return;
      g.save(); g.translate(x + 600, y + 230); g.rotate(-0.18); const sc = 1 + 1.4 * (1 - cl((t - s) / 0.18)); g.scale(sc * Math.min(1, u + 0.0001) || 0.001, sc * Math.min(1, u + 0.0001) || 0.001);
      g.lineWidth = 12; g.strokeStyle = G; g.strokeRect(-190, -70, 380, 140); txt('AI 처리', 0, 4, 84, G, "'Black Han Sans'"); g.restore();
    });
  },
  docs(t) {
    g.fillStyle = '#050505'; g.fillRect(0, 0, W, H);
    const snip = ['회의록: 다음 주까지 시안 3개', '주간 보고: 거래처 미팅 결과', '인수인계: 엑셀 시트 위치', '업무 메모: 이 부분 다시 확인',
      '신입 질문: 이건 왜 이렇게 해요?', '선배 답: 예전에 이런 일이 있어서', '보고서 초안 v3 (수정 반영)', '고객 문의 답장 정리',
      '실수 기록: 숫자 단위 확인할 것', '회의록: 결정 사항 정리', '교육 자료: 처음 오신 분께', '업무 일지 11월 18일'];
    const cx = 1560, cy = 540, dim = 1 - 0.75 * ease((t - STOP - 2.5) / 3);
    const glow = g.createRadialGradient(cx, cy, 10, cx, cy, 260); glow.addColorStop(0, `rgba(0,255,102,${0.55 * dim})`); glow.addColorStop(1, 'rgba(0,255,102,0)');
    g.fillStyle = glow; g.fillRect(cx - 300, cy - 300, 600, 600);
    g.fillStyle = `rgba(0,255,102,${dim})`; g.beginPath(); g.arc(cx, cy, 90, 0, 7); g.fill();
    txt('클로드', cx, cy + 4, 52, '#000');
    for (let k = 0; k < 60; k++) {   // 글 한 줄이 왼쪽에서 들어와 원으로 빨려 들어감
      const born = k * 0.16; if (born >= STOP) break;
      const r = (t - born) / 2.2; if (r < 0 || r > 1) continue;
      const y0 = 120 + rnd(k) * 840, x = 80 + ease(r) * (cx - 200), y = y0 + (cy - y0) * ease(cl((r - 0.45) / 0.55));
      const a = r < 0.1 ? r / 0.1 : 1 - cl((r - 0.8) / 0.2), sz = 40 - 18 * ease(cl((r - 0.5) / 0.5));
      g.globalAlpha = a; txt(snip[k % snip.length], x, y, sz, k % 3 ? '#cfcfcf' : G, 'Wanted', 'left'); g.globalAlpha = 1;
    }
  },
};
window.frame = (name, t) => { DRAW[name](t); return cv.toDataURL('image/jpeg', 0.95); };
"""


async def main(names):
    from playwright.async_api import async_playwright
    fonts = (ROOT / "assets" / "fonts").as_uri()
    html = f"""<html><head><meta charset=utf-8><link rel=stylesheet href='{fonts}/black-han-sans/index.css'><style>
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:400}}
body{{margin:0;background:#000}}</style></head><body><canvas id=c width=1920 height=1080></canvas>
<script>window.ready=Promise.all([document.fonts.load('80px Wanted','가'),document.fonts.load("80px 'Black Han Sans'",'AI처리0123456789')]);
{JS.replace('%STOP%', str(DOCS_STOP))}</script></body></html>"""
    page = OUT / "youth_screens.html"
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
            mp4 = OUT / "clips" / f"youth_{name}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"),
                            "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(mp4)], check=True)
            for s in (0.5, LEN[name] * 0.5, LEN[name] - 0.1):   # 확인용 장면
                shutil.copy(fd / f"{int(s * FPS):04d}.jpg", OUT / f"scr_{name}_{s:.1f}.jpg")
            shutil.rmtree(fd)
            print(mp4)
        await b.close()
    page.unlink()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(LEN)))
