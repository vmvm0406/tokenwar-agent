"""사진 내레이션 릴스 (post type "video" + "photo_reel", 2026-11-17 운영자 "사진은 무조건 넣어", "tts 써보자").

장면마다 사진 한 장이 화면을 꽉 채우고(천천히 확대), 그 위에 숫자·비교 같은 정리 글(overlay)과
내레이션 자막(cap)을 얹는다. 한국어 내레이션(ElevenLabs, agent/tts.py)이 장면 길이를 정한다:
장면 = 그 줄 말 시작 직전부터 다음 줄 말 시작 직전까지. 글·그래프만 있는 장면은 없다 (모든 장면에 img 필수).

화면 (1080x1920, 인스타 안전 영역 안):
    0~500px      검은 띠 + 제목 2줄 (post.title, 처음부터 끝까지)
    500px~       사진 (cover로 꽉 채움, focus 쪽을 중심으로 천천히 확대. 장면이 바뀌면 살짝 당겨지며 등장)
    560~1000px   overlay: big(큰 숫자, 숫자가 0부터 올라감) / steps(날짜·값이 한 줄씩) / bars(두세 막대 비교)
    ~1140px      자막(cap, 내레이션을 짧게 옮긴 글, 검은 상자, 오른쪽 아래 버튼 줄 위)
    사진 위 왼쪽  작은 출처 글씨(credit)
소리: 내레이션 + 실제 음원 조각(music.src, 말하는 동안 덕킹) + 장면 전환 효과음 → 끝 화면(end_cta) → -14 LUFS.

post.json:
  "photo_reel": {
    "voice": {"engine": "elevenlabs", "voice": "deok", "settings": {}},   # 선택. 기본 deok, tts.py ELEVEN_SETTINGS
    "scenes": [
      {"beat": "hook" | "delay1" | "rehook" | "delay2" | "answer",
       "img": "img/a.jpg", "focus": [0.5, 0.3], "zoom": [1.0, 1.08],   # 사진, 보여 줄 중심(가로·세로 0~1), 확대 시작·끝
       "credit": "사진: ... (CC BY 2.0)",
       "vo": "내레이션 (숫자·영어는 tts_ko_norm이 읽는 한글로 바꿔 보냄)",  "cap": "화면 자막\\n2줄까지", "hl": "자막 녹색 강조(선택)",
       "overlay_at": "top" | "low",     # 선택. low면 정리 글을 자막 바로 위로 (사진 위쪽 얼굴을 가리지 않게)
       "overlay": {"type": "big", "big": "1,290조 원", "sub": "한 줄", "size": 130(선택, 기본 150)} |
                  {"type": "steps", "items": [["2025.3", "615억 달러"], ...], "punch": "15배 넘게"} |
                  {"type": "bars", "items": [{"label": "앤트로픽", "value": 1290, "display": "1,290조 원", "on": true}], "note": "한 줄"},
       "fill": true}                    # 선택. 상장일 확정 숫자로 다시 만드는 장면 (ipo 블록, 아래)
    ]
  }
  글자 안의 {cap_usd} {cap_krw} {cap_krw_jo} {cmp_krw} {cmp_krw_jo} {price} {open} {range} {price_ko} {open_ko} {krw_rate}는 post "ipo" 블록에서 계산한다
  (상장 릴스용, 없으면 쓰지 않는다). ipo.status가 "final"이면 장면의 vo_final·cap_final·overlay_final을 먼저 쓴다.
  ipo.compare({"name", "krw_jo"})가 있으면 공모가 기준 시가총액(원)이 그보다 커야 렌더링한다 (비교 문장이 거짓이 되지 않게).

목소리: 대본 전체를 ElevenLabs /with-timestamps 한 번 → voice/narration.wav + narration.json (글자마다 릴스 시각).
    장면 사이 쉼 0.15~0.25초, 한 줄 안 0.4초 넘는 쉼 → 0.25초. 정리 글·로고(pops)는 그 말(at)이 나오는 순간 쾅·톡.
    끝 화면은 박에서 쾅 → 2초 뒤 박에서 뚝 (페이드 없음). 이 컴퓨터에서 만든다 (GitHub Actions에는 TTS가 없음).
    py -3.12 agent/photoreel.py <게시물 폴더> --voice [--force] [--asr]   # 목소리 만들기(대본이 바뀌었을 때만) + 받아쓰기 확인
    py -3.12 agent/photoreel.py <게시물 폴더>                            # 계획(장면·쾅 시각)만 보기
렌더링은 render.py가 부른다.
"""
import asyncio
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)
RAIL_LEFT = _SAFE.get("rail_left", 850)
RAIL_TOP = _SAFE.get("rail_top", 1150)

BAND = 500            # 위 검은 띠 (제목)
CAP_BOTTOM = 1135     # 자막 아래 끝 (오른쪽 아래 버튼 줄 rail_top 위)
VO_LEAD = 0.08        # 장면 시작 뒤 목소리 시작
GAP = 0.22
MIN_SCENE = 1.6
CHARS_PER_SEC = 9.0   # 목소리 파일이 없을 때 길이 어림 (경고)
VOICE_DIR = "voice"
BEATS = ("hook", "delay1", "rehook", "delay2", "answer")
DISCLAIMER_RE = re.compile(r"투자\s*권유|투자\s*조언|매수\s*추천|매도\s*추천|사세요|파세요|오를 것|기회입니다")


# ---------------- 숫자 ----------------
def ko_num(n):
    """정수·소수 한 자리 → 한글 읽기 (74 → 칠십사, 80.5 → 팔십 점 오). 내레이션 글의 숫자를 한글로."""
    digits = "영일이삼사오육칠팔구"
    s = f"{n}".rstrip("0").rstrip(".") if isinstance(n, float) else str(int(n))
    if "." in s:
        a, b = s.split(".")
        return ko_num(int(a)) + " 점 " + "".join(digits[int(c)] for c in b)
    v = int(s)
    if v == 0:
        return "영"
    units = [(10 ** 12, "조"), (10 ** 8, "억"), (10 ** 4, "만")]
    out = ""
    for u, name in units:
        if v >= u:
            q, v = divmod(v, u)
            out += ("" if q == 1 and name == "만" else _ko4(q)) + name + " "
    return (out + _ko4(v)).strip() if v else out.strip()


def _ko4(v):
    digits = "영일이삼사오육칠팔구"
    out = ""
    for u, name in ((1000, "천"), (100, "백"), (10, "십")):
        q, v = divmod(v, u)
        if q:
            out += ("" if q == 1 else digits[q]) + name
    return out + (digits[v] if v else "")


def ipo_vars(post):
    """post.ipo → 글자 틀 값. ipo가 없으면 {}."""
    ipo = post.get("ipo") or {}
    if not ipo.get("price") or not ipo.get("shares_outstanding_after"):
        return {}
    shares, price = float(ipo["shares_outstanding_after"]), float(ipo["price"])
    krw = float(ipo.get("krw_rate") or 0)
    usd_100m = shares * price / 1e8
    v = {"price": f"{price:g}", "price_ko": ko_num(price), "cap_usd_100m": usd_100m,
         "cap_usd": f"{round(usd_100m / 10) * 10:,.0f}억 달러",
         "range": "~".join(f"{x:g}" for x in ipo.get("price_range") or []),
         "open": f"{float(ipo['open']):g}" if ipo.get("open") is not None else "",
         "open_ko": ko_num(float(ipo["open"])) if ipo.get("open") is not None else ""}
    if krw:
        jo = shares * price * krw / 1e12
        v.update(cap_krw_jo=jo, cap_krw=f"{round(jo / 10) * 10:,.0f}조 원", krw_rate=f"{krw:,.1f}".rstrip("0").rstrip("."))
    cmp_ = ipo.get("compare") or {}
    if cmp_.get("krw_jo"):
        v.update(cmp_krw_jo=float(cmp_["krw_jo"]), cmp_krw=f"{round(float(cmp_['krw_jo']) / 10) * 10:,.0f}조 원")
    return v


def fmt(text, vars_):
    if not isinstance(text, str) or "{" not in text:
        return text
    return text.format(**{k: v for k, v in vars_.items()})


def pick(scene, key, final):
    return scene.get(key + "_final", scene.get(key)) if final else scene.get(key)


def resolved(post):
    """장면 목록 (상장일 확정이면 *_final, 글자 틀 채움)."""
    R = post["photo_reel"]
    final = (post.get("ipo") or {}).get("status") == "final"
    vs = ipo_vars(post)
    out = []
    for i, s in enumerate(R["scenes"], 1):
        ov = json.loads(json.dumps(pick(s, "overlay", final) or {}, ensure_ascii=False))

        def deep(x):
            if isinstance(x, str):
                return fmt(x, vs)
            if isinstance(x, list):
                return [deep(y) for y in x]
            if isinstance(x, dict):
                return {k: (vs.get(y[1:-1]) if isinstance(y, str) and re.fullmatch(r"\{(cap_krw_jo|cap_usd_100m|cmp_krw_jo)\}", y) else deep(y))
                        for k, y in x.items()}
            return x
        out.append({"n": i, "beat": s.get("beat"), "img": s["img"], "focus": s.get("focus", [0.5, 0.4]),
                    "zoom": s.get("zoom", [1.0, 1.07]), "credit": s.get("credit", ""),
                    "vo": fmt(pick(s, "vo", final), vs), "cap": fmt(pick(s, "cap", final), vs),
                    "hl": fmt(pick(s, "hl", final), vs), "overlay": deep(ov), "fill": bool(s.get("fill")),
                    "overlay_at": s.get("overlay_at", "top"), "pops": deep(s.get("pops") or [])})
    return out


# ---------------- 목소리: 대본 전체를 한 번에 (호흡 자연스럽게, 2026-11-17 운영자 "호흡 다시 손보고") ----------------
NARR = "narration.wav"
NARR_META = "narration.json"
NARR_OFFSET = 0.05      # 릴스 0초 뒤 목소리 시작
GAP_MIN, GAP_MAX, GAP_SET = 0.15, 0.25, 0.20   # 장면(문장) 사이 쉼: 0.15~0.25초로 맞춤
DEAD_MAX, DEAD_SET = 0.40, 0.25                 # 한 줄 안 쉼이 0.4초 넘으면 0.25초로
HEAD_PAD, TAIL_PAD = 0.03, 0.05                 # 소리 앞뒤 여유 (꼬리·숨 자르지 않게)
CTA_LEN = 2.0           # 끝 화면 (박 4개). 소리·화면 페이드 없이 박에서 뚝 끊음 (운영자 2026-11-17 "페이드 아웃도 제거")
END_HOLD = 0.3          # 마지막 말 뒤 끝 화면까지 최소


def _wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def voice_file(folder, n):
    """예전 형식(장면마다 voice/NN.wav). 새 형식은 voice/narration.wav 하나."""
    return Path(folder) / VOICE_DIR / f"{n:02d}.wav"


def _norm(t):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", t or "")


def _vcfg(post):
    return dict(post["photo_reel"].get("voice") or {})


def script(post):
    """ElevenLabs에 보낼 전체 글(정규화) + 장면별 [시작, 끝) 글자 위치."""
    import tts
    v = _vcfg(post)
    text, spans = "", []
    for s in resolved(post):
        part = tts.eleven_text(s["vo"], v.get("normalize", True), v.get("words")).strip()
        if text:
            text += " "
        spans.append([len(text), len(text) + len(part)])
        text += part
    return text, spans


def _decode(mp3_bytes, sr=44100):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         input=mp3_bytes, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _env(x, sr, hop=0.01):
    import numpy as np
    n = int(hop * sr)
    k = len(x) // n
    e = np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(axis=1) + 1e-12)
    thr = max(e.max() * 10 ** (-38 / 20), 1e-4)
    return e > thr, n


def make_narration(post, folder, force=False):
    """대본 전체를 ElevenLabs /with-timestamps 한 번으로 읽혀(문장 사이 억양이 이어지게) 글자 시각을 받고,
    장면 사이 쉼을 0.15~0.25초, 한 줄 안 0.4초 넘는 쉼을 0.25초로 맞춘다. 소리 앞뒤는 에너지로 찾아 30~60ms 여유.
    voice/narration.wav + voice/narration.json(글, 장면 글자 위치, 글자마다 릴스 시각, 쉼)."""
    import numpy as np
    import tts
    folder = Path(folder)
    v = _vcfg(post)
    text, spans = script(post)
    vid = tts.eleven_voice_id(v.get("voice", "deok"))
    vs = dict(tts.ELEVEN_SETTINGS, **(v.get("settings") or {}))
    meta_p = folder / VOICE_DIR / NARR_META
    if meta_p.exists() and not force and json.loads(meta_p.read_text(encoding="utf-8")).get("text") == text \
            and (folder / VOICE_DIR / NARR).exists():
        print("  목소리: 대본 그대로 (다시 만들지 않음)")
        return
    h = hashlib.sha256(json.dumps([text, vid, vs, tts.ELEVEN_MODEL, tts.ELEVEN_FORMAT, "ts"], ensure_ascii=False,
                                  sort_keys=True).encode()).hexdigest()[:24]
    cache = tts.ELEVEN_CACHE / f"ts_{h}.json"
    if cache.exists():
        res = json.loads(cache.read_text(encoding="utf-8"))
    else:
        res = json.loads(tts._eleven(f"/text-to-speech/{vid}/with-timestamps?output_format={tts.ELEVEN_FORMAT}", tts.eleven_key(),
                                     {"text": text, "model_id": tts.ELEVEN_MODEL, "voice_settings": vs}))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(res), encoding="utf-8")
        print(f"  ElevenLabs {len(text)}자 사용 (대본 전체, 글자 시각 포함)", file=sys.stderr)
    sr = 44100
    x = _decode(base64.b64decode(res["audio_base64"]), sr)
    al = res.get("alignment") or res.get("normalized_alignment")
    st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
    if "".join(al["characters"]) != text:
        print("  ! 글자 시각의 글과 대본이 다름: 위치를 글자 수로 맞춤", file=sys.stderr)
    on, hop = _env(x, sr)
    ft = hop / sr

    def sound_end(t, limit):          # t 뒤로 소리가 이어지는 끝
        i = int(t / ft)
        while i < len(on) and i * ft < limit and on[i]:
            i += 1
        return min(i * ft, limit)

    def sound_start(t, limit):        # t 앞으로 소리가 시작되는 곳
        i = max(0, int(t / ft))
        while i > 0 and (i - 1) * ft > limit and on[i - 1]:
            i -= 1
        return max(i * ft, limit)

    def first(a, b):
        for k in range(a, b):
            if text[k].strip():
                return k
        return a

    def last(a, b):
        for k in range(b - 1, a - 1, -1):
            if _norm(text[k]):
                return k
        return b - 1
    L = len(x) / sr
    segs = []      # 장면마다 [소리 시작, 소리 끝] (원래 시각)
    for i, (a, b) in enumerate(spans):
        s0, e0 = st[first(a, b)], en[last(a, b)]
        segs.append([s0, e0])
    for i in range(len(segs)):
        prev_end = segs[i - 1][1] if i else 0.0
        nxt = segs[i + 1][0] if i + 1 < len(segs) else L
        segs[i][0] = max(0.0, sound_start(segs[i][0], prev_end) - HEAD_PAD)
        segs[i][1] = min(L, sound_end(segs[i][1], nxt) + TAIL_PAD)
    # 원래 시각 구간들을 이어 붙이기: (원래 시작, 원래 끝, 새 시작)
    pieces, out_t, gaps, inner = [], 0.0, [], []
    for i, (a, b) in enumerate(segs):
        if i:
            nat = a - segs[i - 1][1]
            g = GAP_SET if nat > GAP_MAX else max(GAP_MIN, nat)
            gaps.append({"after": i, "natural": round(nat, 3), "set": round(g, 3)})
            out_t += g
        # 한 줄 안 긴 쉼 줄이기
        k0, k1 = int(a / ft), int(b / ft)
        cur = a
        k = k0
        while k < k1:
            if not on[k]:
                j = k
                while j < k1 and not on[j]:
                    j += 1
                if (j - k) * ft > DEAD_MAX:
                    cut_a, cut_b = k * ft + DEAD_SET / 2, j * ft - DEAD_SET / 2
                    pieces.append((cur, cut_a, out_t))
                    out_t += cut_a - cur
                    inner.append({"scene": i + 1, "natural": round((j - k) * ft, 3), "set": DEAD_SET})
                    cur = cut_b
                k = j
            else:
                k += 1
        pieces.append((cur, b, out_t))
        out_t += b - cur
    total = out_t
    y = np.zeros(int(round(total * sr)) + 1, dtype=np.float32)
    fade = int(0.004 * sr)
    for a, b, o in pieces:
        seg = x[int(a * sr):int(b * sr)].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
        i0 = int(round(o * sr))
        y[i0:i0 + len(seg)] += seg[:len(y) - i0]

    def remap(t):
        for a, b, o in pieces:
            if t < a:
                return o
            if t <= b:
                return o + t - a
        return total
    tt = [round(remap(t), 4) for t in st]
    scenes = [{"speech_start": round(remap(segs[i][0]) + 0.0, 3), "speech_end": round(remap(segs[i][1]), 3)} for i in range(len(segs))]
    f = folder / VOICE_DIR / NARR
    tts.save(f, y, sr=sr)
    for old in (folder / VOICE_DIR).glob("[0-9][0-9].wav"):
        old.unlink()
    old_meta = folder / VOICE_DIR / "voice.json"
    if old_meta.exists():
        old_meta.unlink()
    meta = {"text": text, "spans": spans, "t": tt, "scenes": scenes, "end": round(total, 3), "gaps": gaps, "inner": inner,
            "voice": vid, "settings": vs}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"  목소리 {NARR}: {total:.2f}초 (원래 {L:.2f}초)")
    print("  장면 사이 쉼: " + ", ".join(f"{g['after']}→{g['after'] + 1} {g['natural']:.2f}→{g['set']:.2f}초" for g in gaps))
    if inner:
        print("  줄 안 긴 쉼 줄임: " + ", ".join(f"{d['scene']}번 {d['natural']:.2f}→{d['set']:.2f}초" for d in inner))


def narration(post, folder):
    """voice/narration.json (대본이 지금 글과 같을 때만), 없으면 None."""
    p = Path(folder) / VOICE_DIR / NARR_META
    if not p.exists() or not (Path(folder) / VOICE_DIR / NARR).exists():
        return None
    m = json.loads(p.read_text(encoding="utf-8"))
    try:
        text, _ = script(post)
    except Exception:
        return m
    return m if m.get("text") == text else None


def word_time(post, meta, n, phrase):
    """n번 장면 대본(vo) 안 phrase가 말해지는 릴스 시각(목소리 기준, NARR_OFFSET 전). 못 찾으면 None."""
    import tts
    s = resolved(post)[n - 1]
    i = s["vo"].find(phrase)
    if i < 0:
        return None
    v = _vcfg(post)
    pre = tts.eleven_text(s["vo"][:i], v.get("normalize", True), v.get("words")) if i else ""
    a, b = meta["spans"][n - 1]
    k = min(b - 1, a + len(pre.rstrip()) + (1 if pre.strip() else 0))
    while k < b - 1 and not meta["text"][k].strip():
        k += 1
    return meta["t"][k]


def asr_check(post, folder, model="small"):
    """받아쓰기(tts_ko_norm.verify_audio, faster-whisper)로 장면마다 대본대로 읽혔는지 (narration.wav를 장면별로 잘라서)."""
    import tempfile
    from tts_ko_norm import print_verify, verify_audio
    words = _vcfg(post).get("words")
    meta = narration(post, folder)
    bad = []
    with tempfile.TemporaryDirectory() as td:
        for s in resolved(post):
            if meta:
                sc = meta["scenes"][s["n"] - 1]
                f = Path(td) / f"{s['n']:02d}.wav"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{sc['speech_start']:.3f}", "-to",
                                f"{sc['speech_end']:.3f}", "-i", str(Path(folder) / VOICE_DIR / NARR),
                                "-af", "adelay=300:all=1,apad=pad_dur=0.5", str(f)], check=True)   # 앞뒤 무음: 짧은 조각 받아쓰기 안정
            else:
                f = voice_file(folder, s["n"])
            r = verify_audio(f, s["vo"], words, model=model)
            print(f"  {s['n']:02d} 대본: {s['vo']}")
            print_verify(r)
            if not r["ok"]:
                bad.append(s["n"])
    return bad


# ---------------- 계획 ----------------
def _beat(post):
    return 60.0 / float((post.get("music") or {}).get("bpm", 120))


def plan(post, folder, need_voice=True):
    """장면 시각. narration.json이 있으면 목소리 글자 시각대로(장면 = 그 줄 말 시작 직전), 단어 신호(at)도 시각으로."""
    import math
    folder = Path(folder)
    R = post["photo_reel"]
    sc = resolved(post)
    meta = narration(post, folder)
    problems = []
    if meta:
        starts = [0.0] + [NARR_OFFSET + m["speech_start"] - 0.06 for m in meta["scenes"][1:]]
        main_end = NARR_OFFSET + meta["end"] + END_HOLD
    else:
        problems.append(f"목소리 없음 또는 대본이 바뀜: {VOICE_DIR}/{NARR} (py -3.12 agent/photoreel.py <폴더> --voice)")
        starts, t = [], 0.0
        for s in sc:
            starts.append(t)
            t += max(MIN_SCENE, len(_norm(s["vo"])) / CHARS_PER_SEC + GAP)
        main_end = t
    beat = _beat(post)
    cta_start = math.ceil(main_end / beat - 1e-6) * beat
    scenes = []
    for i, s in enumerate(sc):
        t0 = starts[i]
        t1 = starts[i + 1] if i + 1 < len(sc) else cta_start
        cue = {}

        def at(phrase, default=None):
            if not phrase:
                return default
            if not meta:
                return default if default is not None else 0.3
            w = word_time(post, meta, s["n"], phrase)
            if w is None:
                problems.append(f"{s['n']}번 장면: '{phrase}'가 대본(vo)에 없음 (at)")
                return default if default is not None else 0.3
            return round(max(0.0, NARR_OFFSET + w - t0), 3)
        o = s["overlay"] or {}
        cue["ov"] = at(o.get("at"), 0.12)
        cue["sub"] = at(o.get("sub_at"), cue["ov"] + 0.18)
        cue["punch"] = at(o.get("punch_at"), None)
        cue["letters"] = [[at(a, 0.12), txt] for a, txt in (o.get("letters") or [])]
        cue["items"] = [at(it.get("at"), None) if isinstance(it, dict) else None for it in (o.get("items") or [])]
        cue["pops"] = [at(pp.get("at"), 0.1) for pp in s["pops"]]
        if meta:
            m = meta["scenes"][i]
            vo_len = m["speech_end"] - m["speech_start"]
        else:
            vo_len = len(_norm(s["vo"])) / CHARS_PER_SEC
        scenes.append(dict(s, t0=round(t0, 3), dur=round(t1 - t0, 3), vo_len=round(vo_len, 3), cue=cue))
    total = round(cta_start + (CTA_LEN if cta_text(post) else 0), 3)
    return {"scenes": scenes, "main": round(cta_start, 3), "total": total, "problems": problems if need_voice else [],
            "meta": meta, "beat": beat}


def cta_text(post):
    d = post.get("dm") or {}
    return (d.get("cta") or post.get("end_cta") or "").strip() or None


def beats(p):
    out, seen = [], set()
    for s in p["scenes"]:
        if s["beat"] and s["beat"] not in seen:
            seen.add(s["beat"])
            out.append(f"{s['beat']} {s['t0']:.1f}초")
    return out


def hit_times(p):
    """숫자 쾅·로고 톡 시각 (릴스 시각) → 효과음."""
    out = []
    for s in p["scenes"]:
        c, t0 = s["cue"], s["t0"]
        o = s["overlay"] or {}
        if o.get("type") == "big" and not c["letters"]:
            out.append(t0 + c["ov"])
        out += [t0 + t for t, _ in c["letters"]]
        if c["punch"] is not None:
            out.append(t0 + c["punch"])
        out += [t0 + t for t in c["items"] if t is not None]
        out += [t0 + t for t in c["pops"]]
    return sorted(round(t, 3) for t in out)


# ---------------- 화면 ----------------
def _img_uri(folder, rel):
    p = Path(folder) / rel
    mime = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def page_html(post, p, folder, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    title = post["title"]
    hl = post.get("highlight") or ""

    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def mark(s, h):
        s = esc(s).replace("\n", "<br>")
        return s.replace(esc(h), f'<span class="hl">{esc(h)}</span>', 1) if h else s
    imgs = {s["img"]: _img_uri(folder, s["img"]) for s in p["scenes"]}
    for s in p["scenes"]:
        for pp in s["pops"]:
            imgs[pp["img"]] = _img_uri(folder, pp["img"])
    cta = cta_text(post)
    data = {"scenes": [{k: s[k] for k in ("t0", "dur", "img", "focus", "zoom", "credit", "overlay", "overlay_at", "pops", "cue")} |
                       {"cap": mark(s["cap"], s["hl"])} for s in p["scenes"]], "imgs": imgs, "main": p["main"]}
    cta_html = ""
    if cta:
        body = esc(cta).replace("\n", "<br>")
        cta_html = f'<div id="cta"><div class="wrap"><div class="brand">TOKEN WAR</div><div class="t" id="ctat">{body}</div><div class="bar2"></div></div></div>'
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-SemiBold.otf');font-weight:600}}
*{{box-sizing:border-box}} html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};word-break:keep-all}}
#ph{{position:absolute;left:0;top:{BAND}px;width:{W}px;height:{H - BAND}px;overflow:hidden}}
#ph img{{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}}
#shade{{position:absolute;inset:0;background:rgba(0,0,0,.22)}}
#band{{position:absolute;left:0;top:0;width:{W}px;height:{BAND}px;background:{b['bg']}}}
#title{{position:absolute;left:{SIDE + 10}px;right:{SIDE + 10}px;top:{SAFE_TOP + 22}px;font-family:'Black Han Sans';font-size:76px;line-height:1.17;letter-spacing:-.01em}}
.hl{{color:{b['accent']}}}
#credit{{position:absolute;left:{SIDE}px;top:{BAND + 14}px;font:600 22px Wanted;color:#d7ddd9;background:rgba(0,0,0,.62);padding:4px 10px}}
#ov{{position:absolute;left:{SIDE}px;right:{SIDE}px;top:{BAND + 70}px}}
#pops{{position:absolute;inset:0;pointer-events:none}}
.pop{{position:absolute;background:#fff;padding:10px 14px;display:flex;align-items:center;justify-content:center}}
.pop img{{display:block}}
.big{{display:inline-block;font-family:'Black Han Sans';font-size:150px;line-height:1;color:{b['accent']};background:{b['bg']};padding:18px 26px 10px;letter-spacing:-.02em}}
.sub{{display:inline-block;margin-top:14px;font:700 38px Wanted;background:{b['bg']};padding:10px 18px}}
.row{{display:flex;align-items:baseline;gap:20px;background:{b['bg']};padding:6px 20px;margin-bottom:8px;width:max-content}}
.row .d{{font:700 32px Wanted;color:{b['muted']};min-width:140px}}
.row .v{{font-family:'Black Han Sans';font-size:54px}}
.row.on .v{{color:{b['accent']}}}
.punch{{display:inline-block;font-family:'Black Han Sans';font-size:80px;color:{b['bg']};background:{b['accent']};padding:10px 22px 2px;margin-top:4px}}
.bar{{margin-bottom:14px}}
.bar .lab{{display:inline-block;font:800 36px Wanted;background:{b['bg']};padding:6px 14px}}
.bar .track{{height:72px;margin-top:6px;position:relative}}
.bar .fill{{position:absolute;left:0;top:0;bottom:0;background:#cfd6d2}}
.bar.on .fill{{background:{b['accent']}}}
.bar .val{{position:absolute;top:6px;font-family:'Black Han Sans';font-size:54px;color:{b['bg']};padding-left:16px;white-space:nowrap}}
.note{{display:inline-block;font:600 28px Wanted;color:#d7ddd9;background:rgba(0,0,0,.7);padding:6px 12px}}
#cap{{position:absolute;left:{SIDE}px;right:{SIDE}px;bottom:{H - CAP_BOTTOM}px;text-align:center}}
#cap span.box{{display:inline;font:800 54px/1.42 Wanted;background:{b['bg']};padding:6px 16px;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
#cta{{position:absolute;inset:0;background:{b['bg']};display:none}}
#cta .wrap{{position:absolute;left:90px;right:90px;top:{SAFE_TOP + 120}px;bottom:{H - SAFE_BOTTOM + 60}px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:44px;text-align:center}}
#cta .brand{{font-family:'Black Han Sans';font-size:44px;color:{b['accent']}}}
#cta .t{{font-family:'Black Han Sans';font-size:82px;line-height:1.25;letter-spacing:-.02em}}
#cta .bar2{{width:160px;height:8px;background:{b['accent']}}}
</style></head><body><div id="f">
<div id="ph"><img id="im"><div id="shade"></div></div>
<div id="band"><div id="title">{mark(title, hl)}</div></div>
<div id="credit"></div><div id="ov"></div><div id="pops"></div><div id="cap"></div>{cta_html}</div>
<script>
const D = {json.dumps(data, ensure_ascii=False)};
const PW = {W}, PH = {H - BAND};
const im = document.getElementById('im'), ov = document.getElementById('ov'), cap = document.getElementById('cap'), cr = document.getElementById('credit'), pops = document.getElementById('pops');
const cta = document.getElementById('cta');
const nat = {{}};
let cur = -1;
function ease(x){{x=Math.min(1,Math.max(0,x));return 1-Math.pow(1-x,3)}}
function slam(x){{ // 쾅: 크게 → 제자리 (0.16초), 아직이면 0
  if(x < 0) return null; const k = Math.min(1, x/0.16); return 1 + 0.38*Math.pow(1-k, 2) - 0.05*Math.sin(Math.PI*k);
}}
function popk(x){{ if(x < 0) return null; const k = Math.min(1, x/0.2); return k < 0.6 ? 0.4 + 0.75*k/0.6 : 1.15 - 0.15*(k-0.6)/0.4; }}
function countText(s, k){{
  const m = s.match(/[0-9][0-9,]*(\\.[0-9]+)?/); if(!m || k>=1) return s;
  const raw = m[0], dec = (m[1]||'').length ? m[1].length-1 : 0, v = parseFloat(raw.replace(/,/g,''));
  let x = v*k; let t = dec ? x.toFixed(dec) : Math.round(x).toString();
  if(raw.includes(',')) t = Number(t).toLocaleString('en-US', {{minimumFractionDigits:dec, maximumFractionDigits:dec}});
  return s.replace(raw, t);
}}
function esc(s){{return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')}}
function build(sc){{
  const o = sc.overlay || {{}}; let h = '';
  if(o.type==='big'){{ h = `<div><span class="big" id="bigv"${{o.size?` style="font-size:${{o.size}}px"`:''}}></span></div>` + (o.sub?`<div><span class="sub" id="subv">${{esc(o.sub)}}</span></div>`:''); }}
  else if(o.type==='steps'){{ h = (o.items||[]).map((it,i)=>`<div class="row${{i==o.items.length-1?' on':''}}" id="st${{i}}"><span class="d">${{esc(it[0])}}</span><span class="v">${{esc(it[1])}}</span></div>`).join('') + (o.punch?`<div><span class="punch" id="pu">${{esc(o.punch)}}</span></div>`:''); }}
  else if(o.type==='bars'){{ h = (o.items||[]).map((it,i)=>`<div class="bar${{it.on?' on':''}}" id="br${{i}}"><span class="lab">${{esc(it.label)}}</span><div class="track"><div class="fill" id="bf${{i}}"></div><span class="val" id="bv${{i}}">${{esc(it.display)}}</span></div></div>`).join('') + (o.note?`<div><span class="note" id="nt">${{esc(o.note)}}</span></div>`:''); }}
  ov.innerHTML = h;
  pops.innerHTML = (sc.pops||[]).map((pp,i)=>`<div class="pop" id="pp${{i}}" style="left:${{pp.x}}px;top:${{pp.y}}px"><img src="${{D.imgs[pp.img]}}" style="height:${{pp.h||70}}px"></div>`).join('');
  cap.innerHTML = sc.cap ? `<span class="box">${{sc.cap}}</span>` : '';
  cr.textContent = sc.credit || ''; cr.style.display = sc.credit ? 'block' : 'none';
  im.src = D.imgs[sc.img];
  ov.style.top = '{BAND + 70}px';
}}
function place(sc){{
  if(sc.overlay_at !== 'low') return;
  const capTop = sc.cap ? {CAP_BOTTOM} - cap.offsetHeight : {CAP_BOTTOM};
  ov.style.top = (capTop - 24 - ov.offsetHeight) + 'px';
}}
async function init(){{
  for(const [k,u] of Object.entries(D.imgs)){{ const i = new Image(); i.src = u; await i.decode(); nat[k] = [i.naturalWidth || 400, i.naturalHeight || 100]; }}
}}
function problems(){{
  const out = [];
  D.scenes.forEach((sc,i)=>{{ build(sc); frameIn(sc, sc.dur - 0.01, true);
    for(const el of ov.querySelectorAll('.big,.sub,.row,.punch,.lab,.note,.val')){{
      const b = el.getBoundingClientRect(); if(b.right > {W - SIDE} + 1) out.push(`장면 ${{i+1}} 정리 글이 오른쪽 안전 영역을 넘음: ${{el.textContent}}`);
      const capTop = sc.cap ? cap.getBoundingClientRect().top : {CAP_BOTTOM};
      if(b.bottom > capTop - 14) out.push(`장면 ${{i+1}} 정리 글이 자막과 겹침: ${{el.textContent}}`); }}
    for(const el of pops.querySelectorAll('.pop')){{ const b = el.getBoundingClientRect();
      if(b.right > {W - SIDE} + 1 || b.left < {SIDE} - 1 || b.top < {BAND} || b.bottom > {CAP_BOTTOM}) out.push(`장면 ${{i+1}} 로고가 안전 영역 밖`);
      for(const o2 of ov.querySelectorAll('.big,.sub,.row,.punch,.lab,.note')){{ const c = o2.getBoundingClientRect();
        if(!(b.right < c.left || b.left > c.right || b.bottom < c.top || b.top > c.bottom)) out.push(`장면 ${{i+1}} 로고가 정리 글과 겹침: ${{o2.textContent}}`); }}
      const cb = cap.getBoundingClientRect(); if(sc.cap && !(b.bottom < cb.top || b.top > cb.bottom || b.right < cb.left || b.left > cb.right)){{
        for(const rc of cap.querySelector('.box').getClientRects()){{ if(!(b.right < rc.left || b.left > rc.right || b.bottom < rc.top || b.top > rc.bottom)) out.push(`장면 ${{i+1}} 로고가 자막과 겹침`); }} }} }}
    const cb = cap.getBoundingClientRect(); if(sc.cap && cb.height > 2*54*1.42 + 30) out.push(`장면 ${{i+1}} 자막이 2줄을 넘음`);
    for(const el of cap.querySelectorAll('.box')){{ for(const rc of el.getClientRects()){{ if(rc.right > {RAIL_LEFT} && rc.bottom > {RAIL_TOP}) out.push(`장면 ${{i+1}} 자막이 오른쪽 아래 버튼 줄과 겹침`); }} }}
    const tb = document.getElementById('title').getBoundingClientRect(); if(tb.bottom > {BAND - 8}) out.push('제목이 위 띠를 넘음');
  }});
  cur = -1; return out;
}}
function show(el, k){{ if(!el) return; if(k === null){{ el.style.visibility = 'hidden'; }} else {{ el.style.visibility = 'visible'; el.style.transform = `scale(${{k}})`; }} }}
function frameIn(sc, lt, still){{
  const [nw, nh] = nat[sc.img]; const base = Math.max(PW/nw, PH/nh);
  const z0 = sc.zoom[0], z1 = sc.zoom[1];
  const punch = 1 + 0.07*(1-ease(lt/0.32));
  const z = base * (z0 + (z1-z0)*Math.min(1, lt/sc.dur)) * punch;
  const w = nw*z, h = nh*z;
  const x = Math.min(0, Math.max(PW - w, PW/2 - sc.focus[0]*w)), y = Math.min(0, Math.max(PH - h, PH/2 - sc.focus[1]*h));
  im.style.transform = `translate(${{x}}px,${{y}}px) scale(${{z}})`;
  im.style.width = nw+'px'; im.style.height = nh+'px';
  const o = sc.overlay || {{}}, c = sc.cue;
  if(o.type==='big'){{ const el = document.getElementById('bigv'); el.style.transformOrigin = 'left bottom';
    if(c.letters.length){{ let txt = null, t0 = 0; for(const [t, s] of c.letters){{ if(lt >= t){{ txt = s; t0 = t; }} }}
      if(txt === null){{ show(el, null); }} else {{ el.textContent = txt; show(el, still ? 1 : slam(lt - t0)); }} }}
    else {{ const k = still ? 1 : ease((lt - c.ov)/0.5); el.textContent = o.count===false ? o.big : countText(o.big, k); show(el, still ? 1 : slam(lt - c.ov)); }}
    const sb = document.getElementById('subv'); if(sb){{ const a = still ? 1 : ease((lt - c.sub)/0.22); sb.style.visibility = lt >= c.sub || still ? 'visible' : 'hidden';
      sb.style.opacity = a; sb.style.transform = `translateY(${{18*(1-a)}}px)`; }} }}
  if(o.type==='steps'){{ const n = (o.items||[]).length; (o.items||[]).forEach((it,i)=>{{ const el = document.getElementById('st'+i);
      if(i === n-1 && c.punch !== null && !o.punch){{ el.style.transformOrigin = 'left center'; const k = still ? 1 : slam(lt - c.punch);
        el.style.opacity = k === null ? 0 : 1; el.style.transform = `scale(${{k === null ? 1 : k}})`; return; }}
      const t = c.ov + i*0.28; const a = still ? 1 : ease((lt - t)/0.2);
      el.style.opacity = a; el.style.transform = `translateX(${{-40*(1-a)}}px)`; }});
    const pu = document.getElementById('pu'); if(pu){{ const tp = c.punch !== null ? c.punch : c.ov + (o.items||[]).length*0.28; show(pu, still ? 1 : slam(lt - tp)); pu.style.transformOrigin = 'left center'; }} }}
  if(o.type==='bars'){{ const its = o.items||[]; const mx = Math.max(...its.map(i=>i.value)); const full = PW - 2*{SIDE};
    its.forEach((it,i)=>{{ const ti = c.items[i] !== null ? c.items[i] : c.ov + i*0.35; const a = still ? 1 : ease((lt - ti)/0.45);
      const row = document.getElementById('br'+i); row.style.visibility = (still || lt >= ti) ? 'visible' : 'hidden';
      document.getElementById('bf'+i).style.width = (full*0.78*it.value/mx*a)+'px'; const v = document.getElementById('bv'+i);
      v.style.opacity = a > 0.6 ? 1 : 0; const sk = still ? 1 : slam(lt - ti - 0.3); v.style.transform = `scale(${{sk === null ? 1 : sk}})`; v.style.transformOrigin = 'left center'; }});
    const nt = document.getElementById('nt'); if(nt){{ const tl = Math.max(...its.map((it,i)=> c.items[i] !== null ? c.items[i] : c.ov + i*0.35)); nt.style.opacity = still ? 1 : ease((lt - tl - 0.3)/0.25); }} }}
  (sc.pops||[]).forEach((pp,i)=>{{ const el = document.getElementById('pp'+i); show(el, still ? 1 : popk(lt - c.pops[i])); }});
  const ca = still ? 1 : ease((lt-0.05)/0.22); cap.style.opacity = ca; cap.style.transform = `translateY(${{22*(1-ca)}}px)`;
  place(sc);
}}
function frame(t){{
  if(cta){{ if(t >= D.main){{ cta.style.display = 'block'; const k = slam(t - D.main); document.getElementById('ctat').style.transform = `scale(${{k}})`; return; }} cta.style.display = 'none'; }}
  let i = D.scenes.findIndex(s => t >= s.t0 && t < s.t0 + s.dur); if(i < 0) i = D.scenes.length - 1;
  const sc = D.scenes[i]; if(i !== cur){{ build(sc); cur = i; }}
  frameIn(sc, t - sc.t0, false);
}}
</script></body></html>"""


async def _shoot(html_file, times, out_dir):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await pw.chromium.launch(executable_path=exe) if exe else await pw.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(html_file.as_uri())
        await pg.evaluate("""async () => { await document.fonts.load('96px "Black Han Sans"', '가A1');
            for (const w of [600, 700, 800]) await document.fonts.load(w + ' 30px Wanted', '가A1');
            await document.fonts.ready; }""")
        await pg.evaluate("init()")
        problems = await pg.evaluate("problems()")
        el = await pg.query_selector("#f")
        if not problems:
            for k, t in enumerate(times):
                await pg.evaluate(f"frame({t:.5f})")
                await el.screenshot(path=str(out_dir / f"f{k:05d}.jpg"), type="jpeg", quality=92)
        await browser.close()
    return problems


def sfx_track(p, total):
    from music_gen import make_hook_sfx
    sc = p["scenes"]
    imp = [0.0] + [s["t0"] for k, s in enumerate(sc) if s["beat"] in ("rehook", "answer") and k and sc[k - 1]["beat"] != s["beat"]]
    if total > p["main"] + 0.01:
        imp.append(p["main"])                      # 끝 화면: 박에 맞춘 쾅
    wh = [s["t0"] for s in sc[1:] if all(abs(s["t0"] - t) > 0.05 for t in imp)]
    hits = [t for t in hit_times(p) if all(abs(t - u) > 0.08 for u in imp)]
    return make_hook_sfx(total, impacts=imp, hits=hits, whooshes=wh, riser_to=None, drop=None)


def make_photo_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, 페이드 없이 박에서 끝, -14 LUFS), frames/*.jpg. 전체 길이(초)."""
    folder = Path(folder)
    e, _ = check_photo_reel(post, folder)
    p = plan(post, folder)
    if e or p["problems"]:
        raise ValueError("\n".join(e + p["problems"]))
    work = folder / "_photo"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html_file = work / "reel.html"
    html_file.write_text(page_html(post, p, folder, cfg), encoding="utf-8")
    total = p["total"]
    nfr = int(round(total * FPS))
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
        from music_gen import make_hook_music
        music = work / "music.wav"
        make_hook_music(music, 60 / p["beat"], total)
    voices = [(NARR_OFFSET, folder / VOICE_DIR / NARR)] if p["meta"] else []
    sfx, _info = sfx_track(p, total)
    mixed = work / "mix.wav"
    info = mix_audio(music, voices, total, mixed, sfx)
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{total:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    from loudness import normalize
    normalize(out)
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    for k, s in enumerate(p["scenes"], 1):
        t = s["t0"] + s["dur"] * 0.85
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.rmtree(work)
    print("장면: " + " | ".join(f"{s['n']:02d} {s['beat']} {s['t0']:.2f}~{s['t0'] + s['dur']:.2f}초 {Path(s['img']).name}"
                               for s in p["scenes"]))
    print("박자: " + " → ".join(beats(p)) + f" → 끝 화면 {p['main']:.2f}초 (박), 끝 {total:.2f}초 (페이드 없음)")
    print("쾅·톡: " + ", ".join(f"{t:.2f}" for t in hit_times(p)))
    if p["meta"]:
        print("장면 사이 쉼: " + ", ".join(f"{g['after']}→{g['after'] + 1} {g['set']:.2f}초" for g in p["meta"]["gaps"]))
    if info.get("voices"):
        print(f"소리: 말하는 동안 목소리가 음악보다 {info['diff_in_speech_db']:.1f}dB 큼")
    return total


# ---------------- 검사 ----------------
def check_photo_reel(post, folder=None):
    errors, warnings = [], []
    R = post.get("photo_reel") or {}
    sc = R.get("scenes") or []
    if len(sc) < 3:
        errors.append("photo_reel.scenes는 3개 이상")
    for i, s in enumerate(sc, 1):
        if not s.get("img"):
            errors.append(f"photo_reel {i}번 장면에 img(사진) 없음: 모든 장면에 사진 (운영자 2026-11-17 '사진은 무조건')")
        elif folder and not (Path(folder) / s["img"]).exists():
            errors.append(f"photo_reel {i}번 장면 사진 파일 없음: {s['img']}")
        if s.get("img") and not s.get("credit"):
            errors.append(f"photo_reel {i}번 장면 credit(사진 출처·라이선스) 없음")
        for pp in s.get("pops") or []:
            if not pp.get("img") or not pp.get("at"):
                errors.append(f"photo_reel {i}번 pops에 img·at 필요")
            elif folder and not (Path(folder) / pp["img"]).exists():
                errors.append(f"photo_reel {i}번 pops 그림 파일 없음: {pp['img']}")
        if not s.get("vo") or not s.get("cap"):
            errors.append(f"photo_reel {i}번 장면 vo(내레이션)·cap(자막) 필요")
        if s.get("beat") and s["beat"] not in BEATS:
            errors.append(f"photo_reel {i}번 beat는 {BEATS} 중 하나")
        for k in ("cap", "cap_final"):
            if len(_lines(s.get(k) or "")) > 2:
                errors.append(f"photo_reel {i}번 {k}는 2줄 이하")
        texts = [s.get(k) for k in ("vo", "cap", "vo_final", "cap_final")] + [json.dumps(s.get(k) or {}, ensure_ascii=False)
                                                                              for k in ("overlay", "overlay_final")]
        for t in texts:
            m = DISCLAIMER_RE.search(t or "")
            if m:
                errors.append(f"photo_reel {i}번 장면 '{m.group(0)}': 면책·권유 문구 금지, 사실만 (STYLE_GUIDE 0 원칙 6)")
    got = [s.get("beat") for s in sc]
    for b in ("hook", "rehook", "answer"):
        if b not in got:
            warnings.append(f"photo_reel 5박자: '{b}' 장면이 없음 (STYLE_GUIDE 6장)")
    ipo = post.get("ipo") or {}
    vs = ipo_vars(post)
    cmp_ = ipo.get("compare") or {}
    if cmp_.get("krw_jo") and vs.get("cap_krw_jo") is not None and vs["cap_krw_jo"] <= float(cmp_["krw_jo"]):
        errors.append(f"공모가 기준 시가총액 {vs['cap_krw']}이 {cmp_.get('name')} {cmp_['krw_jo']}조 원보다 크지 않음: 비교 장면을 고칠 것")
    try:
        for s in resolved(post):
            for k in ("vo", "cap"):
                if "{" in (s.get(k) or ""):
                    errors.append(f"photo_reel {s['n']}번 {k} 글자 틀이 안 채워짐: {s[k]}")
            o = s["overlay"] or {}
            for ph in [o.get("at"), o.get("sub_at"), o.get("punch_at")] + [a for a, _ in (o.get("letters") or [])] + \
                      [it.get("at") for it in (o.get("items") or []) if isinstance(it, dict)] + [pp.get("at") for pp in s["pops"]]:
                if ph and ph not in s["vo"]:
                    errors.append(f"photo_reel {s['n']}번 신호 '{ph}'가 대본(vo)에 없음")
    except (KeyError, ValueError) as e:
        errors.append(f"photo_reel 글자 틀 오류: {e} (ipo 블록 값 확인)")
    if folder:
        p = plan(post, folder, need_voice=False)
        if not 18 <= p["total"] <= 40:
            warnings.append(f"photo_reel {p['total']:.1f}초: 20~35초 권장")
        if p["scenes"] and p["scenes"][0]["dur"] > 4.0:
            warnings.append(f"후킹 장면이 {p['scenes'][0]['dur']:.1f}초까지: 0~3초 안에 (STYLE_GUIDE 6장)")
    return errors, warnings


def _lines(t):
    return [x for x in str(t).split("\n") if x.strip()]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--voice", action="store_true", help="목소리 만들기 (대본 전체 한 번, 바뀌었을 때만)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--asr", action="store_true", help="받아쓰기로 확인 (장면별)")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    folder = Path(a.folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    if a.voice:
        make_narration(post, folder, a.force)
    if a.asr:
        bad = asr_check(post, folder)
        print("다시 만들 줄:", bad or "없음")
    e, w = check_photo_reel(post, folder)
    for x in w:
        print("경고:", x)
    for x in e:
        print("오류:", x)
    p = plan(post, folder, need_voice=False)
    for s in p["scenes"]:
        c = s["cue"]
        print(f"{s['n']:02d} {s['beat'] or '':7} {s['t0']:6.2f}~{s['t0'] + s['dur']:6.2f}초 말 {s['vo_len']:.2f}초  쾅 {c['ov']:.2f}  {s['vo']}")
    print(f"본편 {p['main']:.2f}초, 끝 {p['total']:.2f}초  박자: {' → '.join(beats(p))}")
    if p["meta"]:
        print("장면 사이 쉼: " + ", ".join(f"{g['after']}→{g['after'] + 1} {g['natural']:.2f}→{g['set']:.2f}초" for g in p["meta"]["gaps"]))


if __name__ == "__main__":
    main()
