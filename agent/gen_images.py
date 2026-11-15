"""AI 이미지 만들기 (Cloudflare Workers AI, FLUX.1 schnell).

게시물 post.json 안에서 이렇게 적힌 그림을 찾아, 파일이 아직 없으면 만든다.

    "visual": {"type": "image", "src": "img/cover.jpg",
               "prompt": "a vast server hall at night, rows of racks ..."}

- prompt는 영어로, 장면만 묘사한다. 브랜드 분위기(어두운 배경, 녹색 조명, 글자·로고·실존 인물 없음)는
  아래 STYLE이 자동으로 붙는다.
- 만든 그림이 하나라도 있으면 post.json에 "ai_image": true를 적는다. 게시할 때 AI 생성 표시가 붙는다.

환경 변수: CF_ACCOUNT_ID, CF_API_TOKEN (GitHub Secrets)
사용법: python agent/gen_images.py <게시물 폴더> [<게시물 폴더> ...]
"""
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

MODEL = "@cf/black-forest-labs/flux-1-schnell"
STYLE = (
    "cinematic editorial photograph, dark moody scene, deep black shadows, "
    "vivid neon green (#00FF66) accent light as the only color, high contrast, sharp focus, "
    "no text, no letters, no words, no logos, no watermark, no recognizable real people"
)
BANNED = ["logo", "text saying", "written", "elon", "altman", "huang", "zuckerberg", "musk",
          "openai logo", "nvidia logo", "photo of ", "portrait of "]


def image_visuals(post):
    for s in post.get("slides", []):
        v = s.get("visual")
        if isinstance(v, dict) and v.get("type") == "image" and v.get("prompt"):
            yield v


def check_prompt(p):
    low = p.lower()
    bad = [w for w in BANNED if w in low]
    if bad:
        raise ValueError(f"프롬프트에 쓰면 안 되는 말: {bad} → 장면만 묘사할 것 (실존 인물·로고·글자 금지)")


def generate(prompt, seed=None):
    acc, tok = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not acc or not tok:
        raise RuntimeError("CF_ACCOUNT_ID / CF_API_TOKEN 없음 (GitHub Secrets 확인)")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{MODEL}"
    body = {"prompt": f"{prompt}. {STYLE}", "steps": 8}
    if seed is not None:
        body["seed"] = seed
    for attempt in range(3):
        r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body, timeout=120)
        if r.status_code == 200:
            data = r.json()
            b64 = (data.get("result") or {}).get("image")
            if b64:
                return base64.b64decode(b64)
            raise RuntimeError(f"응답에 이미지 없음: {str(data)[:300]}")
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"Cloudflare 오류 {r.status_code}: {r.text[:300]}")


def save_jpeg(raw, path):
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=92)


def process(folder):
    folder = Path(folder)
    pj = folder / "post.json"
    post = json.loads(pj.read_text(encoding="utf-8"))
    made = 0
    for v in image_visuals(post):
        out = folder / v["src"]
        if out.exists():
            continue
        check_prompt(v["prompt"])
        print(f"  그림 만들기: {v['src']}")
        save_jpeg(generate(v["prompt"], v.get("seed")), out)
        made += 1
    if any(True for _ in image_visuals(post)) and not post.get("ai_image"):
        post["ai_image"] = True
        pj.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return made


if __name__ == "__main__":
    total = 0
    for f in sys.argv[1:]:
        print(f"[{f}]")
        total += process(f)
    print(f"새로 만든 그림: {total}장")
