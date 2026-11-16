"""게시 승인 관문 (운영자 결정 2026-11-16: 당분간 운영자가 승인한 게시물만 올라간다).

config.json `require_approval`이 true면 publish.py는 post.json에 `"approved": true`가 있는 게시물만 올린다.
`approval_exempt_before`(ISO)보다 publish_at이 이른 게시물은 관문에서 뺀다 (도입 전 예약분).
흐름: 검토 세션 → 운영자 OK → 지휘 세션이 이 스크립트로 approved를 넣고 → main에 push. 속보도 같다.

사용법:
    py -3.12 agent/approve.py <게시물 폴더> [--edits N]
        post.json 맨 위에 "approved": true, "approved_at"(지금, 한국 시간)을 넣고,
        렌더링이 최신이었으면 .render_hash를 새 post.json 기준으로 다시 쓰고,
        data/approvals.csv에 한 줄(date, post_id, edits_before_approval, approved_at)을 남긴다.
        --edits = 승인 전에 운영자 지적으로 고친 횟수 (자동 전환 판단용, LOCAL.md 3장)
    py -3.12 agent/approve.py --pending [--hours 3] [--ref origin/main] [--branches]
        승인 안 된 대기 게시물 중 게시 시각이 N시간 안에 다가오거나 이미 지난 것 (한 줄에 하나, 없으면 출력 없음).
        --ref: 작업 폴더 대신 그 git ref의 posts/queue를 본다. --branches: 열린 검토 브랜치(origin/post/*)도 본다.

approved 줄은 렌더링 지문(build.input_hash)에서 빠지므로, 승인만 넣었을 때 다시 렌더링하지 않는다.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue"
APPROVALS = ROOT / "data" / "approvals.csv"
KST = timezone(timedelta(hours=9))
FIELDS = ["date", "post_id", "edits_before_approval", "approved_at"]


def config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def gated(post, cfg=None):
    """이 게시물이 승인을 받아야 올라가는지 (승인 관문 대상인지)."""
    cfg = cfg if cfg is not None else config()
    if not cfg.get("require_approval"):
        return False
    ex = cfg.get("approval_exempt_before")
    if ex and post.get("publish_at"):
        try:
            if datetime.fromisoformat(post["publish_at"]) < datetime.fromisoformat(ex):
                return False
        except ValueError:
            pass
    return True


def may_publish(post, cfg=None):
    """승인 관문을 통과하는지: 관문이 꺼져 있거나, 예외 날짜 전이거나, approved가 true."""
    return post.get("approved") is True or not gated(post, cfg)


_LINE = re.compile(r'(?m)^[ \t]*"approved(?:_at)?"[ \t]*:[^\n]*\n')


def approve(folder, edits=0, now=None):
    folder = Path(folder).resolve()
    pj = folder / "post.json"
    sys.path.insert(0, str(ROOT / "agent"))
    from build import input_hash
    mark = folder / ".render_hash"
    fresh = mark.exists() and mark.read_text().strip() == input_hash(folder)
    now = (now or datetime.now(KST)).astimezone(KST).replace(microsecond=0)
    text = pj.read_bytes().decode("utf-8").replace("\r\n", "\n")
    text = _LINE.sub("", text)  # 이미 있던 승인 줄은 지우고 새로
    add = f'  "approved": true,\n  "approved_at": "{now.isoformat()}",\n'
    if text.startswith("{\n") and json.loads(text):
        # "{" 바로 다음 줄에 넣는다: 지문에서 이 줄을 빼면 승인 전 바이트와 같아진다 (build.post_bytes)
        new = "{\n" + add + text[2:]
    else:
        post = json.loads(text)
        post = {"approved": True, "approved_at": now.isoformat(), **{k: v for k, v in post.items()
                                                                     if k not in ("approved", "approved_at")}}
        new = json.dumps(post, ensure_ascii=False, indent=2) + "\n"
    post = json.loads(new)
    pj.write_bytes(new.encode("utf-8"))  # LF 그대로 (Actions 리눅스와 같은 지문)
    if fresh:
        mark.write_bytes((input_hash(folder) + "\n").encode())
    log(folder.name, edits, now)  # post_id = 게시물 폴더 이름 (id 필드와 다른 게시물이 있어서)
    return post, fresh


def log(post_id, edits, at):
    APPROVALS.parent.mkdir(parents=True, exist_ok=True)
    new = not APPROVALS.exists()
    with open(APPROVALS, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        if new:
            w.writerow(FIELDS)
        w.writerow([at.date().isoformat(), post_id, int(edits), at.isoformat()])


def _git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


def queued(ref=None, branches=False):
    """대기 게시물 [(폴더 이름, post, 어디)]. 같은 폴더가 여러 곳에 있으면 앞의 것(main/작업 폴더)만.
    이미 게시된 폴더(posts/published)는 옛 검토 브랜치에 남아 있어도 뺀다."""
    out = []
    if ref:
        seen = {p.split("/")[2] for p in _git("ls-tree", "-r", "--name-only", ref, "posts/published").splitlines()
                if p.count("/") >= 3}
    else:
        seen = {p.name for p in (ROOT / "posts" / "published").glob("*") if p.is_dir()}

    def add(name, post, where):
        if name not in seen:
            seen.add(name)
            out.append((name, post, where))

    if ref:
        for path in _git("ls-tree", "-r", "--name-only", ref, "posts/queue").splitlines():
            if path.endswith("/post.json"):
                try:
                    add(path.split("/")[-2], json.loads(_git("show", f"{ref}:{path}")), ref)
                except json.JSONDecodeError:
                    pass
    else:
        for pj in sorted(QUEUE.glob("*/post.json")):
            try:
                add(pj.parent.name, json.loads(pj.read_text(encoding="utf-8")), "posts/queue")
            except (OSError, json.JSONDecodeError):
                pass
    if branches:
        for r in _git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/post/").split():
            for path in _git("ls-tree", "-r", "--name-only", r, "posts/queue").splitlines():
                if path.endswith("/post.json") and path.split("/")[-2] not in seen:
                    try:
                        add(path.split("/")[-2], json.loads(_git("show", f"{r}:{path}")), r)
                    except json.JSONDecodeError:
                        pass
    return out


def pending(hours=3.0, ref=None, branches=False, now=None, cfg=None):
    """승인 안 된(관문 대상) 게시물 중 게시 시각이 hours시간 안이거나 지난 것 [(시각, 폴더, 어디)]."""
    cfg = cfg if cfg is not None else config()
    now = (now or datetime.now(KST)).astimezone(KST)
    out = []
    for name, post, where in queued(ref, branches):
        if may_publish(post, cfg):
            continue
        try:
            at = datetime.fromisoformat(post["publish_at"]).astimezone(KST)
        except (KeyError, ValueError):
            continue
        if at <= now + timedelta(hours=hours):
            out.append((at, name, where))
    return sorted(out), now


def main(argv=None):
    ap = argparse.ArgumentParser(description="게시 승인 관문")
    ap.add_argument("folder", nargs="?", help="승인할 게시물 폴더")
    ap.add_argument("--edits", type=int, default=0, help="승인 전 수정 횟수 (data/approvals.csv)")
    ap.add_argument("--pending", action="store_true", help="게시 시각이 다가오는데 승인 안 된 게시물")
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--ref", help="작업 폴더 대신 이 git ref의 posts/queue (예: origin/main)")
    ap.add_argument("--branches", action="store_true", help="열린 검토 브랜치 origin/post/*도")
    a = ap.parse_args(argv)
    if a.pending:
        items, now = pending(a.hours, a.ref, a.branches)
        for at, name, where in items:
            left = int((at - now).total_seconds() // 60)
            when = f"{left}분 남음" if left >= 0 else f"{-left}분 지남"
            print(f"{at:%m/%d %H:%M} {name} ({where}, {when})")
        return
    if not a.folder:
        ap.error("게시물 폴더나 --pending을 주세요")
    folder = Path(a.folder)
    if not (folder / "post.json").exists():
        ap.error(f"post.json이 없음: {folder}")
    post, fresh = approve(folder, a.edits)
    print(f"승인: {folder.name} (publish_at {post.get('publish_at')}, approved_at {post['approved_at']}, 수정 {a.edits}회)")
    print("  .render_hash 갱신 (다시 렌더링 안 함)" if fresh else
          "  렌더링이 아직 최신이 아님: .render_hash는 그대로 (Actions render.yml이 렌더링한 뒤 게시)")
    print(f"  기록: {APPROVALS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
