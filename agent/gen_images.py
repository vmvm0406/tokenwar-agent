"""게시물에 쓸 그림 준비: 실물 이미지 내려받기 → 없으면 AI로 만들기.

post.json 어디에든(본문 visual, 릴스 thumb.image) 이렇게 적힌 그림을 찾아 파일이 없으면 채운다.

    {"type": "image", "src": "img/thumb.jpg",
     "url": "https://... 실물 이미지 주소",   # 1순위. 있으면 이걸 내려받는다
     "shot": {"url": "https://...", "selector": "..."},  # 2순위. 웹페이지 화면 캡처 (agent/shot.py)
     "prompt": "영어 장면 묘사",              # 3순위. url이 없거나 내려받기에 실패하면 AI로 만든다
     "size": [1088, 1920]}                    # 선택. AI 그림 크기 (기본: 썸네일 1088x1920, 그 외 1088x1360)

마스코트 (선택, "mascot": true, STYLE_GUIDE 1-1 "마스코트"):
    {"type": "image", "src": "img/list/01.jpg", "mascot": true,
     "prompt": "Same grey sofa, same living room ... Change ONLY the lighting: ...",
     "ref": "img/list/scene.jpg"}             # 선택. 참고 이미지(게시물 폴더 기준). 없으면 마스코트 기준 이미지
  - 참고 이미지(ref, 없으면 assets/mascot/slime-base.jpg)를 FLUX.2 편집 입력(input_image_0)으로 붙이고
    seed를 MASCOT_SEED로 고정한다(그림 정보에 seed가 있으면 그 값). 프롬프트 앞에는 "같은 캐릭터를 그대로 두라"는
    문장(MASCOT_KEEP)이 붙는다. 모양을 바꾸는 말은 prompt에 쓰지 않는다.
  - prompt가 없으면 기준 이미지를 그대로 복사한다 (목록형 릴스의 '원본' 줄).
  - ref가 같은 게시물의 다른 그림이면 그 그림을 먼저 만든다 (장면 기준 그림 → 그 장면의 변형들).

AI 그림을 하나라도 실제로 쓰면 post.json에 "ai_image": true를 적는다 → 게시할 때 인스타 'AI 정보' 표시.
실물 이미지를 내려받으면 원본 주소를 그림 정보의 "downloaded_from"에 남긴다.

AI 모델: Cloudflare Workers AI, FLUX.2 [klein] 4B (가로·세로 크기 지정 가능, 하루 무료 한도 안에서 수십 장)
환경 변수: CF_ACCOUNT_ID, CF_API_TOKEN (GitHub Secrets)
사용법: python agent/gen_images.py <게시물 폴더> [...]
"""
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
ROOT = Path(__file__).resolve().parent.parent
MASCOT_BASE = ROOT / "assets" / "mascot" / "slime-base.jpg"   # 기준 이미지 (모양 고정, assets/mascot/README.md)
MASCOT_SEED = 424242
MASCOT_REF_SIDE = 1024   # 참고 이미지 긴 변 (experiments/slime-test: 1024에서 성공)
MASCOT_KEEP = ("Keep exactly the same character from the reference image: the small translucent lime green jelly "
               "slime with two cat ears, two small round black dot eyes, a tiny curved smile, short stubby arms and feet, "
               "tiny air bubbles inside, glossy wet surface. Same shape, same proportions, same face, same color. ")
UA = "Mozilla/5.0 (compatible; tokenwar-bot/1.0; +https://github.com/vmvm0406/tokenwar-agent)"


def find_images(node, in_thumb=False):
    """(그림 정보 dict, 썸네일인지) 목록."""
    if isinstance(node, dict):
        if node.get("type") == "image" and node.get("src"):
            yield node, in_thumb
        for k, v in node.items():
            yield from find_images(v, in_thumb or k == "thumb")
    elif isinstance(node, list):
        for v in node:
            yield from find_images(v, in_thumb)


def ref_png(path, max_side=MASCOT_REF_SIDE):
    """참고 이미지(input_image_0)용 PNG 바이트."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def generate(prompt, w, h, seed=None, ref=None):
    """ref: 참고 이미지 PNG 바이트(선택, FLUX.2 편집 입력 input_image_0)."""
    acc, tok = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not acc or not tok:
        raise RuntimeError("CF_ACCOUNT_ID / CF_API_TOKEN 없음 (GitHub Secrets 확인)")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{MODEL}"
    form = {"prompt": (None, prompt), "width": (None, str(w)), "height": (None, str(h))}
    if seed is not None:
        form["seed"] = (None, str(seed))
    if ref is not None:
        form["input_image_0"] = ("ref.png", ref, "image/png")
    for attempt in range(3):
        r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, files=form, timeout=180)
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


def download(url):
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "image/*"}, timeout=60)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"이미지가 아님 ({r.headers.get('content-type')})")
    img = Image.open(io.BytesIO(r.content))
    if min(img.size) < 400:
        raise RuntimeError(f"너무 작음 {img.size}")
    return r.content


def save_jpeg(raw, path):
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=92)


def process(folder):
    folder = Path(folder)
    pj = folder / "post.json"
    post = json.loads(pj.read_text(encoding="utf-8"))
    changed = made = 0
    imgs = list(find_images(post))
    # 다른 그림의 참고 이미지(ref)로 쓰이는 그림을 먼저 만든다 (마스코트 장면 기준 그림)
    refs = {v.get("ref") for v, _ in imgs if v.get("ref")}
    imgs.sort(key=lambda x: 0 if x[0]["src"] in refs else 1)
    for v, is_thumb in imgs:
        out = folder / v["src"]
        if out.exists():
            continue
        if v.get("mascot"):
            ref_path = folder / v["ref"] if v.get("ref") else MASCOT_BASE
            if not ref_path.exists():
                raise RuntimeError(f"마스코트 참고 이미지 없음: {ref_path}")
            if not v.get("prompt"):   # 기준 이미지 그대로 (목록형 릴스 '원본' 줄)
                out.parent.mkdir(parents=True, exist_ok=True)
                Image.open(ref_path).convert("RGB").save(out, "JPEG", quality=92)
                print(f"  마스코트 기준 이미지 복사: {v['src']} ← {ref_path.name}")
                continue
            w, h = v.get("size") or ((1088, 1920) if is_thumb else (1088, 1360))
            print(f"  마스코트 그림 만들기: {v['src']} ({w}x{h}, 참고 {ref_path.name})")
            save_jpeg(generate(MASCOT_KEEP + v["prompt"], w, h, v.get("seed", MASCOT_SEED), ref_png(ref_path)), out)
            v["ai_generated"] = True
            changed += 1
            made += 1
            continue
        if v.get("url"):
            try:
                save_jpeg(download(v["url"]), out)
                v["downloaded_from"] = v["url"]
                changed += 1
                print(f"  실물 이미지: {v['src']} ← {v['url']}")
                continue
            except Exception as e:
                print(f"  내려받기 실패 ({e}): {v['url']}")
                if not v.get("prompt"):
                    raise
        if v.get("shot"):
            try:
                from shot import capture
                sh = dict(v["shot"])
                capture(sh.pop("url"), out, **{k: sh[k] for k in sh if k in
                        ("selector", "width", "height", "scroll", "wait", "dark")})
                v["captured_from"] = v["shot"]["url"]
                changed += 1
                print(f"  화면 캡처: {v['src']} ← {v['shot']['url']}")
                continue
            except Exception as e:
                print(f"  화면 캡처 실패 ({e}): {v['shot'].get('url')}")
                if not v.get("prompt"):
                    raise
        if v.get("prompt"):
            w, h = v.get("size") or ((1088, 1920) if is_thumb else (1088, 1360))
            print(f"  AI 그림 만들기: {v['src']} ({w}x{h})")
            save_jpeg(generate(v["prompt"], w, h, v.get("seed")), out)
            v["ai_generated"] = True
            changed += 1
            made += 1
    uses_ai = any(v.get("ai_generated") for v, _ in find_images(post))
    if uses_ai and not post.get("ai_image"):
        post["ai_image"] = True
        changed += 1
    if changed:
        pj.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return made


def missing(folder):
    folder = Path(folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    return any((v.get("url") or v.get("prompt") or v.get("shot") or v.get("mascot")) and not (folder / v["src"]).exists()
               for v, _ in find_images(post))


if __name__ == "__main__":
    total = 0
    for f in sys.argv[1:]:
        print(f"[{f}]")
        total += process(f)
    print(f"새로 만든 AI 그림: {total}장")
