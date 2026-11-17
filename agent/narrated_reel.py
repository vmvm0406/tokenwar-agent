"""내레이션 모션 릴스 (post type "video" + "narrated", 운영자 결정 2026-11-17 '만약 ~라면?' 시리즈, "예능이 좋은듯").

남자 내레이션(ElevenLabs 'Deok', 예능 톤)이 장면마다 한 문단씩 읽고, 화면은 그 말에 맞춰 움직인다.
- 장면 길이 = 그 장면 목소리 길이 + SCENE_GAP. 목소리가 시간을 정한다 (박자 맞추기 없음).
- 화면 글(장면 text 줄)은 말 속 위치(at: say 안의 낱말)에 맞춰 줄마다 쾅 박힌다. 시각은 voice/NN.json(로컬 받아쓰기 낱말 시각)으로
  말 속 글자 위치 → 실제 시각을 찾는다. 없으면 글자 비율로 어림.
- 그림 칸: 모든 장면에 사진(운영자 2026-11-17 "사진은 무조건 넣어"). image(천천히 확대) / bars(흐린 사진 위에 막대가 말에 맞춰 자람,
  hidden이면 '?') / big(흐린 사진 위에 큰 숫자가 세며 올라감).
- 제목(질문)과 0초 한 줄(cta_line)은 0초부터 끝까지 같은 자리 → 답은 마지막 장면에만 (운영자 승인 뼈대: 훅 → 질문·지연 → 리훅 → 질문·지연 → 답).
- 소리: 목소리 + 실제 음원 조각(music.src, agent/music_fit.py, 말하는 동안 덕킹) + 효과음(장면 전환 휙, 줄 박힐 때 톡, 답 앞 상승음·쾅) → -14 LUFS.
- 끝 화면: post.end_cta (예: '팔로우하면\\n매일 AI 소식').

장면 (본편 시각, 장면 길이는 목소리가 정함):
    0초          제목 질문 쾅 + 첫 장면(훅) 그림·글
    장면마다     컷 전환(휙) → 그림 칸 → 화면 글 줄마다 쾅(말 속 위치) → 작은 출처 줄
    마지막 장면  beat "answer": 상승음 끝에 쾅, 정답 공개 (bars hidden 공개)
    끝           끝 화면 2.5초 (post.end_cta, video.append_cta_card)

목소리 만들기 (이 컴퓨터에서만, GitHub Actions에는 ElevenLabs 키가 없다):
    py -3.12 agent/narrated_reel.py --voice posts/queue/<폴더> [--force]
  → 대본은 tts_ko_norm으로 읽을 글로 바꿔 보낸다(tts.py 기본) → voice/NN.m4a (장면 번호, 무음 자름)
    + voice/NN.json (받아쓰기 관문 tts_ko_norm.verify_audio 결과, faster-whisper medium 낱말 시각).
    받아쓰기와 대본이 다른 곳을 '!'로 보고한다 → 잘못 들리는 낱말은 대본(say)을 바꿔 다시 (예: '잃은'이 '이룬'으로 들림 → '날린').
    같은 글·목소리·설정이면 ElevenLabs 캐시를 다시 쓴다 (과금 없음, agent/tts.py).

post.json:
  "narrated": {
    "voice": {"voice": "deok", "settings": {...}},   # 선택. 기본 Deok + tts.ELEVEN_SETTINGS (STYLE_GUIDE 6장 '내레이션')
    "cta_line": "AI에게 내 돈, 맡긴다 vs 안 맡긴다? 댓글로",   # 0초 한 줄 (선택, '댓글로'는 초록)
    "scenes": [
      {"beat": "hook",                   # hook / q1 / rehook / q2 / answer (뼈대 확인용, answer는 마지막)
       "say": "만약 AI한테 진짜 돈을 맡기면 어떻게 될까요?",   # 읽을 글. 숫자는 한글로 ('만 달러', '이십이 퍼센트')
       "text": "AI에게\\n진짜 돈을 맡기면?",   # 화면 글 1~2줄 (명사형·짧게, 숫자는 아라비아)
       "at": ["", "진짜 돈"],             # 선택: 줄마다 말 속 낱말 (그 낱말을 말할 때 줄이 박힘). 없으면 고르게
       "hl": "진짜 돈",                  # 선택: 초록으로 칠할 말
       "source": "Nof1 Alpha Arena · 2025.10.18~11.3",   # 선택: 작은 출처 줄 (앞 장면 것을 이어 씀, ""면 지움)
       "kind": "image",                  # image(기본) / bars / big
       "image": {"type": "image", "src": "img/s01.jpg", "prompt": "...", "size": [1344, 672]},   # 모든 장면 필수
       "bars": [{"label": "GPT-5", "value": -63, "shown": "-63%", "at": "지피티", "hidden": false, "win": false}],
                                         # at 없는 막대는 장면 시작부터 다 자란 채 (앞 장면 막대를 이어 그릴 때)
       "bar_max": 70,                    # bars: 막대 최대 절댓값
       "big": "99.9%", "big_at": "구십구"}  # big: 큰 숫자, 세며 올라감 (말 속 낱말 시각에)
    ],
  }
사용법: render.py가 부른다. 단독 확인: py -3.12 agent/narrated_reel.py <게시물 폴더> (계획·길이만)
"""
import asyncio
import base64
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)

VOICE_DIR = "voice"
SCENE_GAP = 0.22          # 말 끝과 다음 장면 사이 (호흡)
LEAD = 0.06               # 장면 시작 뒤 말이 시작되기까지
MIN_SCENE = 1.4
LENGTH_RANGE = (25.0, 40.0)   # 본편 (끝 화면 제외)
BEATS = ("hook", "q1", "rehook", "q2", "answer")
KINDS = ("image", "bars", "big")
CHARS_PER_SEC = 7.2       # 목소리 파일이 없을 때 길이 어림 (Deok 1.1배, 공백 뺀 글자)


def voice_path(folder, k):
    return Path(folder) / VOICE_DIR / f"{k:02d}.m4a"


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _norm(s):
    """비교용: 한글·영문·숫자만."""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s or "")


def est_secs(say):
    return len(_norm(say)) / CHARS_PER_SEC


def char_time(say, pos, words, dur):
    """대본 글자 위치(pos) → 말 속 시각. words: [[낱말, 시작, 끝], ...] (받아쓰기). 없으면 글자 비율."""
    n = len(_norm(say)) or 1
    q = len(_norm(say[:pos])) / n
    if not words:
        return q * dur
    lens = [len(_norm(w[0])) for w in words]
    tot = sum(lens) or 1
    target = q * tot
    acc = 0
    for (w, a, z), L in zip(words, lens):
        if acc + L >= target and L:
            return a + (z - a) * ((target - acc) / L)
        acc += L
    return words[-1][2]


def cue(say, word, words, dur, default):
    if not word:
        return default
    i = say.find(word)
    if i < 0:
        return default
    return char_time(say, i, words, dur)


def plan(post, folder=None):
    """화면·소리 계획 (JS로 넘김)."""
    N = post["narrated"]
    scenes = N.get("scenes") or []
    out, t = [], 0.0
    src_line = ""
    for k, s in enumerate(scenes, 1):
        say = str(s.get("say", ""))
        vp = voice_path(folder, k) if folder else None
        meta = {}
        if vp and vp.exists():
            vdur = _probe(vp)
            mj = vp.with_suffix(".json")
            if mj.exists():
                meta = json.loads(mj.read_text(encoding="utf-8"))
        else:
            vdur = est_secs(say)
            vp = None
        words = meta.get("words") or []
        dur = max(MIN_SCENE, LEAD + vdur + SCENE_GAP)
        lines = [l for l in str(s.get("text", "")).split("\n") if l.strip()]
        at = s.get("at") or []
        lt = []
        for i, ln in enumerate(lines):
            d = (i / max(1, len(lines))) * vdur * 0.6
            w = at[i] if i < len(at) else ""
            lt.append(round(LEAD + (cue(say, w, words, vdur, d) if w else d), 3))
        if "source" in s:
            src_line = str(s.get("source") or "")
        kind = s.get("kind", "image")
        img = None
        im = s.get("image") or {}
        if folder and im.get("src") and (Path(folder) / im["src"]).exists():
            img = "data:image/jpeg;base64," + base64.b64encode((Path(folder) / im["src"]).read_bytes()).decode()
        bars = []
        for b in s.get("bars") or []:
            bars.append({"label": str(b.get("label", "")), "value": float(b.get("value", 0)),
                         "shown": str(b.get("shown", b.get("value", ""))), "hidden": bool(b.get("hidden")),
                         "win": bool(b.get("win")), "instant": not b.get("at"),
                         "t": round(LEAD + cue(say, b.get("at"), words, vdur, 0.0), 3)})
        big_t = round(LEAD + cue(say, s.get("big_at"), words, vdur, 0.0), 3)
        out.append({"k": k, "t0": round(t, 3), "dur": round(dur, 3), "beat": s.get("beat", ""), "kind": kind,
                    "lines": lines, "lt": lt, "hl": s.get("hl") or "", "source": src_line, "img": img,
                    "has_img": bool(im.get("src")), "bars": bars, "bar_max": float(s.get("bar_max") or 0),
                    "big": str(s.get("big", "")), "big_t": big_t, "voice": str(vp) if vp else None,
                    "vdur": round(vdur, 3)})
        t += dur
    # bars가 hidden인 막대는 answer 장면에서 공개: 같은 라벨의 막대를 answer 장면에 그대로 다시 그린다 (bars를 이어받음)
    return {"scenes": out, "end": round(t, 3), "title": str(post["title"]).split("\n"),
            "hl": post.get("highlight") or "", "cta": (N.get("cta_line") or "").strip(),
            "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM, "side": SIDE}}


def sfx_times(p):
    sc = p["scenes"]
    ans = next((s for s in sc if s["beat"] == "answer"), None)
    impacts = [0.0]
    rehook = [s["t0"] for s in sc if s["beat"] == "rehook"]
    if ans:
        impacts.append(ans["t0"] + (ans["lt"][0] if ans["lt"] else 0))
    whooshes = [s["t0"] + 0.05 for s in sc[1:]]
    hits = []
    for s in sc:
        hits += [s["t0"] + x for x in s["lt"][1:]]
        hits += [s["t0"] + b["t"] for b in s["bars"]]
        if s["kind"] == "big" and s["big"]:
            hits.append(s["t0"] + s["big_t"] + 0.5)
    hits += rehook
    riser = (ans["t0"] - 1.6, ans["t0"]) if ans and ans["t0"] > 2 else None
    return {"impacts": impacts, "hits": sorted(set(round(h, 3) for h in hits)), "whooshes": whooshes, "riser": riser}


def page_html(post, p, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    js = (ROOT / "agent" / "narrated_reel.js").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-SemiBold.otf');font-weight:600}}
html,body{{margin:0;background:{b['bg']}}} canvas{{display:block}}
</style></head><body><canvas id="c" width="{W}" height="{H}"></canvas>
<script>const P = {json.dumps(p, ensure_ascii=False)};
const C = {json.dumps({"bg": b["bg"], "accent": b["accent"], "text": b["text"], "muted": b["muted"]})};
{js}</script></body></html>"""


async def _shoot(html_file, times, out_dir):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await pw.chromium.launch(executable_path=exe) if exe else await pw.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(html_file.as_uri())
        await pg.evaluate("nrReady()")
        await pg.evaluate("""async () => { await document.fonts.load('96px "Black Han Sans"', '가A1');
            await document.fonts.load('700 30px Wanted', '가A1'); await document.fonts.load('600 30px Wanted', '가A1');
            await document.fonts.ready; }""")
        problems = await pg.evaluate("nrProblems()")
        for k, t in enumerate(times):
            data = await pg.evaluate(f"nrFrame({t:.5f})")
            (out_dir / f"f{k:05d}.jpg").write_bytes(base64.b64decode(data.split(",", 1)[1]))
        await browser.close()
    return problems


def make_sfx(p, total):
    from music_gen import make_hook_sfx
    s = sfx_times(p)
    r = s["riser"]
    base, info = make_hook_sfx(total, impacts=s["impacts"], hits=s["hits"], whooshes=s["whooshes"],
                               riser_to=r[1] if r else None, riser_len=(r[1] - r[0]) if r else 1.0, drop=None)
    return base, info


def make_narrated_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, -14 LUFS), frames/*.jpg, cover.jpg(썸네일이 덮어씀). 전체 길이(초)."""
    folder = Path(folder).resolve()
    p = plan(post, folder)
    missing = [s["k"] for s in p["scenes"] if not s["voice"]]
    if missing:
        raise ValueError(f"목소리 파일 없음: 장면 {missing} → 이 컴퓨터에서 py -3.12 agent/narrated_reel.py --voice {folder}")
    noimg = [s["k"] for s in p["scenes"] if s["has_img"] and not s["img"]]
    if noimg:
        raise ValueError(f"그림 파일 없음: 장면 {noimg} (render.yml의 gen_images가 만든다)")
    work = folder / "_narrated"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html_file = work / "narrated.html"
    html_file.write_text(page_html(post, p, cfg), encoding="utf-8")
    main = p["end"]
    nfr = int(round(main * FPS))
    problems = asyncio.run(_shoot(html_file, [k / FPS for k in range(nfr)], work))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(work / "f%05d.jpg"),
                    "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-r", str(FPS), str(silent)], check=True)
    from listreel import mix_audio
    pm = post.get("music") or {}
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    else:
        from timeline_reel import make_pad
        music = work / "music.wav"
        make_pad(music, main)
    voices = [(s["t0"] + LEAD, Path(s["voice"])) for s in p["scenes"]]
    sfx, info = make_sfx(p, main)
    mixed = work / "mix.wav"
    m = mix_audio(music, voices, main, mixed, sfx)
    print(f"소리: 목소리 {m.get('voices')}개, 말할 때 목소리-음악 차 {m.get('diff_in_speech_db', 0):.1f} dB")
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
    print("장면: " + ", ".join(f"{s['k']}({s['beat']}) {s['t0']:.1f}~{s['t0'] + s['dur']:.1f}초" for s in p["scenes"]))
    return dur


def preview_times(p, total):
    """미리보기: 장면마다 끝 직전(줄이 다 박힌 뒤) + 끝 화면."""
    ts = [0.5] + [s["t0"] + s["dur"] - 0.25 for s in p["scenes"]]
    if total > p["end"] + 0.5:
        ts.append(total - 1.0)
    return ts


def check_narrated(post):
    """내레이션 릴스 검사 (errors, warnings)."""
    errors, warnings = [], []
    N = post.get("narrated")
    if not isinstance(N, dict):
        return ["narrated는 {scenes: [{beat, say, text, ...}], cta_line} 객체 (TEMPLATES.md '내레이션 모션 릴스')"], warnings
    sc = N.get("scenes") or []
    if not 3 <= len(sc) <= 10:
        errors.append(f"narrated.scenes는 3~10개: 지금 {len(sc)}개")
    if post.get("rights") != "own":
        errors.append("내레이션 릴스는 직접 만든 화면·목소리: rights는 own")
    beats = [s.get("beat") for s in sc]
    for i, s in enumerate(sc, 1):
        say = str(s.get("say", "")).strip()
        if not say:
            errors.append(f"narrated.scenes {i}: say(읽을 글) 필요")
        if re.search(r"\d", say):
            errors.append(f"narrated.scenes {i}: say의 숫자는 한글로 (목소리가 잘못 읽지 않게): '{say}'")
        if re.search(r"[A-Za-z]{2,}", say.replace("AI", "")):
            warnings.append(f"narrated.scenes {i}: say에 영어 '{' '.join(re.findall(r'[A-Za-z]{2,}', say))}' → 한글로 쓰면 읽기가 정확하다")
        if len(_norm(say)) > 70:
            warnings.append(f"narrated.scenes {i}: say가 김 ({len(_norm(say))}자) → 장면을 나누면 화면이 덜 멈춘다")
        lines = [l for l in str(s.get("text", "")).split("\n") if l.strip()]
        if not 1 <= len(lines) <= 2:
            errors.append(f"narrated.scenes {i}: text(화면 글)는 1~2줄")
        for l in lines:
            if len(l.replace(" ", "")) > 14:
                errors.append(f"narrated.scenes {i}: 화면 글 한 줄은 공백 빼고 14자 이하: '{l}'")
        for w in s.get("at") or []:
            if w and w not in say:
                errors.append(f"narrated.scenes {i}: at '{w}'이 say 안에 없음")
        if s.get("hl") and s["hl"] not in str(s.get("text", "")):
            errors.append(f"narrated.scenes {i}: hl '{s['hl']}'이 text 안에 없음")
        kind = s.get("kind", "image")
        if kind not in KINDS:
            errors.append(f"narrated.scenes {i}: kind는 {KINDS} 중 하나")
        im = s.get("image") or {}
        if not (im.get("src") and (im.get("prompt") or im.get("url") or im.get("shot"))):
            # 모든 장면에 사진 (운영자 2026-11-17 "사진은 무조건 넣어"): bars·big도 사진 위에 숫자를 얹는다
            errors.append(f"narrated.scenes {i}: image {{type, src, prompt·url·shot 중 하나}} 필요 (글·그래프만 있는 장면 금지)")
        if kind == "bars":
            bs = s.get("bars") or []
            if not 2 <= len(bs) <= 7:
                errors.append(f"narrated.scenes {i}: bars는 2~7개")
            for b in bs:
                if b.get("at") and b["at"] not in say:
                    errors.append(f"narrated.scenes {i}: 막대 '{b.get('label')}' at '{b['at']}'이 say 안에 없음")
                if len(str(b.get("label", ""))) > 12:
                    errors.append(f"narrated.scenes {i}: 막대 이름은 12자 이하: '{b.get('label')}'")
        if kind == "big" and not str(s.get("big", "")).strip():
            errors.append(f"narrated.scenes {i}: big(큰 숫자) 필요")
        if s.get("big_at") and s["big_at"] not in say:
            errors.append(f"narrated.scenes {i}: big_at '{s['big_at']}'이 say 안에 없음")
        if len(str(s.get("source") or "")) > 40:
            errors.append(f"narrated.scenes {i}: source(출처 줄)는 40자 이하")
        b = s.get("beat")
        if b and b not in BEATS:
            errors.append(f"narrated.scenes {i}: beat는 {BEATS} 중 하나")
    if sc and beats[0] != "hook":
        errors.append("첫 장면은 beat 'hook' (0초부터 질문 + 강한 그림)")
    if sc and beats[-1] != "answer":
        errors.append("마지막 장면은 beat 'answer' (답은 끝에만)")
    if "rehook" not in beats:
        warnings.append("rehook 장면이 없음 (12~15초쯤 새 반전으로 다시 붙잡기)")
    if not any((s.get("source") or "").strip() for s in sc):
        errors.append("화면 출처 줄(scenes[].source) 1개 이상 (STYLE_GUIDE 0 원칙 10)")
    total = sum(max(MIN_SCENE, LEAD + est_secs(s.get("say", "")) + SCENE_GAP) for s in sc)
    if sc and not LENGTH_RANGE[0] - 5 <= total <= LENGTH_RANGE[1] + 5:
        warnings.append(f"어림 길이 {total:.1f}초 (본편 {LENGTH_RANGE[0]:g}~{LENGTH_RANGE[1]:g}초). 목소리를 만든 뒤 렌더링 길이로 확인")
    return errors, warnings


# ---------- 목소리 만들기 + 받아쓰기 확인 (이 컴퓨터) ----------

_asr = None


def asr_words(path):
    """faster-whisper medium (한국어) → (받아쓴 글, [[낱말, 시작, 끝]])."""
    global _asr
    if _asr is None:
        from faster_whisper import WhisperModel
        _asr = WhisperModel("medium", device="cpu", compute_type="int8")
    import tts
    audio = tts.decode(path, 16000)          # 파일을 ffmpeg로 풀어 넘긴다 (PyAV 판 차이 피함)
    segs, _ = _asr.transcribe(audio, language="ko", word_timestamps=True, beam_size=5, vad_filter=False)
    words, text = [], []
    for sg in segs:
        text.append(sg.text.strip())
        for w in sg.words or []:
            words.append([w.word.strip(), round(w.start, 3), round(w.end, 3)])
    return " ".join(text), words


def diff_report(say, heard):
    """대본과 받아쓰기가 다른 곳 (한글·숫자만 비교)."""
    a, b = _norm(say), _norm(heard)
    sm = difflib.SequenceMatcher(None, a, b)
    bad = [(a[i1:i2], b[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    # 받아쓰기가 숫자·영어로 적은 곳('십칠'→'17', '지피티파이브'→'GPT5')은 읽기 문제가 아니다 → 따로 둔다
    real = [x for x in bad if not re.search(r"[0-9A-Za-z]", x[1])]
    return sm.ratio(), real


def make_voices(folder, force=False):
    """장면마다 목소리: tts.eleven_mp3(보내기 전에 tts_ko_norm으로 읽을 글로 바꿈) → voice/NN.m4a,
    받아쓰기 관문(tts_ko_norm.verify_audio, 다르면 '!' + 종료 코드 1) + 낱말 시각(faster-whisper medium) → voice/NN.json."""
    import tts
    from tts_ko_norm import normalize, verify_audio
    folder = Path(folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    N = post["narrated"]
    cfg = N.get("voice") or {}
    vid = tts.eleven_voice_id(cfg.get("voice") or "deok")
    settings = cfg.get("settings")
    (folder / VOICE_DIR).mkdir(exist_ok=True)
    used = 0
    total = 0.0
    failed = []
    for k, s in enumerate(N["scenes"], 1):
        say = s["say"].strip()
        sent = normalize(say)
        out = voice_path(folder, k)
        meta_f = out.with_suffix(".json")
        old = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {}
        if out.exists() and not force and old.get("say") == say and old.get("sent") == sent:
            meta = old
        else:
            h = tts.ELEVEN_CACHE
            before = set(h.glob("*.mp3")) if h.exists() else set()
            mp3 = tts.eleven_mp3(say, vid, settings)
            if mp3 not in before:
                used += len(sent)
            x = tts.trim(tts.decode(mp3, tts.KO_SR), sr=tts.KO_SR)
            wav = out.with_suffix(".wav")
            tts.save(wav, x, tts.KO_SR)
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "96k",
                            str(out)], check=True)
            wav.unlink()
            heard, words = asr_words(out)
            g = verify_audio(out, say)
            meta = {"say": say, "sent": sent, "heard": heard, "gate": g["ok"], "gate_ratio": g["ratio"],
                    "gate_diffs": g["diffs"], "gate_asr": g["asr"], "words": words}
            meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        d = _probe(out)
        total += d + LEAD + SCENE_GAP
        diff = diff_report(sent, meta["heard"])[1]
        flag = "" if meta.get("gate") and not diff else "  !"
        if not meta.get("gate"):
            failed.append(k)
        print(f"{k:02d} {d:5.2f}초 관문 {'통과' if meta.get('gate') else '실패'} {meta.get('gate_ratio')}{flag} | {say}")
        if flag:
            print(f"     들림(small): {meta.get('gate_asr')}")
            print(f"     들림(medium): {meta['heard']}")
            print(f"     관문 차이: {[(x['expected'], x['heard']) for x in meta.get('gate_diffs') or []]}  medium 차이: {diff}")
    print(f"본편 약 {total:.1f}초, 이번에 ElevenLabs {used}자 사용 (캐시 제외)")
    if failed:
        print(f"받아쓰기 관문 실패: 장면 {failed} → say를 다른 말로 바꿔 다시 (STYLE_GUIDE 6장 '내레이션 모션 릴스')")
    return failed


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--voice":
        sys.exit(1 if make_voices(sys.argv[2], force="--force" in sys.argv) else 0)
    f = Path(sys.argv[1])
    post = json.loads((f / "post.json").read_text(encoding="utf-8"))
    p = plan(post, f)
    for s in p["scenes"]:
        print(f"{s['k']:02d} {s['beat']:7s} {s['t0']:5.2f}~{s['t0'] + s['dur']:5.2f}초  줄 {s['lt']}  {' / '.join(s['lines'])}")
    print("본편", p["end"], "초")
    print(json.dumps(sfx_times(p), default=float))
    e, w = check_narrated(post)
    for x in w:
        print("경고:", x)
    for x in e:
        print("오류:", x)


if __name__ == "__main__":
    main()
