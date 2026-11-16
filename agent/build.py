"""대기열 게시물 마무리: AI 그림 만들기 → 렌더링 → .render_hash 남기기.

GitHub Actions(render.yml)가 posts/queue에 바뀐 것이 올라올 때마다 실행한다.
.render_hash는 post.json과 거기서 쓰는 파일(src, 표지 영상 motion.src 포함)의 지문이다. 지문이 같으면 다시 만들지 않는다.
publish.py는 지문이 맞는 게시물만 올린다. (렌더링 전이나 고친 뒤 다시 만들기 전에는 안 올라감)

사용법: python agent/build.py [게시물 폴더 ...]   (폴더를 안 주면 posts/queue 전체)
"""
import hashlib
import json
import re
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


# 승인 표시(approved, approved_at, agent/approve.py)는 렌더링 결과와 상관없어서 지문에서 뺀다.
# 맨 위 단계의 한 줄짜리 키만 줄째로 지운다. approve.py는 이 줄들을 "{" 바로 다음에 넣으므로(끝에 쉼표),
# 줄을 지우면 승인 전 post.json 바이트와 똑같아져 지문이 그대로다 (다시 렌더링하지 않음).
_APPROVAL_LINE = re.compile(rb'(?m)^[ \t]*"approved(?:_at)?"[ \t]*:[^\n]*\n')


def post_bytes(pj):
    """지문용 post.json 바이트: 줄 끝을 LF로 맞추고(윈도우 체크아웃 CRLF도 리눅스와 같은 지문) 승인 줄을 뺀다.
    LF 파일·승인 줄 없는 파일은 원래 바이트 그대로라 예전 지문이 바뀌지 않는다."""
    return _APPROVAL_LINE.sub(b"", Path(pj).read_bytes().replace(b"\r\n", b"\n"))


def input_hash(folder):
    folder = Path(folder)
    pj = folder / "post.json"
    h = hashlib.sha256(post_bytes(pj))
    post = json.loads(pj.read_text(encoding="utf-8"))
    for src in sorted(set(_srcs(post))):
        f = folder / src
        h.update(src.encode())
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()


def build(folder):
    folder = Path(folder).resolve()
    sys.path.insert(0, str(AGENT))
    from gen_images import missing
    if missing(folder):
        r = subprocess.run([sys.executable, str(AGENT / "gen_images.py"), str(folder)])
        if r.returncode:
            return False
    mark = folder / ".render_hash"
    now = input_hash(folder)
    from motion import cover_motion
    # 카드뉴스 첫 장 영상(표지 motion)은 slides/01.mp4까지 있어야 최신 (ffmpeg 없는 곳에서 렌더링한 것은 다시 만든다)
    video_ok = cover_motion(json.loads((folder / "post.json").read_text(encoding="utf-8"))) is None         or (folder / "slides" / "01.mp4").exists()
    if mark.exists() and mark.read_text().strip() == now and video_ok:
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
