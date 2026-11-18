"""사무실 책상 장면 렌더러 (운영자 2026-11-18): 대본 JSON → 대사 음성(ElevenLabs v3, voices.json) → three.js 프레임 → mp4.

대본 JSON (experiments/office/scripts/<이름>.json):
  {"cast": [{"key": "man", "human": true}, {"key": "claude", "x": -0.42, "z": 0.18, "yaw": 0.25}, ...],
   "lines": [{"who": "man", "say": "[sighs] 아... 보고서 다 해 오래요.", "sub": "아… 보고서 다 해 오래요.", "emo": "sad", "gap": 0.3}, ...],
   "events": [{"line": 0, "dt": 0.1, "who": "man", "do": "facepalm", "d": 1.6}, {"t": 3.0, "who": "claude", "do": "look", "at": "man"}],
   "shots": [{"line": 0, "cam": "wide"}, {"line": 1, "cam": "close:claude"}, {"line": 2, "cam": "two:claude:chatgpt"}],
   "tail": 1.2}
  - 대사는 차례로 이어 붙인다 (gap = 앞 대사 끝과의 틈). events/shots의 "line": n, "dt": 초 = n번 대사 시작 + dt초 (또는 "t": 절대초).
  - do: hop(펄쩍) nod(끄덕) shake(도리도리) tilt(갸웃, d) tremble(부들부들, d) look(at: 캐릭터|camera) / 사람: facepalm(d) sigh nod type(d) look.
  - emo: neutral(기본 무표정) smile happy surprised sad angry embarrassed sleepy. 대사의 emo는 그 대사부터 바뀜. 이벤트에도 emo 가능.
  - cam: wide(책상 전체) | close:<누구>(가까이·뒤 흐림) | two:<a>:<b>(둘). 컷마다 천천히 다가감.

실행 (저장소 루트):
  py -3.12 experiments/office/render.py experiments/office/scripts/motion_test.json [--gpu] [--stills 0.5,3,6]
결과: experiments/office/out/<이름>.mp4 (out/은 커밋 안 함)
"""
import argparse
import asyncio
import base64
import hashlib
import json
import mimetypes
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FPS = 30
HOST = "http://tw.local/"
SWIFT = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
GPU = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
VOICES = json.loads((ROOT / "experiments" / "lowpoly-chars" / "voices.json").read_text(encoding="utf-8"))
CACHE = Path.home() / ".cache" / "tokenwar-tts" / "office"


def tts_line(who, text):
    """대사 → mp3 (같은 글·목소리면 캐시, 다시 과금 안 됨)."""
    sys.path.insert(0, str(ROOT / "agent"))
    import tts
    v = VOICES["voices"][who]
    body = {"text": text, "model_id": VOICES["model"], "voice_settings": VOICES["settings"]}
    h = hashlib.sha256(json.dumps([v["voice_id"], body], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    f = CACHE / f"{h}.mp3"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(tts._eleven(f"/text-to-speech/{v['voice_id']}?output_format=mp3_44100_128", tts.eleven_key(), body, accept="audio/mpeg"))
        print(f"  ElevenLabs {len(text)}자 ({who})", file=sys.stderr)
    return f


def decode(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def trim_silence(a, sr=16000, th=0.01):
    idx = np.where(np.abs(a) > th)[0]
    return (idx[0] / sr, idx[-1] / sr) if len(idx) else (0.0, len(a) / sr)


LEAD = 0.4   # 첫 대사 전 여유


def tts_single(l):
    """한 대사를 지정 모델로 따로 (예: v3가 발음을 뭉갤 때 v2, 운영자 2026-11-18 '조롱'). tts_dialogue와 같은 모양으로 돌려줌."""
    sys.path.insert(0, str(ROOT / "agent"))
    import tts
    v = VOICES["voices"][l["who"]]
    if l["model"] == "eleven_v3":   # v3 한 줄짜리 (대화 기능보다 발음이 안정적일 때)
        body = {"text": l["say"], "model_id": "eleven_v3", "language_code": "ko", "voice_settings": {"stability": 0.5}}
    else:
        body = {"text": l["say"], "model_id": l["model"], "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": l.get("style", 0.3)}}
    if l.get("seed") is not None:
        body["seed"] = l["seed"]
    h = hashlib.sha256(json.dumps([v["voice_id"], body], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    f = CACHE / f"one_{h}.mp3"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(tts._eleven(f"/text-to-speech/{v['voice_id']}?output_format=mp3_44100_128", tts.eleven_key(), body, accept="audio/mpeg"))
        print(f"  ElevenLabs {len(l['say'])}자 ({l['who']}, {l['model']})", file=sys.stderr)
    if SPEED != 1.0:
        fs = f.with_name(f.stem + f"_x{SPEED:.2f}.mp3")
        if not fs.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-af", f"atempo={SPEED}", "-b:a", "192k", str(fs)], check=True)
        f = fs
    dur = len(decode(f)) / 16000
    return f, {"segs": [[0.0, dur]], "ranges": [[0, len(l["say"])]], "chars": [], "starts": []}


def tts_dialogue(lines_in):
    if len(lines_in) == 1 and lines_in[0].get("model"):
        return tts_single(lines_in[0])
    """대사 묶음을 한 번에 (ElevenLabs text-to-dialogue, v3): 대사 사이가 자연스럽게 이어진다 (운영자 2026-11-18 '뚝뚝 끊김').
    → (mp3, 대사별 [시작, 끝]초). 같은 대본이면 캐시."""
    sys.path.insert(0, str(ROOT / "agent"))
    import tts
    script = {"lines": lines_in}
    body = {"inputs": [{"text": l["say"], "voice_id": VOICES["voices"][l["who"]]["voice_id"]} for l in script["lines"]],
            "model_id": VOICES["model"], "language_code": "ko", "settings": VOICES["settings"]}
    if lines_in[0].get("seed") is not None:   # 같은 글을 다시 뽑고 싶을 때 (발음이 어긋난 녹음 바꾸기)
        body["seed"] = lines_in[0]["seed"]
    h = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    f, js = CACHE / f"dlg2_{h}.mp3", CACHE / f"dlg2_{h}.json"
    if not (f.exists() and js.exists()):
        CACHE.mkdir(parents=True, exist_ok=True)
        r = json.loads(tts._eleven("/text-to-dialogue/with-timestamps?output_format=mp3_44100_128", tts.eleven_key(), body))
        f.write_bytes(base64.b64decode(r["audio_base64"]))
        segs, ranges = {}, {}
        for s in r["voice_segments"]:
            i = s["dialogue_input_index"]
            a, b = segs.get(i, (s["start_time_seconds"], s["end_time_seconds"]))
            segs[i] = (min(a, s["start_time_seconds"]), max(b, s["end_time_seconds"]))
            c0, c1 = ranges.get(i, (s["character_start_index"], s["character_end_index"]))
            ranges[i] = (min(c0, s["character_start_index"]), max(c1, s["character_end_index"]))
        al = r.get("alignment") or {}
        n = len(script["lines"])
        js.write_text(json.dumps({"segs": [segs[i] for i in range(n)], "ranges": [ranges[i] for i in range(n)],
                                  "chars": al.get("characters", []), "starts": al.get("character_start_times_seconds", [])},
                                 ensure_ascii=False), encoding="utf-8")
        print(f"  ElevenLabs 대화 {sum(len(l['say']) for l in script['lines'])}자", file=sys.stderr)
    d = json.loads(js.read_text(encoding="utf-8"))
    # 말 빠르게 (운영자 2026-11-18 "전체적으로 말 빨리"): 음높이 그대로 atempo, 시각도 같은 비율로
    if SPEED != 1.0:
        fs = f.with_name(f.stem + f"_x{SPEED:.2f}.mp3")
        if not fs.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-af", f"atempo={SPEED}", "-b:a", "192k", str(fs)], check=True)
        f = fs
        d["segs"] = [[a / SPEED, b / SPEED] for a, b in d["segs"]]
        d["starts"] = [x / SPEED for x in d["starts"]]
    return f, d


SPEED = 1.22   # 운영자 2026-11-18 '전체적으로 말 더 빨리' (1.12 → 1.22)


CLIP_FPS = 15


def clip_frames(cid, c):
    """화면 속 릴스: 구간을 15fps 작은 JPEG로 (out/clipframes/<id>/). 원본·프레임 모두 커밋 안 함."""
    """선택 필드 (리트냥이, 2026-11-18): "land": true → 가로 영상(뉴스·영화)을 16:9로 (모니터 꽉 채움, "res" 가로 픽셀, 기본 1280),
    "image": 경로 → 정지 그림 한 장 (수사 보드 등, from/to 없음)."""
    d = HERE / "out" / "clipframes" / cid
    key = json.dumps(c, sort_keys=True)
    if d.exists() and (d / "key.txt").exists() and (d / "key.txt").read_text(encoding="utf-8") != key:
        shutil.rmtree(d)          # 구간·해상도를 바꾸면 다시 뽑음
    if not d.exists() or not any(d.glob("*.jpg")):
        d.mkdir(parents=True, exist_ok=True)
        if c.get("image"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / c["image"]), "-q:v", "2", str(d / "0001.jpg")], check=True)
        else:
            if c.get("land"):
                w = int(c.get("res", 1280)); h = w * 9 // 16
                vf = f"fps={CLIP_FPS},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            else:
                vf = f"fps={CLIP_FPS},scale=360:640:force_original_aspect_ratio=increase,crop=360:640"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(c["from"]), "-to", str(c["to"]), "-i", str(ROOT / c["file"]),
                            "-vf", vf, "-q:v", "3" if c.get("land") else "4", str(d / "%04d.jpg")], check=True)
        (d / "key.txt").write_text(key, encoding="utf-8")
    n = len(list(d.glob("*.jpg")))
    return {"n": n, "fps": CLIP_FPS, "base": f"/experiments/office/out/clipframes/{cid}/", "credit": c.get("credit", ""),
            "land": bool(c.get("land") or c.get("image"))}


def whisper_align(mp3, says):
    """대사 묶음 음성을 받아써서(단어 시각) 대본 글자에 맞춤 → 대사마다 [(글자, 시작, 끝)] (글자·숫자만).
    대본과 받아쓰기 글자를 difflib으로 짝짓고, 못 짝지은 글자는 앞뒤 시각으로 메움. 결과는 mp3 옆 .wa.json 캐시."""
    import difflib
    import re as _re
    cache = Path(str(mp3) + ".wa2.json")
    key = json.dumps(says, ensure_ascii=False)
    if cache.exists():
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("key") == key:
            return c["per"]
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(decode(mp3), language="ko", word_timestamps=True)
    hc = []                                   # 받아쓴 글자와 시각
    for sg in segs:
        for w in sg.words:
            word = w.word
            for en, ko in (("GPT", "지피티"), ("gpt", "지피티"), ("AI", "에이아이")):   # 받아쓰기가 영어로 적은 이름
                word = word.replace(en, ko)
            chs = [ch for ch in word if ch.isalnum()]
            for j, ch in enumerate(chs):
                a = w.start + (w.end - w.start) * j / max(1, len(chs))
                hc.append((ch, a, a + (w.end - w.start) / max(1, len(chs))))
    lines = [[ch for ch in _re.sub(r"\[[^\]]*\]", "", s) if ch.isalnum()] for s in says]
    want = [ch for l in lines for ch in l]
    times = [None] * len(want)
    sm = difflib.SequenceMatcher(None, want, [h[0] for h in hc], autojunk=False)
    for bl in sm.get_matching_blocks():
        for j in range(bl.size):
            times[bl.a + j] = hc[bl.b + j][1:]
    known = [i for i, x in enumerate(times) if x]
    if not known:
        return None
    for i in range(len(times)):              # 빈 곳 메우기 (가장 가까운 앞 글자 끝 / 뒤 글자 시작)
        if times[i] is None:
            prev = max([k for k in known if k < i], default=None)
            nxt = min([k for k in known if k > i], default=None)
            t = times[prev][1] if prev is not None else times[nxt][0]
            times[i] = (t, t + 0.05)
    per, pos = [], 0
    for l in lines:
        per.append([(ch, round(times[pos + j][0], 3), round(times[pos + j][1], 3)) for j, ch in enumerate(l)])
        pos += len(l)
    cache.write_text(json.dumps({"key": key, "per": per}, ensure_ascii=False), encoding="utf-8")
    return per


def split_subs_aligned(sub, d, k, line_t0):
    """자막 조각 경계를 일레븐랩스 글자 시각으로 정확히 (운영자 2026-11-18 '자막 타이밍이 안 맞아').
    대본 say의 글자(대괄호 감정 표시 제외, 글자·숫자만 셈) 순서로 자막 조각의 글자 수를 맞춰, 다음 조각 첫 글자의 시작 시각에서 끊음."""
    parts = [p.strip() for p in sub.split("|") if p.strip()]
    if len(parts) <= 1 or not d.get("chars"):
        return None
    spoken = [x[1] for x in (d.get("_per") or [[]] * (k + 1))[k]]
    if not spoken:
        return None
    cnt = lambda s: sum(ch.isalnum() for ch in s)
    total = sum(cnt(p) for p in parts) or 1
    out, acc, prev = [], 0, 0.0
    for i, p in enumerate(parts):
        acc += cnt(p)
        if i < len(parts) - 1:
            j = min(len(spoken) - 1, acc)   # 자막 글자 순서 = 말한 글자 순서 (비율로 하면 잘린 대사에서 어긋남)
            cut = max(prev, spoken[j] - line_t0 - 0.05)
        else:
            cut = 1e9
        out.append({"text": p, "t0": round(prev, 3), "t1": round(cut, 3)})
        prev = cut
    return out


def split_subs(sub, env, dur):
    """자막을 호흡에 맞게 나눔 (운영자 2026-11-18): 대본 자막의 '|'에서 끊고, 끊는 시각은 글자 비율 근처(±0.45초)에서
    소리가 가장 작은 곳(숨 쉬는 틈)으로. → [{"text", "t0", "t1"}] (대사 시작 기준 초)."""
    parts = [p.strip() for p in sub.split("|") if p.strip()]
    if len(parts) <= 1:
        return [{"text": sub.replace("|", " ").strip(), "t0": 0.0, "t1": round(dur, 3)}]
    total = sum(len(p) for p in parts)
    cuts, acc = [], 0
    for p in parts[:-1]:
        acc += len(p)
        guess = int(acc / total * len(env))
        lo, hi = max(1, guess - int(0.45 * FPS)), min(len(env) - 1, guess + int(0.45 * FPS))
        k = min(range(lo, hi + 1), key=lambda j: env[j] + 0.002 * abs(j - guess)) if hi > lo else guess
        cuts.append(k / FPS)
    bounds = [0.0] + cuts + [dur]
    return [{"text": p, "t0": round(bounds[i], 3), "t1": round(bounds[i + 1], 3)} for i, p in enumerate(parts)]


def build(script):
    """대사 음성·시각·입 모양(소리 크기) 계산 → JS에 넘길 타임라인.
    intro(선택): 대사 전에 릴스 소리 구간. lines의 "break": n초 → 거기서 대화 묶음을 나누고 n초 쉼(자막 카드 자리)."""
    intro = script.get("intro")
    lead = (intro["to"] - intro["from"] + intro.get("pad", 0.3)) if intro else LEAD
    groups, cur = [], []
    for i, l in enumerate(script["lines"]):
        if l.get("overlay"):          # 겹쳐 나오는 소리(예: 흥얼거림)는 대화 순서 밖 → 아래에서 따로
            continue
        if (l.get("break") is not None or l.get("model") or (cur and script["lines"][cur[-1]].get("model"))) and cur:
            groups.append(cur); cur = []
        cur.append(i)
    groups.append(cur)
    hop, lines, parts, t0 = 16000 // FPS, [None] * len(script["lines"]), [], lead
    for gi, g in enumerate(groups):
        t0 += script["lines"][g[0]].get("break", 0.12) if gi else 0
        mp3, dd = tts_dialogue([script["lines"][i] for i in g])
        segs = [list(s) for s in dd["segs"]]
        # 대사 구간은 voice_segments보다 글자 시각이 정확함 (같은 사람이 이어 말할 때 경계가 1초쯤 어긋남) → 말한 글자 첫·끝으로
        # 대사·자막 시각은 받아쓰기 단어 시각으로 (일레븐랩스 글자 시각은 실제 소리보다 0.7초까지 어긋남, 2026-11-18 확인)
        per = whisper_align(mp3, [script["lines"][i]["say"] for i in g])
        if per:
            dd["_per"] = per
            for k in range(len(g)):
                if per[k]:
                    segs[k] = [max(0.0, per[k][0][1] - 0.15), per[k][-1][2] + 0.12]
        # "cut_after": "조롱받" → 그 글자까지만 들리고 소리를 툭 끊음 (팝콘에 맞아 말이 끊김, 운영자 2026-11-18)
        mutes = []
        for k, i in enumerate(g):
            ca = script["lines"][i].get("cut_after")
            if ca and per and per[k]:
                import re as _re
                body_ = "".join(ch for ch in _re.sub(r"\[[^\]]*\]", "", script["lines"][i]["say"]) if ch.isalnum())
                key_ = "".join(ch for ch in ca if ch.isalnum())
                j = body_.rfind(key_)
                if j >= 0:
                    cut = per[k][min(len(per[k]) - 1, j + len(key_) - 1)][2] + 0.03
                    mutes.append([round(cut, 3), round(segs[k][1] + 0.4, 3)])
                    segs[k][1] = cut
        a = decode(mp3)
        parts.append({"file": str(mp3), "t": round(t0, 3), "mute": mutes})
        for k, i in enumerate(g):
            l = script["lines"][i]
            s0, s1 = segs[k]
            seg = a[int(s0 * 16000): int(s1 * 16000)]
            q0, q1 = trim_silence(seg)                               # 구간 안의 실제 소리 시작·끝
            seg = seg[int(q0 * 16000): int(q1 * 16000) + 1]
            env = [float(np.sqrt(np.mean(seg[j:j + hop] ** 2))) for j in range(0, len(seg), hop)] or [0.0]
            peak = max(env) or 1
            lines[i] = {"who": l["who"], "t": round(t0 + s0 + q0, 3), "dur": round(len(seg) / 16000, 3),
                        "env": [round(e / peak, 3) for e in env], "sub": (l.get("sub") or "").replace("|", " "),
                        "subs": split_subs_aligned(l.get("sub") or "", dd, k, s0 + q0) or split_subs(l.get("sub") or "", env, len(seg) / 16000),
                        "emo": l.get("emo"), "note": l.get("note"), "src": str(mp3), "ofs": round(s0 + q0, 3)}
        t0 += len(a) / 16000
    dur = t0 + script.get("tail", 1.0)
    # 겹쳐 나오는 소리: {"overlay": {"line": n, "dt": 초, "vol": 0~1}} — 그 대사 시작 기준으로 얹음 (자막 없음, 입은 움직임)
    for i, l in enumerate(script["lines"]):
        if not l.get("overlay"):
            continue
        ov = l["overlay"]
        mp3, dd = tts_dialogue([l])
        a = decode(mp3)
        s0, s1 = trim_silence(a)
        seg = a[int(s0 * 16000): int(s1 * 16000) + 1]
        env = [float(np.sqrt(np.mean(seg[j:j + hop] ** 2))) for j in range(0, len(seg), hop)] or [0.0]
        peak = max(env) or 1
        t = lines[ov["line"]]["t"] + ov.get("dt", 0)
        parts.append({"file": str(mp3), "t": round(t - s0, 3), "vol": ov.get("vol", 0.5)})
        lines[i] = {"who": l["who"], "t": round(t, 3), "dur": round(len(seg) / 16000, 3), "env": [round(e / peak * 0.7, 3) for e in env],
                    "sub": None, "subs": None, "emo": l.get("emo"), "note": None, "src": str(mp3), "ofs": round(s0, 3), "overlay": True}

    def at(e):   # "end": true → 그 대사 끝 기준
        if "t" in e:
            return e["t"]
        L_ = lines[e["line"]]
        return L_["t"] + (L_["dur"] if e.get("end") else 0) + e.get("dt", 0)
    timed = lambda key: [dict(e, t=round(max(0, at(e)), 3)) for e in script.get(key, [])]
    shots = sorted(timed("shots"), key=lambda s: s["t"])
    shots[0]["t"] = 0
    cards = timed("cards")
    for c in cards:
        if c.get("kind") == "end":          # 끝 화면은 영상 끝까지
            c["d"] = round(dur - c["t"] + 0.1, 3)
        if "until_line" in c:
            c["d"] = round(lines[c["until_line"]]["t"] - c["t"], 3)
    clips = {cid: clip_frames(cid, c) for cid, c in script.get("clips", {}).items()}
    return {"cast": script["cast"], "lines": lines, "events": timed("events"), "shots": shots, "dur": round(dur, 3), "fps": FPS,
            "parts": parts, "intro": intro, "lead": lead, "clips": clips, "clipsrc": script.get("clips", {}),
            "screens": sorted(timed("screens"), key=lambda s: s["t"]), "cards": cards, "audio": timed("audio"), "props": script.get("props", {}), "sfx": timed("sfx")}


def check_pron(tl, script):
    """발음 확인 (운영자 2026-11-18 '발음 신경 쓰자'): 대사마다 받아써서 대본과 다르면 표시."""
    import difflib
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    bad, cache = 0, {}
    for l, src in zip(tl["lines"], script["lines"]):
        if l.get("overlay"):
            continue
        a = cache.setdefault(l["src"], decode(l["src"]))
        s = int(l["ofs"] * 16000)
        seg = a[max(0, s - 1600): s + int(l["dur"] * 16000) + 1600]
        heard = " ".join(x.text.strip() for x in m.transcribe(seg, language="ko")[0])
        want = l.get("sub") or src["say"]
        norm = lambda x: "".join(ch for ch in x if ch.isalnum())
        r = difflib.SequenceMatcher(None, norm(want), norm(heard)).ratio()
        flag = "OK " if r >= 0.92 else "확인"
        bad += r < 0.92
        print(f"  [{flag}] {r:.2f} {l['who']}: 대본「{want}」 들림「{heard}」")
    return bad


async def shoot(tl, frames, out_dir, gpu, still):
    from playwright.async_api import async_playwright

    async def serve(route):
        rel = route.request.url[len(HOST):].split("?")[0]
        f = (ROOT / rel).resolve()
        if ROOT not in f.parents or not f.is_file():
            return await route.fulfill(status=404, body="")
        ct = {".js": "text/javascript", ".otf": "font/otf", ".glb": "model/gltf-binary"}.get(
            f.suffix, mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        await route.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ct})

    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=GPU if gpu else SWIFT)
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route(HOST + "**", serve)
        await pg.goto(HOST + "experiments/office/index.html")
        await pg.wait_for_function("window.twReady === true", timeout=60000)
        js_tl = {k: v for k, v in tl.items() if k not in ("parts", "intro", "clipsrc", "audio", "sfx")}
        js_tl["lines"] = [{k: v for k, v in l.items() if k not in ("src", "ofs")} for l in tl["lines"]]
        info = await pg.evaluate("(s) => window.twInit(s)", js_tl)
        print(json.dumps(info, ensure_ascii=False), flush=True)
        for k in frames:
            data = await pg.evaluate(f"window.twFrame({k / FPS:.5f})")
            name = f"still_{k:04d}.jpg" if still else f"f{k:05d}.jpg"
            (out_dir / name).write_bytes(base64.b64decode(data.split(",", 1)[1]))
        if errs:
            print("JS 오류:", errs[:5], file=sys.stderr)
        await b.close()


def encode(tl, frames_dir, mp4):
    """소리: (intro 릴스 → 페이드아웃) + 대화 묶음들(그대로, 숨·틈 자연스럽게) + 장면 속 릴스 소리(작게)."""
    ins, fl, labs = [], [], []

    def add(path, chain):
        ins.extend(["-i", str(path)])
        k = len(ins) // 2          # 0번 입력은 프레임
        fl.append(f"[{k}:a]{chain}[s{k}]")
        labs.append(f"[s{k}]")
    it = tl.get("intro")
    if it:
        L = it["to"] - it["from"]
        add(ROOT / it["clip"], f"atrim={it['from']}:{it['to']},asetpts=PTS-STARTPTS,afade=t=out:st={L - it.get('fade', 1.0):.2f}:d={it.get('fade', 1.0)},"
                               f"aformat=sample_rates=44100:channel_layouts=stereo,volume=0.9")
    for p in tl["parts"]:
        d = int(p["t"] * 1000)
        mute = "".join(f",volume=0:enable='between(t,{a_},{b_})'" for a_, b_ in p.get("mute", []))
        add(p["file"], f"aformat=sample_rates=44100:channel_layouts=stereo,volume={p.get('vol', 1.0)}{mute},adelay={d}|{d}")
    for x in tl.get("audio", []):
        c = tl["clipsrc"][x["clip"]]
        d = int(x["t"] * 1000)
        add(ROOT / c["file"], f"atrim={x['from']}:{x['to']},asetpts=PTS-STARTPTS,afade=t=in:d=0.3,afade=t=out:st={x['to'] - x['from'] - 0.6:.2f}:d=0.6,"
                              f"aformat=sample_rates=44100:channel_layouts=stereo,volume={x.get('vol', 0.2)},adelay={d}|{d}")
    # 효과음 (직접 합성, 라이선스 문제 없음): ding(스킬 연결) boing(펄쩍) swipe(릴스 넘김) crunch(팝콘) pop(내려놓기) tiptoe(살금살금)
    SFX = {
        "ding": "aevalsrc='0.32*(sin(2*PI*1318*t)+0.6*sin(2*PI*1975*t))*exp(-t*5)':d=0.9:s=44100",
        "boing": "aevalsrc='0.3*sin(2*PI*(300*t+900*t*t))*exp(-t*9)':d=0.35:s=44100",
        "swipe": "anoisesrc=d=0.3:c=white:a=0.6:r=44100,highpass=f=1500,lowpass=f=7000,afade=t=in:d=0.1,afade=t=out:st=0.12:d=0.18,volume=0.45",
        "crunch": "anoisesrc=d=0.08:c=pink:a=0.9:r=44100,bandpass=f=2600:w=1800,afade=t=out:st=0.02:d=0.06,volume=0.5",
        "pop": "aevalsrc='0.4*sin(2*PI*190*t)*exp(-t*28)':d=0.18:s=44100",
        "tiptoe": "aevalsrc='0.22*sin(2*PI*880*t)*exp(-t*40)':d=0.1:s=44100",
        "boom": "aevalsrc='0.55*sin(2*PI*52*t)*exp(-t*1.6)+0.18*sin(2*PI*104*t)*exp(-t*3)':d=2.4:s=44100",   # 쿵 (긴장되는 순간)
    }
    for i, x in enumerate(tl.get("sfx", [])):
        d = int(x["t"] * 1000)
        ins.extend(["-f", "lavfi", "-i", SFX[x["kind"]]])
        k = len([v for v in ins if v == "-i"])
        fl.append(f"[{k}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={x.get('vol', 1.0)},adelay={d}|{d}[x{i}]")
        labs.append(f"[x{i}]")
    fc = ";".join(fl) + ";" + "".join(labs) + f"amix=inputs={len(labs)}:normalize=0,apad,loudnorm=I=-14:TP=-1.5[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.jpg")] + ins +
                   ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(tl["dur"]), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(mp4)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--stills", help="확인용 초(쉼표), 예: 0.5,3,6")
    ap.add_argument("--check", action="store_true", help="발음만 확인 (받아쓰기)")
    a = ap.parse_args()
    sp = Path(a.script)
    script = json.loads(sp.read_text(encoding="utf-8"))
    tl = build(script)
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    print(f"길이 {tl['dur']}초, 대사 {len(tl['lines'])}개", flush=True)
    if a.check:
        sys.exit(1 if check_pron(tl, script) else 0)
    if a.stills:
        frames = [int(float(x) * FPS) for x in a.stills.split(",")]
        asyncio.run(shoot(tl, frames, out, a.gpu, True))
        print("\n".join(str(out / f"still_{k:04d}.jpg") for k in frames))
        return
    fd = out / f"frames_{sp.stem}"   # 대본마다 따로 (두 영상을 동시에 만들어도 안 섞이게)
    if fd.exists():
        shutil.rmtree(fd)
    fd.mkdir()
    asyncio.run(shoot(tl, list(range(int(tl["dur"] * FPS))), fd, a.gpu, False))
    mp4 = out / f"{sp.stem}.mp4"
    encode(tl, fd, mp4)
    shutil.rmtree(fd)
    print(mp4)


if __name__ == "__main__":
    main()
