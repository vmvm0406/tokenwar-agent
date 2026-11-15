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
    py -3.12 agent/slots.py need [--date 2026-11-16]           매일 작업이 그날 더 만들 개수 (daily_target - 이미 예약된 수)
                                                               출력 예: carousel=0 reel=1

검사 대상 브랜치를 최신으로: git fetch origin "+refs/heads/post/*:refs/remotes/origin/post/*" (need/next가 자동으로 함)
"""
import argparse
import json
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
    """예약·게시된 것 [(종류, 게시 시각, 이름)]. 폴더 이름이 같으면 작업 폴더 것을 쓴다."""
    seen, out = set(), []

    def add(name, post):
        try:
            at = datetime.fromisoformat(post["publish_at"]).astimezone(KST)
        except (KeyError, ValueError):
            return
        seen.add(name)
        out.append((kind_of(post), at, name))

    for d in ("posts/queue", "posts/published"):
        for pj in (ROOT / d).glob("*/post.json"):
            try:
                add(pj.parent.name, json.loads(pj.read_text(encoding="utf-8")))
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


def on_day(items, kind, d):
    return sorted(at for k, at, _ in items if k == kind and at.date() == d)


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
            if len(used) >= limit:
                break
            base = _free_base(kind, d, used, after)
            at = base[0] if base else (_free_extra(d, used, after) if limit > len(_times(kind)) else None)
            if not at:
                break
            out.append(at)
            items.append((kind, at, "(새 게시물)"))
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
        out[k] = max(0, int(target.get(k, 0)) - len(on_day(items, k, day)))
    return out


def status(days=3, items=None):
    items = items if items is not None else taken()
    today = datetime.now(KST).date()
    lines = []
    for i in range(days):
        d = today + timedelta(days=i)
        lines.append(f"{d} ({'월화수목금토일'[d.weekday()]})")
        for k in KINDS:
            used = {at.strftime("%H:%M"): n for kk, at, n in items if kk == k and at.date() == d}
            cells = []
            for t in _times(k):
                hm = t.strftime("%H:%M")
                cells.append(f"{hm} {'■ ' + used.pop(hm) if hm in used else '□'}")
            cells += [f"{hm} ■ {n} (추가 칸)" for hm, n in sorted(used.items())]
            lines.append(f"  {k}: " + " | ".join(cells))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="게시 칸 자동 배정")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("status"); a.add_argument("--days", type=int, default=3)
    b = sub.add_parser("next"); b.add_argument("kind", choices=KINDS)
    b.add_argument("--count", type=int, default=1); b.add_argument("--date"); b.add_argument("--max", type=int)
    b.add_argument("--asap", action="store_true")
    c = sub.add_parser("need"); c.add_argument("--date")
    for p in (a, b, c):
        p.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args(argv)
    if not args.no_fetch:
        fetch()
    if args.cmd == "status":
        print(status(args.days))
    elif args.cmd == "need":
        n = need(date.fromisoformat(args.date) if args.date else None)
        print(" ".join(f"{k}={v}" for k, v in n.items()))
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
