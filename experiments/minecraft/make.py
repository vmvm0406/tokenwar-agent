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
def sfx(kind):
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
    "absorbtons": [(0.3, "slurp"), ("r0.3", "slurp"), ("r0.55", "thud")],
    "nether": [("r0.45", "fizz")],
    "realanimal": [("r0.15", "whoosh"), ("r0.3", "pop"), ("r0.75", "pop"), ("r0.8", "pop")],
}


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
            sec = s["d"] * float(at[1:]) if isinstance(at, str) else at
            i = int((s["t0"] + sec) * SR); x = sfx(kind); fx[i: i + len(x)] += x[: len(fx) - i]
    mix = mix + fx * 0.55
    return scenes, mix[: int(SR * total)], total





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
    body = {"text": text, "model_id": "eleven_v3", "language_code": "ko", "voice_settings": {"stability": 0.5}}
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
    for si, l in clips:
        c = decode(HERE / l[2][5:])
        gap = np.zeros(int(SR * 0.45), np.float32)
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
            sec = s["d"] * float(at[1:]) if isinstance(at, str) else at
            j = int((s["t0"] + sec) * SR); x = sfx(kind); fx[j: j + len(x)] += x[: len(fx) - j]
    return scenes, (mix + fx * 0.55)[: int(SR * total)], total


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def render_video(scenes, total, fps, wav, out):
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
        pg.evaluate("ep => { window.EP = ep; }", {"scenes": scenes})
        for k in range(n):
            url = pg.evaluate("T => { renderTimeline(T); return document.getElementById('c').toDataURL('image/png'); }", k / fps)
            ff.stdin.write(base64.b64decode(url.split(",", 1)[1]))
            if k % 150 == 0:
                print(f"  프레임 {k}/{n}", file=sys.stderr, flush=True)
        b.close()
    ff.stdin.close(); ff.wait()
    srv.shutdown()


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
        render_video(scenes, total, a.fps, wav, out)
        print(out)


if __name__ == "__main__":
    main()
