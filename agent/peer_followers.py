"""벤치마크 계정 팔로워 기록 → data/followers_peers.csv, 빠르게 크는 계정 순위.

benchmarks.py는 계정마다 최신 팔로워 수 하나만 data/benchmarks/<계정>.json에 덮어쓴다.
이 스크립트가 매일(analysis.yml, benchmarks 뒤) 그 값을 날짜별로 쌓는다. API를 부르지 않고 AI도 쓰지 않는다.

  py -3.12 agent/peer_followers.py            오늘 값 추가 (같은 날·같은 계정은 덮어씀) + 순위 출력
  py -3.12 agent/peer_followers.py --backfill  git 기록에서 지난 값까지 채움 (전체 기록이 있는 로컬에서 한 번)

순위(growth_rows)는 patterns.py가 data/benchmark_patterns.md '빠르게 크는 계정'에 쓴다.
"""
import csv
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BENCH = DATA / "benchmarks"
CSV = DATA / "followers_peers.csv"
KST = timezone(timedelta(hours=9))
FIELDS = ["date", "account", "followers", "media_count"]


def read_rows():
    if not CSV.exists():
        return {}
    with CSV.open(encoding="utf-8", newline="") as f:
        return {(r["date"], r["account"]): r for r in csv.DictReader(f) if r.get("followers")}


def write_rows(rows):
    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({x: rows[k].get(x, "") for x in FIELDS})


def _day(updated_at):
    """benchmarks.py의 updated_at(UTC ISO) → 한국 날짜."""
    try:
        return datetime.fromisoformat(updated_at).astimezone(KST).date().isoformat()
    except (TypeError, ValueError):
        return datetime.now(KST).date().isoformat()


def add(rows, d):
    if not isinstance(d, dict) or not d.get("username") or d.get("followers") is None:
        return
    key = (_day(d.get("updated_at")), d["username"])
    rows[key] = {"date": key[0], "account": key[1], "followers": str(int(d["followers"])),
                 "media_count": str(d.get("media_count") or "")}


def snapshot(rows):
    for f in sorted(BENCH.glob("*.json")):
        try:
            add(rows, json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue


def backfill(rows):
    """git 기록의 지난 data/benchmarks/*.json에서 날짜별 팔로워를 꺼낸다 (얕은 clone이면 있는 만큼만)."""
    git = shutil.which("git")
    if not git:
        return 0
    run = lambda *a: subprocess.run([git, "-C", str(ROOT), *a], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace").stdout
    n = 0
    for line in run("log", "--format=%H", "--", "data/benchmarks").split():
        for name in run("ls-tree", "--name-only", line, "data/benchmarks/").split():
            if not name.endswith(".json"):
                continue
            try:
                add(rows, json.loads(run("show", f"{line}:{name}")))
                n += 1
            except ValueError:
                continue
    return n


def history(rows=None):
    """{계정: [(date, followers), ...] 날짜순}"""
    rows = read_rows() if rows is None else rows
    out = {}
    for (d, acc), r in rows.items():
        out.setdefault(acc, []).append((date.fromisoformat(d), int(r["followers"])))
    return {a: sorted(v) for a, v in out.items()}


def _at_or_before(series, day):
    past = [x for x in series if x[0] <= day]
    return past[-1] if past else None


def growth_rows(rows=None):
    """[(계정, 최신 팔로워, 7일 증가, 7일 %, 30일 증가, 30일 %, 기간 일수)] — 기록 2개 이상인 계정만.
    7·30일 전 기록이 없으면 가장 오래된 기록과 비교하고 기간 일수를 같이 돌려준다."""
    out = []
    for acc, s in history(rows).items():
        if len(s) < 2:
            continue
        last_d, last_n = s[-1]
        res = [acc, last_n]
        span = 0
        for days in (7, 30):
            base = _at_or_before(s, last_d - timedelta(days=days)) or s[0]
            span = max(span, (last_d - base[0]).days)
            diff = last_n - base[1]
            res += [diff, (diff / base[1] * 100) if base[1] else 0.0]
        out.append(tuple(res + [span]))
    return sorted(out, key=lambda r: -r[3])


def main():
    rows = read_rows()
    if "--backfill" in sys.argv:
        print(f"git 기록에서 {backfill(rows)}개 파일 읽음")
    snapshot(rows)
    write_rows(rows)
    print(f"{CSV.relative_to(ROOT)}: {len(rows)}줄, 계정 {len({k[1] for k in rows})}개, 날짜 {len({k[0] for k in rows})}개")
    g = growth_rows(rows)
    if not g:
        print("증가 순위: 날짜가 2개 이상 쌓이면 나온다")
    for acc, n, d7, p7, d30, p30, span in g:
        print(f"@{acc}: {n:,}명, 7일 {d7:+,} ({p7:+.1f}%), 30일 {d30:+,} ({p30:+.1f}%), 기록 {span}일")


if __name__ == "__main__":
    main()
