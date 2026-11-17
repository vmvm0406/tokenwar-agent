"""막대 경주 릴스 (post type "video" + "race", 2026-11-17).

회사·서비스별 실제 수치(사용자 수, 기업가치)를 날짜 순으로 쌓아 막대가 서로 앞지르는 '바 차트 레이스'로 보여 준다.
값은 **공식 발표·보도가 나온 날에만 바뀐다** (발표 사이를 지어내지 않음). 바뀔 때 0.45초 동안 부드럽게 늘어나고,
순위가 바뀌면 막대가 미끄러지며 자리를 바꾼다. 1·2위로 올라선 순간은 막대가 번쩍이고 날짜 옆에 짧은 띠('Meta AI 1위').
끝은 1위 막대만 녹색으로 남고 punch 한 줄이 쾅 박힌 뒤 end_cta 끝 화면.

장면 (본편):
    0초          제목 두 줄이 쾅 박히고(쿵) 첫 발표 막대가 이미 보인다. 날짜 숫자판이 바로 굴러간다
    0.6초~       발표마다 막대가 늘어나고(틱) 순위가 바뀌면 휙 + 타격 + 번쩍 + 띠
    race_end~    1위만 녹색, 나머지 흐리게, punch 한 줄 쾅 (3.2초, 1위 막대는 천천히 커짐 → 정지 화면 없음)
    끝           end_cta(또는 dm.cta) 끝 화면 2.5초 (video.append_cta_card)

발표 사이 영상 시간 = 실제 간격(일)^0.45에 비례 → 발표가 드문 초기는 빨리, 촘촘한 최근은 천천히 지나간다.
글자 자리: 모두 안전 영역(config.json reel_safe) 안. 날짜·띠는 오른쪽 아래 버튼 줄(x 850~) 왼쪽. 렌더링이 글자 폭을 검사한다.
디자인: 검정 배경, 막대는 회사 색 단색 직각(그라데이션·둥근 모서리·글로우 없음), 로고 대신 회사 이름 글자.
소리: 실제 음원 조각(music.src, agent/music_fit.py) + 효과음(music_gen.make_hook_sfx) → -14 LUFS.

post.json:
  "race": {
    "format": "people_m" | "usd_b",       # 값 단위: 백만 명 → '12억 명' / 십억 달러 → '1조 2,500억 달러'
    "end": "2026-11-17",                    # 숫자판 끝 날짜 (선택, 기본 마지막 발표일). 처음은 첫 발표일
    "series": [{"name": "ChatGPT", "color": "#10A37F", "tag": "주간",          # tag: 값 뒤 작은 글씨 (선택)
                "points": [{"date": "2023-11-06", "value": 100, "src": "출처 이름", "url": "https://...",
                            "kind": "official" | "reported", "note": "(선택)"}]}],
    "basis_line": "회사 공식 발표 · ChatGPT는 주간, 나머지 월간 사용자",   # 화면 위 작은 근거 줄 (필수, 40자 이하)
    "cta_line": "ChatGPT vs Gemini, 뭐 쓰세요?",   # 0초부터 제목 아래 한 줄 (선택)
    "punch": "일주일에 12억 명이\nChatGPT를 씁니다",  # 끝 한 줄 (필수, 2줄까지)
    "thumb_src": "img/thumb.jpg",           # 렌더링이 그리는 썸네일 바탕 (thumb.image.src와 같게)
    "beats": {                              # 선택. 이야기 박자 (운영자 승인 뼈대: 후킹 0~3 → 지연 → 반전 12~15 → 지연 → 답 25~30)
      "hook": "AI 사용자 1위,\\n지금은 누구?", "hook_until": 3,      # 0초부터 막대 칸 아래에 크게 (끝 1위는 아직 안 보임)
      "anchors": [["2024-08-29", 3], ["2026-02-04", 12], ["2026-07-22", 13.5], ["2026-09-29", 22]],  # [발표일, 영상 초]
      "rehook": {"date": "2026-07-22", "text": "ChatGPT 3위로"},  # 그 발표의 띠를 이 글로, 큰 쿵
      "ask": {"text": "1위 자리,\\n또 뒤집힐까?", "from": 15}  # from ~ 마지막 순위 바뀜(답)까지 날짜 옆에
    }
  }
사용법: render.py가 부른다. 계획만 보기: py -3.12 agent/racereel.py <게시물 폴더>
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
RAIL_LEFT = _SAFE.get("rail_left", 850)

FIRST = 0.6            # 첫 발표 다음 변화가 시작하는 시각
RACE_END = 21.0        # 마지막 발표 + 숫자판이 끝 날짜까지 가는 시각
LAST_HOLD = 0.9        # 마지막 발표 뒤 끝 날짜까지
WIN_LEN = 3.2          # 1위 + punch
TWEEN = 0.45
GAP_POWER = 0.45
MIN_STEP = 0.32
END_LEN = 2.5
LENGTH_RANGE = (20.0, 35.0)
FORMATS = ("people_m", "usd_b")


def _d(s):
    return dt.date.fromisoformat(str(s))


def fmt_value(v, fmt):
    """화면 값 표기 (JS fmtValue와 같은 규칙)."""
    if fmt == "people_m":
        if v >= 100:
            x = round(v / 100, 1)
            return f"{x:g}억 명"
        return f"{round(v * 100):,}만 명"
    eok = v * 10                      # 십억 달러 → 억 달러
    if eok >= 10000:
        jo, rest = divmod(round(eok), 10000)
        return f"{jo}조 {rest:,}억 달러" if rest else f"{jo}조 달러"
    if eok < 10:
        return f"{round(eok, 1):g}억 달러"
    return f"{round(eok):,}억 달러"


def plan(post):
    R = post["race"]
    series = R["series"]
    dates = sorted({p["date"] for s in series for p in s["points"]})
    ds = [_d(x) for x in dates]
    start = ds[0]
    end = _d(R.get("end") or dates[-1])
    gaps = [max(1, (ds[i] - ds[i - 1]).days) for i in range(1, len(ds))]
    # 영상 시각: 고정점(anchors, [발표일, 초]) 사이 발표는 실제 간격^GAP_POWER 비례로 나눈다.
    # 기본 고정점: 첫 발표 0초, 둘째 FIRST, 마지막 RACE_END - LAST_HOLD. beats.anchors로 이야기 박자(후킹·반전·답)에 맞춘다
    B = R.get("beats") or {}
    anchors = {dates[0]: 0.0}
    if B.get("anchors"):
        for d, t in B["anchors"]:
            anchors[str(d)] = float(t)
    else:
        if len(ds) > 1:
            anchors[dates[1]] = FIRST
        anchors[dates[-1]] = RACE_END - LAST_HOLD
    idx = sorted(dates.index(d) for d in anchors)
    times = [0.0] * len(ds)
    for a_i, b_i in zip(idx, idx[1:]):
        ta, tb = anchors[dates[a_i]], anchors[dates[b_i]]
        w = [gaps[j - 1] ** GAP_POWER for j in range(a_i + 1, b_i + 1)]
        c = 0.0
        for j, x in zip(range(a_i + 1, b_i + 1), w):
            c += x
            times[j] = ta + (tb - ta) * c / sum(w)
    times[0] = 0.0
    tmap = dict(zip(dates, times))
    # 숫자판: (영상 시각, 날짜 일수) 꺾은선
    keys = [(0.0, (start - start).days)]
    for x, t in zip(ds, times):
        if t > 0:
            keys.append((t, (x - start).days))
    last_t = times[-1]
    keys.append((last_t + LAST_HOLD, (end - start).days))
    ser = []
    for s in series:
        pts = sorted(s["points"], key=lambda p: p["date"])
        ser.append({"name": s["name"], "color": s.get("color", "#9AA59F"), "tag": s.get("tag", ""),
                    "pts": [{"t": tmap[p["date"]], "v": float(p["value"])} for p in pts]})
    race_end = last_t + LAST_HOLD
    p = {"fmt": R.get("format", "people_m"), "ser": ser, "keys": keys,
         "start": [start.year, start.month, start.day], "tween": TWEEN, "race_end": race_end,
         "win_end": race_end + WIN_LEN, "title": str(post["title"]).split("\n"), "hl": post.get("highlight") or "",
         "cta": (R.get("cta_line") or "").strip(), "basis": R.get("basis_line", ""),
         "punch": str(R.get("punch", "")).split("\n"),
         "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM, "side": SIDE, "rail": RAIL_LEFT}}
    p["overtakes"] = overtakes(p)
    # 이야기 박자 (운영자 승인 릴스 뼈대 2026-11-17): 후킹 질문(0~hook_until) → 반전(rehook) → 질문(ask) → 답
    p["hook"] = [l for l in str(B.get("hook", "")).splitlines() if l.strip()]
    p["hook_until"] = float(B.get("hook_until", 3.0))
    rh = B.get("rehook") or {}
    p["rehook_t"] = None
    if rh.get("date") in tmap:
        t0 = tmap[rh["date"]]
        o = next((o for o in p["overtakes"] if t0 - 1e-6 <= o["t"] <= t0 + TWEEN + 0.05), None)
        if o is None:
            o = {"t": t0 + 0.1, "i": -1, "rank": 0, "label": ""}
            p["overtakes"].append(o)
            p["overtakes"].sort(key=lambda x: x["t"])
        if rh.get("text"):
            o["label"] = rh["text"]
        o["rehook"] = True
        p["rehook_t"] = o["t"]
    p["answer_t"] = p["overtakes"][-1]["t"] if p["overtakes"] else race_end
    ak = B.get("ask") or {}
    p["ask"] = {"lines": [l for l in str(ak.get("text", "")).splitlines() if l.strip()],
                "from": float(ak.get("from", 15.0)), "to": p["answer_t"]} if ak.get("text") else None
    vals = [(s["pts"][-1]["v"], i) for i, s in enumerate(ser)]
    p["winner"] = max(vals)[1]
    p["event_times"] = sorted({pt["t"] for s in ser for pt in s["pts"] if pt["t"] > 0})
    p["spot"], p["hook_strip"] = spotlight(p, images_of(post))
    return p


def images_of(post):
    """race.images (사진 필수, STYLE_GUIDE 0장 원칙 0): [{series, src, x, y, dim, credit, url}] (dim: 사진 위 어둡게 0~1, 기본 0.6, 밝은 화면 캡처는 0.85) → {막대 번호: 항목}."""
    names = [s["name"] for s in post["race"]["series"]]
    out = {}
    for im in post["race"].get("images") or []:
        if im.get("series") in names and im.get("src"):
            out[names.index(im["series"])] = im
    return out


SPOT_HOLD = 1.6        # 배경 사진은 이 시간 안에 다시 바뀌지 않는다 (앞지르기는 0.6초)


def spotlight(p, imgs):
    """배경 사진 순서 [(시각, 막대 번호)]: 발표가 난 회사 사진으로 바뀌고(1.6초 이상 유지), 앞지르기·반전은 바로,
    답(마지막 순위 바뀜)부터는 1위 사진 고정. 후킹 동안은 경쟁 회사 사진 세 장을 세로로 나눠 보여 준다(끝 1위를 홀로 드러내지 않음)."""
    if not imgs:
        return [], []
    start = p["hook_until"] if p["hook"] else 0.0
    evs = sorted([(pt["t"], i, False) for i, s in enumerate(p["ser"]) for pt in s["pts"] if pt["t"] > 0] +
                 [(o["t"], o["i"], True) for o in p["overtakes"] if o["i"] >= 0])
    first = next((i for t, i, _ in reversed(evs) if t <= start and i in imgs), None)
    if first is None:
        first = next(i for i in range(len(p["ser"])) if i in imgs)
    spot = [(start, first)]
    for t, i, strong in evs:
        if t < start or i not in imgs or i == spot[-1][1] or t >= p["answer_t"] - 1e-6:
            continue
        if t - spot[-1][0] >= (0.6 if strong else SPOT_HOLD):
            spot.append((t, i))
    w = p["winner"]
    end = p["answer_t"]
    # 4초 넘게 같은 사진이면 그때 상위 3개 회사 사진을 2.4초마다 돌린다 (질문 구간에서 '누가?' 긴장)
    filled = []
    for k, (t0, i0) in enumerate(spot):
        filled.append((t0, i0))
        t1 = spot[k + 1][0] if k + 1 < len(spot) else end
        t = t0 + 2.4
        last = i0
        while t1 - t >= 1.6:
            top = [j for j in _order(p, t)[:3] if j in imgs and j != last]
            if not top:
                break
            last = top[0]
            filled.append((t, last))
            t += 2.4
    spot = filled
    if w in imgs and spot[-1][1] != w:
        spot.append((max(end, spot[-1][0] + 0.4), w))
    strip = []
    if p["hook"]:
        order = sorted(range(len(p["ser"])), key=lambda i: -max(pt["v"] for pt in p["ser"][i]["pts"]))
        strip = [i for i in order if i in imgs][:3]
    return [[round(t, 3), i] for t, i in spot], strip


def _ease_io(x):
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def _value_at(s, t):
    """화면에 보이는 값 (JS cur()와 같음: 발표 뒤 TWEEN초 동안 easeIO로 늘어남)."""
    k = -1
    for j, pt in enumerate(s["pts"]):
        if pt["t"] <= t:
            k = j
    if k < 0:
        return None
    pt = s["pts"][k]
    if pt["t"] == 0:
        return pt["v"]
    prev = s["pts"][k - 1]["v"] if k > 0 else 0.0
    return prev + (pt["v"] - prev) * _ease_io((t - pt["t"]) / TWEEN)


def _order(p, t):
    vs = [(_value_at(s, t), i) for i, s in enumerate(p["ser"])]
    present = sorted([x for x in vs if x[0] is not None], key=lambda x: (-x[0], x[1]))
    return [i for _, i in present]


def overtakes(p):
    """발표 시각마다 순위가 오른 것 중 1·2위로 올라선 것 (띠와 효과음). [{t, i, rank, label}]"""
    out = []
    ts = sorted({pt["t"] for s in p["ser"] for pt in s["pts"] if pt["t"] > 0})
    for t in ts:
        before, after = _order(p, t - 1e-4), _order(p, t + TWEEN + 0.01)
        best = None
        for r, i in enumerate(after, 1):
            if r > 2:
                break
            old = before.index(i) + 1 if i in before else None
            if old is None and len(after) == 1:
                continue
            if old is None or r < old:
                passed = [j for j in before[:old - 1 if old else len(before)] if j in after and after.index(j) + 1 > r]
                if passed and (best is None or r < best["rank"]):
                    # 띠·번쩍·효과음은 막대가 실제로 앞지르는 순간 (늘어나는 도중)
                    tc = next((t + k * 0.01 for k in range(int(TWEEN * 100) + 2)
                               if i in _order(p, t + k * 0.01)[:r] and _order(p, t + k * 0.01).index(i) + 1 == r), t)
                    best = {"t": round(tc, 3), "i": i, "rank": r, "label": f"{p['ser'][i]['name']} {r}위"}
        # 붙어 있는 발표에서 같은 앞지르기가 두 번 잡히면 하나만
        if best and not any(o["i"] == best["i"] and o["rank"] == best["rank"] and best["t"] - o["t"] < TWEEN + 0.2
                            for o in out):
            out.append(best)
    return out


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
    ot = [o["t"] for o in p["overtakes"]]
    ticks = [t for t in p["event_times"] if all(abs(t - o) > 0.05 for o in ot)]
    imp = [0.0, p["race_end"] + 0.05] + ([p["rehook_t"]] if p.get("rehook_t") else []) +           ([p["answer_t"]] if p["answer_t"] < p["race_end"] - 0.2 else [])
    return make_hook_sfx(total, impacts=imp, hits=[t + 0.12 for t in ot],
                         whooshes=[t + 0.1 for t in ot], riser_to=p["answer_t"],
                         riser_len=min(2.0, p["answer_t"] - 1), drop=None, ticks=ticks)


def make_race_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, -14 LUFS), frames/*.jpg, race.thumb_src(썸네일 바탕). 전체 길이(초)."""
    folder = Path(folder)
    p = plan(post)
    work = folder / "_race"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html_file = work / "race.html"
    missing = [im["src"] for im in images_of(post).values() if not (folder / im["src"]).exists()]
    if missing:
        shutil.rmtree(work)
        raise ValueError("race.images 파일 없음: " + ", ".join(missing))
    # data URI로 넣는다 (file:// 그림은 캔버스를 오염시켜 toDataURL이 막힘)
    p["imgs"] = {str(i): {"uri": "data:image/jpeg;base64," + base64.b64encode((folder / im["src"]).read_bytes()).decode(),
                          "x": im.get("x", 50), "y": im.get("y", 40), "dim": float(im.get("dim", 0.6))}
                 for i, im in images_of(post).items()}
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
    on = info["onsets"]
    print(f"발표 {len(p['event_times']) + 1}번, 순위 바뀜: " +
          ", ".join(f"{o['label']} {o['t']:.1f}초" for o in p["overtakes"]))
    print("효과음: " + ", ".join(f"{k} {len(v) if isinstance(v, (list, tuple)) else v}" for k, v in on.items()))
    print("박자: " + " → ".join(beats(p)))
    print("배경 사진: " + ", ".join(f"{t:.1f}초 {p['ser'][i]['name']}" for t, i in p["spot"]) +
          (f" (후킹: {', '.join(p['ser'][i]['name'] for i in p['hook_strip'])})" if p["hook_strip"] else ""))
    print(f"1위: {p['ser'][p['winner']]['name']} {fmt_value(p['ser'][p['winner']]['pts'][-1]['v'], p['fmt'])}, "
          f"본편 {main:.1f}초")
    return dur


def beats(p):
    """이야기 박자 요약 (보고·PR 본문용)."""
    out = [f"후킹 0~{p['hook_until']:g}초({' '.join(p['hook'])})" if p["hook"] else "후킹 0초"]
    if p.get("rehook_t"):
        lab = next(o["label"] for o in p["overtakes"] if o.get("rehook"))
        out.append(f"반전 {p['rehook_t']:.1f}초({lab})")
    if p.get("ask"):
        out.append(f"질문 {p['ask']['from']:.1f}~{p['ask']['to']:.1f}초({' '.join(p['ask']['lines'])})")
    out.append(f"답 {p['answer_t']:.1f}초 → 1위·punch {p['race_end']:.1f}~{p['win_end']:.1f}초")
    return out


def preview_times(p, total):
    """미리보기: 0.3초, 후킹 끝, 순위가 바뀐 0.6초 뒤(마지막 4개), 질문 중간, 1위 장면, 끝 화면."""
    ts = [0.3, p["hook_until"] - 0.3] + [o["t"] + 0.6 for o in p["overtakes"]][-4:]
    if p.get("ask"):
        ts.append((p["ask"]["from"] + p["ask"]["to"]) / 2)
    ts = sorted(ts) + [p["race_end"] + 1.5]
    if total > p["win_end"] + 0.5:
        ts.append(total - 1.0)
    return ts


def check_race(post):
    """막대 경주 릴스 검사 (errors, warnings)."""
    errors, warnings = [], []
    R = post.get("race")
    if not isinstance(R, dict):
        return ["race는 {format, series: [{name, color, points: [{date, value, src, url}]}], basis_line, punch} 객체 "
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
    if not str(R.get("basis_line", "")).strip():
        errors.append("race.basis_line 필수: 화면에 띄울 근거·단위 한 줄 (STYLE_GUIDE 0 원칙 10)")
    elif len(R["basis_line"]) > 40:
        errors.append(f"race.basis_line은 40자 이하: {len(R['basis_line'])}자")
    pl = [l for l in str(R.get("punch", "")).split("\n") if l.strip()]
    if not pl or len(pl) > 2 or any(len(l) > 16 for l in pl):
        errors.append("race.punch 필수: 1~2줄, 줄당 16자 이하")
    if post.get("rights") != "own":
        errors.append("막대 경주 릴스는 직접 그린 그래프: rights는 own")
    B = R.get("beats") or {}
    dates = {p.get("date") for s in ser for p in (s.get("points") or [])}
    prev_t = 0.0
    for a in B.get("anchors") or []:
        if not (isinstance(a, list) and len(a) == 2 and a[0] in dates):
            errors.append(f"race.beats.anchors 항목은 [발표일(points의 date), 초]: {a!r}")
        elif float(a[1]) <= prev_t:
            errors.append(f"race.beats.anchors 시각은 커지는 순서: {a!r}")
        else:
            prev_t = float(a[1])
    if B.get("rehook") and B["rehook"].get("date") not in dates:
        errors.append("race.beats.rehook.date는 points의 발표일")
    for k in ("hook", "rehook", "ask"):
        v = B.get(k)
        txt = v.get("text", "") if isinstance(v, dict) else (v or "")
        if any(len(l) > 14 for l in str(txt).splitlines()):
            errors.append(f"race.beats.{k} 한 줄 14자 이하: {txt!r}")
    names = [s.get("name") for s in ser]
    imgs = R.get("images") or []
    for im in imgs:
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
    p = plan(post)
    print(check_race(post))
    print("발표 시각:", [round(t, 2) for t in p["event_times"]])
    for o in p["overtakes"]:
        print(f"  {o['t']:.2f}초 {o['label']}")
    print("박자:", " → ".join(beats(p)))
    print(f"본편 {p['win_end']:.1f}초")
