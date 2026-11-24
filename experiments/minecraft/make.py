"""마인크래프트 블록 파고들기 영상 만들기 (운영자 2026-11-22).
episodes/<이름>.json → 내레이션(ElevenLabs, 줄마다 앞뒤 문맥) → 장면 길이·자막 시각 → 효과음 → scene.html 프레임 → mp4.
  py -3.12 experiments/minecraft/make.py experiments/minecraft/episodes/sponge.json <출력.mp4> [--fps 30] [--audio-only]
줄 형식: [자막] 또는 [자막, 읽을 글] 또는 [자막, 읽을 글, "v3"] (v3: [whispers] 같은 감정 태그)."""
import argparse, base64, functools, hashlib, http.server, json, shutil, subprocess, sys, threading
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "agent"))
import tts  # noqa: E402

SR = 44100
GAP_LINE, GAP_SCENE, LEAD, TAIL, MIN_SCENE = 0.10, 0.28, 0.25, 0.9, 1.9


def decode(f):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(f), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim(a, th=0.02):
    w = 441
    n = len(a) // w
    rms = np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(1))
    on = np.where(rms > max(th * rms.max(), 1e-4))[0]
    if not len(on):
        return a
    return a[max(0, on[0] * w - 441): min(len(a), (on[-1] + 1) * w + 2205)]


def voice_line(say, prev, nxt, model, voice):
    if model == "v3":
        body = {"text": say, "model_id": "eleven_v3", "language_code": "ko", "voice_settings": {"stability": 0.5}}
        h = hashlib.sha256(json.dumps([voice, body], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
        f = tts.ELEVEN_CACHE / f"v3_{h}.mp3"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(tts._eleven(f"/text-to-speech/{voice}?output_format=mp3_44100_128", tts.eleven_key(), body, accept="audio/mpeg"))
            print(f"  ElevenLabs v3 {len(say)}자", file=sys.stderr)
        return f
    return tts.eleven_mp3(say, voice, previous_text=prev, next_text=nxt)


# ---------- 효과음 (직접 합성) ----------
_MC = {}


def sfx(kind):
    # 'mc:이름@크기' = 마인크래프트 게임 소리 (minecraft.wiki에서 받은 assets/sounds/<이름>.ogg, 커밋 안 함). 운영자 2026-11-23 '마크 소리 써도 됨'
    if kind.startswith("mc:"):
        name, _, opt = kind[3:].partition("@")   # 'mc:이름@0.6~1.2' = 크기 0.6, 1.2초에서 잘라 끝을 줄임
        vol, _, cut = opt.partition("~")
        if name not in _MC:
            a = decode(HERE / "assets" / "sounds" / f"{name}.ogg")
            _MC[name] = a / max(1e-6, float(np.abs(a).max()))
        a = _MC[name] * float(vol or 0.6)
        if cut:
            a = a[: int(SR * float(cut))].copy(); fo = min(len(a), int(SR * 0.2)); a[-fo:] *= np.linspace(1, 0, fo)
        return a.astype(np.float32)
    t = lambda d: np.arange(int(SR * d)) / SR
    rng = np.random.default_rng(len(kind))
    if kind == "pop":
        x = t(0.12); f = 500 + 900 * x / 0.12; s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-x * 25) * 0.35
    elif kind == "thud":
        x = t(0.45); s = (np.sin(2 * np.pi * 60 * x) * 0.9 + rng.normal(0, 0.25, len(x)) * np.exp(-x * 30)) * np.exp(-x * 9) * 0.8
    elif kind == "slap":
        x = t(0.15); s = rng.normal(0, 1, len(x)) * np.exp(-x * 40) * 0.45
    elif kind == "fizz":
        x = t(0.9); n = rng.normal(0, 1, len(x)); n = n - np.convolve(n, np.ones(6) / 6, "same"); s = n * np.exp(-x * 3.5) * 0.45
    elif kind == "slurp":
        x = t(1.6); f = 900 - 600 * x / 1.6; s = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * x)) * np.minimum(1, x * 8) * np.exp(-x * 1.2) * 0.22
    elif kind == "drip":
        x = t(0.18); f = 1400 - 900 * x / 0.18; s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 30) * 0.3
    elif kind == "whoosh":
        x = t(0.5); n = rng.normal(0, 1, len(x)); n = np.convolve(n, np.ones(20) / 20, "same"); s = n * np.sin(np.pi * x / 0.5) * 1.2
    elif kind == "splash":
        x = t(0.35); n = rng.normal(0, 1, len(x)); n = np.convolve(n, np.ones(4) / 4, "same"); s = n * np.exp(-x * 12) * 0.4
    elif kind == "boom":
        x = t(1.2); n = rng.normal(0, 1, len(x)); n = np.convolve(n, np.ones(30) / 30, "same") * 6
        s = (n + np.sin(2 * np.pi * 45 * x) * 0.8) * np.exp(-x * 3.5) * 0.7
    elif kind == "crack":
        x = t(0.3); s = rng.normal(0, 1, len(x)) * (np.exp(-x * 30) + 0.5 * np.exp(-np.abs(x - 0.08) * 60)) * 0.5
    elif kind == "portal":
        x = t(1.4); f = 180 + 60 * np.sin(2 * np.pi * 3 * x); s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, x * 3) * np.exp(-x * 1.5) * 0.3
    else:
        raise ValueError(kind)
    return s.astype(np.float32)


# 장면별 효과음: (시각, 종류). 숫자 = 장면 시작부터 초, 'r0.5' = 장면 길이 비율
CUES = {
    "hook": [(0.5, "slap"), (0.62, "slap")],
    "flood": [(0.2, "splash"), ("r0.4", "splash"), ("r0.7", "splash")],
    "drop": [(0.6, "thud"), (0.7, "slurp")],
    "bubble": [(0.05, "pop")],
    "useless": [(1.0, "pop")],
    "inventory": [("r0.35", "pop"), ("r0.55", "pop"), ("r0.75", "pop"), ("r0.9", "pop")],
    "revive": [("r0.35", "thud"), ("r0.7", "drip"), ("r0.8", "drip")],
    "absorb": [(0.3, "slurp"), ("r0.5", "slurp")],
    "tons": [(0.05, "pop"), ("r0.45", "thud")],
    "dry": [("r0.25", "fizz"), ("r0.58", "fizz")],
    "monument": [(0.6, "pop")],
    "textures": [(0.0, "pop"), (0.35, "pop"), (0.7, "pop")],
    "realsponge": [("r0.3", "whoosh"), ("r0.5", "pop")],
    "animal": [("r0.5", "pop"), ("r0.55", "pop")],
    "sieve": [("r0.2", "whoosh"), ("r0.55", "whoosh"), ("r0.92", "pop")],
    "next": [(0.3, "thud")],
    "follow": [],
    "bhook": [("s2-0.4", "whoosh"), ("s2+0.3", "crack"), ("s2+0.9", "slap")],
    "b2009": [("r0.1", "pop"), ("r0.3", "pop"), ("r0.5", "pop")],
    "b2010": [(0.62, "fizz"), (1.87, "fizz")],
    "b2011": [("r0.45", "pop"), ("r0.47", "crack"), ("r0.52", "slap")],
    "b2021": [("s1", "whoosh"), ("s1+1.0", "thud")],
    "bnow": [("r0.45", "pop")],
    "breal": [("r0.55", "crack")],
    "bdeep": [(0.1, "whoosh"), ("s1", "pop"), ("s2", "pop"), ("s3", "thud")],
    "thook": [("s2", "pop"), ("s2+0.05", "splash")],
    "t2009": [("s1+0.3", "slap"), ("s1+1.9", "boom")],
    "t2010": [(0.3, "drip"), ("s2", "pop"), ("s2+0.4", "pop"), ("s2+1.2", "pop")],
    "t2012": [(0.8, "whoosh")],
    "tdyna": [(0.4, "pop")],
    "treal": [(0.1, "pop"), ("r0.45", "whoosh")],
    "tmelt": [(0.0, "slap"), (0.625, "slap"), (1.25, "slap"), (1.875, "slap")],
    "ohook": [("s2", "crack"), ("s2+0.5", "slap")],
    "ocobble": [("s1+0.0", "crack"), ("s1+0.4", "pop")],
    "olava": [("r0.2", "splash"), ("r0.55", "fizz")],
    "otnt": [(0.2, "pop"), ("s1", "boom")],
    "oportal": [("r0.1", "pop"), ("r0.2", "pop"), ("s1+0.4", "portal")],
    "omine": [("s2", "whoosh"), ("s3", "pop"), ("s4", "pop")],
    "ovolcano": [(0.1, "fizz")],
    "oblade": [(0.1, "pop"), ("s1", "pop")],
    "nhook": [(0.3, "pop"), (0.8, "slap"), ("s1", "thud")],
    "n2012": [(0.2, "pop"), ("s1", "pop"), ("s1+0.2", "pop"), ("s1+0.4", "pop"), ("s1+0.6", "pop"), ("s1+0.8", "pop"), ("s1+0.95", "thud")],
    "nbuild": [("r0.05", "pop"), ("r0.12", "pop"), ("r0.19", "pop"), ("r0.26", "pop"), ("s1", "fizz"), ("s2", "whoosh"), ("s2+0.9", "thud")],
    "ncount": [(0.1, "pop"), ("r0.6", "thud")],
    "nloot": [(0.2, "drip"), (0.6, "pop"), (1.0, "pop"), ("s2", "thud")],
    "n2015": [(0.1, "portal"), ("s1+0.2", "crack"), ("s2", "pop"), ("s2+0.3", "slap")],
    "nnow": [("r0.2", "pop"), ("s1", "pop"), ("s1+0.4", "slap")],
    "shook": [(0.1, "pop"), ("s1", "whoosh")],
    "sslow": [(0.1, "whoosh"), ("r0.42", "pop"), ("r0.73", "thud")],
    "s2010": [(0.1, "portal"), ("s1", "pop")],
    "s2012": [("r0.05", "pop"), ("r0.13", "pop"), ("r0.21", "pop"), ("r0.29", "pop"), ("s1", "pop"), ("s1+0.2", "pop"), ("s1+0.4", "pop"), ("s2", "boom")],
    "s2018": [(0.1, "splash"), ("r0.4", "drip"), ("r0.7", "drip")],
    "s2020": [(0.2, "fizz"), ("s1", "slap")],
    "sreal": [(0.1, "whoosh"), ("s1", "pop")],
    # 스컬크 편: 마크 게임 소리 (운영자 2026-11-23 '효과음 잘 찾아보고', '마크 소리 써도 됨'). 함수 = 장면 정보로 시각 계산 (scene.html과 같은 식)
    "khook": [(lambda s: _sub(s, 0) + s["d"] * 0.3 - 0.4, "mc:Zombie_death@0.7"),
              (lambda s: _sub(s, 0) + s["d"] * 0.3 + 0.2, "mc:Sculk_spread1@0.7"),
              (lambda s: _sub(s, 0) + s["d"] * 0.3 + 0.55, "mc:Sculk_spread2@0.6"),
              (lambda s: _sub(s, 0) + s["d"] * 0.3 + 0.9, "mc:Sculk_spread3@0.6"),
              ("s1", "mc:Sculk_charge1@0.5")],
    "kname": [(0.1, "mc:Warden_heartbeat1@0.45"), ("s1-0.05", "mc:Warden_emerge@0.7~1.8")],
    "k2020": [(0.1, "mc:Click@0.5"), ("s1", "mc:Page_turn1@0.7"), ("s1+0.45", "mc:Page_turn2@0.7"), ("s1+1.0", "mc:Anvil_land@0.35~0.6")],
    "k2022": [(0.3, "mc:Sculk_charge2@0.6"), (0.6, "mc:Warden_angry1@0.55~1.3")]
             + [(lambda s, m=m: _sub(s, 2) + m * (s["d"] - _sub(s, 2)) * 0.16, f"mc:Sculk_shrieker_shriek{m + 1}@0.45~0.9") for m in range(4)]
             + [(lambda s: _sub(s, 2) + 3 * (s["d"] - _sub(s, 2)) * 0.16 + 0.05, "mc:Warden_emerge@0.7~1.6")],
    "kspread": [(0.6, "mc:Zombie_death@0.7"), (1.0, "mc:Sculk_charge1@0.5"), (1.6, "mc:Sculk_spread1@0.7"), (2.0, "mc:Sculk_spread2@0.6"), (2.4, "mc:Sculk_spread3@0.6")],
    "ktool": [(0.35, "mc:Stone_dig1@0.6"), (0.6, "slap"), (lambda s: s["d"] * 0.5, "mc:Hoe_till1@0.8"), (lambda s: s["d"] * 0.5 + 0.25, "mc:Sculk_Break1@0.6~0.7")],
    "kreal": [(0.1, "mc:Grass_dig1@0.5"), ("s2", "pop")],
    # 피스톤 편 (게임 소리)
    "ghook": [(0.05, "pop"), (0.9, "mc:Page_turn1@0.4"), ("s1", "mc:Random_break@0.6"), ("s1+0.3", "whoosh"), ("s1+0.9", "thud")],
    "g2010": [(0.15, "pop"), ("s1", "mc:Page_turn1@0.5"), ("s1+1.3", "slap")],
    "gpass": [(0.3, "mc:Grass_dig1@0.3"), ("s1+0.2", "mc:Zombie_hurt1@0.25")],
    "ghold": [(0.25, "splash"), ("s1", "mc:Grass_dig1@0.5"), ("s1+0.35", "thud")],
    "gtrap": [("s2", "pop"), ("s3", "mc:Grass_dig1@0.4"), ("s4-0.45", "whoosh"), ("s4", "mc:Grass_dig1@0.6"), ("s4+0.05", "pop"), ("s5", "mc:Random_break@0.6"), ("s5+0.5", "whoosh"), ("s5+1.1", "thud")],
    "gfake": [(0.2, "mc:Click@0.3"), ("s1", "whoosh"), ("s1+0.4", "splash")],
    "g2023": [(0.2, "mc:Page_turn2@0.5"), ("s1+0.45", "slurp"), ("s1+0.9", "slap")],
    "gseal": [(0.2, "mc:Page_turn1@0.5"), ("s1", "thud"), ("s1+0.9", "slap")],
    "whook": [(0.05, "mc:Click@0.3"), (0.35, "mc:Click@0.3"), (0.65, "mc:Click@0.3"), (1.0, "whoosh"), (1.3, "mc:Grass_dig1@0.5"), ("s1", "pop")],
    "wmap": [(0.1, "whoosh"), ("s1", "mc:Grass_dig1@0.5"), ("s1+0.4", "mc:Stone_dig1@0.4")],
    "wperlin": [(0.4, "pop")],
    "woct": [(0.4, "pop"), (0.9, "pop"), (1.4, "pop"), ("s1", "mc:Stone_dig2@0.4")],
    "w3d": [("s1", "whoosh"), ("s2", "mc:Stone_dig3@0.5")],
    "wcave": [(0.3, "whoosh"), ("s1", "mc:Cave1@0.35~2.0"), ("s2", "whoosh"), ("s2+0.6", "mc:Grass_dig1@0.5")],
    "wchunk": [(0.2, "pop"), ("s1", "mc:Grass_dig1@0.4"), ("s1+0.6", "mc:Grass_dig1@0.4"), ("s1+1.2", "mc:Grass_dig1@0.4")],
    "wreal": [(0.2, "mc:Click@0.3"), ("s1+0.6", "whoosh"), ("s2", "mc:Bell_use1@0.5~1.5")],
    "phook": [(0.35, "mc:Piston_extend_JE3@0.7"), ("s1", "mc:Anvil_land@0.35~0.6")],
    "p2011": [(0.1, "mc:Click@0.4"), ("s1+0.3", "whoosh"), ("s1+0.6", "mc:Piston_extend_JE3@0.6"), ("s2", "mc:Page_turn1@0.5")],
    "pbug": [(0.4, "mc:Piston_extend_JE3@0.6"), ("s1", "mc:Random_break@0.6"), ("s2+0.2", "slap")],
    "plimit": [(0.4, "mc:Piston_extend_JE3@0.7"), ("s1", "mc:Piston_extend_JE3@0.5"), ("s1+0.1", "slap")],
    "pimmov": [(0.4, "slap"), (0.75, "slap"), (1.1, "slap")],
    "preal": [(0.1, "mc:Piston_contract_JE3@0.4"), ("s3", "whoosh")],
    "pcompare": [(0.4, "mc:Piston_extend_JE3@0.7"), ("s2", "mc:Piston_extend_JE3@0.5"), ("s2+0.8", "mc:Piston_contract_JE3@0.4")],
    "ppress": [(0.2, "mc:Piston_contract_JE3@0.4"), ("s1+0.1", "mc:Anvil_land@0.6~0.8"), ("s1+0.12", "thud"), ("s2", "pop")],
    "rportal": [("s1", "mc:End_portal_activation@0.5~2.0"), ("s3", "mc:Nether_portal_ambient@0.35~1.5")],
    "rsift": [(0.1, "pop"), (0.28, "pop"), (0.46, "pop"), (0.64, "mc:Bell_use1@0.4~1.2"), ("s1", "pop")],
    # 보강된 심층암 편 (게임 소리)
    "rhook": [(lambda s, m=m: 0.1 + m * 0.36, f"mc:Stone_dig{m % 3 + 1}@0.35") for m in range(13)] + [("s2", "mc:Anvil_land@0.35~0.6")],
    "rcity": [(0.15 + m * 0.2, f"mc:Stone_dig{m % 3 + 1}@0.4") for m in range(6)] + [("s1", "mc:Warden_emerge@0.6~1.4")],
    "r2021": [(0.1, "mc:Click@0.4"), ("s1", "mc:Anvil_land@0.35~0.6"), ("s1+0.3", "mc:Page_turn1@0.5")],
    "rhard": [(0.2, "pop"), (0.35, "pop"), (0.5, "pop"), ("s1", "mc:Fuse@0.35~0.35"), ("s1+0.35", "mc:Explosion1@0.5~1.4"),
              ("s1+0.75", "mc:Wither_hurt1@0.45~0.8"), ("s1+1.45", "mc:Ender_dragon_hurt1@0.5~0.8")],
    "rvault": [(0.05, "mc:Anvil_land@0.3~0.5"), ("s1", "pop"), ("s2", "whoosh")],
    "rrank": [(0.05, "pop"), ("s1", "mc:Anvil_land@0.35~0.6"), ("s2", "mc:Anvil_land@0.35~0.6")],
    "rreal": [(lambda s: _sub(s, 1) + 0.6 - 0.3, "whoosh"), (lambda s: _sub(s, 1) + 0.6, "mc:Random_break@0.8"),
              (lambda s: _sub(s, 1) + 0.6, "crack")],
    "absorbtons": [(0.3, "slurp"), ("r0.3", "slurp"), ("r0.55", "thud")],
    "nether": [("r0.45", "fizz")],
    "realanimal": [("r0.15", "whoosh"), ("r0.3", "pop"), ("r0.75", "pop"), ("r0.8", "pop")],
}


def _sub(s, k):
    subs = s.get("subs") or []
    return subs[k][1] if k < len(subs) else s["d"] * 0.5


def cue_time(at, s):
    """효과음 시각: 숫자 = 장면 시작부터 초, 'r0.5' = 장면 길이 비율, 's2+0.5' = 2번째 자막 시작 + 초."""
    if callable(at):
        return at(s)
    if not isinstance(at, str):
        return at
    if at.startswith("r"):
        return s["d"] * float(at[1:])
    import re as _re
    m = _re.match(r"(\d+)([+-][\d.]+)?$", at[1:])
    k, off = int(m.group(1)), float(m.group(2) or 0)
    subs = s.get("subs") or []
    base = subs[k][1] if k < len(subs) else s["d"] * 0.5
    return base + off


def build_audio(ep, voice):
    lines_all = [(si, li, l) for si, s in enumerate(ep["scenes"]) for li, l in enumerate(s["lines"])]
    clips = {}
    for k, (si, li, l) in enumerate(lines_all):
        say = (l[1] if len(l) > 1 else l[0]).replace("|", " ")   # | = 자막 줄바꿈 자리
        model = l[2] if len(l) > 2 else None
        prev = lines_all[k - 1][2] if k else None
        nxt = lines_all[k + 1][2] if k + 1 < len(lines_all) else None
        get = lambda x: (x[1] if len(x) == 2 else x[0]).replace("|", " ") if x else None   # 앞뒤 문맥: 읽을 글(v3 줄은 자막 글)
        f = voice_line(say, get(prev), get(nxt), model, voice)
        clips[(si, li)] = trim(decode(f))
    t = LEAD
    voice_track, scenes = [], []
    for si, s in enumerate(ep["scenes"]):
        start = t
        subs = []
        for li, l in enumerate(s["lines"]):
            a = clips[(si, li)]
            subs.append([l[0], round(t - start, 3), round(t - start + len(a) / SR, 3)])
            voice_track.append((t, a))
            t += len(a) / SR + GAP_LINE
        t += GAP_SCENE - GAP_LINE
        d = max(t - start, MIN_SCENE)
        if si == len(ep["scenes"]) - 1:
            d += TAIL
        if si == 0:
            d += LEAD
            subs = [[x[0], x[1] + LEAD, x[2] + LEAD] for x in subs]
            start -= LEAD
        t = start + d
        # 다음 자막이 나올 때까지 이어서 보이게 (짧은 틈 메우기)
        for k in range(len(subs) - 1):
            subs[k][2] = subs[k + 1][1]
        subs[-1][2] = min(d, subs[-1][2] + 0.35)
        scenes.append(dict(s, d=round(d, 3), subs=subs, t0=round(start, 3)))
    total = sum(s["d"] for s in scenes)
    mix = np.zeros(int(SR * (total + 0.5)), np.float32)
    for t0, a in voice_track:
        i = int(t0 * SR); mix[i: i + len(a)] += a[: len(mix) - i]
    fx = np.zeros_like(mix)
    for s in scenes:
        for at, kind in CUES.get(s["scene"], []):
            sec = cue_time(at, s)
            i = int((s["t0"] + sec) * SR); x = sfx(kind); fx[i: i + len(x)] += x[: len(fx) - i]
    mix = mix + fx * 0.55
    return scenes, mix[: int(SR * total)], total





def squeeze_gaps(a, keep, th_db=-38.0):
    """keep초보다 긴 무음을 keep초로 줄인 소리와, 옛 시각 → 새 시각 함수."""
    w = int(SR * 0.01); n = len(a) // w
    db = 20 * np.log10(np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
    quiet = db < th_db
    cuts, k = [], 0
    while k < n:
        if quiet[k]:
            j = k
            while j < n and quiet[j]:
                j += 1
            if (j - k) * 0.01 > keep:
                mid = (k + j) / 2 * 0.01
                cuts.append((mid - ((j - k) * 0.01 - keep) / 2, mid + ((j - k) * 0.01 - keep) / 2))
            k = j
        else:
            k += 1
    out, last = [], 0
    for c0, c1 in cuts:
        out.append(a[int(last * SR): int(c0 * SR)]); last = c1
    out.append(a[int(last * SR):])
    def remap(t):
        sh = 0.0
        for c0, c1 in cuts:
            if t >= c1:
                sh += c1 - c0
            elif t > c0:
                sh += t - c0
        return t - sh
    return np.concatenate(out), remap


def onetake_audio(ep, voice):
    """본문 전체를 v3로 한 번에 녹음 (운영자 2026-11-22 '말이 뚝뚝 끊김'). 감정·쉬는 태그 [..]는 읽지 않음.
    글자 시각으로 줄·장면 시각을 잡는다."""
    all_lines = [(si, l) for si, s in enumerate(ep["scenes"]) for l in s["lines"]]
    # 줄의 셋째 칸 "clip:<파일>" = 녹음하지 않고 저장해 둔 소리를 끝에 붙임 (끝맺음 속삭임은 매 편 같은 말투, 운영자 2026-11-22)
    clips = [(si, l) for si, l in all_lines if len(l) > 2 and str(l[2]).startswith("clip:")]
    lines = [(si, l) for si, l in all_lines if (si, l) not in clips]
    text, spans = "", []
    for si, l in lines:
        say = (l[1] if len(l) > 1 else l[0]).replace("|", " ")
        if text:
            text += " "
        a = len(text); text += say; spans.append((a, len(text)))
    body = {"text": text, "model_id": "eleven_v3", "language_code": "ko", "voice_settings": {"stability": float(ep.get("stability", 0.5))}}   # 1.0 = 차분하게(추억 편)
    if ep.get("seed") is not None:
        body["seed"] = ep["seed"]
    h = hashlib.sha256(json.dumps([voice, body, "ts"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    f = tts.ELEVEN_CACHE / f"v3ts_{h}.mp3"; js = f.with_suffix(".json")
    if not (f.exists() and js.exists()):
        f.parent.mkdir(parents=True, exist_ok=True)
        d = json.loads(tts._eleven(f"/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128", tts.eleven_key(), body))
        f.write_bytes(base64.b64decode(d["audio_base64"]))
        js.write_text(json.dumps(d.get("alignment") or d.get("normalized_alignment"), ensure_ascii=False), encoding="utf-8")
        print(f"  ElevenLabs v3 {len(text)}자 (한 번에, 시각 포함)", file=sys.stderr)
    al = json.loads(js.read_text(encoding="utf-8"))
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    # 보낸 글의 '읽는 글자'(태그·공백·문장부호 빼고) 위치 → 받은 글자 시각 (순서대로 맞춤)
    def readable(seq):   # 태그 [..] 안·공백·문장부호를 뺀 글자 위치
        out, inside = [], False
        for k, c in enumerate(seq):
            if c == "[": inside = True; continue
            if c == "]": inside = False; continue
            if not inside and c.strip() and c not in ",.!?~'":
                out.append(k)
        return out
    spoken, got = readable(text), readable(chars)
    if len(got) != len(spoken):
        print(f"  ! 글자 수 다름: 보낸 {len(spoken)} / 받은 {len(got)} (비율로 맞춤)", file=sys.stderr)
    def at(i, end=False):
        pos = spoken.index(i) if i in spoken else 0
        k = got[min(len(got) - 1, round(pos * (len(got) - 1) / max(1, len(spoken) - 1)))] if len(got) != len(spoken) else got[pos]
        return en[k] if end else st[k]
    times = []
    for (a, b) in spans:
        idx = [i for i in spoken if a <= i < b]
        times.append((at(idx[0]), at(idx[-1], True)))
    tempo = float(ep.get("tempo", 1.0))   # 길이 맞추기: 목소리 높이는 그대로 빠르기만 (운영자 2026-11-22 "30~40초")
    if tempo != 1.0:
        ft = f.with_name(f.stem + f"_x{tempo:.2f}.mp3")
        if not ft.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-af", f"atempo={tempo}", "-b:a", "192k", str(ft)], check=True)
        f = ft
        times = [(a / tempo, b / tempo) for a, b in times]
    audio = decode(f)
    if ep.get("max_gap"):   # 긴 쉼 줄이기: 이보다 긴 조용한 구간은 이 길이로 (운영자 2026-11-22 "30~40초")
        audio, remap = squeeze_gaps(audio, float(ep["max_gap"]))
        times = [(remap(a), remap(b)) for a, b in times]
    for si, l in clips:
        c = decode(HERE / l[2][5:])
        # 본문 끝 무음을 0.05초만 남기고 잘라 속삭임이 늦게 나오지 않게 (운영자 2026-11-23 '조오금 늦게 나온다')
        w = int(SR * 0.01); n = len(audio) // w
        loud = np.where(20 * np.log10(np.sqrt((audio[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9) > -38)[0]
        if len(loud):
            audio = audio[: min(len(audio), (loud[-1] + 1) * w + int(SR * 0.05))]
        # 이어 붙인 티가 덜 나게: 소리 크기를 본문 말소리의 60%에 맞추고 쉼은 짧게 (운영자 2026-11-23 '끊기는 느낌')
        rms = lambda x: float(np.sqrt(np.mean(x[np.abs(x) > 0.02] ** 2))) if np.any(np.abs(x) > 0.02) else 1.0
        c = c * (0.6 * rms(audio) / rms(c))
        # 완전 무음(디지털 0)은 뚝 끊긴 느낌 → 본문 끝을 살짝 줄이고, 쉼은 아주 작은 잡음(방 소리)으로 채움
        fo = int(SR * 0.08); audio = audio.copy(); audio[-fo:] *= np.linspace(1, 0.15, fo, dtype=np.float32)
        gap = (np.random.default_rng(1).normal(0, 1, int(SR * 0.3)) * 10 ** (-58 / 20)).astype(np.float32)
        t0 = (len(audio) + len(gap)) / SR
        audio = np.concatenate([audio, gap, c])
        lines.append((si, l)); times.append((t0, t0 + len(c) / SR))
    return lines, times, audio


def build_onetake(ep, voice):
    lines, times, audio = onetake_audio(ep, voice)
    n = len(ep["scenes"])
    first = {}
    for k, (si, l) in enumerate(lines):
        first.setdefault(si, k)
    starts = [0.0] + [max(0.0, times[first[si]][0] - 0.15) + LEAD for si in range(1, n)]
    total = len(audio) / SR + LEAD + TAIL
    scenes = []
    for si, s in enumerate(ep["scenes"]):
        t0 = starts[si]; t1 = starts[si + 1] if si + 1 < n else total
        ks = [k for k, (x, _) in enumerate(lines) if x == si]
        subs = []
        for j, k in enumerate(ks):
            a = times[k][0] + LEAD - t0
            b = (times[ks[j + 1]][0] + LEAD - t0) if j + 1 < len(ks) else min(t1 - t0, times[k][1] + LEAD - t0 + 0.4)
            subs.append([lines[k][1][0], round(max(0.0, a), 3), round(b, 3)])
        scenes.append(dict(s, d=round(t1 - t0, 3), subs=subs, t0=round(t0, 3)))
    mix = np.zeros(int(SR * (total + 0.5)), np.float32)
    i = int(LEAD * SR); mix[i: i + len(audio)] += audio
    fx = np.zeros_like(mix)
    for s in scenes:
        for at, kind in CUES.get(s["scene"], []):
            sec = cue_time(at, s)
            j = int((s["t0"] + sec) * SR); x = sfx(kind); fx[j: j + len(x)] += x[: len(fx) - j]
    return scenes, (mix + fx * 0.55)[: int(SR * total)], total


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def render_video(scenes, total, fps, wav, out, meta=None):
    from playwright.sync_api import sync_playwright
    srv = serve()
    n = int(round(total * fps))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-i", "-", "-i", str(wav),
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(f"http://127.0.0.1:{srv.server_port}/scene.html")
        pg.evaluate("window.ready")
        pg.evaluate("ep => { window.EP = ep; }", dict(meta or {}, scenes=scenes))   # years·nextBlock 등도 넘김
        subs = [x[0] for sc in scenes for x in sc.get("subs", [])]
        for txt, ws in zip(subs, pg.evaluate("s => subWidths(s)", subs)):   # 자막이 세 줄로 넘치지 않게 미리 경고
            if max(ws) > 940:
                print(f"  ! 자막 한 줄이 너무 김({max(ws)}px > 940): {txt}  → 대본에서 | 로 나누거나 줄을 쪼갤 것", file=sys.stderr)
        for k in range(n):
            url = pg.evaluate("T => { renderTimeline(T); return document.getElementById('c').toDataURL('image/png'); }", k / fps)
            ff.stdin.write(base64.b64decode(url.split(",", 1)[1]))
            if k % 150 == 0:
                print(f"  프레임 {k}/{n}", file=sys.stderr, flush=True)
        b.close()
    ff.stdin.close(); ff.wait()
    srv.shutdown()


def edge_check(mp4, scenes=(), fps=4):
    """그림이 화면 양옆 끝에 닿아 잘렸는지 검사 (운영자 2026-11-23 '그림 안 잘리게 가운데로'). 닿은 시각을 경고로 출력."""
    w, h = 270, 480
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},scale={w}:{h}:flags=neighbor", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    y0, y1 = int(h * 440 / 1920), int(h * 1150 / 1920)
    hits = []
    for i, f in enumerate(fr):
        strip = np.concatenate([f[y0:y1, :6], f[y0:y1, -6:]], 1)
        tt = i / fps
        yr = any(sc.get("year") and sc["t0"] <= tt < sc["t0"] + sc["d"] for sc in scenes)
        top = f[y0 + 1: y0 + 4]   # 연도 장면: 띠 바로 아래(440px)에서 그림이 잘려 일자로 끊긴 것
        if (f.max(2) > 90).mean() > 0.6:   # 화면 전체 번쩍임은 잘림 아님
            continue
        if (strip.max(2) > 60).mean() > 0.01 or (yr and (top.max(2) > 60).mean() > 0.02):   # 배경은 밝기 40 아래, 어두운 블록(소울 샌드)도 잡게 60
            hits.append(round(i / fps, 1))
    if hits:
        print(f"  ⚠ 그림이 화면 옆 끝이나 연도 띠 아래에서 잘림: {hits[:20]}초", file=sys.stderr)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("out"); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--audio-only", action="store_true")
    a = ap.parse_args()
    ep = json.loads(Path(a.episode).read_text(encoding="utf-8"))
    voice = tts.eleven_voice_id(ep.get("voice", "deok"))
    scenes, mix, total = build_onetake(ep, voice) if ep.get("onetake") else build_audio(ep, voice)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw.wav"); wav = out.with_suffix(".wav")
    import soundfile as sf
    sf.write(raw, mix, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), str(wav)], check=True)
    raw.unlink()
    out.with_suffix(".timeline.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"길이 {total:.1f}초, 장면 {len(scenes)}개", file=sys.stderr)
    if not a.audio_only:
        render_video(scenes, total, a.fps, wav, out, {k: v for k, v in ep.items() if k != "scenes"})
        edge_check(out, scenes)
        print(out)


if __name__ == "__main__":
    main()
