"""게시 칸 자동 배정 (config.json `slots`).

릴스·카드뉴스마다 하루 게시 칸(시각)이 정해져 있다. 새 게시물은 이미 예약된 것
(posts/queue, posts/published, 아직 병합 안 된 검토 브랜치 origin/post/*)을 피해 가장 가까운 빈 칸에 넣는다.
오늘 칸이 차면 내일, 모레로 넘어간다.

사용법:
    py -3.12 agent/slots.py status [--days 3]                 날짜별 칸 상황
    py -3.12 agent/slots.py next reel --count 3                빈 칸 3개 (게시 시각 ISO, 한 줄에 하나)
    py -3.12 agent/slots.py next carousel --count 2 --date 2026-11-16 --max 4
                                                               그날만 상한을 4개로 (칸 사이 최소 1시간 반)
    py -3.12 agent/slots.py next reel --asap                   바로 올리기: 지금 시각 (렌더링이 끝나면 다음 15분 확인 때 게시)
    py -3.12 agent/slots.py need [--days 2]                    매일 작업이 미리 만들 개수: 오늘부터 days일 뒤까지 날짜별
                                                               (daily_target - 이미 예약된 수, 오늘은 남은 빈 칸까지만)
                                                               출력 예: 2026-11-17 carousel=0 reel=2
                                                                        2026-11-18 carousel=1 reel=5
                                                                        carousel=1 reel=7        (마지막 줄 = 합계)
    py -3.12 agent/slots.py need --date 2026-11-16             그날 하루만 (예전 방식, 한 줄: carousel=0 reel=1)
    py -3.12 agent/slots.py bump [--near 2026-11-16T13:20+09:00] [--window 90] [--dry-run]
                                                               속보 정리: posts/queue에서 속보(breaking) 앞뒤 window분 안의
                                                               따라 하기·질문(format howto/ask)만 다음 빈 칸으로 옮긴다
    py -3.12 agent/slots.py swap <폴더A> <폴더B> [--dry-run]    두 게시물의 publish_at을 맞바꾼다 (기대 순위 칸 배치)
    py -3.12 agent/slots.py move <폴더> 19:43 [--dry-run]      게시 시각만 옮긴다 (HH:MM = 그 게시물 날짜의 그 시각, 또는 ISO).
                                                               같은 종류 예약이 이미 있는 시각이면 거절 (swap을 쓴다)
    폴더는 posts/queue 안의 폴더 이름이나 경로. swap·move·bump는 렌더링이 최신이었으면 .render_hash를 새 post.json
    기준으로 다시 써서 다시 렌더링하지 않는다 (게시 시각은 렌더링 결과와 상관없음). 승인 표시(approved)는 그대로.

기대 순위 칸 (config.json `slots.prime_slots`, 운영자 결정 2026-11-17): 하루 릴스 중 가장 잘 나올 것 같은 두 개를
18:13·19:43에 둔다 (data/trends.md 18~21시 1.19x). 만든 뒤 순위가 바뀌면 swap으로 맞바꾼다. status에서 ★ 표시.

속보(post.json `"breaking": true`, LOCAL.md 6장)는 --asap으로 지금 시각을 받을 뿐 기존 예약을 밀지 않는다.
속보는 하루 칸 수(상한·daily_target)에 세지 않는다. 시의성 있는 게시물(소식·인용 등)은 원래 시각 그대로 두고,
속보와 가까워도 같은 종류 90분 간격 규칙의 예외로 둔다. 옮기는 것은 bump가 고르는 howto/ask뿐.

검사 대상 브랜치를 최신으로: git fetch origin "+refs/heads/post/*:refs/remotes/origin/post/*" (need/next가 자동으로 함)
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
KST = timezone(timedelta(hours=9))
KINDS = ("carousel", "reel")

S = CONFIG.get("slots", {})
GAP = timedelta(minutes=int(S.get("min_gap_minutes", 90)))      # 상한을 넘겨 칸을 더 만들 때 같은 종류끼리 최소 간격
LEAD = timedelta(minutes=int(S.get("lead_minutes", 40)))        # 지금부터 이만큼 뒤의 칸부터 (렌더링·검토 시간)
DAY_START, DAY_END = time(10, 0), time(23, 0)                    # 상한을 넘겨 칸을 더 만들 때 쓸 수 있는 시간대
PRIME = set(S.get("prime_slots", []))                            # 기대 순위 1·2위 릴스를 두는 칸 (운영자 결정 2026-11-17)


def _times(kind):
    v = S.get(kind) or []
    if isinstance(v, str):  # 예전 형식 {"carousel": "10:13"}
        v = [v]
    return [time(*map(int, x.split(":"))) for x in v]


def kind_of(post):
    return "carousel" if post.get("type") == "carousel" else "reel"


def _git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


def fetch():
    _git("fetch", "-q", "origin", "+refs/heads/post/*:refs/remotes/origin/post/*")


def taken():
    """예약·게시된 것 [(종류, 게시 시각, 이름, 정보)]. 정보 = {format, breaking, path(작업 폴더 posts/queue 것만)}.
    폴더 이름이 같으면 작업 폴더 것을 쓴다."""
    seen, out = set(), []

    def add(name, post, path=None):
        try:
            at = datetime.fromisoformat(post["publish_at"]).astimezone(KST)
        except (KeyError, ValueError):
            return
        seen.add(name)
        out.append((kind_of(post), at, name, {"format": post.get("format"), "breaking": bool(post.get("breaking")),
                                              "path": path}))

    for d in ("posts/queue", "posts/published"):
        for pj in (ROOT / d).glob("*/post.json"):
            st = pj.parent / "published.json"
            if d == "posts/published" and st.exists() and '"status"' in st.read_text(encoding="utf-8"):
                seen.add(pj.parent.name)  # 옛 검토 브랜치에 남은 같은 게시물도 세지 않게
                continue  # 운영자가 지운 게시물(다시 안 올림 등)은 칸을 차지하지 않는다
            try:
                add(pj.parent.name, json.loads(pj.read_text(encoding="utf-8")), pj if d == "posts/queue" else None)
            except (OSError, json.JSONDecodeError):
                pass
    cur = _git("branch", "--show-current").strip()
    for ref in _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin/post/").split():
        if cur and ref == f"refs/remotes/origin/{cur}":
            continue  # 지금 작업 중인 브랜치는 작업 폴더가 최신
        for path in _git("ls-tree", "-r", "--name-only", ref, "posts/queue").splitlines():
            if path.endswith("/post.json") and path.split("/")[-2] not in seen:
                try:
                    add(path.split("/")[-2], json.loads(_git("show", f"{ref}:{path}")))
                except json.JSONDecodeError:
                    pass
    return out


def on_day(items, kind, d, breaking=True):
    """그날 그 종류 예약 시각. breaking=False면 속보는 빼고 센다 (속보는 하루 칸 수에 들어가지 않는다)."""
    return sorted(at for k, at, _, info in items if k == kind and at.date() == d and (breaking or not info.get("breaking")))


def _free_base(kind, d, used, after):
    """그날 기본 칸 중 빈 것 (after 이후)."""
    out = []
    for t in _times(kind):
        at = datetime.combine(d, t, KST)
        if at >= after and all(abs((u - at).total_seconds()) >= 60 for u in used):
            out.append(at)
    return out


def _free_extra(d, used, after):
    """상한을 넘길 때 더 만드는 칸: 같은 종류 예약과 1시간 반 이상 떨어진 15분 단위 시각."""
    at = datetime.combine(d, DAY_START, KST)
    end = datetime.combine(d, DAY_END, KST)
    while at <= end:
        if at >= after and all(abs(at - u) >= GAP for u in used):
            return at
        at += timedelta(minutes=15)
    return None


def next_slots(kind, count=1, now=None, day=None, day_max=None, items=None):
    """빈 칸 count개. day를 주면 그날부터, day_max를 주면 그날만 상한을 day_max개로."""
    now = (now or datetime.now(KST)).astimezone(KST)
    items = list(items if items is not None else taken())
    after = now + LEAD
    if day_max and not day:
        day = after.date()
    d = day or after.date()
    out = []
    for _ in range(60):  # 최대 60일 앞까지
        while len(out) < count:
            used = on_day(items, kind, d)
            limit = day_max if (day_max and d == day) else len(_times(kind))
            if len(on_day(items, kind, d, breaking=False)) >= limit:
                break
            base = _free_base(kind, d, used, after)
            at = base[0] if base else (_free_extra(d, used, after) if limit > len(_times(kind)) else None)
            if not at:
                break
            out.append(at)
            items.append((kind, at, "(새 게시물)", {}))
        if len(out) >= count:
            break
        d += timedelta(days=1)
    return out


def need(d=None, items=None, now=None):
    """매일 작업이 더 만들 개수: daily_target - 그날 이미 예약된 수 (0 미만이면 0).
    d를 안 주면 오늘. 단 그 종류의 오늘 칸이 이미 다 지났으면 내일을 센다 (밤에 돌아도 같은 걸 또 만들지 않게)."""
    now = (now or datetime.now(KST)).astimezone(KST)
    items = items if items is not None else taken()
    target = S.get("daily_target", {"carousel": 1, "reel": 1})
    out = {}
    for k in KINDS:
        day = d
        if day is None:
            day = now.date()
            if not any(datetime.combine(day, t, KST) >= now + LEAD for t in _times(k)):
                day += timedelta(days=1)
        out[k] = max(0, int(target.get(k, 0)) - len(on_day(items, k, day, breaking=False)))
    return out


def need_days(days=2, items=None, now=None):
    """오늘부터 days일 뒤까지 날짜별로 더 만들 개수 [(날짜, {종류: 개수})] (승인·검토 시간을 벌려고 미리 만든다).
    날마다 daily_target - 그날 예약된 수(속보 빼고). 오늘은 지금+lead_minutes 뒤의 빈 기본 칸 수까지만."""
    now = (now or datetime.now(KST)).astimezone(KST)
    items = items if items is not None else taken()
    target = S.get("daily_target", {"carousel": 1, "reel": 1})
    out = []
    for i in range(days + 1):
        d = now.date() + timedelta(days=i)
        row = {}
        for k in KINDS:
            n = max(0, int(target.get(k, 0)) - len(on_day(items, k, d, breaking=False)))
            if i == 0:
                n = min(n, len(_free_base(k, d, on_day(items, k, d), now + LEAD)))
            row[k] = n
        out.append((d, row))
    return out


def status(days=3, items=None):
    items = items if items is not None else taken()
    today = datetime.now(KST).date()
    lines = []
    for i in range(days):
        d = today + timedelta(days=i)
        lines.append(f"{d} ({'월화수목금토일'[d.weekday()]})")
        for k in KINDS:
            used = {at.strftime("%H:%M"): n + (" (속보)" if info.get("breaking") else "")
                    for kk, at, n, info in items if kk == k and at.date() == d}
            cells = []
            for t in _times(k):
                hm = t.strftime("%H:%M")
                star = "★" if k == "reel" and hm in PRIME else ""
                cells.append(f"{star}{hm} {'■ ' + used.pop(hm) if hm in used else '□'}")
            cells += [f"{hm} ■ {n} (추가 칸)" for hm, n in sorted(used.items())]
            lines.append(f"  {k}: " + " | ".join(cells))
    return "\n".join(lines)


_PUBLISH_AT = re.compile(r'(?m)^([ \t]*"publish_at"[ \t]*:[ \t]*)"[^"\n]*"')


def set_publish_at(pj, new):
    """post.json의 publish_at만 바꾼다. 다른 줄은 바이트 그대로 두고(줄 끝은 LF, Actions 리눅스와 같게)
    렌더링이 최신이었으면 .render_hash를 새 post.json 기준으로 다시 쓴다. 반환: 렌더링이 최신이었는지.
    지문 계산식(build.input_hash)은 그대로라 대기열·열린 브랜치의 기존 .render_hash가 모두 유효하다."""
    pj = Path(pj)
    sys.path.insert(0, str(ROOT / "agent"))
    from build import input_hash
    mark = pj.parent / ".render_hash"
    fresh = mark.exists() and mark.read_text().strip() == input_hash(pj.parent)
    text = pj.read_bytes().decode("utf-8").replace("\r\n", "\n")
    new_text, n = _PUBLISH_AT.subn(lambda m: f'{m.group(1)}"{new.isoformat()}"', text, count=1)
    if n != 1 or json.loads(new_text).get("publish_at") != new.isoformat():
        post = json.loads(text)
        post["publish_at"] = new.isoformat()
        new_text = json.dumps(post, ensure_ascii=False, indent=2) + "\n"
    pj.write_bytes(new_text.encode("utf-8"))
    if fresh:
        mark.write_bytes((input_hash(pj.parent) + "\n").encode())
    return fresh


def _folder(arg):
    p = Path(arg)
    for cand in (p, ROOT / "posts" / "queue" / arg):
        if (cand / "post.json").exists():
            return cand.resolve()
    sys.exit(f"게시물 폴더를 못 찾음: {arg} (posts/queue 안 폴더 이름이나 경로)")


def _at(pj):
    return datetime.fromisoformat(json.loads(Path(pj).read_text(encoding="utf-8"))["publish_at"]).astimezone(KST)


def swap(a, b, dry_run=False):
    """두 게시물의 publish_at을 맞바꾼다. 반환 [(폴더 이름, 이전, 새 시각, 렌더링 최신이었는지(시험이면 None))]."""
    pa, pb = Path(a) / "post.json", Path(b) / "post.json"
    ta, tb = _at(pa), _at(pb)
    if dry_run:
        return [(Path(a).name, ta, tb, None), (Path(b).name, tb, ta, None)]
    return [(Path(a).name, ta, tb, set_publish_at(pa, tb)), (Path(b).name, tb, ta, set_publish_at(pb, ta))]


def move(folder, when, dry_run=False, items=None):
    """게시 시각을 when(HH:MM이면 그 게시물 날짜의 그 시각, 아니면 ISO)으로. 같은 종류 예약이 1분 안에 있으면 거절."""
    pj = Path(folder) / "post.json"
    old = _at(pj)
    if re.fullmatch(r"\d{1,2}:\d{2}", when):
        new = datetime.combine(old.date(), time(*map(int, when.split(":"))), KST)
    else:
        new = datetime.fromisoformat(when).astimezone(KST)
    kind = kind_of(json.loads(pj.read_text(encoding="utf-8")))
    items = items if items is not None else taken()
    clash = [n for k, at, n, _ in items if k == kind and n != Path(folder).name and abs((at - new).total_seconds()) < 60]
    if clash:
        raise ValueError(f"{new:%m/%d %H:%M}에 이미 {', '.join(clash)} 예약: swap으로 맞바꾸세요")
    return Path(folder).name, old, new, (None if dry_run else set_publish_at(pj, new))


TIMELESS = ("howto", "ask")   # 시의성 없는 형식: 속보 때문에 칸을 정리할 때 이것만 뒤로 민다


def bump(near=None, window=90, dry_run=False, now=None, items=None):
    """속보 앞뒤 window분 안에 잡힌 따라 하기·질문(format howto/ask)을 다음 빈 칸(속보와 window분 넘게 떨어진)으로 옮긴다.
    near를 안 주면 속보(breaking) 게시물들의 시각. 작업 폴더 posts/queue의 post.json만 고친다
    (열린 post/* 브랜치에 있는 것은 그 브랜치에서 돌린다). 소식·인용처럼 시의성 있는 것은 옮기지 않는다.
    렌더링 표시(.render_hash)가 최신이었으면 새 post.json 기준으로 다시 쓴다 (게시 시각만 바뀌어 다시 렌더링할 필요 없음)."""
    now = (now or datetime.now(KST)).astimezone(KST)
    items = list(items if items is not None else taken())
    centers = [near] if near else [at for _, at, _, info in items if info.get("breaking") and at >= now - timedelta(hours=3)]
    win = timedelta(minutes=window)
    moved = []
    for kind, at, name, info in sorted(items, key=lambda x: x[1]):
        if info.get("format") not in TIMELESS or info.get("breaking") or not info.get("path") or at < now:
            continue
        if not any(abs(at - c) < win for c in centers):
            continue
        probe = [x for x in items if x[2] != name]
        new = None
        for _ in range(20):
            got = next_slots(kind, 1, now=now, items=probe)
            if not got:
                break
            if all(abs(got[0] - c) >= win for c in centers):
                new = got[0]
                break
            probe.append((kind, got[0], "(속보 주변)", {"breaking": True}))  # 그 칸은 건너뛰되 하루 개수에는 안 셈
        if not new:
            continue
        moved.append((name, at, new))
        items = [x for x in items if x[2] != name] + [(kind, new, name, info)]
        if dry_run:
            continue
        set_publish_at(info["path"], new)
    return moved


def main(argv=None):
    ap = argparse.ArgumentParser(description="게시 칸 자동 배정")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("status"); a.add_argument("--days", type=int, default=3)
    b = sub.add_parser("next"); b.add_argument("kind", choices=KINDS)
    b.add_argument("--count", type=int, default=1); b.add_argument("--date"); b.add_argument("--max", type=int)
    b.add_argument("--asap", action="store_true")
    c = sub.add_parser("need"); c.add_argument("--date"); c.add_argument("--days", type=int, default=2)
    e = sub.add_parser("bump", help="속보 앞뒤의 따라 하기·질문(howto/ask)만 다음 빈 칸으로")
    e.add_argument("--near", help="속보 게시 시각 (ISO). 없으면 breaking 게시물들의 시각")
    e.add_argument("--window", type=int, default=90, help="속보 앞뒤 몇 분 (기본 90)")
    e.add_argument("--dry-run", action="store_true")
    f = sub.add_parser("swap", help="두 게시물의 publish_at 맞바꾸기 (.render_hash도 같이)")
    f.add_argument("a"); f.add_argument("b"); f.add_argument("--dry-run", action="store_true")
    g = sub.add_parser("move", help="게시 시각만 옮기기 (HH:MM 또는 ISO, .render_hash도 같이)")
    g.add_argument("folder"); g.add_argument("when"); g.add_argument("--dry-run", action="store_true")
    for p in (a, b, c, e, f, g):
        p.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd in ("swap", "move"):
        if args.cmd == "swap":
            rows = swap(_folder(args.a), _folder(args.b), args.dry_run)
        else:
            if not args.no_fetch:
                fetch()
            try:
                rows = [move(_folder(args.folder), args.when, args.dry_run)]
            except ValueError as err:
                sys.exit(str(err))
        for name, old, new, fresh in rows:
            note = "" if fresh is None else (" (.render_hash 갱신, 다시 렌더링 안 함)" if fresh
                                             else " (렌더링이 최신 아님: render.yml이 렌더링한 뒤 게시)")
            print(f"{'(시험) ' if args.dry_run else ''}{name}: {old:%m/%d %H:%M} → {new:%m/%d %H:%M}{note}")
        return
    if not args.no_fetch:
        fetch()
    if args.cmd == "status":
        print(status(args.days))
    elif args.cmd == "bump":
        near = datetime.fromisoformat(args.near).astimezone(KST) if args.near else None
        moved = bump(near, args.window, args.dry_run)
        for name, old, new in moved:
            print(f"{'(시험) ' if args.dry_run else ''}옮김: {name} {old:%m/%d %H:%M} → {new:%m/%d %H:%M}")
        if not moved:
            print("옮길 따라 하기·질문 없음")
    elif args.cmd == "need":
        if args.date:
            n = need(date.fromisoformat(args.date))
            print(" ".join(f"{k}={v}" for k, v in n.items()))
            return
        rows = need_days(args.days)
        for d, n in rows:
            print(f"{d} " + " ".join(f"{k}={v}" for k, v in n.items()))
        print(" ".join(f"{k}={sum(n[k] for _, n in rows)}" for k in KINDS))
    else:
        if args.asap:
            for _ in range(args.count):
                print(datetime.now(KST).replace(second=0, microsecond=0).isoformat())
            return
        day = date.fromisoformat(args.date) if args.date else None
        got = next_slots(args.kind, args.count, day=day, day_max=args.max)
        for at in got:
            print(at.isoformat())
        if len(got) < args.count:
            print(f"빈 칸을 {len(got)}개만 찾음 (60일 안)", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
