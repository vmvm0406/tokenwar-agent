"""막대 경주 릴스 (post type "video" + "race", 2026-11-17, 고전 바 차트 레이스로 다시 만듦).

운영자 (2026-11-17): "시간에 따라서 연속적으로 숫자가 바뀌어야", "년도랑 월은 너무 눈에 잘 안 띄어", "쓸데없는 부연설명이 많아".
- 시간 한 줄: 본편 race_len초 동안 날짜가 한결같은 속도로 흐르고(달마다 째깍), 오른쪽 위 작은 날짜판이 따라 바뀐다.
- 값은 발표·보도 사이를 비율로 이어 그린다(기하 보간). 막대 끝 숫자가 계속 올라가고, 순위가 바뀌면 막대가 0.3초 미끄러진다.
  첫 발표 때 0에서 짧게 자라 들어오고, 마지막 발표 뒤에는 그 값을 유지한다.
- 화면 글: 제목 2줄(0초 쾅), 0초 질문 한 줄(cta_line), 작은 단위 라벨(unit_label), 날짜, 막대(이름·숫자·막대 끝 동그란 사진),
  끝 punch 한 줄(선택). 중간 글자 카드·띠·근거 줄 없음 (근거는 캡션).
- 배경: 1위 회사 사진을 흐리고 어둡게 (1위가 바뀌면 0.5초 겹쳐 바뀜). 사진 필수 (STYLE_GUIDE 0장 원칙 0).
- 끝: 1위 막대만 녹색, 나머지 흐리게, punch → end_cta(또는 dm.cta) 끝 화면 2.5초.
소리: 실제 음원 조각(music.src, agent/music_fit.py) + 효과음(1위 바뀔 때 휙·쿵, 해 바뀔 때 틱, 끝 상승음·쿵) → -14 LUFS.

post.json:
  "race": {
    "format": "people_m" | "usd_b",       # 값 단위: 백만 명 → '12억'·'700만' / 십억 달러 → '1조 2,500억'·'5.2억'
    "start": "2024-06-01", "end": "2026-11-17",   # 날짜판 처음·끝 (선택, 기본 첫·마지막 발표일). 처음 전 발표는 보간에만 씀
    "seconds": 24,                         # 선택. 본편(날짜가 흐르는) 길이
    "interp": "geometric" | "step",        # 선택. 기본: people_m은 발표 사이 이어 그림, usd_b는 다음 발표까지 유지
    "unit_label": "사용자 수(명) · ChatGPT는 주간",   # 날짜 왼쪽 작은 단위 라벨 (지표가 섞이면 여기에 짧게)
    "cta_line": "ChatGPT vs Gemini, 뭐 쓰세요?",      # 0.5초부터 제목 아래 한 줄 (선택)
    "punch": "ChatGPT 주간 12억 명",       # 선택. 끝 한 줄 (1~2줄, 줄당 16자 이하)
    "series": [{"name": "ChatGPT", "color": "#10A37F",
                "points": [{"date": "2023-11-06", "value": 100, "kind": "official", "src": "누가·어디서", "url": "https://..."}]}],
    "images": [{"series": "ChatGPT", "src": "img/altman.jpg", "x": 50, "y": 40, "fy": 25, "credit": "...", "url": "..."}],
    "thumb_src": "img/thumb.jpg"            # 렌더링이 그리는 썸네일 바탕 (thumb.image.src와 같게)
  }
  (예전 필드 basis_line·beats·series[].tag는 화면에 쓰지 않는다)
사용법: render.py가 부른다. 계획만 보기: py -3.12 agent/racereel.py <게시물 폴더>
"""
import asyncio
import base64
import datetime as dt
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)
RAIL_LEFT = _SAFE.get("rail_left", 850)

RACE_LEN = 24.0        # 본편: 날짜가 처음부터 끝까지 흐르는 시간
HOLD = 0.4             # 끝 날짜에서 잠깐
WIN_LEN = 3.1          # 1위 녹색 + punch
ENTRY_SEC = 0.4        # 새 회사가 0에서 자라 들어오는 시간
END_LEN = 2.5
LENGTH_RANGE = (20.0, 35.0)
FORMATS = ("people_m", "usd_b")


def _d(s):
    return dt.date.fromisoformat(str(s))


def fmt_value(v, fmt):
    """화면 값 표기 (JS fmtValue와 같음). 단위는 unit_label에."""
    if fmt == "people_m":
        if v >= 100:
            return f"{round(v / 100, 1):g}억"
        return f"{round(v * 100):,}만"
    eok = v * 10
    if eok >= 10000:
        jo, rest = divmod(round(eok), 10000)
        return f"{jo}조 {rest:,}억" if rest else f"{jo}조"
    if eok < 10:
        return f"{round(eok, 1):g}억"
    return f"{round(eok):,}억"


def images_of(post):
    """race.images (사진 필수, STYLE_GUIDE 0장 원칙 0) → {막대 번호: 항목}."""
    names = [s["name"] for s in post["race"]["series"]]
    return {names.index(im["series"]): im for im in post["race"].get("images") or []
            if im.get("series") in names and im.get("src")}


def value_at(s, day, entry_days, step=False):
    """JS valueAt와 같음: 발표 사이 기하 보간(step이면 다음 발표까지 유지하고 발표 때 entry_days 동안 늘어남),
    첫 발표 때 자라 들어옴, 마지막 뒤 유지."""
    pts = s["pts"]
    if day < pts[0]["d"]:
        return None
    if step:
        k = max(j for j, q in enumerate(pts) if q["d"] <= day)
        a = pts[k - 1]["v"] if k > 0 else 0.0
        if k == 0 and pts[0]["d"] <= 0:
            return pts[0]["v"]
        span = s.get("span", 10 ** 9)
        x = min(1.0, (day - pts[k]["d"]) / max(1, min(entry_days, span - pts[k]["d"])))
        return a + (pts[k]["v"] - a) * (1 - (1 - x) ** 3)
    if pts[0]["d"] > 0 and day < pts[0]["d"] + entry_days:
        x = (day - pts[0]["d"]) / entry_days
        return pts[0]["v"] * (1 - (1 - x) ** 3)
    for a, b in zip(pts, pts[1:]):
        if day < b["d"]:
            f = (day - a["d"]) / (b["d"] - a["d"])
            return a["v"] * (b["v"] / a["v"]) ** f if a["v"] > 0 and b["v"] > 0 else a["v"] + (b["v"] - a["v"]) * f
    return pts[-1]["v"]


def plan(post):
    R = post["race"]
    dates = sorted({p["date"] for s in R["series"] for p in s["points"]})
    start = _d(R.get("start") or dates[0])
    end = _d(R.get("end") or dates[-1])
    span = (end - start).days
    race_len = float(R.get("seconds", RACE_LEN))
    entry_days = ENTRY_SEC / race_len * span
    ser = []
    for s in R["series"]:
        pts = sorted(s["points"], key=lambda p: p["date"])
        ser.append({"name": s["name"], "color": s.get("color", "#9AA59F"), "span": span,
                    "pts": [{"d": (_d(p["date"]) - start).days, "v": float(p["value"])} for p in pts]})
    race_end = race_len + HOLD
    # 값 잇는 법: 사용자 수는 발표 사이를 비율로 이어 그림, 기업가치는 투자 때 정해지는 값이라 다음 발표까지 유지(step)
    step = R.get("interp", "step" if R.get("format") == "usd_b" else "geometric") == "step"
    p = {"fmt": R.get("format", "people_m"), "step": step, "ser": ser, "start": [start.year, start.month, start.day], "span": span,
         "race_len": race_len, "race_end": race_end, "win_end": race_end + WIN_LEN, "entry_days": entry_days,
         "title": str(post["title"]).splitlines(), "hl": post.get("highlight") or "",
         "cta": (R.get("cta_line") or "").strip(), "unit": (R.get("unit_label") or "").strip(),
         "punch": [l for l in str(R.get("punch", "")).splitlines() if l.strip()],
         "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM, "side": SIDE, "rail": RAIL_LEFT}}
    # 1위 바뀜(배경 사진·효과음)과 순위 바뀜: 프레임마다 값으로 정한다
    lead, swaps, prev_order = [], [], None
    for k in range(int(race_len * FPS) + 1):
        t = k / FPS
        day = t / race_len * span
        vs = [value_at(s, day, entry_days, step) for s in ser]
        order = sorted([i for i, v in enumerate(vs) if v is not None], key=lambda i: (-vs[i], i))
        if order and (not lead or lead[-1][1] != order[0]):
            if not lead or t - lead[-1][0] >= 0.5:
                lead.append([round(t, 3), order[0]])
        if prev_order and [i for i in order if i in prev_order] != prev_order:
            swaps.append(round(t, 3))
        prev_order = order
    p["lead"] = lead
    p["swaps"] = swaps
    p["winner"] = max(range(len(ser)), key=lambda i: value_at(ser[i], span, entry_days, step) or 0)
    p["years"] = [round((dt.date(y, 1, 1) - start).days / span * race_len, 3)
                  for y in range(start.year + 1, end.year + 1)]
    return p


def page_html(p, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    js = (ROOT / "agent" / "racereel.js").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-SemiBold.otf');font-weight:600}}
html,body{{margin:0;background:{b['bg']}}} canvas{{display:block}}
</style></head><body><canvas id="c" width="{W}" height="{H}"></canvas>
<script>const P = {json.dumps(p, ensure_ascii=False)};
const C = {json.dumps({"bg": b["bg"], "accent": b["accent"], "text": b["text"], "muted": b["muted"]})};
{js}</script></body></html>"""


async def _shoot(html_file, times, out_dir, thumb_png=None):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await pw.chromium.launch(executable_path=exe) if exe else await pw.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(html_file.as_uri())
        await pg.evaluate("""async () => { await document.fonts.load('96px "Black Han Sans"', '가A1');
            await document.fonts.load('700 30px Wanted', '가A1'); await document.fonts.load('600 30px Wanted', '가A1');
            await document.fonts.ready; }""")
        await pg.evaluate("rcInit()")   # 사진을 다 읽을 때까지 기다린다
        problems = await pg.evaluate("rcProblems()")
        if not problems:
            for k, t in enumerate(times):
                data = await pg.evaluate(f"rcFrame({t:.5f})")
                (out_dir / f"f{k:05d}.jpg").write_bytes(base64.b64decode(data.split(",", 1)[1]))
            if thumb_png:
                data = await pg.evaluate("rcThumb()")
                Path(thumb_png).write_bytes(base64.b64decode(data.split(",", 1)[1]))
        await browser.close()
    return problems




def sfx_tracks(p, total):
    from music_gen import make_hook_sfx
    lead = [t for t, _ in p["lead"][1:]]
    hits = [t for t in p["swaps"] if all(abs(t - x) > 0.2 for x in lead)]
    hits = [t for k, t in enumerate(hits) if k == 0 or t - hits[k - 1] > 0.4]
    return make_hook_sfx(total, impacts=[0.0, p["race_end"] + 0.1] + lead, hits=hits,
                         whooshes=lead, riser_to=p["race_end"] + 0.1, riser_len=1.6, drop=None, ticks=p["years"])


def make_race_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, -14 LUFS), frames/*.jpg, race.thumb_src(썸네일 바탕). 전체 길이(초)."""
    folder = Path(folder)
    p = plan(post)
    work = folder / "_race"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    missing = [im["src"] for im in images_of(post).values() if not (folder / im["src"]).exists()]
    if missing:
        shutil.rmtree(work)
        raise ValueError("race.images 파일 없음: " + ", ".join(missing))
    # data URI로 넣는다 (file:// 그림은 캔버스를 오염시켜 toDataURL이 막힘)
    p["imgs"] = {str(i): {"uri": "data:image/jpeg;base64," + base64.b64encode((folder / im["src"]).read_bytes()).decode(),
                          "x": im.get("x", 50), "y": im.get("y", 40), "fy": im.get("fy", im.get("y", 40))}
                 for i, im in images_of(post).items()}
    html_file = work / "race.html"
    html_file.write_text(page_html(p, cfg), encoding="utf-8")
    main = p["win_end"]
    nfr = int(round(main * FPS))
    thumb_rel = post["race"].get("thumb_src")
    thumb_png = work / "thumb.jpg" if thumb_rel else None
    problems = asyncio.run(_shoot(html_file, [k / FPS for k in range(nfr)], work, thumb_png))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    if thumb_rel:
        from PIL import Image
        out = folder / thumb_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(thumb_png).convert("RGB").save(out, quality=92)
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(work / "f%05d.jpg"),
                    "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-r", str(FPS), str(silent)], check=True)
    from listreel import mix_audio
    pm = post.get("music") or {}
    if pm.get("src") and (folder / pm["src"]).exists():     # 실제 음원 조각 (agent/music_fit.py)
        music = folder / pm["src"]
    else:                                                    # 대체: 코드로 만든 후킹 비트
        from music_gen import make_hook_music
        music = work / "music.wav"
        make_hook_music(music, 120, main)
    sfx, info = sfx_tracks(p, main)
    mixed = work / "mix.wav"
    mix_audio(music, [], main, mixed, sfx)
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{main:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    dur = main
    from video import dm_cta, append_cta_card
    cta = dm_cta(post)
    if cta:
        dur = append_cta_card(out, cta, cfg, work, dur)
    from loudness import normalize
    normalize(out)
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    for k, t in enumerate(preview_times(p, dur), 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(summary(p))
    return dur


def summary(p):
    names = [s["name"] for s in p["ser"]]
    return (f"1위 바뀜: " + ", ".join(f"{t:.1f}초 {names[i]}" for t, i in p["lead"]) +
            f" / 순위 바뀜 {len(p['swaps'])}번 / 1위 {names[p['winner']]} "
            f"{fmt_value(p['ser'][p['winner']]['pts'][-1]['v'], p['fmt'])} / 본편 {p['win_end']:.1f}초")


def preview_times(p, total):
    """미리보기: 0.3초, 3초, 본편 1/3·1/2·2/3, 1위 바뀐 0.6초 뒤(마지막 2개), 끝 장면, 끝 화면."""
    L = p["race_len"]
    ts = [0.3, 3.0, L / 3, L / 2, L * 2 / 3] + [t + 0.6 for t, _ in p["lead"][1:]][-2:] + [p["race_end"] + 1.5]
    if total > p["win_end"] + 0.5:
        ts.append(total - 1.0)
    return sorted(set(round(t, 2) for t in ts))


def check_race(post):
    """막대 경주 릴스 검사 (errors, warnings)."""
    errors, warnings = [], []
    R = post.get("race")
    if not isinstance(R, dict):
        return ["race는 {format, series: [{name, color, points: [{date, value, src, url}]}], unit_label, images} 객체 "
                "(TEMPLATES.md '막대 경주 릴스')"], warnings
    if R.get("format", "people_m") not in FORMATS:
        errors.append(f"race.format은 {FORMATS} 중 하나")
    ser = R.get("series") or []
    if not 2 <= len(ser) <= 8:
        errors.append(f"race.series는 2~8개: 지금 {len(ser)}개")
    for s in ser:
        nm = str(s.get("name", "")).strip()
        if not nm:
            errors.append("race.series: name 필요")
        pts = s.get("points") or []
        if not pts:
            errors.append(f"race.series {nm}: points 1개 이상")
        prev = ""
        for p in pts:
            try:
                _d(p.get("date"))
            except (TypeError, ValueError):
                errors.append(f"race {nm}: date는 YYYY-MM-DD ({p.get('date')!r})")
                continue
            if not isinstance(p.get("value"), (int, float)) or p["value"] < 0:
                errors.append(f"race {nm} {p['date']}: value는 0 이상 숫자")
            if not str(p.get("url", "")).startswith("http") or not str(p.get("src", "")).strip():
                errors.append(f"race {nm} {p['date']}: src(누가·어디서)와 url(확인한 출처) 필요 — 확인한 수치만 쓴다")
            if p.get("kind") not in ("official", "reported"):
                warnings.append(f"race {nm} {p['date']}: kind(official/reported)를 적으면 rights_note·검토가 쉽다")
            if p["date"] <= prev:
                errors.append(f"race {nm}: 날짜 순서·중복 ({p['date']})")
            prev = p["date"]
    if not str(R.get("unit_label", "")).strip():
        errors.append("race.unit_label 필수: 날짜 옆 작은 단위 라벨 한 줄 (예: '사용자 수(명) · ChatGPT는 주간', STYLE_GUIDE 0 원칙 10)")
    elif len(R["unit_label"]) > 24:
        errors.append(f"race.unit_label은 24자 이하 (작은 라벨 하나): {len(R['unit_label'])}자")
    pl = [l for l in str(R.get("punch", "")).splitlines() if l.strip()]
    if len(pl) > 2 or any(len(l) > 16 for l in pl):
        errors.append("race.punch는 1~2줄, 줄당 16자 이하 (없어도 됨)")
    if post.get("rights") != "own":
        errors.append("막대 경주 릴스는 직접 그린 그래프: rights는 own")
    names = [s.get("name") for s in ser]
    for im in R.get("images") or []:
        if im.get("series") not in names:
            errors.append(f"race.images: series '{im.get('series')}'가 race.series 이름에 없음")
        if not im.get("src") or not str(im.get("credit", "")).strip():
            errors.append(f"race.images {im.get('series')}: src와 credit(저작자·라이선스) 필요")
    ts = R.get("thumb_src")
    if ts and (post.get("thumb") or {}).get("image", {}).get("src") != ts:
        warnings.append("race.thumb_src와 thumb.image.src가 다름 (렌더링이 그린 그림을 썸네일로 쓰려면 같게)")
    if not errors:
        p = plan(post)
        total = p["win_end"] + (END_LEN if ((post.get("dm") or {}).get("cta") or post.get("end_cta")) else 0)
        if not LENGTH_RANGE[0] <= total <= LENGTH_RANGE[1]:
            errors.append(f"막대 경주 릴스 길이 {total:.1f}초 ({LENGTH_RANGE[0]:g}~{LENGTH_RANGE[1]:g}초)")
        if not ((post.get("dm") or {}).get("cta") or post.get("end_cta")):
            warnings.append("끝 화면 없음: 소식 릴스는 end_cta (STYLE_GUIDE 0 원칙 8)")
    return errors, warnings


if __name__ == "__main__":
    f = Path(sys.argv[1])
    post = json.loads((f / "post.json").read_text(encoding="utf-8"))
    print(check_race(post))
    print(summary(plan(post)))
