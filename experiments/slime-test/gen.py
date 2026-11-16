"""실험: 같은 슬라임 캐릭터를 조명만 바꿔 4장 (FLUX.2 [klein] 4B, Cloudflare).

1) base: 글 묘사 + 고정 seed로 만든다.
2) 1~3: base 그림을 참고 이미지(input_image_0)로 넣고 "조명만 바꿔라"로 만든다 (FLUX.2 편집 기능).
   비교용으로 참고 이미지 없이 같은 seed + 같은 묘사로 만든 것도 seedonly_*.jpg로 남긴다.

GitHub Actions(experiment-images.yml, 지금은 지움)에서만 돌았다 (CF_ACCOUNT_ID, CF_API_TOKEN).
기록용. 0-base.jpg는 마스코트 기준 이미지로 assets/mascot/slime-base.jpg에 옮겼다 (2026-11-16). 새 그림은 agent/gen_images.py의 "mascot": true로 만든다.
    python experiments/slime-test/gen.py           # 그림 만들기
    py -3.12 experiments/slime-test/gen.py --sheet  # 4장 모음(sheet.jpg)만, 이 컴퓨터에서
"""
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))
from gen_images import MODEL, save_jpeg  # noqa: E402

OUT = Path(__file__).resolve().parent
W, H = 1088, 1360
SEED = 424242

SLIME = (
    "a small cute glossy translucent jelly slime creature, rounded dome shape like a soft gumdrop, "
    "about the size of a cat, vivid lime green tint (#00FF66) with subtle inner subsurface glow, "
    "smooth wet glossy surface with soft specular highlights, a few tiny air bubbles suspended inside, "
    "simple face: two small round solid black dot eyes set wide apart and a tiny curved smile, no nose, "
    "no limbs, no crown, no hat, no accessories"
)
SCENE = (
    "sitting alone in the center of the seat cushion of a plain light grey fabric three-seat sofa "
    "in a minimal modern living room, white wall behind, one small potted plant at the left edge, "
    "camera at eye level, front view, medium shot, the slime centered in frame, "
    "photorealistic 3D render, octane render style, shallow depth of field, vertical 4:5 composition, "
    "no text, no letters, no logos, no watermark"
)
BASE_LIGHT = "soft neutral daylight from a window on the left, even balanced exposure"

LIGHTS = {
    "1-golden-hour": "warm golden hour sunlight streaming low through a window from the left, long soft "
                     "orange shadows, warm amber glow on the slime and sofa",
    "2-neon": "neon lighting, strong hot pink neon light from the left and electric blue neon light from "
              "the right, colored reflections on the glossy slime, dim room otherwise",
    "3-low-key-rim": "low-key dramatic lighting, dark room almost black, a single strong white rim light "
                     "from behind outlining the slime's edge, deep shadows, high contrast",
}


def call(prompt, seed, ref=None):
    acc, tok = os.environ["CF_ACCOUNT_ID"], os.environ["CF_API_TOKEN"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{MODEL}"
    form = {"prompt": (None, prompt), "width": (None, str(W)), "height": (None, str(H)),
            "seed": (None, str(seed))}
    if ref is not None:
        form["input_image_0"] = ("ref.png", ref, "image/png")
    for attempt in range(3):
        t = time.time()
        r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, files=form, timeout=180)
        dt = time.time() - t
        if r.status_code == 200:
            b64 = (r.json().get("result") or {}).get("image")
            if b64:
                return base64.b64decode(b64), dt
            raise RuntimeError(f"응답에 이미지 없음: {r.text[:300]}")
        print(f"  오류 {r.status_code}: {r.text[:300]}")
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"Cloudflare 오류 {r.status_code}")


def ref_png(path, max_side):
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), img.size


def gen():
    log = {"model": MODEL, "seed": SEED, "size": [W, H], "items": []}
    base_prompt = f"{SLIME}, {SCENE}, {BASE_LIGHT}"
    raw, dt = call(base_prompt, SEED)
    save_jpeg(raw, OUT / "0-base.jpg")
    log["items"].append({"file": "0-base.jpg", "seconds": round(dt, 1), "ref": None})
    print(f"0-base {dt:.1f}s")

    ref_ok = None
    for name, light in LIGHTS.items():
        edit_prompt = (
            "Keep exactly the same green slime character, same face, same shape, same size, same pose, "
            "same grey sofa, same living room, same camera angle and framing. "
            f"Change ONLY the lighting: {light}. Photorealistic 3D render, no text."
        )
        done = False
        for side in ([ref_ok] if ref_ok else [1024, 512]):
            ref, rsize = ref_png(OUT / "0-base.jpg", side)
            try:
                raw, dt = call(edit_prompt, SEED, ref)
            except Exception as e:
                print(f"  참고 이미지 {rsize} 실패: {e}")
                continue
            ref_ok = side
            save_jpeg(raw, OUT / f"{name}.jpg")
            log["items"].append({"file": f"{name}.jpg", "seconds": round(dt, 1), "ref": list(rsize)})
            print(f"{name} (ref {rsize}) {dt:.1f}s")
            done = True
            break
        if not done:
            log["items"].append({"file": f"{name}.jpg", "error": "참고 이미지 방식 실패"})

        # 비교용: 참고 이미지 없이 같은 seed + 같은 묘사
        raw, dt = call(f"{SLIME}, {SCENE}, {light}", SEED)
        save_jpeg(raw, OUT / f"seedonly-{name}.jpg")
        log["items"].append({"file": f"seedonly-{name}.jpg", "seconds": round(dt, 1), "ref": None})
        print(f"seedonly-{name} {dt:.1f}s")

    for p in OUT.glob("*.jpg"):  # 1080px 이하로
        img = Image.open(p)
        if max(img.size) > 1080:
            img.thumbnail((1080, 1080))
            img.save(p, "JPEG", quality=90)
    (OUT / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def font(size):
    for f in [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def sheet():
    items = [("0-base.jpg", "0 기본 (자연광)"), ("1-golden-hour.jpg", "1 골든아워"),
             ("2-neon.jpg", "2 네온 (분홍·파랑)"), ("3-low-key-rim.jpg", "3 로우키 림 라이트")]
    cw, ch, lab, pad = 540, 675, 44, 12
    S = Image.new("RGB", (pad + 2 * (cw + pad), pad + 2 * (ch + lab + pad)), (0, 0, 0))
    d = ImageDraw.Draw(S)
    f = font(26)
    for i, (fn, label) in enumerate(items):
        x = pad + (i % 2) * (cw + pad)
        y = pad + (i // 2) * (ch + lab + pad)
        img = Image.open(OUT / fn).convert("RGB")
        img = img.resize((cw, round(img.height * cw / img.width)))
        S.paste(img.crop((0, 0, cw, min(ch, img.height))), (x, y))
        d.text((x + 4, y + ch + 8), label, fill=(0, 255, 102), font=f)
    S.save(OUT / "sheet.jpg", "JPEG", quality=90)
    print("sheet.jpg", S.size)


if __name__ == "__main__":
    sheet() if "--sheet" in sys.argv else gen()
