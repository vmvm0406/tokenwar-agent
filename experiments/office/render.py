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


def build(script):
    """대사 음성·시각·입 모양(소리 크기) 계산 → JS에 넘길 타임라인."""
    t, lines = 0.4, []
    for i, l in enumerate(script["lines"]):
        mp3 = tts_line(l["who"], l["say"])
        a = decode(mp3)
        s0, s1 = trim_silence(a)
        seg = a[int(s0 * 16000): int(s1 * 16000)]
        hop = 16000 // FPS
        env = [float(np.sqrt(np.mean(seg[k:k + hop] ** 2))) for k in range(0, len(seg), hop)]
        peak = max(env) or 1
        t += l.get("gap", 0.25) if i else 0
        lines.append({"who": l["who"], "t": round(t, 3), "dur": round(len(seg) / 16000, 3), "env": [round(e / peak, 3) for e in env],
                      "sub": l.get("sub"), "emo": l.get("emo"), "mp3": str(mp3), "s0": s0})
        t += len(seg) / 16000
    dur = t + script.get("tail", 1.0)

    def at(e):
        return e["t"] if "t" in e else lines[e["line"]]["t"] + e.get("dt", 0)
    events = [dict(e, t=round(at(e), 3)) for e in script.get("events", [])]
    shots = sorted([dict(s, t=round(at(s) if ("line" in s or "t" in s) else 0, 3)) for s in script["shots"]], key=lambda s: s["t"])
    shots[0]["t"] = 0
    return {"cast": script["cast"], "lines": lines, "events": events, "shots": shots, "dur": round(dur, 3), "fps": FPS}


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
        js_tl = {k: v for k, v in tl.items()}
        js_tl["lines"] = [{k: v for k, v in l.items() if k not in ("mp3", "s0")} for l in tl["lines"]]
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
    ins, fl = [], []
    for i, l in enumerate(tl["lines"]):
        ins += ["-ss", f"{l['s0']:.3f}", "-i", l["mp3"]]
        d = int(l["t"] * 1000)
        fl.append(f"[{i + 1}:a]atrim=0:{l['dur'] + 0.05:.3f},adelay={d}|{d}[a{i}]")
    n = len(tl["lines"])
    fc = ";".join(fl) + ";" + "".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad,loudnorm=I=-14:TP=-1.5[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.jpg")] + ins +
                   ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(tl["dur"]), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(mp4)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--stills", help="확인용 초(쉼표), 예: 0.5,3,6")
    a = ap.parse_args()
    sp = Path(a.script)
    tl = build(json.loads(sp.read_text(encoding="utf-8")))
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    print(f"길이 {tl['dur']}초, 대사 {len(tl['lines'])}개", flush=True)
    if a.stills:
        frames = [int(float(x) * FPS) for x in a.stills.split(",")]
        asyncio.run(shoot(tl, frames, out, a.gpu, True))
        print("\n".join(str(out / f"still_{k:04d}.jpg") for k in frames))
        return
    fd = out / "frames"
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
