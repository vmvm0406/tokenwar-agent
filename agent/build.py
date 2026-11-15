"""대기열 게시물 마무리: AI 그림 만들기 → 렌더링 → .render_hash 남기기.

GitHub Actions(render.yml)가 posts/queue에 바뀐 것이 올라올 때마다 실행한다.
.render_hash는 post.json과 거기서 쓰는 파일(src)의 지문이다. 지문이 같으면 다시 만들지 않는다.
publish.py는 지문이 맞는 게시물만 올린다. (렌더링 전이나 고친 뒤 다시 만들기 전에는 안 올라감)

사용법: python agent/build.py [게시물 폴더 ...]   (폴더를 안 주면 posts/queue 전체)
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue"
AGENT = Path(__file__).resolve().parent


def _srcs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "src" and isinstance(v, str):
                yield v
            else:
                yield from _srcs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _srcs(v)


def input_hash(folder):
    folder = Path(folder)
    pj = folder / "post.json"
    h = hashlib.sha256(pj.read_bytes())
    post = json.loads(pj.read_text(encoding="utf-8"))
    for src in sorted(set(_srcs(post))):
        f = folder / src
        h.update(src.encode())
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()


def needs_images(folder):
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    for s in post.get("slides", []):
        v = s.get("visual") or {}
        if v.get("type") == "image" and v.get("prompt") and not (folder / v["src"]).exists():
            return True
    return False


def build(folder):
    folder = Path(folder).resolve()
    if needs_images(folder):
        r = subprocess.run([sys.executable, str(AGENT / "gen_images.py"), str(folder)])
        if r.returncode:
            return False
    else:
        # 그림이 이미 있어도 ai_image 표시는 맞춰 둔다
        sys.path.insert(0, str(AGENT))
        from gen_images import process
        process(folder)
    mark = folder / ".render_hash"
    now = input_hash(folder)
    if mark.exists() and mark.read_text().strip() == now:
        print(f"이미 최신: {folder.name}")
        return True
    r = subprocess.run([sys.executable, str(AGENT / "render.py"), str(folder)])
    if r.returncode:
        return False
    mark.write_text(input_hash(folder) + "\n")
    return True


def main(args):
    folders = [Path(a) for a in args] or sorted(p for p in QUEUE.iterdir() if (p / "post.json").exists())
    bad = []
    for f in folders:
        print(f"== {f.name}")
        if not build(f):
            bad.append(f.name)
    if bad:
        print("실패:", ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
