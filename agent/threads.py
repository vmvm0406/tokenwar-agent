"""스레드(Threads) 게시. publish.py가 인스타 게시 뒤에 부른다.

흐름 (Meta Threads API, graph.threads.net):
    1. 컨테이너 만들기  POST /me/threads  (TEXT / IMAGE / CAROUSEL, 주제 태그 topic_tag)
    2. 약 30초 기다린 뒤 상태 확인  GET /<컨테이너>?fields=status,error_message
    3. 게시  POST /me/threads_publish creation_id=<컨테이너>
    4. replies를 내 답글로 차례로 (reply_to_id = 본글). 출처 링크는 여기에.

환경 변수:
    THREADS_ACCESS_TOKEN  스레드 장기 토큰 (GitHub Secrets). 없으면 스레드는 조용히 건너뛴다.
    THREADS_API_VERSION   기본 v1.0
    DRY_RUN=1             요청을 보내지 않고 할 일만 출력

post.json 선택 필드 (TEMPLATES.md "스레드 글"):
    "threads": {"text": "...", "images": ["cover", 2, 3], "topic": "AI Threads", "replies": ["출처: ... https://..."]}
    topic(선택): 커뮤니티 주제 태그. 게임·앱 따라 하기 "바이브코딩", 그림·영상 따라 하기 "AI 콘텐츠"/"AI 영상 제작", 없으면 "AI Threads" (STYLE_GUIDE 7-2)
사용자 ID 대신 /me를 쓴다. 토큰 값은 어디에도 출력하지 않는다.
"""
import os
import time

import requests

API = "https://graph.threads.net/" + os.environ.get("THREADS_API_VERSION", "v1.0")
TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
DRY = os.environ.get("DRY_RUN") == "1"
DEFAULT_TOPIC = "AI Threads"


class ThreadsError(Exception):
    pass


def enabled():
    """토큰이 있거나 시험 실행이면 스레드 단계를 돈다."""
    return bool(TOKEN) or DRY


def call(method, path, **params):
    if DRY:
        shown = {k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v) for k, v in params.items()}
        print(f"  [DRY][스레드] {method} {path} {shown}")
        return {"id": f"dry-th-{path.strip('/').replace('/', '-')}", "status": "FINISHED",
                "permalink": "https://www.threads.net/@tokenwar_ai/post/dry"}
    r = requests.request(method, f"{API}/{path.lstrip('/')}",
                         params=params if method == "GET" else None,
                         data=params if method == "POST" else None,
                         headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or "error" in body:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise ThreadsError(f"{method} {path} 실패 ({r.status_code}): {err.get('message', r.text[:300])}")
    return body


def wait_ready(cid, first_wait, minutes=5):
    """컨테이너가 FINISHED가 될 때까지. Meta 문서는 게시 전 평균 30초 기다리기를 권한다."""
    if not DRY:
        time.sleep(first_wait)
    deadline = time.time() + minutes * 60
    while True:
        info = call("GET", cid, fields="status,error_message")
        st = info.get("status")
        if st in ("FINISHED", "PUBLISHED"):
            return
        if st in ("ERROR", "EXPIRED"):
            raise ThreadsError(f"스레드 컨테이너 {cid} 상태 {st}: {info.get('error_message', '')}")
        if time.time() > deadline:
            raise ThreadsError(f"스레드 컨테이너 {cid} 처리 시간 초과 (마지막 상태 {st})")
        time.sleep(10)


def image_files(folder, post):
    """threads.images → 게시물 폴더 안 상대 경로 목록. 장 번호는 slides/의 n번째 jpg, "cover"는 표지.
    첫 장이 영상(slides/01.mp4)인 카드뉴스도 스레드에는 그 정지 화면 slides/01.jpg를 쓴다 (jpg만 고름)."""
    th = post.get("threads") or {}
    slides = sorted(p.name for p in (folder / "slides").glob("*.jpg")) if (folder / "slides").exists() else []
    out = []
    for x in th.get("images") or []:
        if x == "cover":
            rel = f"slides/{slides[0]}" if post.get("type") == "carousel" and slides else "cover.jpg"
        elif isinstance(x, int) and 1 <= x <= len(slides):
            rel = f"slides/{slides[x - 1]}"
        else:
            raise ThreadsError(f"threads.images 항목을 찾을 수 없음: {x!r}")
        if not (folder / rel).exists():
            raise ThreadsError(f"스레드 이미지 파일 없음: {rel}")
        if rel not in out:
            out.append(rel)
    return out


def publish_main(post, urls):
    """본글 게시 → 미디어 ID. urls: 공개 이미지 주소 목록 (0개면 글만)."""
    th = post["threads"]
    text = th["text"].strip()
    topic = {"topic_tag": th.get("topic") or DEFAULT_TOPIC}
    if not urls:
        c = call("POST", "me/threads", media_type="TEXT", text=text, **topic)
        wait_ready(c["id"], 5)
    elif len(urls) == 1:
        c = call("POST", "me/threads", media_type="IMAGE", image_url=urls[0], text=text, **topic)
        wait_ready(c["id"], 30)
    else:
        kids = [call("POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"]
                for u in urls]
        time.sleep(0 if DRY else 30)
        for k in kids:
            wait_ready(k, 0)
        c = call("POST", "me/threads", media_type="CAROUSEL", children=",".join(kids), text=text, **topic)
        wait_ready(c["id"], 30)
    return call("POST", "me/threads_publish", creation_id=c["id"])["id"]


def publish_reply(root_id, text):
    c = call("POST", "me/threads", media_type="TEXT", text=text.strip(), reply_to_id=root_id)
    wait_ready(c["id"], 5)
    return call("POST", "me/threads_publish", creation_id=c["id"])["id"]


def permalink(media_id):
    if DRY:
        return ""
    try:
        return call("GET", media_id, fields="permalink").get("permalink", "")
    except ThreadsError:
        return ""


def post_thread(post, urls, state):
    """본글과 답글을 올리고 state(published.json 내용)에 결과를 적는다.
    도중에 실패하면 이미 올린 것은 state에 남아 다음 실행이 이어서 한다 (본글을 두 번 올리지 않는다)."""
    replies = [r for r in (post["threads"].get("replies") or []) if str(r).strip()]
    if not state.get("threads_id"):
        mid = publish_main(post, urls)
        state["threads_id"] = mid
        state["threads_permalink"] = permalink(mid)
    done = state.setdefault("threads_reply_ids", [])
    for text in replies[len(done):]:
        done.append(publish_reply(state["threads_id"], str(text)))
    return state
