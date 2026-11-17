"""연표 릴스 (post type "video" + "timeline", 운영자 요청 2026-11-17 "AI 신모델 개발 간격 / 지수적으로 발전한다는 걸 보여주자").

한 가지 생각만: 새 모델이 점점 빨리 나온다. 결과(숫자)는 끝에만 (운영자 2026-11-17 "초반부터 결과 내용 보여주지마").
흐름: 제목 질문(0초 쾅) → 연표 재생(점이 점점 빨리 들어옴, 대표 모델에서 잠깐 멈춰 그림 + 특징 한 줄) → 끝 정리 화면
'새 모델 하나 나오는 데 걸린 시간' (기간마다 'N개월에 1개' 막대, 마지막 줄 쾅, 다 뜬 뒤 3.5초 이상 그대로 읽힘).
회사 줄 앞에는 로고(assets/logos, 작게, 지명적 사용) + 회사 색 이름, 점도 회사 색. 로고가 없는 회사는 회사 색 점.
제목 두 줄과 0초 한 줄(timeline.cta_line)은 0초부터 끝까지 같은 자리. 재생 중 아래 숫자는 '출시된 주요 모델 N개'(결과 아님).

장면 (본편 시각):
    0~0.5초     제목 쾅(줄마다) + 빈 연표
    0.5초~      재생: 점 하나 = 실제 모델 하나. 영상 속 간격은 실제 간격의 0.6제곱에 비례 → 점이 계속 빨라진다.
                timeline.beats의 모델이 찍히면 BEAT_LEN초 멈추고 그 모델 그림(점에서 튀어나옴) + 이름 + 특징 한 줄
    재생 끝~    정리 화면 SUM_LEN초
    끝          끝 화면 2.5초 (dm.cta 또는 post.end_cta, video.append_cta_card)

글자 자리: 모두 안전 영역(config.json reel_safe) 안. 오른쪽 아래 버튼 줄(x 850~, y 1150~)에는 읽을 글을 두지 않는다.
디자인: 검정 배경 + #00FF66 재생선·큰 숫자, 점·회사 이름은 회사 색. 제목·숫자 Black Han Sans, 설명 Wanted Sans.
소리: 실제 음원 조각(post music.src, agent/music_fit.py) 또는 대체 패드 + 쾅·휙·점마다 부드러운 톡 → -14 LUFS.

post.json:
  "timeline": {
    "events": [{"date": "2023-03-14", "lab": "OpenAI", "name": "GPT-4", "url": "공식 발표 주소"}, ...],   # 5개 이상, 날짜 순
    "beats": [{"name": "GPT-4", "text": "모의 변호사 시험 상위 10%",                                     # 선택, 6개 안팎
               "image": {"type": "image", "src": "img/beat-gpt4.jpg", "prompt": "...", "size": [1344, 1088]}}],
    "periods": [["2020~22년", 2020, 2022], ["2023년", 2023, 2023], ...],   # 끝 정리 (선택, 없으면 해마다)
    "unit_note": "주요 AI 모델 56개 · 각 회사 공식 발표",                  # 연표 아래 작은 출처 줄
    "cta_line": "AI 속도, 무섭다 vs 기대된다? 댓글로",                       # 0초 한 줄 (선택, '댓글로'는 초록)
    "thumb_src": "img/thumb.jpg"   # 렌더링이 그리는 썸네일 바탕 그림 (thumb.image.src와 같게)
  }
사용법: render.py가 부른다. 단독 확인: py -3.12 agent/timeline_reel.py <게시물 폴더>
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

TL_START = 0.5                    # 제목 쾅 뒤 바로 재생
TL_LEN = 13.0                     # 점만 찍히는 시간 (그림 멈춤 제외)
BEAT_LEN = 1.1                    # 대표 모델 그림 멈춤
TAIL = 0.6                        # 마지막 점 뒤
SUM_LEN = 5.5                     # 끝 정리 화면 (줄이 다 뜬 뒤 3.5초 이상 그대로)
GAP_POWER = 0.6                   # 영상 속 간격 = 실제 간격^0.6 (비례 상수는 TL_LEN에 맞춤)
MIN_STEP = 0.07                   # 같은 날 나온 모델도 0.07초는 띄운다
LENGTH_RANGE = (20.0, 35.0)       # 끝 화면 포함
LABS = ["OpenAI", "Google", "Anthropic", "Meta", "xAI", "DeepSeek"]
# 회사 색·로고 (assets/logos, Simple Icons CC0. 로고 파일이 없는 회사는 회사 색 점 + 회사 색 이름)
LAB_INFO = {
    "OpenAI": {"color": "#FFFFFF", "logo": "openai.svg"},
    "Google": {"color": "#4285F4", "logo": "google.svg"},
    "Anthropic": {"color": "#D97757", "logo": "anthropic.svg"},
    "Meta": {"color": "#0A7CFF", "logo": "meta.svg"},
    "xAI": {"color": "#B9B9B9"},
    "DeepSeek": {"color": "#6F86FF"},
}


def lab_info():
    """JS로 넘길 회사 정보: {회사: {color, short, logo(data URL, 회사 색으로 칠한 SVG)}}."""
    out = {}
    for lab, v in LAB_INFO.items():
        d = {"color": v["color"], "short": lab}
        f = ROOT / "assets" / "logos" / v.get("logo", "-")
        if v.get("logo") and f.exists():
            svg = f.read_text(encoding="utf-8").replace("<svg ", f'<svg fill="{v["color"]}" ', 1)
            d["logo"] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()
        out[lab] = d
    return out


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


def plan(post, folder=None):
    """화면 계획 (JS로 넘김): 점 위치·등장 시각, 그림 멈춤, 장면 시각."""
    tl = post["timeline"]
    ev = sorted(tl["events"], key=lambda e: e["date"])
    ds = [_d(e["date"]) for e in ev]
    gaps = [max(0, (ds[i] - ds[i - 1]).days) for i in range(1, len(ds))]
    w = [g ** GAP_POWER for g in gaps]
    usable = TL_LEN - 0.4
    k = usable / (sum(w) or 1)
    steps = [max(MIN_STEP, x * k) for x in w]
    k2 = (usable - (sum(steps) - usable if sum(steps) > usable else 0)) / sum(steps)
    steps = [s * min(1.0, k2) for s in steps]
    beat_of = {}
    for b in tl.get("beats") or []:
        j = next((i for i, e in enumerate(ev) if e["name"] == b.get("name")), None)
        if j is not None:
            beat_of[j] = b
    times, beats, t = [], [], TL_START + 0.2
    for i in range(len(ev)):
        if i:
            t += steps[i - 1]
        times.append(t)
        if i in beat_of:
            b = beat_of[i]
            img = None
            src = (b.get("image") or {}).get("src")
            if folder and src and (Path(folder) / src).exists():
                img = "data:image/jpeg;base64," + base64.b64encode((Path(folder) / src).read_bytes()).decode()
            beats.append({"i": i, "t0": t + 0.1, "name": ev[i]["name"], "lab": ev[i]["lab"],
                          "text": str(b.get("text", "")), "img": img})
            t += BEAT_LEN
    x0d, x1d = dt.date(ds[0].year, 1, 1), dt.date(ds[-1].year, 12, 31)
    span = (x1d - x0d).days
    years = list(range(ds[0].year, ds[-1].year + 1))
    stats = gap_stats(post)
    tl_end = times[-1] + TAIL
    rows_t = [tl_end + 0.45 + 0.3 * i for i in range(len(stats))]
    return {
        "ev": [{"name": e["name"], "lab": e["lab"], "date": e["date"].replace("-", "."),
                "u": (d - x0d).days / span, "row": LABS.index(e["lab"]) if e["lab"] in LABS else len(LABS) - 1,
                "t": t} for e, d, t in zip(ev, ds, times)],
        "beats": beats, "beat_len": BEAT_LEN,
        "labs": LABS, "lab_info": lab_info(), "years": years, "x0year": ds[0].year, "span": span,
        "tl_start": TL_START, "tl_end": tl_end, "end": tl_end + SUM_LEN,
        "title": str(post["title"]).split("\n"), "hl": post.get("highlight") or "",
        "note": tl.get("unit_note", ""), "cta": (tl.get("cta_line") or "").strip(),
        "rows": [{"name": n, "value": f"{fmt_gap(a)}에 1개", "days": a} for n, a, _ in stats], "rows_t": rows_t,
        "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM, "side": SIDE},
    }


def sfx_times(p):
    """효과음 시각 (화면이 바뀌는 프레임 시각, JS와 같은 식)."""
    return {"impacts": [0.0, 0.3] + p["rows_t"][-1:], "hits": p["rows_t"][:-1],
            "marks": [e["t"] for e in p["ev"]],
            "whoosh_end": [b["t0"] + 0.12 for b in p["beats"]] + [p["tl_end"] + 0.3],
            "riser": (p["ev"][len(p["ev"]) * 2 // 3]["t"], p["tl_end"])}


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
        await pg.evaluate("twReady()")
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
    """쾅(제목·정리 마지막 줄), 휙(그림 등장·정리 화면), 점마다 부드러운 톡(500→1000Hz로 조금씩 올라감, 날카로운 고음 없음),
    재생 끝 무렵 상승음. 심장 박동은 뺐다 (2026-11-17)."""
    import numpy as np
    from music_gen import SR, env, make_hook_sfx
    s = sfx_times(p)
    r0, r1 = s["riser"]
    base, info = make_hook_sfx(total, impacts=s["impacts"], hits=s["hits"], whooshes=s["whoosh_end"],
                               riser_to=r1, riser_len=max(0.5, min(3.0, r1 - r0)), drop=None)
    n = len(base)
    tok = np.zeros(n)
    beats = s["marks"]
    for k, t0 in enumerate(beats):
        m = int(0.07 * SR)
        f = 500 + 500 * k / max(1, len(beats) - 1)
        x = np.sin(2 * np.pi * f * np.arange(m) / SR) * env(m, 0.002, 0.025)
        i = int(round(t0 * SR))
        if 0 <= i < n:
            tok[i:i + m] += x[:n - i]
    tok = tok / (np.max(np.abs(tok)) or 1) * 0.45
    mix = base + np.stack([tok, tok], axis=1)
    info["onsets"]["toks"] = len(beats)
    return mix / (np.max(np.abs(mix)) or 1), info


# ---------- 렌더링 ----------

def make_timeline_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/*.jpg, timeline.thumb_src(썸네일 바탕). 전체 길이(초)."""
    folder = Path(folder)
    p = plan(post, folder)
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
    # 소리: 음원 + 효과음(쾅·휙·틱·상승음) → listreel.mix_audio (효과음은 음악보다 3dB 크게)
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
    print(f"효과음: 톡 {on['toks']}번, 쾅 {', '.join(f'{x:.2f}' for x in on['impact'])}, "
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
    """미리보기: 0.3초, 그림 멈춤마다 가운데, 재생 끝 직전, 정리 화면 끝, 끝 화면."""
    ts = [0.3] + [b["t0"] + p["beat_len"] * 0.5 for b in p["beats"]] + [p["tl_end"] - 0.4, p["end"] - 0.3]
    if total > p["end"] + 0.5:
        ts.append(total - 1.0)
    return ts


def check_timeline(post):
    """연표 릴스 검사 (errors, warnings)."""
    errors, warnings = [], []
    tl = post.get("timeline")
    if not isinstance(tl, dict):
        return ["timeline은 {events: [{date, lab, name, url}], periods, unit_note, cta_line, thumb_src} 객체 (TEMPLATES.md '연표 릴스')"], warnings
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
    names = [e.get("name") for e in ev]
    for j, b in enumerate(tl.get("beats") or [], 1):
        if b.get("name") not in names:
            errors.append(f"timeline.beats {j}: name '{b.get('name')}'이 events에 없음")
        txt = str(b.get("text", "")).strip()
        if not txt or len(txt) > 18:
            errors.append(f"timeline.beats {j}: text(특징 한 줄)는 1~18자: '{txt}'")
        im = b.get("image") or {}
        if not (im.get("src") and (im.get("prompt") or im.get("url"))):
            errors.append(f"timeline.beats {j}: image {{type, src, prompt 또는 url}} 필요")
    if tl.get("metr"):
        warnings.append("timeline.metr는 더 이상 화면에 그리지 않는다 (한 가지 생각만, 2026-11-17). 근거는 캡션에")
    ts = tl.get("thumb_src")
    if ts and (post.get("thumb") or {}).get("image", {}).get("src") != ts:
        warnings.append("timeline.thumb_src와 thumb.image.src가 다름 (렌더링이 그린 그림을 썸네일로 쓰려면 같게)")
    if not errors and ev:
        nb = len([b for b in tl.get("beats") or [] if any(e.get("name") == b.get("name") for e in ev)])
        total = TL_START + 0.2 + TL_LEN + nb * BEAT_LEN + TAIL + SUM_LEN + (2.5 if ((post.get("dm") or {}).get("cta") or post.get("end_cta")) else 0)
        if not LENGTH_RANGE[0] <= total <= LENGTH_RANGE[1]:
            errors.append(f"연표 릴스 길이 {total:.1f}초 ({LENGTH_RANGE[0]:g}~{LENGTH_RANGE[1]:g}초)")
    return errors, warnings


if __name__ == "__main__":
    f = Path(sys.argv[1])
    post = json.loads((f / "post.json").read_text(encoding="utf-8"))
    p = plan(post)
    for n, a, c in gap_stats(post):
        print(f"{n}: 평균 {a:.1f}일 ({fmt_gap(a)}), 간격 {c}개")
    print("본편", round(p["end"], 2), "초, 효과음 시각:", json.dumps(sfx_times(p), default=float)[:300])
