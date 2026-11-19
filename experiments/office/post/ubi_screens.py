"""기본소득 편 모니터 화면 (운영자 2026-11-19 확정 대본 ubi.md): 2035년 설정, 뉴스·은행·게임은 모두 지어낸 화면.
news(2035.03.02 'AI가 번 돈으로 전 국민 기본소득') / deposit(기본소득 입금 알림) / game(한 달 뒤 게임만 하는 화면) / pause(멈춘 게임).
실행: py -3.12 experiments/office/post/ubi_screens.py [이름…] → out/clips/ubi_<이름>.mp4 (1920x1080, 15fps)"""
import asyncio
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "office" / "out"
FPS = 15
LEN = {"resign": 6, "news": 6, "deposit": 5, "game": 8, "pause": 6, "work": 6}

JS = r"""
const W = 1920, H = 1080, G = '#00FF66', R = '#ff4a4a';
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (u) => { u = cl(u); return u * u * (3 - 2 * u); };
const back = (u) => { u = cl(u); const c = 1.7; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
const cv = document.getElementById('c'), g = cv.getContext('2d');
const txt = (s, x, y, size, col, font, align) => { g.font = `${size}px ${font || 'Wanted'}`; g.fillStyle = col; g.textAlign = align || 'center'; g.textBaseline = 'middle'; g.fillText(s, x, y); };
const bg = () => { g.fillStyle = '#0b0b0b'; g.fillRect(0, 0, W, H); };
const stamp = (s, x, y, size, col, t0, t) => { if (t < t0) return; const u = back((t - t0) / 0.22), sc = 1 + 1.2 * (1 - cl((t - t0) / 0.15));
  g.save(); g.translate(x, y); g.rotate(-0.14); g.scale(sc * Math.max(0.001, u), sc * Math.max(0.001, u)); g.font = `${size}px 'Black Han Sans'`;
  const w = g.measureText(s).width + 70; g.lineWidth = 14; g.strokeStyle = col; g.strokeRect(-w / 2, -size * 0.75, w, size * 1.5); txt(s, 0, 6, size, col, "'Black Han Sans'"); g.restore(); };
const notice = (title, body, hl, t) => { bg(); txt('강의 공지', 110, 110, 52, '#9a9a9a', 'Wanted', 'left');
  g.fillStyle = '#141414'; g.fillRect(110, 180, 1700, 780); txt(title, 180, 280, 76, '#fff', 'Wanted', 'left'); txt('교수', 1740, 280, 46, '#9a9a9a', 'Wanted', 'right');
  body.forEach((b, i) => { const y = 470 + i * 130, u = ease((t - hl - i * 0.25) / 0.4); g.font = '70px Wanted'; const w = g.measureText(b).width;
    if (u > 0) { g.fillStyle = G; g.fillRect(170, y - 50, (w + 30) * u, 100); }
    txt(b, 185, y, 70, '#fff', 'Wanted', 'left'); if (u > 0) { g.save(); g.beginPath(); g.rect(170, y - 50, (w + 30) * u, 100); g.clip(); txt(b, 185, y, 70, '#000', 'Wanted', 'left'); g.restore(); } }); };
const LMS = (crumb) => {   // 가상의 학교 강의 사이트 (실제 학교·서비스 아님)
  g.fillStyle = '#f4f6f9'; g.fillRect(0, 0, W, H);
  g.fillStyle = '#1d3b6f'; g.fillRect(0, 0, W, 110); txt('토큰대학교 e-강의실', 60, 56, 46, '#fff', 'Wanted', 'left');
  txt('로그아웃', 1860, 56, 32, '#c9d6ee', 'Wanted', 'right');
  g.fillStyle = '#fff'; g.fillRect(0, 110, W, 80); g.fillStyle = '#e1e6ee'; g.fillRect(0, 189, W, 2);
  txt('AI와 사회 (2분반)  >  ' + crumb, 60, 150, 34, '#5a6577', 'Wanted', 'left'); };
const post = (title, date, body, hl, t) => { LMS('공지사항');
  g.fillStyle = '#fff'; g.fillRect(60, 230, 1800, 810); g.strokeStyle = '#dde3ec'; g.lineWidth = 2; g.strokeRect(60, 230, 1800, 810);
  txt(title, 110, 310, 64, '#1b2433', 'Wanted', 'left');
  txt(`작성자  김교수      ${date}      조회 1,284`, 110, 385, 32, '#7a8597', 'Wanted', 'left');
  g.fillStyle = '#e8ecf2'; g.fillRect(110, 430, 1700, 3);
  body.forEach(([line, mark], i) => { const y = 520 + i * 100; g.font = '56px Wanted'; const w = g.measureText(line).width;
    const u = mark ? ease((t - hl - i * 0.25) / 0.45) : 0; if (u > 0) { g.fillStyle = 'rgba(255,214,0,0.55)'; g.fillRect(105, y + 4, (w + 10) * u, 34); }
    txt(line, 110, y, 56, mark ? '#c0182b' : '#2b3445', 'Wanted', 'left'); }); };
const table = (rows, head, t, t0) => { const x0 = 60, cw = [700, 500, 600];
  g.fillStyle = '#fff'; g.fillRect(x0, 230, 1800, 120 + rows.length * 130); g.fillStyle = '#eef2f8'; g.fillRect(x0, 230, 1800, 100);
  head.forEach((h, j) => txt(h, x0 + 60 + cw.slice(0, j).reduce((a, b) => a + b, 0), 280, 38, '#5a6577', 'Wanted', 'left'));
  rows.forEach((r, i) => { const y = 330 + i * 130 + 65; g.fillStyle = '#e8ecf2'; g.fillRect(x0, y + 64, 1800, 2);
    r.forEach((c, j) => { const x = x0 + 60 + cw.slice(0, j).reduce((a, b) => a + b, 0), big = j === 2;
      if (big && t < (t0[i] ?? 0)) return; const u = big ? back((t - (t0[i] ?? 0)) / 0.3) : 1;
      g.save(); g.translate(x, y); g.scale(u || 0.001, u || 0.001);
      txt(c, 0, 0, big ? 96 : 50, big ? (c === 'A' ? '#14a34a' : c === '-' ? '#9aa3b2' : '#d92b3a') : '#1b2433', big ? "'Black Han Sans'" : 'Wanted', 'left'); g.restore(); }); }); };
const chat = (msgs, t) => {   // 메신저 친구 단톡방 (일반 모양, 특정 앱 아님, 운영자 2026-11-19 '친구 단톡방 느낌')
  g.fillStyle = '#b8c9d9'; g.fillRect(0, 0, W, H);
  g.fillStyle = '#a9bccd'; g.fillRect(0, 0, W, 110); txt('<', 50, 56, 56, '#1b2433', 'Wanted', 'left');
  txt('냥냥이들  4', 960, 56, 44, '#1b2433');
  let y = 200;
  msgs.forEach(([who, m, col, tm], i) => { const at = 0.2 + i * 0.6, u = back((t - at) / 0.3); if (u <= 0) return;
    g.save(); g.translate(0, (1 - Math.min(1, u)) * 40); g.globalAlpha = Math.min(1, u);
    g.fillStyle = col; g.beginPath(); g.arc(110, y + 40, 46, 0, 7); g.fill(); txt(who[0], 110, y + 42, 44, '#fff');
    txt(who, 180, y + 6, 32, '#2b3445', 'Wanted', 'left');
    g.font = '52px Wanted'; const w = g.measureText(m).width + 60;
    g.fillStyle = '#fff'; g.beginPath(); g.roundRect(180, y + 34, w, 96, 26); g.fill(); txt(m, 210, y + 84, 52, '#111', 'Wanted', 'left');
    txt(tm, 195 + w, y + 118, 26, '#4c5a6b', 'Wanted', 'left'); g.restore(); y += 190; }); };
const DRAW = {
  resign(t) { g.fillStyle = '#f4f6f9'; g.fillRect(0, 0, W, H); g.fillStyle = '#2b3a55'; g.fillRect(0, 0, W, 110);   // 퇴사 처리 메일 (지어낸 회사)
    txt('토큰상사 메일', 60, 56, 46, '#fff', 'Wanted', 'left'); txt('2035.03.02 (금) 오전 8:40', 1860, 56, 36, '#c9d6ee', 'Wanted', 'right');
    g.fillStyle = '#fff'; g.fillRect(80, 160, 1760, 860);
    txt('[인사팀] 퇴사 처리 완료 안내', 140, 250, 66, '#1b2433', 'Wanted', 'left'); txt('보낸 사람  인사팀', 140, 330, 36, '#7a8597', 'Wanted', 'left');
    g.fillStyle = '#e8ecf2'; g.fillRect(140, 380, 1640, 3);
    [['그동안 수고 많으셨습니다.', '#2b3445'], ['오늘부로 퇴사 처리가 완료되었습니다.', '#2b3445'], ['담당 업무는 AI 에이전트 클로드가 이어받습니다.', '#c0182b']].forEach(([l, c], i) => {
      const v = ease((t - 0.3 - i * 0.5) / 0.4); if (v <= 0) return; g.globalAlpha = v; txt(l, 140, 480 + i * 100, 56, c, 'Wanted', 'left'); g.globalAlpha = 1; }); },
  work(t) { g.fillStyle = '#0f1115'; g.fillRect(0, 0, W, H);   // 클로드가 쉬지 않고 일하는 화면 (끝 그림)
    txt('클로드 작업 중', 80, 90, 64, '#00FF66', "'Black Han Sans'", 'left'); txt('● 24시간 가동', 1840, 90, 40, '#00FF66', 'Wanted', 'right');
    const n = Math.floor(1284 + t * 37), won = Math.floor(48210000 + t * 913000);
    txt('오늘 처리한 일', 80, 260, 44, '#9aa3b2', 'Wanted', 'left'); txt(`${n.toLocaleString()}건`, 80, 360, 110, '#fff', "'Black Han Sans'", 'left');
    txt('오늘 번 돈', 1000, 260, 44, '#9aa3b2', 'Wanted', 'left'); txt(`${won.toLocaleString()}원`, 1000, 360, 100, '#00FF66', "'Black Han Sans'", 'left');
    const jobs = ['보고서 작성', '고객 응대', '회의록 정리', '코드 수정', '번역', '디자인 시안', '자료 조사', '엑셀 정리'];
    for (let k = 0; k < 7; k++) { const idx = Math.floor(t * 6) + k, y = 520 + k * 76, a = 1 - k * 0.12;
      g.globalAlpha = a; g.fillStyle = '#1a1e26'; g.fillRect(80, y - 30, 1760, 64);
      txt(jobs[idx % jobs.length], 120, y + 2, 40, '#e8eaf0', 'Wanted', 'left'); txt('완료 ✓', 1800, y + 2, 38, '#00FF66', 'Wanted', 'right'); g.globalAlpha = 1; } },
  news(t) { g.fillStyle = '#f5f5f2'; g.fillRect(0, 0, W, H); g.fillStyle = '#c0182b'; g.fillRect(0, 0, W, 120);
    txt('토큰뉴스', 60, 62, 60, '#fff', "'Black Han Sans'", 'left'); txt('2035.03.02 (금)', 1860, 62, 40, '#ffe0e0', 'Wanted', 'right');
    g.fillStyle = '#c0182b'; g.fillRect(100, 210, 160, 64); txt('속보', 180, 243, 40, '#fff');
    const u = ease((t - 0.05) / 0.25); g.save(); g.globalAlpha = u;
    txt('AI가 번 돈으로', 100, 400, 110, '#111', "'Black Han Sans'", 'left'); txt('전 국민 기본소득', 100, 540, 130, '#c0182b', "'Black Han Sans'", 'left'); g.restore();
    [['매달, 모든 국민에게', 1.2], ['일하지 않아도 받는다', 1.7]].forEach(([s, a]) => { const v = ease((t - a) / 0.4); if (v <= 0) return;
      g.globalAlpha = v; g.fillStyle = '#111'; g.fillRect(100, 650 + (a > 1.5 ? 110 : 0), 14, 70); txt(s, 140, 685 + (a > 1.5 ? 110 : 0), 64, '#333', 'Wanted', 'left'); g.globalAlpha = 1; });
    g.fillStyle = '#e4e4de'; g.fillRect(1240, 250, 560, 600);
    for (let k = 0; k < 8; k++) { const x = 1290 + k * 62, h = 60 + k * 55 * ease((t - 0.8) / 1.5); g.fillStyle = k > 5 ? '#c0182b' : '#9aa0a8'; g.fillRect(x, 800 - h, 44, h); }
    txt('AI 기업 수익', 1520, 300, 40, '#555'); },
  deposit(t) { g.fillStyle = '#20232a'; g.fillRect(0, 0, W, H);
    txt('오전 9:00', 960, 160, 120, '#fff', 'Wanted'); txt('2035년 3월 25일 일요일', 960, 260, 44, '#cfd3da', 'Wanted');
    const v = back((t - 0.12) / 0.3); if (v <= 0) return; g.save(); g.translate(960, 560); g.scale(v, v);
    g.fillStyle = 'rgba(245,245,245,0.97)'; g.beginPath(); g.roundRect(-760, -150, 1520, 300, 46); g.fill();
    g.fillStyle = '#1d6fe0'; g.beginPath(); g.roundRect(-700, -90, 120, 120, 28); g.fill(); txt('₩', -640, -28, 80, '#fff');
    txt('토큰은행', -540, -80, 40, '#555', 'Wanted', 'left'); txt('지금', 700, -80, 36, '#888', 'Wanted', 'right');
    txt('[입금] 3월 기본소득', -540, -10, 60, '#111', 'Wanted', 'left'); txt('정부 · 전 국민 지급', -540, 70, 40, '#666', 'Wanted', 'left'); g.restore(); },
  game(t) { g.fillStyle = '#0d1b2a'; g.fillRect(0, 0, W, H);   // 우리가 그린 단순한 달리기 게임 (특정 게임 아님)
    g.fillStyle = '#1b3a5a'; g.fillRect(0, 820, W, 260);
    for (let k = 0; k < 30; k++) { g.fillStyle = 'rgba(255,255,255,0.35)'; g.fillRect((k * 197 - t * 120) % W + W * (((k * 197 - t * 120) % W) < 0), (k * 61) % 700, 3, 3); }
    const ph = (t * 1.6) % 1, jump = Math.max(0, Math.sin(ph * Math.PI)) * 260;
    g.fillStyle = '#ff7a59'; g.beginPath(); g.arc(420, 760 - jump, 60, 0, 7); g.fill();
    for (let k = 0; k < 5; k++) { const x = 1980 - ((t * 700 + k * 480) % 2300); g.fillStyle = '#e8e3d0'; g.beginPath(); g.moveTo(x, 820); g.lineTo(x + 50, 700); g.lineTo(x + 100, 820); g.fill(); }
    txt(`점수 ${Math.floor(t * 137).toLocaleString()}`, 60, 80, 56, '#fff', "'Black Han Sans'", 'left'); txt(`플레이 시간 ${312 + Math.floor(t * 9)}시간`, 1860, 80, 44, '#ffcc33', 'Wanted', 'right'); },
  pause(t) { DRAW.game(0); g.fillStyle = 'rgba(0,0,0,0.6)'; g.fillRect(0, 0, W, H); txt('일시 정지', 960, 520, 120, '#fff', "'Black Han Sans'"); txt('계속하려면 아무 키나 누르세요', 960, 650, 46, '#cfd3da'); },
};
window.frame = (name, t) => { DRAW[name](t); return cv.toDataURL('image/jpeg', 0.95); };
"""


async def main(names):
    from playwright.async_api import async_playwright
    fonts = (ROOT / "assets" / "fonts").as_uri()
    html = f"""<html><head><meta charset=utf-8><link rel=stylesheet href='{fonts}/black-han-sans/index.css'><style>
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:400}}
body{{margin:0;background:#000}}</style></head><body><canvas id=c width=1920 height=1080></canvas>
<script>window.ready=Promise.all([document.fonts.load('80px Wanted','가'),document.fonts.load("80px 'Black Han Sans'",'토큰뉴스속보AI가번돈으로전국민기본소득일시정지점수0123456789')]);
{JS}</script></body></html>"""
    page = OUT / "ubi_screens.html"
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
            mp4 = OUT / "clips" / f"ubi_{name}.mp4"
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
