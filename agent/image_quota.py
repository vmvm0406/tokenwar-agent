"""AI 그림 하루 상한 (Cloudflare Workers Paid, 운영자 결제 2026-11-17).

그림을 많이 만들면 돈이 나가므로 하루(UTC 날짜, Cloudflare 하루 한도 초기화 기준) 만드는 장 수를 센다.
- 상한: config.json "image_gen": {"daily_limit": 60}. 없으면 DEFAULT_LIMIT. null이면 상한 없음.
- 기록: data/image_gen_count.json = {"2026-11-17": 23, ...} (날짜별, 최근 KEEP_DAYS일만).
  render.yml은 main의 기록을 임시 파일로 가져와(환경 변수 IMAGE_GEN_COUNT_FILE) 쓰고,
  끝나면 merge로 "main의 지금 값 + 이번 실행에서 만든 장 수"를 main에 따로 커밋한다.
  게시물 결과 커밋과 섞지 않아 rebase 충돌이 생기지 않고, 브랜치가 달라도 숫자는 main 하나에 모인다.
- DRY_RUN=1이면 세지 않는다. 키가 없으면 그림이 안 만들어지므로 셀 일도 없다.

명령줄:
  python agent/image_quota.py status
  python agent/image_quota.py merge --base B --local L --remote R --out O
      O = R + (L - B) 날짜별 (R 파일이 없으면 빈 기록). 오래된 날짜는 지운다.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "data" / "image_gen_count.json"
DEFAULT_LIMIT = 60
KEEP_DAYS = 30


class DailyLimitReached(RuntimeError):
    """오늘 상한에 닿음. 남은 그림은 다음 날(UTC 0시 뒤) 실행에서 이어서 만든다."""


def count_file():
    return Path(os.environ.get("IMAGE_GEN_COUNT_FILE") or DEFAULT_FILE)


def today():
    return datetime.now(timezone.utc).date().isoformat()


def daily_limit():
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_LIMIT
    ig = cfg.get("image_gen") or {}
    if "daily_limit" not in ig:
        return DEFAULT_LIMIT
    return None if ig["daily_limit"] is None else int(ig["daily_limit"])


def load(path=None):
    p = Path(path) if path else count_file()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def trim(counts, now=None):
    cut = (datetime.fromisoformat(now or today()) - timedelta(days=KEEP_DAYS - 1)).date().isoformat()
    return {k: v for k, v in sorted(counts.items()) if k >= cut}


def save(counts, path=None):
    p = Path(path) if path else count_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(trim(counts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def used(day=None):
    return load().get(day or today(), 0)


def remaining():
    lim = daily_limit()
    return None if lim is None else max(0, lim - used())


def check():
    """그림 한 장 만들기 전에. 상한이면 DailyLimitReached."""
    lim = daily_limit()
    n = used()
    if lim is not None and n >= lim:
        raise DailyLimitReached(
            f"오늘(UTC {today()}) AI 그림 상한 {lim}장에 닿아 더 만들지 않습니다 (지금까지 {n}장). "
            f"남은 그림은 UTC 0시(한국 오전 9시) 뒤 render.yml이 이어서 만듭니다. "
            f"상한을 바꾸려면 config.json \"image_gen\"의 \"daily_limit\"을 고치세요.")


def add(n=1):
    """Cloudflare 호출이 성공해 그림을 받은 뒤에. DRY_RUN이면 세지 않는다."""
    if os.environ.get("DRY_RUN") == "1":
        return
    counts = load()
    d = today()
    counts[d] = counts.get(d, 0) + n
    save(counts)


def merge(base, local, remote):
    out = dict(remote)
    for d, v in local.items():
        delta = v - base.get(d, 0)
        if delta > 0:
            out[d] = out.get(d, 0) + delta
    return trim(out)


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    m = sub.add_parser("merge")
    for k in ("base", "local", "remote", "out"):
        m.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        lim = daily_limit()
        print(f"UTC {today()}: {used()}장 / 상한 {'없음' if lim is None else lim} ({count_file()})")
        return 0
    res = merge(load(a.base), load(a.local), load(a.remote))
    save(res, a.out)
    print("그림 수 기록:", json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
