"""릴스용 모션 그래픽 렌더러.

render.py가 릴스(type=reel)를 만들 때 호출한다.
- 일반 장면: 카드와 같은 HTML에 등장 애니메이션을 입혀 프레임 단위로 촬영 → 장면 영상
- kind=clip 장면: 사용자가 넣은 영상을 잘라 우리 레이아웃(제목, 출처, 자막) 안에 합성
- 장면들을 페이드로 잇고, assets/music/에 곡이 있으면 낮은 볼륨으로 깔아준다.
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
W, H = 1080, 1920

# 장면에 애니메이션을 붙이는 스크립트. 요소마다 DOM 순서대로 조금씩 늦게 등장한다.
ANIM_CSS = """
@keyframes twUp{from{opacity:0;transform:translateY(46px)}to{opacity:1;transform:none}}
@keyframes twPop{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:none}}
@keyframes twFade{from{opacity:0}to{opacity:1}}
@keyframes twGrow{from{width:0}}
@keyframes twZoom{from{transform:scale(1)}to{transform:scale(1.05)}}
@keyframes twDrift{from{transform:translateX(0)}to{transform:translateX(-90px)}}
@keyframes twGlow{0%{border-color:#1d2a22}100%{border-color:var(--acc)}}
.a-up{animation:twUp .7s cubic-bezier(.2,.8,.2,1) both}
.a-pop{animation:twPop .8s cubic-bezier(.2,.8,.2,1) both}
.a-fade{animation:twFade .5s ease-out both}
"""

ANIM_JS = """
window.twSetup = (idx, dur) => {
  const slides = [...document.querySelectorAll('.slide')];
  slides.forEach((s, i) => s.style.display = i === idx ? '' : 'none');
  const s = slides[idx];
  const acc = getComputedStyle(document.documentElement).getPropertyValue('--acc') || '#00FF66';
  let d = 0.15;
  const add = (el, cls, delay) => { el.classList.add(cls); el.style.animationDelay = delay + 's'; };
  // 큰 시각 요소는 먼저 튀어나오고 천천히 확대
  s.querySelectorAll('.card,.term,.bars,.tl,.bignum,.tiles,.tile:not(.tiles .tile),.word,.bvis').forEach(el => add(el, 'a-pop', 0));
  const vis = s.querySelector('.vis');
  if (vis) { vis.style.animation = `twZoom ${dur}s linear both`; }
  const wall = s.querySelector('.wall');
  if (wall) { wall.style.animation = `twDrift ${dur}s linear both`; }
  // 글과 목록은 순서대로 아래에서 올라온다
  const seq = [...s.querySelectorAll('.tag,.ctitle,.csub,.num,.heading,.pbox,.body,.point,.step,.cmp .col,.tli,.opt,.bub,.brow,.stat .u,.bignum .c,.word .lab,.word .wd,.slogan,.mark,.cta,.src,.term pre')];
  // 그림 속 요소(설정 항목, 말풍선 등)와 글은 따로 순서를 매겨 동시에 진행한다
  let dv = 0.3;
  seq.forEach(el => {
    const inVis = !!el.closest('.vis,.bvis');
    const cls = el.matches('.term pre') ? 'a-fade' : 'a-up';
    if (inVis) { add(el, cls, dv); dv += 0.2; }
    else { add(el, cls, d); d += el.matches('.step,.tli,.cmp .col') ? 0.22 : 0.14; }
  });
  d = Math.max(d, dv);
  // 선택된 설정은 마지막에 녹색으로 켜진다
  s.querySelectorAll('.opt.on').forEach(el => { el.style.borderColor = '#1d2a22'; el.style.animation = `twUp .7s cubic-bezier(.2,.8,.2,1) ${el.style.animationDelay} both, twGlow .4s ease-out ${d + 0.2}s forwards`; });
  s.querySelectorAll('.brow .bt i, .bot .pb i').forEach(el => { el.style.animation = `twGrow 1s cubic-bezier(.2,.8,.2,1) ${0.4}s both`; });
  // 숫자는 0부터 올라간다
  window.twCounters = [...s.querySelectorAll('.stat .n, .bignum .n')].map(el => {
    const node = [...el.childNodes].find(n => n.nodeType === 3);
    const raw = node ? node.textContent.trim() : '';
    const num = parseFloat(raw.replace(/,/g, ''));
    return { node, raw, num, dec: (raw.split('.')[1] || '').length, comma: raw.includes(',') };
  }).filter(c => c.node && !isNaN(c.num));
  window.twAnims = document.getAnimations();
  window.twAnims.forEach(a => a.pause());
};
window.twSeek = (t) => {
  window.twAnims.forEach(a => { a.currentTime = t * 1000; });
  const k = Math.min(1, Math.max(0, (t - 0.15) / 1.1));
  const e = 1 - Math.pow(1 - k, 3);
  window.twCounters.forEach(c => {
    let v = (c.num * e).toFixed(c.dec);
    if (c.comma) v = Number(v).toLocaleString('en-US', { minimumFractionDigits: c.dec, maximumFractionDigits: c.dec });
    c.node.textContent = v;
  });
};
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return bool(out)


async def render_scene(page, idx, dur, out_mp4):
    """페이지의 idx번째 장을 dur초짜리 무음 영상으로."""
    await page.evaluate(f"twSetup({idx}, {dur})")
    el = (await page.query_selector_all(".slide"))[idx]
    n = int(round(dur * FPS))
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                             "-c:v", "mjpeg", "-i", "-", "-f", "lavfi", "-t", f"{dur:.3f}",
                             "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "128k", str(out_mp4)], stdin=subprocess.PIPE)
    for i in range(n):
        await page.evaluate(f"twSeek({i / FPS})")
        proc.stdin.write(await el.screenshot(type="jpeg", quality=90))
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("장면 영상 만들기 실패")


async def render_clip_overlay(page, idx, out_png):
    """인용 장면의 틀(영상 자리는 투명)을 PNG로."""
    await page.evaluate(f"twSetup({idx}, 1)")
    await page.evaluate("twSeek(5)")
    el = (await page.query_selector_all(".slide"))[idx]
    await page.evaluate("""(i) => { const s = [...document.querySelectorAll('.slide')][i];
        s.style.background = 'transparent'; document.body.style.background = 'transparent'; document.documentElement.style.background = 'transparent';
        const cb = s.querySelector('.clipbox'); cb.style.background = 'transparent'; cb.querySelector('.ph').style.display = 'none'; }""", idx)
    await el.screenshot(path=str(out_png), omit_background=True)


def render_clip_scene(folder, s, overlay_png, out_mp4, box):
    """사용자 영상을 잘라 틀 안에 합성."""
    src = folder / s["src"]
    start, end = float(s["start"]), float(s["end"])
    dur = end - start
    bx, by, bw, bh = box
    audio_in = ["-ss", f"{start}", "-t", f"{dur}", "-i", str(src)]
    vf = (f"[1:v]scale={bw}:{bh}:force_original_aspect_ratio=decrease,"
          f"pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=0x0A0B0A,setsar=1[clip];"
          f"[0:v][clip]overlay={bx}:{by}[base];[base][2:v]overlay=0:0,format=yuv420p,fps={FPS}[v]")
    if has_audio(src):
        af = "[1:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]"
    else:
        af = "anullsrc=r=44100:cl=stereo[a]"
    run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
         "-f", "lavfi", "-t", f"{dur}", "-i", f"color=c=0x0A0B0A:s={W}x{H}:r={FPS}",
         *audio_in, "-loop", "1", "-t", f"{dur}", "-i", str(overlay_png),
         "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-t", f"{dur}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "128k", str(out_mp4)])
    return dur


def join_scenes(parts, durs, fade, out_mp4, music=None, music_volume=0.3):
    """장면들을 페이드로 잇고 음악을 깐다."""
    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error"]
    for p in parts:
        cmd += ["-i", str(p)]
    fc, v_prev, a_prev, offset = [], "[0:v]", "[0:a]", 0.0
    for i in range(1, len(parts)):
        offset += durs[i - 1] - fade
        fc.append(f"{v_prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}[v{i}]")
        fc.append(f"{a_prev}[{i}:a]acrossfade=d={fade}[a{i}]")
        v_prev, a_prev = f"[v{i}]", f"[a{i}]"
    total = sum(durs) - fade * (len(parts) - 1)
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        m = len(parts)
        fc.append(f"[{m}:a]volume={music_volume},atrim=duration={total:.3f},"
                  f"afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.3f}:d=1.5[m]")
        # 말소리·영상 소리가 나오는 동안 배경음악을 눌러(덕킹) 말소리보다 15~20dB 낮게 둔다 (STYLE_GUIDE 6장 "릴스 소리")
        fc.append(f"{a_prev}asplit=2[amain][akey]")
        fc.append("[m][akey]sidechaincompress=threshold=0.015:ratio=5:attack=30:release=500:knee=4[md]")
        fc.append("[amain][md]amix=inputs=2:duration=first:normalize=0[aout]")
        a_prev = "[aout]"
    cmd += ["-filter_complex", ";".join(fc), "-map", v_prev, "-map", a_prev, "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_mp4)]
    run(cmd)
    return total


def _clip_has_sound(src):
    """인용 영상에 실제 소리가 있는지 (평균 -50dB 이상). 화면 녹화처럼 무음이면 False."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return bool(m and float(m.group(1)) >= -50)


async def make_motion_reel(page_html, post, folder, config):
    from playwright.async_api import async_playwright

    rc = config["reel"]
    fade = rc["fade_seconds"]
    work = folder / "_scenes"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html = page_html.replace("</style>", ANIM_CSS + f":root{{--acc:{config['brand']['accent']}}}</style>", 1)
    html = html.replace("</body>", f"<script>{ANIM_JS}</script></body>")
    tmp = folder / "_motion.html"
    tmp.write_text(html, encoding="utf-8")

    slides = post["slides"] + [{"kind": "outro"}]
    parts, durs = [], []
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H})
        await page.goto(tmp.as_uri())
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        for i, s in enumerate(slides):
            out = work / f"{i:02d}.mp4"
            if s["kind"] == "clip":
                ov = work / f"{i:02d}_overlay.png"
                await render_clip_overlay(page, i, ov)
                box = await page.evaluate("""(i) => { const s = [...document.querySelectorAll('.slide')][i];
                    const r = s.querySelector('.clipbox').getBoundingClientRect(), b = s.getBoundingClientRect();
                    return [Math.round(r.left - b.left), Math.round(r.top - b.top), Math.round(r.width / 2) * 2, Math.round(r.height / 2) * 2]; }""", i)
                d = render_clip_scene(folder, s, ov, out, box)
            else:
                if s["kind"] == "cover":
                    d = rc["cover_seconds"]
                elif s["kind"] == "outro":
                    d = rc["seconds_per_frame"] + 0.8
                else:
                    d = rc["seconds_per_frame"] + 0.25 * len(s.get("items", []))
                    if s["kind"] == "prompt":
                        # 프롬프트는 읽을 시간을 더 준다 (한글 초당 약 12자)
                        chars = sum(len(x) for x in (s.get("prompts") or [s.get("prompt", "")]))
                        d = max(d, 2.5 + chars / 12)
                await render_scene(page, i, d + fade, out)
                d = d + fade
            parts.append(out)
            durs.append(d)
        await browser.close()
    tmp.unlink()
    # 소리 없는 릴스 금지 (운영자 결정 2026-11-16): post.music(상업 이용 가능한 음원, credit 필수) → assets/music → 코드로 생성
    pm = post.get("music") or {}
    music_files = sorted((ROOT / "assets" / "music").glob("*.mp3")) + sorted((ROOT / "assets" / "music").glob("*.m4a"))
    vol = rc["music_volume"]
    gen = None
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
        vol = float(pm.get("volume", vol))
    elif music_files and not pm.get("generate"):
        music = random.choice(music_files)
    else:
        from music_gen import make_music
        gen = folder / "_music.wav"
        info = make_music(gen, durs, fade, seed=int(pm.get("seed", 7)))
        print(f"배경음악: 코드로 생성 (BPM {info['bpm']}, 장면 전환 {len(info['bounds'])}곳에 박자 맞춤)")
        music = gen
        has_clip_sound = any(s.get("kind") == "clip" and _clip_has_sound(folder / s["src"]) for s in post["slides"])
        vol = float(pm.get("volume", 0.25 if has_clip_sound else 0.8))
    total = join_scenes(parts, durs, fade, folder / "reel.mp4", music, vol)
    # 소리 크기 맞추기: -14 LUFS, 순간 최대 -1.5 dBTP, 튀는 효과음 누르기 (실패하면 원래 소리 그대로)
    from loudness import normalize
    normalize(folder / "reel.mp4")
    if gen and gen.exists():
        gen.unlink()
    shutil.rmtree(work)
    return total


# ---------- 카드뉴스 첫 장 영상 (표지 motion, TEMPLATES.md "표지 영상") ----------
# 캐러셀 첫 장을 짧은 영상(1080x1350, H.264 + AAC, 30fps)으로. 같은 장의 정지 화면 slides/01.jpg는 그대로 남긴다
# (스레드·검토 페이지·미리보기용). 인스타 캐러셀 자식에 media_type=VIDEO로 올라간다 (publish.py).
COVER_SECONDS = 6.0
COVER_SECONDS_RANGE = (3.0, 10.0)   # 모션만(영상 src 없이)일 때
COVER_VIDEO_RANGE = (3.0, 60.0)     # 결과 mp4 길이 (인스타 캐러셀 영상 장 기준, checks.py·render.py 검사)


def cover_motion(post):
    """캐러셀 표지의 motion 설정(dict) 또는 None. 예전 게시물은 None (지금과 똑같이 사진만)."""
    if post.get("type") != "carousel":
        return None
    slides = post.get("slides") or []
    if not slides or slides[0].get("kind") != "cover":
        return None
    m = slides[0].get("motion")
    if m is True:
        return {}
    return m if isinstance(m, dict) else None


async def _cover_overlay(page, idx, out_png):
    """표지 틀(그림 자리는 투명, 아래로 어두워지는 그늘은 남김)을 PNG로. 영상 위에 얹는다."""
    await page.evaluate(f"twSetup({idx}, 1)")
    await page.evaluate("twSeek(5)")
    el = (await page.query_selector_all(".slide"))[idx]
    await page.evaluate("""(i) => { const s = [...document.querySelectorAll('.slide')][i];
        s.style.background = 'transparent'; document.body.style.background = 'transparent';
        document.documentElement.style.background = 'transparent';
        const v = s.querySelector('.vis'); if (v) { v.style.animation = 'none'; v.style.transform = 'none';
          v.querySelectorAll('img').forEach(x => x.style.visibility = 'hidden'); } }""", idx)
    await el.screenshot(path=str(out_png), omit_background=True)
    return await page.evaluate("""(i) => { const s = [...document.querySelectorAll('.slide')][i];
        const v = s.querySelector('.vis'); const b = s.getBoundingClientRect();
        if (!v) return [0, 0, Math.round(b.width), Math.round(b.height)];
        const r = v.getBoundingClientRect();
        return [Math.round(r.left - b.left), Math.round(r.top - b.top), Math.round(r.width / 2) * 2, Math.round(r.height / 2) * 2]; }""", idx)


def _cover_from_src(folder, m, overlay_png, box, size, out_mp4):
    """motion.src 영상을 표지 그림 자리에 꽉 채워(잘라서) 깔고 틀 PNG를 얹는다. 길이(초) 반환."""
    w, h = size
    src = folder / m["src"]
    start = float(m.get("start", 0))
    end = float(m["end"]) if m.get("end") is not None else probe_duration(src)
    dur = end - start
    bx, by, bw, bh = box
    vf = (f"[1:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},setsar=1,fps={FPS}[clip];"
          f"[0:v][clip]overlay={bx}:{by}[base];[base][2:v]overlay=0:0,format=yuv420p[v]")
    keep_sound = has_audio(src) and not m.get("mute") and _clip_has_sound_range(src, start, dur)
    af = ("[1:a]aresample=48000,aformat=channel_layouts=stereo,apad[a]" if keep_sound
          else "anullsrc=r=48000:cl=stereo[a]")
    run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
         "-f", "lavfi", "-t", f"{dur}", "-i", f"color=c=0x0A0B0A:s={w}x{h}:r={FPS}",
         "-ss", f"{start}", "-t", f"{dur}", "-i", str(src),
         "-loop", "1", "-t", f"{dur}", "-i", str(overlay_png),
         "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "160k", str(out_mp4)])
    return dur, keep_sound


def _clip_has_sound_range(src, start, dur):
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{start}", "-t", f"{dur}", "-i", str(src),
                        "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return bool(m and float(m.group(1)) >= -50)


def _add_music(video_mp4, music, dur, volume, out_mp4):
    """소리 없는 영상에 음악을 깐다 (앞 0.3초 페이드인, 끝 1초 페이드아웃)."""
    fo = min(1.0, dur / 4)
    run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(video_mp4),
         "-stream_loop", "-1", "-i", str(music),
         "-filter_complex", f"[1:a]volume={volume},atrim=duration={dur:.3f},aresample=48000,"
                            f"aformat=channel_layouts=stereo,afade=t=in:d=0.3,afade=t=out:st={dur - fo:.3f}:d={fo:.3f}[a]",
         "-map", "0:v:0", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "160k", str(out_mp4)])


async def make_cover_video(page_html, post, folder, config, out_mp4):
    """캐러셀 첫 장 영상. motion.src가 있으면 그 영상을 그림 자리에, 없으면 표지에 모션(그림 천천히 확대, 글 올라오기).
    원본 소리가 없으면 음악(post.music → assets/music → 코드 생성)을 깔고 -14 LUFS로 맞춘다. 길이(초) 반환."""
    from playwright.async_api import async_playwright

    m = cover_motion(post)
    if m is None:
        raise ValueError("표지 motion 없음")
    w, h = 1080, 1350
    folder = Path(folder)
    work = folder / "_cover"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html = page_html.replace("</style>", ANIM_CSS + f":root{{--acc:{config['brand']['accent']}}}</style>", 1)
    html = html.replace("</body>", f"<script>{ANIM_JS}</script></body>")
    tmp = work / "_motion.html"
    tmp.write_text(html, encoding="utf-8")
    raw = work / "raw.mp4"
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        page = await browser.new_page(viewport={"width": w, "height": h})
        await page.goto(tmp.as_uri())
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        if m.get("src"):
            ov = work / "overlay.png"
            box = await _cover_overlay(page, 0, ov)
            dur, has_sound = _cover_from_src(folder, m, ov, box, (w, h), raw)
        else:
            dur = float(m.get("seconds", COVER_SECONDS))
            await render_scene(page, 0, dur, raw)
            has_sound = False
        await browser.close()
    if has_sound:
        shutil.move(str(raw), str(out_mp4))
        print(f"표지 영상: 원본 소리 사용 ({dur:.1f}초)")
    else:
        # 무음 금지 (STYLE_GUIDE 6장): post.music.src → assets/music → 코드로 만든 음악
        pm = post.get("music") or {}
        files = sorted((ROOT / "assets" / "music").glob("*.mp3")) + sorted((ROOT / "assets" / "music").glob("*.m4a"))
        vol = float(pm.get("volume", 0.8))
        if pm.get("src") and (folder / pm["src"]).exists():
            music = folder / pm["src"]
        elif files and not pm.get("generate"):
            music = random.choice(files)
        else:
            from music_gen import make_music
            music = work / "music.wav"
            info = make_music(music, [dur], 0, seed=int(pm.get("seed", 7)))
            print(f"표지 영상 배경음악: 코드로 생성 (BPM {info['bpm']})")
        _add_music(raw, music, dur, vol, out_mp4)
    # 소리 크기 -14 LUFS, 순간 최대 -1.5 dBTP (STYLE_GUIDE 6장 "릴스 소리"). faststart로 다시 묶인다
    from loudness import normalize
    normalize(out_mp4)
    shutil.rmtree(work)
    return dur
