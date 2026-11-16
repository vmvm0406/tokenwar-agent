"""posts/queue 안에서 게시 시각(publish_at)이 지난 게시물을 인스타에 올린다.

GitHub Actions에서 실행된다 (.github/workflows/publish.yml).
필요한 환경 변수:
    IG_ACCESS_TOKEN   인스타 장기 토큰 (GitHub Secrets)
    GITHUB_REPOSITORY 예: yourname/tokenwar-agent (Actions가 자동으로 넣음)
선택:
    THREADS_ACCESS_TOKEN 스레드 장기 토큰 (없으면 스레드는 건너뜀, agent/threads.py)
    MEDIA_BASE        미디어 공개 주소 앞부분. 기본은 GitHub Pages의 docs/media
    DRY_RUN=1         실제로 올리지 않고 할 일만 출력 (docs/media에 복사만 하고 push하지 않음)

미디어 주소: 올릴 게시물의 이미지·영상을 docs/media/<폴더>-<지문 8자>/에 복사해 main에 push하고,
GitHub Pages(https://<owner>.github.io/<repo>/media/...)가 배포되면 그 주소를 인스타에 넘긴다.
jsDelivr는 저장소가 50MB를 넘으면 403을 낼 수 있고, raw.githubusercontent와 Release 자산은
영상을 application/octet-stream으로 줘서 쓰지 않는다. Pages는 video/mp4·image/jpeg로 바로 준다.
게시가 끝나면(성공·실패 모두) docs/media를 비운다. 같은 파일이라 git 저장소 크기는 늘지 않는다.

스레드(agent/threads.py, 선택): post.json에 threads가 있고 THREADS_ACCESS_TOKEN이 있으면(또는 DRY_RUN),
인스타 게시 시각 + config.json threads_delay_min(기본 40분)이 지난 뒤의 실행이 스레드에 올린다.
'인스타는 됐고 스레드는 아직'인 게시물 = posts/published/<폴더>에 있고 published.json에 threads_id가 없는 것.
스레드 이미지는 docs/media/<폴더>-th/에 두고, 스레드 게시가 끝날 때까지 지우지 않는다.
스레드가 실패해도 인스타 게시는 성공으로 둔다 (published.json에 threads_error, threads_tries만 남김).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import threads

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue"
DONE = ROOT / "posts" / "published"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

# 기본은 Facebook 로그인 방식(graph.facebook.com, 페이지 토큰). 경쟁 계정 조회수 분석(Business Discovery)이 이쪽에서만 된다.
API = f"https://{os.environ.get('IG_API_HOST') or 'graph.facebook.com'}/" + os.environ.get("IG_API_VERSION", "v27.0")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
DRY = os.environ.get("DRY_RUN") == "1"
REPO = os.environ.get("GITHUB_REPOSITORY", "vmvm0406/tokenwar-agent")
STAGE = ROOT / "docs" / "media"
_owner, _, _name = REPO.partition("/")
MEDIA_BASE = (os.environ.get("MEDIA_BASE") or f"https://{_owner.lower()}.github.io/{_name}/media").rstrip("/")
CONTENT_TYPES = {".jpg": "image/jpeg", ".mp4": "video/mp4"}
MAX_TRIES = 3
THREADS_DELAY_MIN = int(CONFIG.get("threads_delay_min", 40))
THREADS_MAX_AGE_H = float(CONFIG.get("threads_max_age_hours", 12))  # 이보다 늦어진 스레드 글은 올리지 않는다 (지난 소식)


class PublishError(Exception):
    pass


def call(method, path, **params):
    if DRY:
        print(f"  [DRY] {method} {path} {params}")
        return {"id": f"dry-{path.strip('/').replace('/', '-')}", "status_code": "FINISHED", "user_id": "dry"}
    r = requests.request(method, f"{API}/{path.lstrip('/')}",
                         params=params if method == "GET" else None,
                         data=params if method == "POST" else None,
                         headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60)
    body = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
    if r.status_code >= 400 or "error" in body:
        err = body.get("error", {})
        raise PublishError(f"{method} {path} 실패 ({r.status_code}): {err.get('message', r.text[:300])}")
    return body


def stage_name(folder):
    """docs/media 안의 폴더 이름. 렌더링 지문을 붙여 다시 렌더링하면 주소가 바뀐다 (Pages 캐시 10분 회피)."""
    from build import input_hash
    return f"{folder.name}-{input_hash(folder)[:8]}"


def media_files(folder, post):
    if post["type"] == "carousel":
        return [f"slides/{p.name}" for p in sorted((folder / "slides").glob("*.jpg"))]
    return ["reel.mp4", "cover.jpg"]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def clear_stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)


def threads_stage_name(folder):
    """스레드 이미지 자리. 게시 뒤 폴더가 published로 옮겨져도 이름이 같아야 해서 렌더링 지문을 쓰지 않는다."""
    return f"{folder.name}-th"


def threads_files(folder, post):
    """스레드에 쓸 이미지 (게시물 폴더 안 상대 경로). 잘못돼 있으면 빈 목록 (스레드 단계에서 오류로 남긴다)."""
    if not post.get("threads"):
        return []
    try:
        return threads.image_files(folder, post)
    except threads.ThreadsError as e:
        print(f"  스레드 이미지 확인 실패 ({folder.name}): {e}")
        return []


def wanted(todo, th_posts):
    """docs/media에 있어야 할 파일 {docs/media 안 경로: 원본 경로}."""
    files = {}
    for folder, post in todo:
        for rel in media_files(folder, post):
            files[f"{stage_name(folder)}/{rel}"] = folder / rel
    for folder, post in th_posts:
        for rel in threads_files(folder, post):
            files[f"{threads_stage_name(folder)}/{rel}"] = folder / rel
    return files


def write_stage(files):
    clear_stage()
    for dst, src in files.items():
        (STAGE / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, STAGE / dst)


def stage(files):
    """올릴 미디어를 docs/media에 복사하고 main에 push한다 (GitHub Pages가 배포)."""
    write_stage(files)
    if DRY:
        print(f"  [DRY] docs/media에 복사만 함 (push 안 함): {len(files)}개")
        return
    git("add", "-A", "docs/media")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    git("commit", "-q", "-m", "게시할 미디어를 GitHub Pages에 올림")
    for i in range(3):
        try:
            git("pull", "-q", "--rebase", "origin", "main")
            git("push", "-q", "origin", "HEAD:main")
            print("  미디어 push 완료, Pages 배포 기다리는 중")
            return
        except subprocess.CalledProcessError as e:
            print(f"  push 재시도 ({i + 1}): {e.stderr.strip()[:200]}")
            time.sleep(5)
    raise PublishError("docs/media push 실패")


def media_url(folder, rel, name=None):
    url = f"{MEDIA_BASE}/{name or stage_name(folder)}/{rel}"
    if DRY:
        return url
    # Pages 배포가 끝나 주소가 실제로 열리는지 확인 (크기·종류까지). 확인 요청엔 ?v=를 붙여 404가 캐시되지 않게 한다.
    size = (folder / rel).stat().st_size
    want = CONTENT_TYPES.get(Path(rel).suffix.lower(), "")
    for _ in range(48):  # 최대 12분
        try:
            r = requests.head(f"{url}?v={int(time.time())}", timeout=30)
            if (r.status_code == 200 and r.headers.get("content-type", "").startswith(want)
                    and int(r.headers.get("content-length", -1)) == size):
                return url
        except requests.RequestException:
            pass
        time.sleep(15)
    raise PublishError(f"미디어 공개 주소가 열리지 않음 (Pages 배포 확인): {url}")


def wait_ready(cid, minutes):
    deadline = time.time() + minutes * 60
    while True:
        st = call("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            info = call("GET", cid, fields="status")
            raise PublishError(f"컨테이너 {cid} 상태 {st}: {info.get('status')}")
        if time.time() > deadline:
            raise PublishError(f"컨테이너 {cid} 처리 시간 초과 (마지막 상태 {st})")
        time.sleep(20)


def full_caption(post):
    tags = " ".join(post.get("hashtags", []))
    return post["caption"].strip() + ("\n\n" + tags if tags else "")


def extra(post):
    # AI 생성 표시. 캐러셀은 묶음(부모)에만 붙인다 (Meta 문서). 생성 이미지를 쓴 게시물은 반드시 붙인다.
    return {"is_ai_generated": "true"} if (CONFIG.get("ai_label") or post.get("ai_image")) else {}


def ready(folder, post):
    """렌더링이 끝났는지. build.py가 남긴 .render_hash가 지금 입력과 같아야 한다."""
    from build import input_hash
    h = folder / ".render_hash"
    return h.exists() and h.read_text().strip() == input_hash(folder)


def publish_carousel(ig_id, folder, post):
    images = sorted((folder / "slides").glob("*.jpg"))
    if not 2 <= len(images) <= 10:
        raise PublishError(f"캐러셀 이미지는 2~10장이어야 함: {len(images)}장")
    children = []
    for img in images:
        c = call("POST", f"{ig_id}/media", image_url=media_url(folder, f"slides/{img.name}"),
                 is_carousel_item="true")
        children.append(c["id"])
    for cid in children:
        wait_ready(cid, 3)
    parent = call("POST", f"{ig_id}/media", media_type="CAROUSEL", children=",".join(children),
                  caption=full_caption(post), **extra(post))
    wait_ready(parent["id"], 5)
    return call("POST", f"{ig_id}/media_publish", creation_id=parent["id"])["id"]


def publish_reel(ig_id, folder, post):
    c = call("POST", f"{ig_id}/media", media_type="REELS", video_url=media_url(folder, "reel.mp4"),
             cover_url=media_url(folder, "cover.jpg"), caption=full_caption(post),
             share_to_feed="true", **extra(post))
    wait_ready(c["id"], 10)
    return call("POST", f"{ig_id}/media_publish", creation_id=c["id"])["id"]


def due(post, now):
    at = datetime.fromisoformat(post["publish_at"])
    return at <= now


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_state(folder, state):
    (folder / "published.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def threads_pending(now):
    """인스타는 됐고 스레드는 아직인 게시물 [(폴더, post, published.json 내용, 올릴 시각이 됐는지)]."""
    out = []
    if not threads.enabled() or not DONE.exists():
        return out
    for f in sorted(p for p in DONE.iterdir() if p.is_dir()):
        post, state = read_json(f / "post.json"), read_json(f / "published.json")
        if not post or not state or not (post.get("threads") or {}).get("text"):
            continue
        if state.get("status") or state.get("threads_skipped"):  # 운영자가 인스타 게시물을 지운 것 등
            continue
        n_replies = len([r for r in post["threads"].get("replies") or [] if str(r).strip()])
        if state.get("threads_id") and len(state.get("threads_reply_ids") or []) >= n_replies:
            continue
        if state.get("threads_tries", 0) >= MAX_TRIES:
            continue
        try:
            at = datetime.fromisoformat(state["published_at"])
        except (KeyError, ValueError):
            continue
        go = at + timedelta(minutes=THREADS_DELAY_MIN)
        if not state.get("threads_id") and now > go + timedelta(hours=THREADS_MAX_AGE_H):
            print(f"스레드 건너뜀 (인스타 게시 뒤 {THREADS_MAX_AGE_H:g}시간이 넘음): {f.name}")
            if not DRY:
                state["threads_skipped"] = "오래됨"
                save_state(f, state)
            continue
        out.append((f, post, state, now >= go))
    return out


def publish_threads(folder, post, state):
    """스레드 본글 + 답글. 실패해도 예외를 밖으로 내지 않는다 (인스타는 이미 성공)."""
    print(f"스레드: {folder.name}")
    try:
        urls = [] if state.get("threads_id") else [  # 본글이 이미 올라갔으면 답글만 이어서
            media_url(folder, rel, threads_stage_name(folder)) for rel in threads.image_files(folder, post)]
        threads.post_thread(post, urls, state)
        state.pop("threads_error", None)
        state["threads_published_at"] = datetime.now(timezone.utc).isoformat()
        print(f"  스레드 완료: {state.get('threads_permalink') or state.get('threads_id')}")
    except (threads.ThreadsError, PublishError, requests.RequestException) as e:
        state["threads_tries"] = state.get("threads_tries", 0) + 1
        state["threads_error"] = str(e)[:500]
        print(f"  스레드 실패 ({state['threads_tries']}/{MAX_TRIES}, 인스타는 그대로 성공): {e}")
    if not DRY:
        save_state(folder, state)


def keep_threads_media(now):
    """실행 끝: 아직 스레드에 안 올린 게시물의 스레드 이미지만 docs/media에 남긴다 (커밋은 워크플로 마지막 단계)."""
    write_stage(wanted([], [(f, p) for f, p, _, _ in threads_pending(now)]))


def main():
    if not TOKEN and not DRY:
        print("IG_ACCESS_TOKEN이 없음. GitHub 저장소 Settings › Secrets에 넣었는지 확인.")
        sys.exit(1)
    now = datetime.now(timezone.utc)
    folders = sorted(p for p in QUEUE.iterdir() if p.is_dir())
    todo = []
    for f in folders:
        post = json.loads((f / "post.json").read_text(encoding="utf-8"))
        log = f / "error.log"
        tries = log.read_text(encoding="utf-8").count("\n---\n") if log.exists() else 0
        if tries >= MAX_TRIES:
            print(f"건너뜀 (실패 {tries}회, error.log 확인 후 삭제하면 다시 시도): {f.name}")
            continue
        if due(post, now):
            if not ready(f, post):
                print(f"건너뜀 (아직 렌더링 전, 렌더링 작업이 끝나면 다음 확인 때 올라감): {f.name}")
                continue
            todo.append((f, post))
    pending = threads_pending(now)
    th_due = [(f, p, st) for f, p, st, go in pending if go]
    if not todo and not th_due:
        print("올릴 시각이 된 게시물 없음.")
        if not DRY:
            keep_threads_media(now)  # 지난 실행이 남긴 미디어는 치우고, 스레드를 기다리는 이미지만 남긴다
        return
    # 스레드 이미지는 인스타 게시 때 같이 올려 두면, 40분 뒤 스레드 차례에 Pages 배포를 기다리지 않는다.
    th_posts = [(f, p) for f, p in todo if p.get("threads") and threads.enabled()]
    th_posts += [(f, p) for f, p, _, _ in pending]
    try:
        stage(wanted(todo, th_posts))
    except (PublishError, subprocess.CalledProcessError) as e:
        print(f"미디어 올리기 실패: {e}")
        sys.exit(1)

    failed = False
    if todo:
        if IG_USER_ID:
            ig_id = IG_USER_ID
            print(f"계정 ID: {ig_id}")
        else:
            me = call("GET", "me", fields="user_id,username")
            ig_id = me.get("user_id") or me.get("id")
            print(f"계정: {me.get('username')} ({ig_id})")
    for folder, post in todo:
        print(f"게시: {folder.name} ({post['type']})")
        try:
            if post["type"] == "carousel":
                media_id = publish_carousel(ig_id, folder, post)
            else:
                media_id = publish_reel(ig_id, folder, post)
            link = "" if DRY else call("GET", media_id, fields="permalink").get("permalink", "")
            result = {"media_id": media_id, "permalink": link,
                      "published_at": datetime.now(timezone.utc).isoformat()}
            (folder / "published.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            if not DRY:
                # 렌더링 원본 구간(clips/source.mp4)은 게시 뒤엔 필요 없다. 저장소가 커지지 않게 지운다.
                (folder / "clips" / "source.mp4").unlink(missing_ok=True)
                DONE.mkdir(parents=True, exist_ok=True)
                shutil.move(str(folder), str(DONE / folder.name))
            print(f"  완료: {link or media_id}")
            if post.get("threads"):
                print(f"  스레드는 {THREADS_DELAY_MIN}분 뒤 실행에서 올림" if threads.enabled()
                      else "  스레드 건너뜀 (THREADS_ACCESS_TOKEN 없음)")
        except PublishError as e:
            failed = True
            print(f"  실패: {e}")
            with open(folder / "error.log", "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now(timezone.utc).isoformat()}\n{e}\n---\n")

    for folder, post, state in th_due:
        publish_threads(folder, post, state)

    if not DRY:
        keep_threads_media(now)  # 끝난 미디어는 Pages에서 내리고 스레드를 기다리는 이미지만 남긴다 (워크플로 마지막 단계가 커밋)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
