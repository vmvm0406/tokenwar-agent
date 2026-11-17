"""posts/queue 안에서 게시 시각(publish_at)이 지난 게시물을 인스타에 올린다.

GitHub Actions에서 실행된다 (.github/workflows/publish.yml).
필요한 환경 변수:
    IG_ACCESS_TOKEN   인스타 장기 토큰 (GitHub Secrets)
    GITHUB_REPOSITORY 예: yourname/tokenwar-agent (Actions가 자동으로 넣음)
선택:
    THREADS_ACCESS_TOKEN 스레드 장기 토큰 (없으면 스레드는 건너뜀, agent/threads.py)
    MEDIA_BASE        미디어 공개 주소 앞부분. 기본은 GitHub Pages의 docs/media
    DRY_RUN=1         실제로 올리지 않고 할 일만 출력 (docs/media에 복사만 하고 push하지 않음)
    GITHUB_TOKEN      Actions 기본 토큰. dm 게시물이 올라가면 "Zorcha 설정 필요" 이슈를 연다 (없으면 이슈만 건너뜀)

Zorcha 알림 (STYLE_GUIDE 7-1): post.json에 dm이 있는 게시물이 올라가면 바로
  1. GitHub 이슈 "Zorcha 설정 필요: <제목>" (라벨 zorcha, 본문 = 인스타 링크 + dm.md 설정 메모) → 운영자에게 메일
  2. data/zorcha_todo.md에 한 줄 (워크플로 마지막 단계가 커밋. 이 컴퓨터의 watch-models.ps1이 읽어 data/zorcha_alerts.md로)
DRY_RUN에서는 이슈를 열지 않고 파일도 안 바꾸고 내용만 출력한다. 알림이 실패해도 게시는 성공으로 둔다.

승인 관문 (config.json require_approval, agent/approve.py): 켜져 있으면 post.json에 "approved": true가 있는
게시물만 올린다. 승인 없는 게시물은 게시 시각이 지나도 "승인 대기"로 건너뛴다 (error.log·실패로 치지 않음).
approval_exempt_before보다 이른 publish_at은 관문에서 뺀다.

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

중복 게시 막기 (2026-11-17 FPS 릴스 두 번 게시): 게시 기록 push가 실패하면 폴더가 queue에 남아 다음 실행이 또 올린다.
그래서 올리기 전에 우리 계정 최근 게시물(GET /{ig-user-id}/media)을 보고, DEDUP_HOURS(12시간) 안에
캡션 첫 줄이 같은 게시물이 있으면 다시 올리지 않고 그 게시물로 published.json을 쓴 뒤 published로 옮긴다
(Zorcha 이슈는 이미 열렸으니 zorcha_todo 줄만). 조회가 실패하면 경고만 찍고 그대로 올린다.
같은 조회로 published.json에 media_id가 비어 있는 최근 게시물(손으로 고친 기록)의 media_id를 permalink로 채운다.

스토리 (2026-11-17 운영자 "게시물을 스토리로 올려"): 피드 게시가 끝나면 같은 게시물을 스토리로도 올린다
(media_type=STORIES). 릴스는 같은 영상(60초가 넘으면 앞 59.5초로 잘라서, ffmpeg가 없으면 cover.jpg 사진),
카드뉴스는 1번 장 사진(slides/01.jpg). post.json "story": false면 건너뛴다. published.json에 story_id·story_at
(실패면 story_error)을 남기고, story_id가 있으면 다시 올리지 않는다. 스토리가 실패해도 피드 게시는 성공으로 둔다.
중복 게시 막기로 건너뛴 게시물은 앞 실행이 스토리도 올렸을 수 있어 올리지 않는다 (story_skipped).
지금 올라가 있는 게시물을 한꺼번에: python agent/publish.py --stories-backfill (stories-backfill.yml,
STORY_GAP_MIN 간격, 인스타에서 지운 게시물·published.json status가 있는 게시물은 건너뜀).
"""
import json
import os
import shutil
import subprocess
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import threads
from approve import may_publish

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
THREADS_MAX_AGE_H = float(CONFIG.get("threads_max_age_hours", 12))
# 게시 직후 docs/media를 바로 비우면 인스타가 뒤늦게 사진을 다시 가져갈 때 파일이 없어 회색 장이 생긴다
# (2026-11-16 사이버캡 카드 4번 장). 게시 뒤 이 시간 동안은 미디어를 Pages에 남긴다.
MEDIA_KEEP_MIN = int(CONFIG.get("media_keep_min", 120))  # 이보다 늦어진 스레드 글은 올리지 않는다 (지난 소식)
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ZORCHA_TODO = ROOT / "data" / "zorcha_todo.md"
ZORCHA_LABEL = "zorcha"
# 스토리 켜기/끄기 (config.json stories_enabled, 기본 꺼짐). 운영자 2026-11-17 "스토리는 다 내려": 끔.
STORIES_ON = bool(CONFIG.get("stories_enabled", False))
STORY_MAX_SEC = 60    # 스토리 영상 최대 길이 (Graph API). 넘으면 앞부분만
STORY_TMP = Path(tempfile.gettempdir()) / "tokenwar-story"
DEDUP_HOURS = 12      # 이 시간 안에 캡션 첫 줄이 같은 게시물이 있으면 다시 올리지 않는다
FILL_ID_HOURS = 48    # 이 시간 안 게시물 중 media_id가 빈 것만 채운다


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


def has_cover_video(post):
    """카드뉴스 첫 장이 영상인지 (표지 motion, TEMPLATES.md "표지 영상")."""
    from motion import cover_motion
    return cover_motion(post) is not None


def media_files(folder, post):
    if post["type"] == "carousel":
        files = [f"slides/{p.name}" for p in sorted((folder / "slides").glob("*.jpg"))]
        if has_cover_video(post) and files:
            # 첫 장은 영상(slides/01.mp4)으로. 정지 화면 01.jpg는 스레드·검토용이라 인스타에 올리지 않는다
            if not (folder / "slides" / "01.mp4").exists():
                raise PublishError("표지 motion이 있는데 slides/01.mp4가 없음 (render.yml 렌더링 확인)")
            files[0] = "slides/01.mp4"
        return files
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


def media_url(folder, rel, name=None, src=None):
    """src: 원본이 게시물 폴더 밖에 있을 때(스토리용으로 자른 영상) 그 경로."""
    url = f"{MEDIA_BASE}/{name or stage_name(folder)}/{rel}"
    if DRY:
        return url
    src = Path(src) if src else folder / rel
    # Pages 배포가 끝나 주소가 실제로 열리는지 확인 (크기·종류까지). 확인 요청엔 ?v=를 붙여 404가 캐시되지 않게 한다.
    size = src.stat().st_size
    want = CONTENT_TYPES.get(Path(rel).suffix.lower(), "")
    for _ in range(48):  # 최대 12분
        try:
            r = requests.head(f"{url}?v={int(time.time())}", timeout=30)
            if (r.status_code == 200 and r.headers.get("content-type", "").startswith(want)
                    and int(r.headers.get("content-length", -1)) == size):
                # 인스타는 ?v= 없는 주소를 가져가니, 그 주소도 내용이 같은지 본다 (배포 중이거나 옛 캐시면 다름)
                if want.startswith("image/"):
                    import hashlib
                    g = requests.get(url, timeout=60)
                    if g.status_code != 200 or hashlib.sha256(g.content).digest() != hashlib.sha256(src.read_bytes()).digest():
                        time.sleep(15)
                        continue
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
    if has_cover_video(post) and not (folder / "slides" / "01.mp4").exists():
        return False  # 첫 장 영상이 아직 없음 (ffmpeg 없는 곳에서 렌더링한 것)
    return h.exists() and h.read_text().strip() == input_hash(folder)


def publish_carousel(ig_id, folder, post):
    items = media_files(folder, post)
    if not 2 <= len(items) <= 20:
        raise PublishError(f"캐러셀은 2~20장이어야 함: {len(items)}장")
    children, waits = [], []
    for rel in items:
        if rel.endswith(".mp4"):
            # 영상 장 (사진과 섞기 가능, Meta 문서: 캐러셀 자식 media_type=VIDEO + video_url)
            url = media_url(folder, rel)
            from motion import cover_motion
            # 모션 표지는 첫 0.5초쯤 글이 아직 안 올라와 있어서, 미리보기(격자) 장면을 2초로 잡는다
            thumb = {} if (cover_motion(post) or {}).get("src") else {"thumb_offset": "2000"}
            try:
                c = call("POST", f"{ig_id}/media", media_type="VIDEO", video_url=url, is_carousel_item="true", **thumb)
            except PublishError as e:
                if not thumb:
                    raise
                print(f"  thumb_offset 없이 다시 시도: {e}")
                c = call("POST", f"{ig_id}/media", media_type="VIDEO", video_url=url, is_carousel_item="true")
            waits.append(10)
        else:
            c = call("POST", f"{ig_id}/media", image_url=media_url(folder, rel), is_carousel_item="true")
            waits.append(3)
        children.append(c["id"])
    for cid, minutes in zip(children, waits):
        wait_ready(cid, minutes)
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


def check_published_media(media_id):
    """게시 뒤 인스타가 가진 장(children)마다 사진을 받아 열어 본다. 회색·빈 장이면 경고 목록 (게시는 그대로)."""
    if DRY:
        return []
    warns = []
    try:
        kids = call("GET", f"{media_id}/children", fields="media_url,media_type").get("data") or []
        if not kids:
            kids = [call("GET", media_id, fields="media_url,media_type")]
        from io import BytesIO
        from PIL import Image, ImageStat
        for i, k in enumerate(kids, 1):
            if k.get("media_type") == "VIDEO" or not k.get("media_url"):
                continue
            r = requests.get(k["media_url"], timeout=60)
            try:
                im = Image.open(BytesIO(r.content))
                im.load()
                sd = ImageStat.Stat(im.convert("L")).stddev[0]
            except Exception as e:  # noqa: BLE001
                warns.append(f"{i}번 장 사진을 열 수 없음: {e}")
                continue
            if sd < 4:
                warns.append(f"{i}번 장이 거의 한 색(표준편차 {sd:.1f}): 인스타에서 회색으로 보일 수 있음")
    except (PublishError, requests.RequestException) as e:
        warns.append(f"게시 뒤 사진 확인 실패: {e}")
    for w in warns:
        print(f"  경고: {w}")
    return warns


def ffmpeg_exe():
    """ffmpeg 경로 (PATH, 없으면 pip imageio-ffmpeg). 없으면 None."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def video_seconds(path):
    """영상 길이(초). ffmpeg -i 출력의 Duration을 읽는다. 모르면 None."""
    exe = ffmpeg_exe()
    if not exe:
        return None
    r = subprocess.run([exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def trim_video(src, dst, seconds):
    """src 앞 seconds초를 dst로 (다시 인코딩, 끝 0.5초 소리 페이드). 실패하면 False."""
    exe = ffmpeg_exe()
    if not exe:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([exe, "-y", "-v", "error", "-i", str(src), "-t", f"{seconds:.2f}",
                        "-af", f"afade=t=out:st={seconds - 0.5:.2f}:d=0.5",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dst)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not dst.exists():
        print(f"  스토리 영상 자르기 실패: {r.stderr.strip()[:200]}")
        return False
    return True


_story_cache = {}


def story_media(folder, post):
    """스토리에 쓸 미디어 (docs/media 안 상대 이름, 원본 경로, "VIDEO"|"IMAGE"). 올리지 않으면 None."""
    if not STORIES_ON:
        return None
    if post.get("story") is False:
        return None
    key = folder.name
    if key in _story_cache:
        return _story_cache[key]
    out = None
    if post["type"] == "carousel":
        f = folder / "slides" / "01.jpg"
        out = ("slides/01.jpg", f, "IMAGE") if f.exists() else None
    elif (folder / "reel.mp4").exists():
        sec = video_seconds(folder / "reel.mp4")
        if sec is None or sec <= STORY_MAX_SEC:
            out = ("reel.mp4", folder / "reel.mp4", "VIDEO")
        else:
            cut = STORY_MAX_SEC - 0.5
            tmp = STORY_TMP / f"{folder.name}.mp4"
            if trim_video(folder / "reel.mp4", tmp, cut):
                print(f"  스토리: {sec:.1f}초 릴스를 앞 {cut:g}초로 자름 ({folder.name})")
                out = ("story.mp4", tmp, "VIDEO")
            elif (folder / "cover.jpg").exists():
                print(f"  스토리: {sec:.1f}초 릴스, ffmpeg가 없어 cover.jpg 사진으로 ({folder.name})")
                out = ("cover.jpg", folder / "cover.jpg", "IMAGE")
    _story_cache[key] = out
    return out


def story_files(items):
    """docs/media에 올려 둘 스토리 미디어 {docs/media 안 경로: 원본 경로}."""
    files = {}
    for folder, post in items:
        try:
            sm = story_media(folder, post)
        except Exception as e:  # noqa: BLE001  스토리 준비 실패로 피드 게시를 막지 않는다
            print(f"  경고: 스토리 미디어 준비 실패 ({folder.name}): {e}")
            _story_cache[folder.name] = None
            continue
        if sm:
            files[f"{stage_name(folder)}/{sm[0]}"] = sm[1]
    return files


def publish_story(ig_id, folder, post):
    """스토리 하나를 올리고 (story_id, 쓴 미디어 이름). 실패하면 PublishError."""
    sm = story_media(folder, post)
    if not sm:
        raise PublishError("스토리에 쓸 미디어 없음")
    rel, src, kind = sm
    url = media_url(folder, rel, src=src)
    if kind == "VIDEO":
        c = call("POST", f"{ig_id}/media", media_type="STORIES", video_url=url)
        wait_ready(c["id"], 10)
    else:
        c = call("POST", f"{ig_id}/media", media_type="STORIES", image_url=url)
        wait_ready(c["id"], 3)
    return call("POST", f"{ig_id}/media_publish", creation_id=c["id"])["id"], rel


def add_story(ig_id, folder, post, state):
    """피드 게시가 끝난 게시물을 스토리로도 올리고 state(published.json 내용)에 기록한다.
    예외를 밖으로 내지 않는다 (피드 게시는 이미 성공). 올렸으면 True."""
    if not STORIES_ON:
        return False
    if state.get("story_id"):
        return False
    if post.get("story") is False:
        state["story_skipped"] = "post.json story: false"
        return False
    try:
        sid, rel = publish_story(ig_id, folder, post)
        state["story_id"] = sid
        state["story_at"] = datetime.now(timezone.utc).isoformat()
        state["story_media"] = rel
        state.pop("story_error", None)
        print(f"  스토리 완료: {sid} ({rel})")
        return True
    except Exception as e:  # noqa: BLE001  스토리 실패로 피드 게시 기록이 틀어지면 안 된다
        state["story_error"] = str(e)[:500]
        print(f"  경고: 스토리 실패 (피드 게시는 그대로 성공): {e}")
        return False


def open_issue(title, body):
    """GitHub 이슈를 연다 (GITHUB_TOKEN). (번호, 주소) 또는 실패하면 (None, 이유). 토큰은 출력하지 않는다."""
    if not GH_TOKEN:
        return None, "GITHUB_TOKEN 없음"
    api = f"https://api.github.com/repos/{REPO}"
    h = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    try:
        # 라벨이 없으면 만든다 (있으면 422, 무시)
        requests.post(f"{api}/labels", headers=h, timeout=30,
                      json={"name": ZORCHA_LABEL, "color": "00FF66", "description": "게시 뒤 Zorcha 자동 DM 설정 필요"})
        r = requests.post(f"{api}/issues", headers=h, timeout=30,
                          json={"title": title, "body": body, "labels": [ZORCHA_LABEL]})
        if r.status_code >= 300:
            return None, f"이슈 만들기 실패 ({r.status_code}): {r.text[:200]}"
        j = r.json()
        return j.get("number"), j.get("html_url", "")
    except requests.RequestException as e:
        return None, f"이슈 만들기 실패: {e}"


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def parse_ts(ts):
    """인스타 timestamp('2026-11-17T12:19:05+0000')나 ISO 문자열 → datetime. 못 읽으면 None."""
    for f in (lambda t: datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z"), datetime.fromisoformat):
        try:
            at = f(str(ts))
            return at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def recent_media(ig_id):
    """우리 계정 최근 게시물 [{id, caption, permalink, timestamp}]. 조회 실패면 None (게시는 막지 않음)."""
    if DRY:
        fake = os.environ.get("DEDUP_FAKE_MEDIA")  # 시험용: 가짜 최근 게시물 목록(json 파일)
        return json.loads(Path(fake).read_text(encoding="utf-8")) if fake else []
    try:
        return call("GET", f"{ig_id}/media", fields="id,caption,permalink,timestamp", limit="25").get("data") or []
    except (PublishError, requests.RequestException, ValueError) as e:
        print(f"  경고: 최근 게시물 조회 실패, 중복 확인 없이 진행: {e}")
        return None


def find_duplicate(post, media, now, hours=DEDUP_HOURS):
    """media 중 hours 시간 안에 올라온, 캡션 첫 줄이 이 게시물과 같은 것 (없으면 None)."""
    want = first_line(full_caption(post))
    if not want:
        return None
    for m in media or []:
        at = parse_ts(m.get("timestamp"))
        if at is None or now - at > timedelta(hours=hours):
            continue
        if first_line(m.get("caption")) == want:
            return m
    return None


def missing_id_folders(now):
    """published.json에 media_id가 비어 있고 permalink만 있는 최근(FILL_ID_HOURS) 게시물 폴더."""
    out = []
    if not DONE.exists():
        return out
    for f in sorted(p for p in DONE.iterdir() if p.is_dir()):
        state = read_json(f / "published.json")
        if not state or state.get("media_id") or not state.get("permalink"):
            continue
        at = parse_ts(state.get("published_at"))
        if at is not None and now - at <= timedelta(hours=FILL_ID_HOURS):
            out.append(f)
    return out


def fill_missing_ids(media, now):
    """media_id가 빈 최근 게시물에 permalink가 같은 게시물의 id를 채운다."""
    by_link = {(m.get("permalink") or "").rstrip("/"): m for m in media or [] if m.get("permalink")}
    for f in missing_id_folders(now):
        state = read_json(f / "published.json")
        m = by_link.get(state["permalink"].rstrip("/"))
        if m:
            state["media_id"] = m["id"]
            at = parse_ts(m.get("timestamp"))
            if at:  # 손으로 적은 대략의 시각을 인스타 기록으로
                state["published_at"] = at.astimezone(timezone.utc).isoformat()
            print(f"media_id 채움: {f.name} → {m['id']}")
            if not DRY:
                save_state(f, state)


def notify_zorcha(folder, post, permalink, new_issue=True):
    """dm 게시물이 올라가면 운영자에게 Zorcha 설정을 알린다 (이슈 + data/zorcha_todo.md). 예외를 밖으로 내지 않는다.
    new_issue=False: 이슈는 이미 열린 것(중복 게시 막기로 건너뛴 게시물)이라 zorcha_todo 줄만 남긴다."""
    if not post.get("dm"):
        return
    try:
        import dm
        memo = f"posts/published/{folder.name}/dm.md"
        title, body = dm.notice(post, permalink, memo)
        when = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
        NL = chr(10)
        line = f"- [ ] {when} | {title} | {permalink or '(주소 확인 실패)'} | ISSUE | {memo}"
        if DRY:
            print(f"  [DRY] Zorcha 알림 (이슈 안 엶, {ZORCHA_TODO.name} 안 바꿈)")
            print(f"  이슈 제목: {title}")
            print(NL.join("    " + l for l in body.splitlines()))
            print(f"  [DRY] {ZORCHA_TODO.name}에 쌓을 줄: " + line.replace("ISSUE", "이슈 #?"))
            return
        num, info = open_issue(title, body) if new_issue else (None, "이미 올라간 게시물이라 이슈를 새로 열지 않음")
        if num:
            print(f"  Zorcha 알림 이슈 #{num}: {info}")
        else:
            print(f"  Zorcha 알림 이슈를 열지 못함 (게시는 그대로 성공, {ZORCHA_TODO.name}에는 남김): {info}")
        head = ["# Zorcha 설정할 게시물", "",
                "publish.py가 dm 게시물을 올릴 때마다 한 줄씩 쌓는다 (손으로 고치지 않는다). 설정이 끝나면 운영자가 GitHub 이슈를 닫는다. "
                "이 컴퓨터의 scripts/watch-models.ps1이 열린 이슈의 줄만 tokenwar-daily/data/zorcha_alerts.md에 남긴다.", "",
                "게시 시각(한국) | 제목 | 인스타 | 이슈 | 설정 메모", "", ""]
        new = not ZORCHA_TODO.exists()
        ZORCHA_TODO.parent.mkdir(parents=True, exist_ok=True)
        with open(ZORCHA_TODO, "a", encoding="utf-8", newline=NL) as fh:
            if new:
                fh.write(NL.join(head))
            fh.write(line.replace("ISSUE", f"이슈 #{num}" if num else "이슈 없음") + NL)
    except Exception as e:  # noqa: BLE001  알림 실패로 게시 기록이 틀어지면 안 된다
        print(f"  Zorcha 알림 실패 (게시는 그대로 성공): {e}")


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


def recent_published(now):
    """게시한 지 MEDIA_KEEP_MIN분이 안 된 게시물 [(폴더, post)]. 이 미디어는 Pages에서 내리지 않는다."""
    out = []
    if not DONE.exists():
        return out
    for f in sorted(p for p in DONE.iterdir() if p.is_dir()):
        post, state = read_json(f / "post.json"), read_json(f / "published.json")
        if not post or not state:
            continue
        try:
            at = datetime.fromisoformat(state["published_at"])
        except (KeyError, ValueError):
            continue
        if now - at < timedelta(minutes=MEDIA_KEEP_MIN):
            out.append((f, post))
    return out


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
    """실행 끝: 최근 게시물(MEDIA_KEEP_MIN분 안)의 미디어와 아직 스레드에 안 올린 이미지만 docs/media에 남긴다
    (커밋은 워크플로 마지막 단계)."""
    write_stage(wanted(recent_published(now), [(f, p) for f, p, _, _ in threads_pending(now)]))


def account_id():
    if IG_USER_ID:
        print(f"계정 ID: {IG_USER_ID}")
        return IG_USER_ID
    me = call("GET", "me", fields="user_id,username")
    print(f"계정: {me.get('username')} ({me.get('user_id') or me.get('id')})")
    return me.get("user_id") or me.get("id")


def finish(folder, post, result, new_issue=True):
    """게시된 게시물: published.json을 쓰고 posts/published로 옮긴 뒤 Zorcha 알림."""
    (folder / "published.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not DRY:
        # 렌더링 원본 구간(clips/source.mp4)은 게시 뒤엔 필요 없다. 저장소가 커지지 않게 지운다.
        (folder / "clips" / "source.mp4").unlink(missing_ok=True)
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(DONE / folder.name))
    notify_zorcha(folder, post, result.get("permalink", ""), new_issue=new_issue)
    if post.get("threads"):
        print(f"  스레드는 {THREADS_DELAY_MIN}분 뒤 실행에서 올림" if threads.enabled()
              else "  스레드 건너뜀 (THREADS_ACCESS_TOKEN 없음)")


def main():
    if not TOKEN and not DRY:
        print("IG_ACCESS_TOKEN이 없음. GitHub 저장소 Settings › Secrets에 넣었는지 확인.")
        sys.exit(1)
    now = datetime.now(timezone.utc)
    if CONFIG.get("publish_paused"):
        # 운영자 2026-11-18 "릴스 자동으로 올리기는 잠깐 멈추자. 계정을 리뉴얼 할거야": 인스타·스레드 게시 전부 멈춤
        print("게시 멈춤 (config.json publish_paused true). 아무것도 올리지 않음.")
        return
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
            if not may_publish(post, CONFIG):
                # 승인 관문 (config require_approval, agent/approve.py). 실패가 아니라 기다림이라 error.log에 남기지 않는다
                print(f"승인 대기: {f.name}")
                continue
            if not ready(f, post):
                print(f"건너뜀 (아직 렌더링 전, 렌더링 작업이 끝나면 다음 확인 때 올라감): {f.name}")
                continue
            todo.append((f, post))
    ig_id = None
    if todo or missing_id_folders(now):
        ig_id = account_id()
        media = recent_media(ig_id)
        if media:
            fill_missing_ids(media, now)
        # 이미 올라간 게시물(게시 기록 push 실패 등)은 다시 올리지 않고 기록만 맞춘다
        for f, p in list(todo):
            dup = find_duplicate(p, media, now) if media else None
            if dup:
                todo.remove((f, p))
                print(f"이미 게시됨, 다시 올리지 않음: {f.name} → {dup.get('permalink') or dup['id']}")
                at = parse_ts(dup.get("timestamp")) or now
                finish(f, p, {"media_id": dup["id"], "permalink": dup.get("permalink", ""),
                              "published_at": at.astimezone(timezone.utc).isoformat(),
                              "note": "중복 게시 막기: 앞 실행이 이미 올렸고 게시 기록만 빠져 있어 다시 올리지 않음",
                              "story_skipped": "중복 게시 막기 (앞 실행이 스토리도 올렸을 수 있음)"},
                       new_issue=False)
    pending = threads_pending(now)
    th_due = [(f, p, st) for f, p, st, go in pending if go]
    if not todo and not th_due:
        print("올릴 시각이 된 게시물 없음.")
        if not DRY:
            keep_threads_media(now)  # 오래된 미디어는 치우고, 최근 게시물·스레드를 기다리는 이미지만 남긴다
        return
    # 스레드 이미지는 인스타 게시 때 같이 올려 두면, 40분 뒤 스레드 차례에 Pages 배포를 기다리지 않는다.
    th_posts = [(f, p) for f, p in todo if p.get("threads") and threads.enabled()]
    th_posts += [(f, p) for f, p, _, _ in pending]
    try:
        stage({**wanted(todo + recent_published(now), th_posts), **story_files(todo)})
    except (PublishError, subprocess.CalledProcessError) as e:
        print(f"미디어 올리기 실패: {e}")
        sys.exit(1)

    failed = False
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
            if post["type"] == "carousel":
                time.sleep(20)  # 인스타가 장마다 처리를 마칠 시간
                mw = check_published_media(media_id)
                if mw:
                    result["media_warnings"] = mw
            print(f"  완료: {link or media_id}")
            add_story(ig_id, folder, post, result)
            finish(folder, post, result)
        except PublishError as e:
            failed = True
            print(f"  실패: {e}")
            with open(folder / "error.log", "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now(timezone.utc).isoformat()}\n{e}\n---\n")

    for folder, post, state in th_due:
        publish_threads(folder, post, state)

    if not DRY:
        keep_threads_media(now)  # 오래된 미디어는 내리고 최근 게시물·스레드 이미지만 남긴다 (워크플로 마지막 단계가 커밋)
    if failed:
        sys.exit(1)


def backfill_candidates():
    """스토리가 아직 없는 게시된 게시물 [(폴더, post, state)], 게시 순(오래된 것부터). 운영자가 지운 것(status)은 뺀다."""
    out = []
    if not DONE.exists():
        return out
    for f in sorted(p for p in DONE.iterdir() if p.is_dir()):
        post, state = read_json(f / "post.json"), read_json(f / "published.json")
        if not post or not state:
            continue
        why = ("status: " + str(state["status"])[:40] if state.get("status")
               else "story_id 있음" if state.get("story_id")
               else "story_skipped" if state.get("story_skipped")
               else "post.json story: false" if post.get("story") is False
               else "media_id 없음" if not state.get("media_id") else "")
        if why:
            print(f"건너뜀 ({why}): {f.name}")
            continue
        out.append((f, post, state))
    out.sort(key=lambda t: parse_ts(t[2].get("published_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return out


def live_media_ids(ig_id):
    """지금 인스타에 남아 있는 우리 게시물 id 집합 (최근 200개까지). 조회 실패면 PublishError."""
    if DRY:
        fake = os.environ.get("DEDUP_FAKE_MEDIA")  # 시험용: 가짜 게시물 목록(json 파일)
        if fake:
            return {m["id"] for m in json.loads(Path(fake).read_text(encoding="utf-8"))}
        if not TOKEN:
            return None
    # 읽기만 하는 조회라 DRY_RUN에서도 실제로 묻는다 (시험 실행에서 건너뛸 게시물을 미리 보려고)
    ids, after = set(), None
    for _ in range(4):
        params = {"fields": "id,permalink", "limit": "50", **({"after": after} if after else {})}
        r = requests.get(f"{API}/{ig_id}/media", params=params, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60)
        j = r.json()
        if r.status_code >= 400 or "error" in j:
            raise PublishError(f"게시물 목록 조회 실패 ({r.status_code}): {(j.get('error') or {}).get('message', '')}")
        ids |= {m["id"] for m in j.get("data") or []}
        after = ((j.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (j.get("paging") or {}).get("next"):
            break
    return ids


def backfill_stories():
    """지금 올라가 있는 게시물 중 스토리가 없는 것을 오래된 것부터 스토리로 (STORY_GAP_MIN분 간격, 기본 2).
    STORY_LIMIT: 앞에서부터 이 개수만 (0이면 전부)."""
    if not STORIES_ON:
        print("스토리 꺼짐 (config.json stories_enabled false). 아무것도 올리지 않음.")
        return
    if not TOKEN and not DRY:
        print("IG_ACCESS_TOKEN이 없음.")
        sys.exit(1)
    gap = float(os.environ.get("STORY_GAP_MIN") or 2)
    limit = int(os.environ.get("STORY_LIMIT") or 0)
    cands = backfill_candidates()
    ig_id = account_id()
    live = live_media_ids(ig_id)
    if live is not None:
        for f, _, st in cands:
            if st["media_id"] not in live:
                print(f"건너뜀 (인스타에 없음, 지운 게시물): {f.name}")
        cands = [(f, p, st) for f, p, st in cands if st["media_id"] in live]
    if limit:
        cands = cands[:limit]
    print(f"스토리로 올릴 게시물 {len(cands)}개 (간격 {gap:g}분):")
    files = story_files([(f, p) for f, p, _ in cands])
    for f, p, st in cands:
        sm = _story_cache.get(f.name)
        print(f"  {st.get('published_at', '')[:16]}  {f.name}  → {sm[0] if sm else '(미디어 없음)'}")
    if not cands:
        return
    try:
        # 최근 게시물 미디어·스레드를 기다리는 이미지는 그대로 두고 스토리 미디어를 더한다
        now = datetime.now(timezone.utc)
        keep = wanted(recent_published(now), [(f, p) for f, p, _, _ in threads_pending(now)])
        stage({**keep, **files})
    except (PublishError, subprocess.CalledProcessError) as e:
        print(f"미디어 올리기 실패: {e}")
        sys.exit(1)
    ok = fail = 0
    for i, (f, p, st) in enumerate(cands):
        if i and not DRY:
            time.sleep(gap * 60)
        print(f"스토리: {f.name}")
        if add_story(ig_id, f, p, st):
            ok += 1
        else:
            fail += 1
        if not DRY:
            save_state(f, st)
    print(f"스토리 {ok}개 올림, 실패 {fail}개")
    if not DRY:
        keep_threads_media(datetime.now(timezone.utc))  # 스토리용 미디어는 내린다 (워크플로 마지막 단계가 커밋)
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    if "--stories-backfill" in sys.argv[1:]:
        backfill_stories()
    else:
        main()
