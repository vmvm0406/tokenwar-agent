"""같은 내용이 겹치지 않게 막는 검사.

비교 대상: posts/queue, posts/published, 그리고 아직 병합 안 된 검토 브랜치(origin/post/*)의 게시물.
(검토 브랜치를 보려면 먼저 `git fetch origin "+refs/heads/post/*:refs/remotes/origin/post/*"`)

막는 것 (오류):
- 같은 원본 영상(유튜브 ID 등) 90일 안에 다시 쓰기
- 같은 출처 링크를 30일 안에 다시 쓰기 (같은 기사·발표로 또 만들기)
- 주제(topic)가 절반 이상 같은 게시물이 14일 안에 있음 (카드뉴스와 릴스 사이도 포함)
- 같은 인물 영상을 7일 안에 세 번째로 쓰기

알리는 것 (경고):
- 가벼운 화제(format buzz)가 같은 주(월~일, 게시 시각 기준)에 3개째 (주 1~2개, 카드·릴스 합쳐서. STYLE_GUIDE 3-2)

post.json에 "topic": ["젠슨 황", "AI 안전", "엔비디아"] 처럼 핵심 대상 2~4개를 적는다. 사람·회사·제품·사건 이름 위주.
사용법: python agent/dupes.py <게시물 폴더>   (render.py가 렌더링 전에 자동으로 부른다)
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent


def _git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


def all_posts():
    """(이름, post) 목록. 폴더 이름이 같으면 한 번만."""
    seen, out = set(), []
    for d in ["posts/queue", "posts/published"]:
        for pj in (ROOT / d).glob("*/post.json"):
            try:
                out.append((pj.parent.name, json.loads(pj.read_text(encoding="utf-8"))))
                seen.add(pj.parent.name)
            except (OSError, json.JSONDecodeError):
                pass
    cur = _git("branch", "--show-current").strip()
    for ref in _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin/post/").split():
        if cur and ref == f"refs/remotes/origin/{cur}":
            continue  # 지금 고치고 있는 검토 브랜치의 예전 버전(origin)은 비교하지 않는다. 작업 폴더가 최신
        for path in _git("ls-tree", "-r", "--name-only", ref, "posts/queue").splitlines():
            if not path.endswith("/post.json"):
                continue
            name = path.split("/")[-2]
            if name in seen:
                continue
            try:
                out.append((name, json.loads(_git("show", f"{ref}:{path}"))))
                seen.add(name)
            except json.JSONDecodeError:
                pass
    return out


def post_date(post):
    for k in ("publish_at", "date"):
        v = post.get(k)
        if v:
            try:
                return datetime.fromisoformat(str(v)).date()
            except ValueError:
                pass
    return None


def video_id(url):
    if not url:
        return None
    u = urlparse(url)
    if "youtu.be" in u.netloc:
        return "yt:" + u.path.strip("/")
    if "youtube.com" in u.netloc:
        v = parse_qs(u.query).get("v")
        if v:
            return "yt:" + v[0]
        m = re.search(r"/(shorts|live|embed)/([\w-]+)", u.path)
        if m:
            return "yt:" + m.group(2)
    return (u.netloc + u.path).rstrip("/").lower()


def links(post):
    out = {(s.get("url") or "").split("#")[0].rstrip("/") for s in post.get("sources", []) if s.get("url")}
    return {x for x in out if x}


def topics(post):
    return {re.sub(r"\s+", "", t).lower() for t in post.get("topic", []) if t}


def person(post):
    p = (post.get("thumb") or {}).get("person") or {}
    return (p.get("name") or "").strip().lower() or None


def check(post, self_name=None, today=None):
    errors, warnings = [], []
    if not post.get("topic"):
        warnings.append('topic(핵심 대상 2~4개)이 없어 주제 겹침을 검사하지 못함: "topic": ["인물", "회사", "사건"]')
    d0 = post_date(post) or today or date.today()
    vid = video_id(post.get("source_url"))
    mine_links, mine_topics, mine_person = links(post), topics(post), person(post)
    person_uses = 0
    buzz_week = []
    wk0 = d0.isocalendar()[:2]
    for name, other in all_posts():
        if name == self_name or other.get("id") == post.get("id"):
            continue
        d1 = post_date(other)
        if not d1:
            continue
        if post.get("format") == "buzz" and other.get("format") == "buzz" and d1.isocalendar()[:2] == wk0:
            buzz_week.append(name)
        gap = abs((d0 - d1).days)
        if vid and gap <= 90 and video_id(other.get("source_url")) == vid:
            errors.append(f"같은 원본 영상을 {gap}일 전에 이미 씀: {name}")
        same = mine_links & links(other)
        if same and gap <= 30:
            errors.append(f"같은 출처를 {gap}일 안에 다시 씀 ({name}): {sorted(same)[0]}")
        ot = topics(other)
        if mine_topics and ot and gap <= 14:
            overlap = len(mine_topics & ot) / min(len(mine_topics), len(ot))
            if overlap >= 0.5:
                errors.append(f"주제가 겹침 ({name}, {gap}일 차이): {sorted(mine_topics & ot)} → 다른 소식을 고르거나 확실히 새로운 각도로")
            elif mine_topics & ot:
                warnings.append(f"주제 일부 겹침 ({name}): {sorted(mine_topics & ot)}")
        if mine_person and gap <= 7 and person(other) == mine_person:
            person_uses += 1
    if len(buzz_week) >= 2:
        warnings.append(f"가벼운 화제(buzz)가 이번 주(월~일)에 이미 {len(buzz_week)}개: {sorted(buzz_week)} → 주 1~2개까지, 다른 형식으로 (STYLE_GUIDE 3-2)")
    if person_uses >= 2:
        errors.append(f"같은 인물({mine_person}) 영상을 7일 안에 이미 {person_uses}번 씀 (주 2회까지)")
    return errors, warnings


if __name__ == "__main__":
    folder = Path(sys.argv[1]).resolve()
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    e, w = check(post, folder.name)
    for x in w:
        print("경고:", x)
    for x in e:
        print("오류:", x)
    sys.exit(1 if e else 0)
