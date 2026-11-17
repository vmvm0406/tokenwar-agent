"""연표 릴스 (post type "video" + "timeline", 운영자 요청 2026-11-17 "AI 신모델 개발 간격 / 지수적으로 발전한다는 걸 보여주자").

실제 출시일 목록(timeline.events)을 세로 화면(1080x1920) 위 연표에 점으로 찍는다. 점이 점점 빨리 들어오고
심장 박동 같은 효과음도 따라 빨라지며, 아래 숫자(그해 새 모델 사이 평균 간격)가 '개월 → 주 → 일'로 줄어든다.
끝에는 점이 누적 곡선으로 모이고, (선택) METR '혼자 끝내는 일의 길이' 추세선이 화면 위로 뚫고 나간다.
화면은 계속 움직인다(정지 화면 없음). 길이는 본편 약 25초 + '자료' 끝 화면 2.5초.

장면 (본편 시각):
    0~2.4초    첫 화면: 다 찍힌 연표 + 제목 두 줄이 쾅 박히고(쿵) 올해 평균 간격 숫자가 박힌다. 올해 점이 차례로 번쩍(박동)
    2.4~2.9초  되감기: 점이 오른쪽부터 사라지며 처음(2020)으로 (휙). 제목은 작아져 위쪽 자리로
    2.9~17.9초 재생: 점 하나 = 실제 모델 하나. 영상 속 간격은 실제 간격의 0.6제곱에 비례 (먼 간격은 길게, 촘촘한 간격은 짧게)
               → 점이 들어오는 속도가 계속 빨라진다. 숫자는 그해 지금까지 들어온 간격의 평균 (정직한 누적 평균)
    17.9~22.6초 점이 누적 출시 수 곡선으로 모인 뒤, METR 추세선(2배 되는 기간 timeline.metr)이 화면 위로 뚫고 나감
    22.6~25.1초 기간별 평균 간격 표 (timeline.periods), 마지막 줄이 쾅
    끝         dm.cta 끝 화면 2.5초 (video.append_cta_card), 3초부터 '자료' 안내 띠 (banner.apply_banner)

글자 자리: 모두 안전 영역(config.json reel_safe) 안. 오른쪽 아래 버튼 줄(x 850~, y 1150~)에는 큰 숫자를 두지 않는다.
디자인: 검정 배경 + #00FF66 점·선·큰 숫자, 제목·숫자 Black Han Sans, 설명 Wanted Sans. 그라데이션·둥근 카드·이모지 없음.
소리: 코드로 만든 어두운 패드 + 점마다 심장 박동(쿵) + 쾅·휙·상승음(music_gen.make_hook_sfx) → -14 LUFS (loudness.normalize).

post.json:
  "timeline": {
    "events": [{"date": "2023-03-14", "lab": "OpenAI", "name": "GPT-4", "url": "공식 발표 주소"}, ...],   # 5개 이상, 날짜 순
    "periods": [["2020~22년", 2020, 2022], ["2023년", 2023, 2023], ...],   # 끝 표 (선택, 없으면 해마다)
    "unit_note": "주요 AI 모델 55개 · 각 회사 공식 발표",                  # 연표 아래 작은 출처 줄
    "metr": {"label", "long", "recent", "recent_from", "long_months", "recent_months", "source"},   # 선택
    "thumb_src": "img/thumb.jpg"   # 렌더링이 그리는 썸네일 바탕 그림 (thumb.image.src와 같게)
  }
사용법: render.py가 부른다. 단독 미리보기: py -3.12 agent/timeline_reel.py <게시물 폴더> --plan
"""
import asyncio
import base64
import datetime as dt
import json
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

HOOK, REWIND = 2.4, 0.5
TL_START = HOOK + REWIND          # 2.9
TL_LEN = 15.0
CURVE_LEN = 4.7
END_LEN = 2.5
GAP_POWER = 0.6                   # 영상 속 간격 = 실제 간격^0.6 (비례 상수는 TL_LEN에 맞춤)
MIN_STEP = 0.07                   # 같은 날 나온 모델도 0.07초는 띄운다
LENGTH_RANGE = (20.0, 35.0)       # 끝 화면 포함
LABS = ["OpenAI", "Google", "Anthropic", "Meta", "xAI", "DeepSeek"]


def fmt_gap(days):
    """간격 표기: 60일 이상 'N개월', 28일 이상 'N주', 그 아래 'N일'."""
    if days >= 60:
        return f"{round(days / 30.44)}개월"
    if days >= 28:
        return f"{round(days / 7)}주"
    return f"{round(days)}일"


def _d(s):
    return dt.date.fromisoformat(str(s))


def periods_of(post):
    tl = post["timeline"]
    if tl.get("periods"):
        return [(str(a), int(b), int(c)) for a, b, c in tl["periods"]]
    ys = sorted({_d(e["date"]).year for e in tl["events"]})
    return [(f"{y}년", y, y) for y in ys]


def gap_stats(post):
    """기간별 평균 간격(일): [(이름, 평균, 간격 수)]. 간격은 뒤 모델이 나온 해의 기간에 넣는다."""
    ev = sorted(post["timeline"]["events"], key=lambda e: e["date"])
    ds = [_d(e["date"]) for e in ev]
    out = []
    for name, a, b in periods_of(post):
        g = [(ds[i] - ds[i - 1]).days for i in range(1, len(ds)) if a <= ds[i].year <= b]
        if g:
            out.append((name, sum(g) / len(g), len(g)))
    return out


def plan(post):
    """화면 계획 (JS로 넘김): 점 위치·등장 시각, 숫자 변화, 장면 시각."""
    tl = post["timeline"]
    ev = sorted(tl["events"], key=lambda e: e["date"])
    ds = [_d(e["date"]) for e in ev]
    gaps = [max(0, (ds[i] - ds[i - 1]).days) for i in range(1, len(ds))]
    w = [g ** GAP_POWER for g in gaps]
    usable = TL_LEN - 0.75
    k = usable / (sum(w) or 1)
    steps = [max(MIN_STEP, x * k) for x in w]
    k2 = (usable - (sum(steps) - usable if sum(steps) > usable else 0)) / sum(steps)
    steps = [s * min(1.0, k2) for s in steps]
    times = [TL_START + 0.25]
    for s in steps:
        times.append(times[-1] + s)
    x0d, x1d = dt.date(ds[0].year, 1, 1), dt.date(ds[-1].year, 12, 31)
    span = (x1d - x0d).days
    periods = periods_of(post)

    def period_of(y):
        return next((p for p in periods if p[1] <= y <= p[2]), (f"{y}년", y, y))
    counters = [None]
    run = {}
    for i in range(1, len(ds)):
        p = period_of(ds[i].year)
        run.setdefault(p[0], []).append(gaps[i - 1])
        r = run[p[0]]
        counters.append({"label": f"{p[0]} 평균 간격", "value": fmt_gap(sum(r) / len(r)), "days": sum(r) / len(r)})
    years = list(range(ds[0].year, ds[-1].year + 1))
    stats = gap_stats(post)
    m = tl.get("metr")
    tl_end = TL_START + TL_LEN
    curve_end = tl_end + CURVE_LEN
    hook_pulse = [i for i, d in enumerate(ds) if d.year == ds[-1].year]
    return {
        "ev": [{"name": e["name"], "lab": e["lab"], "date": e["date"].replace("-", "."),
                "u": (d - x0d).days / span, "row": LABS.index(e["lab"]) if e["lab"] in LABS else len(LABS) - 1,
                "t": t, "days": (d - x0d).days} for e, d, t in zip(ev, ds, times)],
        "counters": counters, "labs": LABS, "years": years, "x0year": ds[0].year, "span": span,
        "hook": HOOK, "rewind": REWIND, "tl_start": TL_START, "tl_end": tl_end, "curve_end": curve_end,
        "end": curve_end + END_LEN, "hook_pulse": hook_pulse,
        "title": str(post["title"]).split("\n"), "hl": post.get("highlight") or "",
        "note": tl.get("unit_note", ""),
        "rows": [{"name": n, "value": fmt_gap(a)} for n, a, _ in stats],
        "metr": m, "last_year": ds[-1].year, "last_days": (ds[-1] - x0d).days,
        "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM, "side": SIDE},
    }


def sfx_times(p):
    """효과음 시각 (화면이 바뀌는 프레임 시각)."""
    pulses = []
    n = len(p["hook_pulse"])
    for j in range(n):
        pulses.append(0.75 + j * (HOOK - 0.95) / max(1, n - 1))
    marks = [e["t"] for e in p["ev"]]
    cur = p["tl_end"]
    morph = cur + 0.0
    metr_on = cur + 1.45
    pen0, pen1 = cur + 1.75, cur + 4.45
    switch = None
    if p["metr"]:
        frac = _metr_switch_frac(p)
        switch = pen0 + (pen1 - pen0) * frac
    rows = [p["curve_end"] + 0.15 + 0.22 * i for i in range(len(p["rows"]))]
    return {"impacts": [0.0, 0.3, 0.62], "pulses": pulses, "marks": marks, "whoosh_end": [TL_START],
            "morph": morph, "metr_on": metr_on, "pen": (pen0, pen1), "switch": switch,
            "exit": pen1, "rows": rows}


def _metr_switch_frac(p):
    """METR 추세선에서 '최근' 구간이 시작하는 x 비율 (펜 진행 비율로 씀, JS penX와 같은 식)."""
    m = p["metr"]
    y0 = p["x0year"] - 1
    a = (dt.date(int(m.get("recent_from", 2023)), 1, 1) - dt.date(y0, 1, 1)).days
    b = (dt.date(p["last_year"], 11, 15) - dt.date(y0, 1, 1)).days
    return (a / b) ** 0.5  # JS 펜 진행: x = u^2 (끝으로 갈수록 빨라짐) → u = sqrt(x)


def page_html(post, p, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    js = (ROOT / "agent" / "timeline_reel.js").read_text(encoding="utf-8")
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
        problems = await pg.evaluate("twProblems()")
        for k, t in enumerate(times):
            data = await pg.evaluate(f"twFrame({t:.5f})")
            (out_dir / f"f{k:05d}.jpg").write_bytes(base64.b64decode(data.split(",", 1)[1]))
        if thumb_png:
            data = await pg.evaluate("twThumb()")
            Path(thumb_png).write_bytes(base64.b64decode(data.split(",", 1)[1]))
        await browser.close()
    return problems


# ---------- 소리 ----------

def _heartbeat(n_sr, strong=True, rng=None):
    """심장 박동 한 번: 160→60Hz로 떨어지는 짧은 쿵 + 작은 클릭 (폰 스피커에서도 들리게 중저음)."""
    import numpy as np
    from music_gen import SR, env, lowpass
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    f = 60 + 100 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.05)
    x += 0.35 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * env(n, 0.001, 0.02)
    if rng is not None:
        c = rng.standard_normal(n) * env(n, 0.0005, 0.006) * 0.25
        x += c - lowpass(c, 4)
    return x * (1.0 if strong else 0.6)


def make_pad(out_wav, total, rise=None):
    """어두운 패드(Am → F → C → E, 마디 길이 2.4초) + 낮은 지속음. rise=(시작, 끝)이면 그 구간 동안 패드가 밝아진다."""
    import numpy as np
    import wave
    from music_gen import SR, hz, tone, lowpass
    n = int((total + 0.5) * SR)
    L = np.zeros(n)
    R = np.zeros(n)
    chords = [(45, 52, 57, 60), (41, 48, 53, 57), (36, 48, 52, 55), (40, 47, 52, 56)]
    bar = 2.4
    nb = int(total / bar) + 1
    for i in range(nb):
        c = chords[i % 4]
        d = int((bar + 0.6) * SR)
        bright = 18
        if rise:
            fr = min(1, max(0, (i * bar - rise[0]) / max(0.1, rise[1] - rise[0])))
            bright = int(18 - 12 * fr)
        pad = sum(lowpass(tone(hz(m), d, "saw", r=2.5, a=0.5) + tone(hz(m) * 1.005, d, "saw", r=2.5, a=0.5), bright)
                  for m in c) / 8
        i0 = int(i * bar * SR)
        k = min(d, n - i0)
        if k <= 0:
            break
        L[i0:i0 + k] += pad[:k]
        R[i0:i0 + k] += pad[:k] * 0.92
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * hz(33) * t) * 0.25
    L += sub
    R += sub
    st = np.stack([L, R], axis=1)[: int(total * SR)]
    fo = int(1.2 * SR)
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    st[: int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR))[:, None]
    st = st / (np.max(np.abs(st)) or 1) * 0.8
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def make_sfx(p, total):
    import numpy as np
    from music_gen import SR, make_hook_sfx
    s = sfx_times(p)
    hits = [s["morph"], s["metr_on"]] + s["rows"][:-1] + ([s["switch"]] if s["switch"] else [])
    base, info = make_hook_sfx(total, impacts=s["impacts"] + [s["exit"], s["rows"][-1]] if s["rows"] else s["impacts"],
                               hits=hits, whooshes=s["whoosh_end"] + [s["morph"] + 0.6],
                               riser_to=s["exit"], riser_len=min(2.4, s["exit"] - s["pen"][0]), drop=None)
    rng = np.random.default_rng(5)
    n = int(round(total * SR))
    heart = np.zeros(n)

    def add(sig, t0, g=1.0):
        i = int(round(t0 * SR))
        if 0 <= i < n:
            m = min(len(sig), n - i)
            heart[i:i + m] += sig[:m] * g
    beats = s["pulses"] + s["marks"]
    for j, t0 in enumerate(beats):
        nxt = beats[j + 1] if j + 1 < len(beats) else t0 + 1
        add(_heartbeat(SR, True, rng), t0)
        if nxt - t0 > 0.42:      # 간격이 넉넉하면 '쿵-쿵' (두 번째는 약하게)
            add(_heartbeat(SR, False, rng), t0 + 0.17, 0.7)
    heart = heart / (np.max(np.abs(heart)) or 1)
    mix = base * 0.85 + np.stack([heart, heart], axis=1) * 0.9
    mix = mix / (np.max(np.abs(mix)) or 1)
    info["onsets"]["heartbeats"] = len(beats)
    return mix, info


# ---------- 렌더링 ----------

def make_timeline_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/*.jpg, timeline.thumb_src(썸네일 바탕). 전체 길이(초)."""
    folder = Path(folder)
    p = plan(post)
    work = folder / "_timeline"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html_file = work / "timeline.html"
    html_file.write_text(page_html(post, p, cfg), encoding="utf-8")
    main = p["end"]
    nfr = int(round(main * FPS))
    thumb_rel = post["timeline"].get("thumb_src")
    thumb_png = work / "thumb.png" if thumb_rel else None
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
    # 소리: 패드 + 효과음(심장 박동·쾅·휙·상승음) → listreel.mix_audio (효과음은 음악보다 3dB 크게)
    from listreel import mix_audio
    pm = post.get("music") or {}
    if pm.get("src") and (folder / pm["src"]).exists():     # 실제 음원 조각 (agent/music_fit.py, STYLE_GUIDE 0 원칙)
        music = folder / pm["src"]
    else:                                                    # 대체: 코드로 만든 패드
        music = work / "music.wav"
        make_pad(music, main, rise=(p["tl_start"], p["tl_end"]))
    sfx, info = make_sfx(p, main)
    mixed = work / "mix.wav"
    mix_audio(music, [], main, mixed, sfx)
    on = info["onsets"]
    print(f"효과음: 심장 박동 {on['heartbeats']}번, 쾅 {', '.join(f'{x:.2f}' for x in on['impact'])}, "
          f"휙 {', '.join(f'{x:.2f}' for x in on['whoosh_end'])}")
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{main:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    dur = main
    from banner import banner_text, make_banner_png, apply_banner
    bt = banner_text(post)
    if bt:
        png = make_banner_png(bt, cfg, W - 2 * SIDE, work / "banner.png")
        apply_banner(out, png, SIDE, SAFE_TOP, dur)
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
    st = gap_stats(post)
    print(f"연표 {len(p['ev'])}개, 기간별 평균 간격: " + ", ".join(f"{n} {a:.1f}일({c}개)" for n, a, c in st))
    print(f"점 간격(영상): 처음 {p['ev'][1]['t'] - p['ev'][0]['t']:.2f}초 → 마지막 {p['ev'][-1]['t'] - p['ev'][-2]['t']:.2f}초")
    return dur


def preview_times(p, total):
    """미리보기: 0.3초, 1초, 재생 중간 두 곳, 곡선, 끝 표, 끝 화면."""
    a, b = p["tl_start"], p["tl_end"]
    ts = [0.3, 1.0, a + (b - a) * 0.35, a + (b - a) * 0.8, p["tl_end"] + 3.9, p["end"] - 0.3]
    if total > p["end"] + 0.5:
        ts.append(total - 1.0)
    return ts


def check_timeline(post):
    """연표 릴스 검사 (errors, warnings)."""
    errors, warnings = [], []
    tl = post.get("timeline")
    if not isinstance(tl, dict):
        return ["timeline은 {events: [{date, lab, name, url}], periods, metr, thumb_src} 객체 (TEMPLATES.md '연표 릴스')"], warnings
    ev = tl.get("events") or []
    if len(ev) < 5:
        errors.append(f"timeline.events는 5개 이상: 지금 {len(ev)}개")
    prev = ""
    for i, e in enumerate(ev, 1):
        try:
            _d(e.get("date"))
        except (TypeError, ValueError):
            errors.append(f"timeline.events {i}: date는 YYYY-MM-DD ({e.get('date')!r})")
            continue
        if not str(e.get("name", "")).strip() or not str(e.get("lab", "")).strip():
            errors.append(f"timeline.events {i}: name·lab 필요")
        if not str(e.get("url", "")).startswith("http"):
            errors.append(f"timeline.events {i} ({e.get('name')}): url(공식 발표 주소) 필요 — 실제 날짜만 쓴다")
        if e["date"] < prev:
            errors.append(f"timeline.events {i}: 날짜 순서가 아님 ({e['date']} < {prev})")
        prev = e["date"]
        if e.get("lab") not in LABS:
            warnings.append(f"timeline.events {i}: lab '{e.get('lab')}'은 줄 목록 {LABS} 밖 → 마지막 줄에 그린다")
    if post.get("rights") != "own":
        errors.append("연표 릴스는 직접 그린 그래프: rights는 own")
    m = tl.get("metr")
    if m:
        for k in ("label", "long", "recent", "source"):
            if not str(m.get(k, "")).strip():
                errors.append(f"timeline.metr.{k} 필요")
        if not any("metr" in str(s.get("url", "")).lower() for s in post.get("sources", [])):
            errors.append("timeline.metr를 쓰면 sources에 METR 원문 주소")
    ts = tl.get("thumb_src")
    if ts and (post.get("thumb") or {}).get("image", {}).get("src") != ts:
        warnings.append("timeline.thumb_src와 thumb.image.src가 다름 (렌더링이 그린 그림을 썸네일로 쓰려면 같게)")
    if not errors and ev:
        total = TL_START + TL_LEN + CURVE_LEN + END_LEN + (2.5 if ((post.get("dm") or {}).get("cta") or post.get("end_cta")) else 0)
        if not LENGTH_RANGE[0] <= total <= LENGTH_RANGE[1]:
            errors.append(f"연표 릴스 길이 {total:.1f}초 ({LENGTH_RANGE[0]:g}~{LENGTH_RANGE[1]:g}초)")
    return errors, warnings


if __name__ == "__main__":
    f = Path(sys.argv[1])
    post = json.loads((f / "post.json").read_text(encoding="utf-8"))
    p = plan(post)
    for n, a, c in gap_stats(post):
        print(f"{n}: 평균 {a:.1f}일 ({fmt_gap(a)}), 간격 {c}개")
    print("효과음 시각:", json.dumps(sfx_times(p), default=float)[:400])
