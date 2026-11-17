"""three.js 3D 캐릭터 릴스 시제품 렌더러 (실험, 2026-11-17).

헤드리스 Chromium(Playwright)에서 장면 JS를 띄우고 twFrame(t)를 프레임마다 불러 JPEG를 받는다 (실시간 아님, 결정적).
→ ffmpeg로 1080x1920 30fps mp4 + 대사(ElevenLabs, line/*.mp3) + 점프 효과음(직접 합성), -14 LUFS.

장면 두 가지:
  v2 (기본)  scene.js  : 슬라임 진행자 + 클로드·제미나이, 대사 Deok
  v3 (--v3)  scene3.js : 사람 주인공 '나'(20대 여성 직장인) + 클로드·챗GPT·제미나이, 대사 Hana Lee

사용법 (저장소 루트에서):
  py -3.12 experiments/threejs-test/render.py [--v3] --gpu            # 이 컴퓨터 GPU
  py -3.12 experiments/threejs-test/render.py [--v3]                  # SwiftShader(CPU): GitHub Actions와 같은 조건
  py -3.12 experiments/threejs-test/render.py [--v3] --gpu --frames 15,75,190 --stills   # 몇 장만 out/still_*.jpg
  py -3.12 experiments/threejs-test/render.py [--v3] --bench          # 효과별 프레임당 시간 (5프레임씩, 컴파일 제외)
  py -3.12 experiments/threejs-test/render.py [--v3] --range 0:105    # 프레임 일부만 out/frames에 (행렬 분할 렌더링)
  py -3.12 experiments/threejs-test/render.py --v3 --gpu --sheet      # '나' 캐릭터 시트 (정면·3/4)
  --opt '{"dof":false,"trans":false,"shadows":false,"msaa":0,"scale":0.667}'   # 효과 끄기·낮은 해상도
  --tts   대사 다시 받기 (캐시 있으면 ElevenLabs 0자)
결과: experiments/threejs-test/out/threejs-test-v2.mp4 / -v3.mp4 (out/은 커밋 안 함)
"""
import argparse
import asyncio
import base64
import json
import mimetypes
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FPS = 30
HOST = "http://tw.local/"
SWIFT = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
GPU = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
VARIANTS = {
    "v2": {"page": "index.html", "line": "line01", "dur": 7.0, "t0": 1.2, "voice": "deok", "settings": None,
           "text": "자, 오늘의 대결! 클로드랑 제미나이, 누가 더 빠를까?",
           "hops": [("대결", -0.02), ("클로드", 0), ("제미나이", 0)], "end_hops": [5.35, 5.6]},
    "v3": {"page": "index3.html", "line": "line03", "dur": 7.5, "t0": 0.5, "voice": "QPFsEL6IBxlT15xfiD6C",   # Hana Lee (여성, 한국어)
           "settings": {"stability": 0.45, "style": 0.45, "speed": 1.05},
           "text": "클로드, 제미나이, 지피티! 오늘 보고서, 누가 먼저 끝낼래?",
           "hops": [("클로드", 0), ("제미나이", 0), ("지피티", 0), ("끝낼래", -0.05)], "end_hops": [5.75, 5.9, 6.05]},
}
V = VARIANTS["v2"]


def make_tts():
    sys.path.insert(0, str(ROOT / "agent"))
    import tts
    vid = tts.ELEVEN_VOICES.get(V["voice"], V["voice"])
    mp3, meta = tts.eleven_mp3_ts(V["text"], voice_id=vid, settings=V["settings"])
    (HERE / "line").mkdir(exist_ok=True)
    shutil.copy(mp3, HERE / "line" / f"{V['line']}.mp3")
    (HERE / "line" / f"{V['line']}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


async def shoot(frames, out_dir, gpu, still, opt=None, warmup=False, sheet=None):
    from playwright.async_api import async_playwright
    line = json.loads((HERE / "line" / f"{V['line']}.json").read_text(encoding="utf-8"))

    async def serve(route):
        rel = route.request.url[len(HOST):].split("?")[0]
        f = (ROOT / rel).resolve()
        if ROOT not in f.parents or not f.is_file():
            return await route.fulfill(status=404, body="")
        ct = {".js": "text/javascript", ".otf": "font/otf", ".woff2": "font/woff2", ".woff": "font/woff"}.get(
            f.suffix, mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        await route.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ct})

    stats = {}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=GPU if gpu else SWIFT)
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route(HOST + "**", serve)
        t = time.time()
        await pg.goto(HOST + "experiments/threejs-test/" + V["page"])
        await pg.wait_for_function("window.twReady === true", timeout=60000)
        stats["info"] = await pg.evaluate("([l, o]) => window.twInit(l, o)", [line, opt or {}])
        if sheet:
            for k, yaw in enumerate(sheet):
                data = await pg.evaluate(f"window.twSheet({yaw})")
                (out_dir / f"sheet_{k}.jpg").write_bytes(base64.b64decode(data.split(",", 1)[1]))
            await b.close()
            return stats
        if warmup:   # 셰이더 컴파일을 재기 밖으로
            await pg.evaluate(f"window.twFrame({frames[0] / FPS:.5f})")
        stats["init_s"] = round(time.time() - t, 2)
        t = time.time()
        for k in frames:
            data = await pg.evaluate(f"window.twFrame({k / FPS:.5f})")
            raw = base64.b64decode(data.split(",", 1)[1])
            if out_dir is None:
                continue
            (out_dir / (f"still_{k:03d}.jpg" if still else f"f{k:05d}.jpg")).write_bytes(raw)
        stats["frames"] = len(frames)
        stats["frames_s"] = round(time.time() - t, 2)
        stats["s_per_frame"] = round((time.time() - t) / max(1, len(frames)), 3)
        if errs:
            stats["errors"] = errs[:5]
        await b.close()
    return stats


def sfx(path, times, dur):
    """점프할 때 '뿅' (사인 주파수 올림 + 빠른 감쇠). 직접 합성이라 라이선스 문제 없음."""
    parts, labels = [], []
    for i, t in enumerate(times):
        ms = int(max(0, t) * 1000)
        parts.append(f"aevalsrc='0.25*sin(2*PI*(380*t+1400*t*t))*exp(-t*22)':d=0.18:s=44100,adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(times)}:normalize=0,apad=whole_dur={dur}[o]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", fc, "-map", "[o]", "-t", str(dur), str(path)], check=True)


def encode(frames_dir, out, name):
    """프레임 + 대사 + 효과음 → mp4."""
    dur, t0 = V["dur"], V["t0"]
    line = json.loads((HERE / "line" / f"{V['line']}.json").read_text(encoding="utf-8"))
    times = [t0 + line["starts"][line["text"].index(w)] + d for w, d in V["hops"]] + V["end_hops"]
    sfx(out / "sfx.wav", times, dur)
    mp4 = out / f"{name}.mp4"
    d = int(t0 * 1000)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.jpg"),
                    "-i", str(HERE / "line" / f"{V['line']}.mp3"), "-i", str(out / "sfx.wav"),
                    "-filter_complex", f"[1:a]adelay={d}|{d},apad[v];[v][2:a]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(mp4)], check=True)
    (out / "sfx.wav").unlink()
    return mp4


def main():
    global V
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", action="store_true")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--tts", action="store_true")
    ap.add_argument("--frames", help="쉼표로 프레임 번호 (확인용)")
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--name")
    ap.add_argument("--opt", help='JSON: {"dof":false,"trans":false,"shadows":false,"msaa":0,"scale":0.667}')
    ap.add_argument("--range", help="프레임 구간 a:b만 그려 out/frames에 남김 (GitHub Actions 행렬 분할용)")
    ap.add_argument("--encode-only", action="store_true", help="out/frames에 모인 프레임으로 mp4만 (행렬 분할 뒤 합치기)")
    ap.add_argument("--bench", action="store_true")
    a = ap.parse_args()
    V = VARIANTS["v3" if a.v3 else "v2"]
    name = a.name or ("threejs-test-v3" if a.v3 else "threejs-test-v2")
    if a.tts or not (HERE / "line" / f"{V['line']}.json").exists():
        make_tts()
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    frames_dir = out / "frames"
    opt = json.loads(a.opt) if a.opt else None
    n = int(V["dur"] * FPS)
    if a.sheet:
        print(json.dumps(asyncio.run(shoot([], out, a.gpu, True, opt, sheet=[0.0, 0.7])), ensure_ascii=False))
        return
    if a.bench:
        confs = [("full", {}), ("no_dof", {"dof": False}), ("no_trans", {"trans": False}), ("no_shadows", {"shadows": False}),
                 ("msaa0", {"msaa": 0}), ("scale_0.667(720p)", {"scale": 2 / 3}),
                 ("light(720p,no_dof,msaa0)", {"scale": 2 / 3, "dof": False, "msaa": 0}),
                 ("lightest(720p,all_off)", {"scale": 2 / 3, "dof": False, "msaa": 0, "trans": False, "shadows": False})]
        res, st = {}, {}
        sample = [int(n * f) for f in (0.15, 0.35, 0.55, 0.75, 0.9)]
        for cname, o in confs:
            st = asyncio.run(shoot(sample, None, a.gpu, True, o, warmup=True))
            res[cname] = st["s_per_frame"]
            print(cname, st["s_per_frame"], flush=True)
        print(json.dumps({"renderer": st["info"]["renderer"], "s_per_frame": res}, ensure_ascii=False))
        return
    if a.range:
        x, y = (int(v) for v in a.range.split(":"))
        frames_dir.mkdir(exist_ok=True)
        print(json.dumps(asyncio.run(shoot(list(range(x, min(y, n))), frames_dir, a.gpu, False, opt)), ensure_ascii=False))
        return
    if a.encode_only:
        print(encode(frames_dir, out, name))
        return
    if a.frames:
        st = asyncio.run(shoot([int(x) for x in a.frames.split(",")], out, a.gpu, True, opt))
        print(json.dumps(st, ensure_ascii=False))
        return
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir()
    st = asyncio.run(shoot(list(range(n)), frames_dir, a.gpu, False, opt))
    t = time.time()
    mp4 = encode(frames_dir, out, name)
    st["encode_s"] = round(time.time() - t, 2)
    st["render_s_per_video_s"] = round(st["frames_s"] / V["dur"], 2)
    shutil.rmtree(frames_dir)
    print(json.dumps(st, ensure_ascii=False))
    print(mp4)


if __name__ == "__main__":
    main()
