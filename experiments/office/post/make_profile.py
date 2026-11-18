"""프로필 사진: AI 캐릭터들이 서로 싸우고(AI 전쟁) 가운데 일반 남성이 끼어 있는 장면 (운영자 2026-11-18).
사무실 장면(scene.js)을 그대로 쓰고 render.shoot로 정지 화면 몇 장 → 가운데를 정사각형으로 잘라 profile_*.jpg.
실행: py -3.12 experiments/office/post/make_profile.py"""
import asyncio, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "office"))
import render  # noqa: E402

OUT = ROOT / "experiments" / "office" / "out"
FPS = render.FPS
tl = {
    "cast": [{"key": "man", "human": True},
             {"key": "claude", "x": -0.33, "z": 0.22, "yaw": 0.55, "size": 0.36},
             {"key": "gemini", "x": 0.0, "z": 0.46, "yaw": 0.0, "size": 0.27},
             {"key": "chatgpt", "x": 0.33, "z": 0.22, "yaw": -0.55, "size": 0.36}],
    "lines": [], "screens": [], "cards": [], "clips": {}, "props": {}, "fps": FPS, "dur": 3.0,
    "events": [
        {"t": 0, "who": "claude", "emo": "angry"}, {"t": 0, "who": "chatgpt", "emo": "angry"}, {"t": 0, "who": "gemini", "emo": "angry"},
        {"t": 0, "who": "claude", "do": "look", "at": "chatgpt"}, {"t": 0, "who": "chatgpt", "do": "look", "at": "claude"},
        {"t": 0, "who": "gemini", "do": "look", "at": "claude"}, {"t": 0, "who": "claude", "do": "tremble", "d": 3}, {"t": 0, "who": "chatgpt", "do": "tremble", "d": 3},
        {"t": 0, "who": "man", "emo": "embarrassed"},
    ],
    "shots": [{"t": 0, "cam": "wide"}],
}
frames = [int(x * FPS) for x in (0.12, 0.2)]
asyncio.run(render.shoot(tl, frames, OUT, True, True))
from PIL import Image, ImageDraw
import math
def bolt(d, a, b, w, col, seed):   # 지그재그 번개 (두 캐릭터 눈 사이 불꽃 = 라이벌 신경전)
    import random
    r = random.Random(seed); pts = [a]
    for i in range(1, 7):
        t = i / 7; x = a[0] + (b[0] - a[0]) * t; y = a[1] + (b[1] - a[1]) * t
        pts.append((x + r.uniform(-14, 14), y + (26 if i % 2 else -26)))
    pts.append(b); d.line(pts, fill=(0, 0, 0), width=w + 14, joint="curve"); d.line(pts, fill=col, width=w, joint="curve")
for k in frames:
    im = Image.open(OUT / f"still_{k:04d}.jpg").convert("RGB")
    d = ImageDraw.Draw(im)
    bolt(d, (300, 1250), (520, 1150), 14, (0, 255, 102), 1)    # 클로드 → 가운데
    bolt(d, (790, 1250), (560, 1150), 14, (0, 255, 102), 2)    # 지피티 → 가운데
    cx, cy = 540, 1150                                         # 부딪히는 자리 별 모양 섬광
    star = [(cx + (70 if i % 2 == 0 else 28) * math.cos(math.pi * i / 6), cy + (70 if i % 2 == 0 else 28) * math.sin(math.pi * i / 6)) for i in range(12)]
    d.polygon(star, fill=(0, 255, 102), outline=(0, 0, 0), width=8)
    s = 1080; top = 560
    im.crop((0, top, s, top + s)).save(ROOT / "experiments" / "office" / "post" / f"profile_{k}.jpg", quality=93)
    print("profile", k)
