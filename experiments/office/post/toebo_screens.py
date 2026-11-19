"""퇴보 vs 퇴화 편 모니터 화면 (운영자 2026-11-19 확정 대본 toebo_toehwa.md): 우리가 그린 화면만, 교수·학생은 지어낸 것.
notice1(AI 작성 과제 다 잡아냄) / allnight(혼자 밤새 쓰기, 시계 23시→05시) / gradec(과제 C + 단톡 A 알림) / grader(채점 도우미: 클로드)
/ gradea(A A A) / notice2(기말 재난문자) / caught(부정행위 적발 → F).
실행: py -3.12 experiments/office/post/toebo_screens.py [이름…] → out/clips/toebo_<이름>.mp4 (1920x1080, 15fps)"""
import asyncio
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "office" / "out"
FPS = 15
LEN = {"notice1": 5, "allnight": 6.6, "gradec": 7, "grader": 6, "aiwrite": 3.4, "gradea": 4, "notice2": 7, "caught": 4.6}

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
  notice1(t) { post('[공지] 중간 과제 제출 안내', '2026.10.02', [['과제는 A4 5쪽, 10월 20일까지 제출하세요.', 0], ['AI로 작성한 과제는 전부 잡아냅니다.', 1], ['적발 시 0점 처리합니다.', 1]], 0.7, t); },
  allnight(t) { const u = cl(t / 5.6), mins = 23 * 60 + Math.floor(u * 390), hh = Math.floor(mins / 60) % 24, mm = mins % 60;
    g.fillStyle = '#e9ebee'; g.fillRect(0, 0, W, H); g.fillStyle = '#2b579a'; g.fillRect(0, 0, W, 70); txt('중간과제_최종_진짜최종.docx', 960, 36, 34, '#fff');
    g.fillStyle = '#f7f7f7'; g.fillRect(0, 70, W, 90); ['파일', '홈', '삽입', '레이아웃', '검토'].forEach((m, i) => txt(m, 60 + i * 150, 115, 32, '#333', 'Wanted', 'left'));
    g.fillStyle = '#fff'; g.fillRect(360, 190, 1200, 820); g.strokeStyle = '#d0d4da'; g.strokeRect(360, 190, 1200, 820);
    const n = Math.floor(u * 21); for (let k = 0; k < n; k++) { g.fillStyle = '#9aa0a8'; g.fillRect(440, 250 + k * 36, 1040 - ((k * 137) % 360), 13); }
    g.fillStyle = '#20232a'; g.fillRect(0, 1020, W, 60); txt(`${Math.floor(u * 4800).toLocaleString()}자`, 60, 1050, 32, '#cfd3da', 'Wanted', 'left');
    txt(`${hh < 12 ? '오전' : '오후'} ${String(hh % 12 || 12)}:${String(mm).padStart(2, '0')}`, 1860, 1050, 40, hh < 6 ? '#ffb24a' : '#fff', 'Wanted', 'right');
    if (t > 5.4) { const v = back((t - 5.4) / 0.3); g.save(); g.translate(960, 560); g.scale(v || 0.001, v || 0.001);
      g.fillStyle = 'rgba(0,0,0,0.25)'; g.fillRect(-470, -190, 960, 400); g.fillStyle = '#fff'; g.fillRect(-480, -200, 960, 400);
      txt('토큰대학교 e-강의실', 0, -130, 36, '#7a8597'); txt('과제 제출 완료', 0, -30, 80, '#1b2433'); txt('제출 시각 오전 5:30', 0, 80, 40, '#7a8597'); g.restore(); } },
  gradec(t) { if (t < 1.9) { LMS('성적 조회');   // 운영자 2026-11-19: 내 성적만, 로딩되다가 C 딱
      g.fillStyle = '#fff'; g.fillRect(360, 260, 1200, 700); g.strokeStyle = '#dde3ec'; g.lineWidth = 2; g.strokeRect(360, 260, 1200, 700);
      txt('중간 과제', 960, 360, 60, '#1b2433');
      if (t < 1.0) { for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2 + t * 8; g.fillStyle = `rgba(29,59,111,${(k / 12)})`; g.beginPath(); g.arc(960 + Math.cos(a) * 80, 640 + Math.sin(a) * 80, 14, 0, 7); g.fill(); }
        txt('성적 불러오는 중...', 960, 820, 44, '#7a8597'); return; }
      const u = back((t - 1.0) / 0.25); g.save(); g.translate(960, 650); g.scale(u || 0.001, u || 0.001); txt('C', 0, 0, 360, '#d92b3a', "'Black Han Sans'"); g.restore(); return; }
    chat([['박냥이', '나 A ㅋㅋ', '#e0795b', '오전 9:02'], ['김냥이', '나도 A', '#5b8fe0', '오전 9:02'], ['이냥이', 'AI가 써 줌 ㅋㅋㅋ', '#59b07a', '오전 9:03']], t - 1.9); },
  grader(t) { g.fillStyle = '#f6f5f0'; g.fillRect(0, 0, W, H); g.fillStyle = '#1b2433'; g.fillRect(0, 0, W, 110);   // 내 과제만 채점
    txt('과제 자동 채점', 60, 56, 46, '#fff', 'Wanted', 'left'); txt('채점: 클로드', 1860, 56, 42, G, "'Black Han Sans'", 'right');
    g.fillStyle = '#fff'; g.fillRect(260, 200, 1400, 820); txt('중간과제_최종_진짜최종.docx', 320, 270, 44, '#1b2433', 'Wanted', 'left');
    for (let k = 0; k < 7; k++) { g.fillStyle = '#c9cdd3'; g.fillRect(320, 340 + k * 40, 900 - (k * 97) % 300, 14); }
    const sc = cl((t - 0.3) / 1.4); g.fillStyle = 'rgba(0,255,102,0.25)'; if (sc < 1) g.fillRect(310, 330 + sc * 280, 1000, 30);
    [[0, 140, 120], [2, 420, 160], [3, 90, 110], [5, 300, 140], [6, 520, 120]].forEach(([k, x, w], i) => {   // 오류 빨간 밑줄 (운영자 2026-11-19 '문법 오류 같은 걸로')
      if (t < 0.6 + i * 0.25) return; g.strokeStyle = '#e53935'; g.lineWidth = 5; g.beginPath();
      for (let q = 0; q <= w; q += 10) g.lineTo(320 + x + q, 362 + k * 40 + (q / 10 % 2 ? 6 : 0)); g.stroke(); });
    if (t > 1.9) { txt('검토 의견', 320, 690, 40, '#9aa3b2', 'Wanted', 'left'); txt('맞춤법 오류 7건, 비문 3건', 320, 760, 54, '#d92b3a', 'Wanted', 'left'); txt('분량 미달 (4쪽 반 / 5쪽)', 320, 830, 54, '#6a7383', 'Wanted', 'left'); }
    if (t > 2.6) { const u = back((t - 2.6) / 0.3); g.save(); g.translate(1450, 560); g.scale(u || 0.001, u || 0.001); txt('C', 0, 0, 300, '#d92b3a', "'Black Han Sans'"); g.restore(); } },
  aiwrite(t) { g.fillStyle = '#e9ebee'; g.fillRect(0, 0, W, H); g.fillStyle = '#2b579a'; g.fillRect(0, 0, W, 70); txt('과제 작성 중 · 클로드', 960, 36, 34, '#fff');
    [0, 1, 2].forEach((i) => { const x = 140 + i * 570, u = cl((t - 0.2 - i * 0.7) / 0.9);
      g.fillStyle = '#fff'; g.fillRect(x, 140, 520, 760); g.strokeStyle = '#d0d4da'; g.strokeRect(x, 140, 520, 760); txt(`과제 ${i + 1}.docx`, x + 30, 190, 36, '#333', 'Wanted', 'left');
      const n = Math.floor(u * 15); for (let k = 0; k < n; k++) { g.fillStyle = '#9aa0a8'; g.fillRect(x + 30, 250 + k * 40, 460 - ((k * 97) % 180), 13); }
      if (u >= 1) { const v = back((t - 1.1 - i * 0.7) / 0.25); g.save(); g.translate(x + 260, 960); g.scale(v || 0.001, v || 0.001); txt('완료', 0, 0, 56, '#14a34a', "'Black Han Sans'"); g.restore(); } });
    txt(`${Math.min(3, Math.floor(cl((t - 0.2) / 2.3) * 3 + 0.0001 + (t > 2.5 ? 1 : 0)))}/3`, 1860, 1030, 44, '#1b2433', 'Wanted', 'right'); },
  gradea(t) { LMS('성적 조회'); table([['과제 1', '100점 만점', 'A'], ['과제 2', '100점 만점', 'A'], ['과제 3', '100점 만점', 'A']], ['평가 항목', '배점', '성적'], t, [0.3, 0.75, 1.2]); },
  notice2(t) { post('[공지] 기말고사 안내', '2026.12.08', [['12월 15일 10시, 본관 301호.', 0], ['수능처럼 시험 시작 전 재난문자를 보냅니다.', 1], ['휴대폰이 울리면 부정행위로 처리합니다.', 1]], 0.8, t); },
  caught(t) { LMS('성적 조회'); if (t < 0.9) { g.fillStyle = '#fff'; g.fillRect(360, 260, 1200, 700);
      for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2 + t * 8; g.fillStyle = `rgba(29,59,111,${k / 12})`; g.beginPath(); g.arc(960 + Math.cos(a) * 80, 600 + Math.sin(a) * 80, 14, 0, 7); g.fill(); }
      txt('기말고사 성적 불러오는 중...', 960, 790, 44, '#7a8597'); return; }
    const t2 = t - 0.9; table([['기말고사', '100점 만점', t2 > 1.5 ? 'F' : '-']], ['평가 항목', '배점', '성적'], t2, [1.5]);   // 기말만 (운영자 2026-11-19 '과제 A는 헷갈려')
    if (t2 > 0.15) { const u = back((t2 - 0.15) / 0.3); g.save(); g.translate(960, 820); g.rotate(-0.08); g.scale(u || 0.001, u || 0.001);
      g.font = "130px 'Black Han Sans'"; const w = g.measureText('부정행위 적발').width + 80; g.lineWidth = 14; g.strokeStyle = '#d92b3a'; g.strokeRect(-w / 2, -100, w, 200);
      txt('부정행위 적발', 0, 8, 130, '#d92b3a', "'Black Han Sans'"); g.restore(); } },
};
window.frame = (name, t) => { DRAW[name](t); return cv.toDataURL('image/jpeg', 0.95); };
"""


async def main(names):
    from playwright.async_api import async_playwright
    fonts = (ROOT / "assets" / "fonts").as_uri()
    html = f"""<html><head><meta charset=utf-8><link rel=stylesheet href='{fonts}/black-han-sans/index.css'><style>
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:400}}
body{{margin:0;background:#000}}</style></head><body><canvas id=c width=1920 height=1080></canvas>
<script>window.ready=Promise.all([document.fonts.load('80px Wanted','가'),document.fonts.load("80px 'Black Han Sans'",'AI처리부정행위적발CFA0123456789:')]);
{JS}</script></body></html>"""
    page = OUT / "toebo_screens.html"
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
            mp4 = OUT / "clips" / f"toebo_{name}.mp4"
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
