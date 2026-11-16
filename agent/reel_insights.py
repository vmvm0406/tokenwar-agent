"""우리 릴스의 시청 지표 모으기 (조회가 왜 130~300에서 멈추는지 보려고).

최근 30일 우리 REELS마다 미디어 인사이트를 받는다:
  views, reach, saved, shares, total_interactions, likes, comments,
  ig_reels_avg_watch_time(평균 시청 시간, 밀리초), ig_reels_video_view_total_time(총 재생 시간, 밀리초),
  reels_skip_rate(처음 3초 안에 넘긴 비율, %, 메타 문서상 '추정·개발 중')
  (공식 문서: developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights)
지표 하나가 오류를 내면 그것만 빼고 다시 묻고, 안 되는 지표를 기록한다(unsupported).
길이: posts/published/<폴더>/reel.mp4를 ffprobe로 재고(없으면 post.json video end-start), 한 번 잰 값은 저장해 둔다.
시청 비율 = 평균 시청 시간 / 길이.

→ data/reel_insights.json (날짜별 기록), data/reel_insights.md (표 + 보이는 것 3줄)
환경 변수: IG_ACCESS_TOKEN, IG_USER_ID, (선택) IG_API_HOST, IG_API_VERSION
GitHub Actions(reel-insights.yml)가 매일 '인스타 반응 분석' 뒤에 돈다. 한 번에 API 호출 40회 이하.
저장된 데이터로 md만 다시 쓰기: python agent/reel_insights.py --offline
"""
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_JSON = DATA / "reel_insights.json"
OUT_MD = DATA / "reel_insights.md"
PUBLISHED = ROOT / "posts" / "published"
API = f"https://{os.environ.get('IG_API_HOST') or 'graph.facebook.com'}/" + os.environ.get("IG_API_VERSION", "v27.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
ME = os.environ.get("IG_USER_ID", "")
KST = timezone(timedelta(hours=9))
DAYS = 30
MAX_CALLS = 40
METRICS = ["views", "reach", "saved", "shares", "total_interactions", "likes", "comments",
           "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate"]
CALLS = {"n": 0}


class Budget(RuntimeError):
    pass


class ApiError(RuntimeError):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def get(path, **params):
    if CALLS["n"] >= MAX_CALLS:
        raise Budget(f"호출 {MAX_CALLS}회 다 씀")
    CALLS["n"] += 1
    r = requests.get(f"{API}/{path}", params={**params, "access_token": TOKEN}, timeout=60)
    body = r.json()
    if "error" in body:
        err = body["error"]
        if err.get("code") in (4, 17, 32, 613):
            raise Budget(f"한도 ({err.get('code')})")
        # 토큰 값이 오류 문장에 섞여 나오지 않게 지운다
        msg = str(err.get("message", ""))[:200]
        raise ApiError(msg.replace(TOKEN, "***") if TOKEN else msg, err.get("code"))
    return body


def load():
    if OUT_JSON.exists():
        return json.loads(OUT_JSON.read_text(encoding="utf-8"))
    return {"days": {}, "durations": {}, "unsupported": {}}


def folder_map():
    """media_id → posts/published 폴더."""
    out = {}
    for pj in PUBLISHED.glob("*/published.json"):
        try:
            mid = str(json.loads(pj.read_text(encoding="utf-8")).get("media_id") or "")
        except (ValueError, OSError):
            continue
        if mid:
            out[mid] = pj.parent
    return out


def probe(path):
    exe = shutil.which("ffprobe")
    if not exe or not path.exists():
        return None
    try:
        r = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60)
        return round(float(r.stdout.strip()), 1)
    except (ValueError, subprocess.SubprocessError):
        return None


def duration_of(folder):
    if folder is None:
        return None
    d = probe(folder / "reel.mp4")
    if d:
        return d
    try:
        v = json.loads((folder / "post.json").read_text(encoding="utf-8")).get("video") or {}
        if v.get("end") is not None and v.get("start") is not None:
            return round(float(v["end"]) - float(v["start"]), 1)
    except (ValueError, OSError, TypeError):
        pass
    return None


def title_of(folder, caption):
    if folder is not None:
        try:
            t = json.loads((folder / "post.json").read_text(encoding="utf-8")).get("title")
            if t:
                return " ".join(str(t).split())
        except (ValueError, OSError):
            pass
    return (caption or "").strip().split("\n")[0][:60]


def bad_metric(msg, wanted):
    """오류 문장에 이름이 나온 지표를 찾는다."""
    for m in wanted:
        if re.search(rf"\b{re.escape(m)}\b", msg):
            return m
    return None


def insights(mid, wanted, unsupported):
    """되는 지표만 남기며 묻는다. 반환: (값 dict, 오류 문장)."""
    wanted = [m for m in wanted if m not in unsupported]
    while wanted:
        try:
            body = get(f"{mid}/insights", metric=",".join(wanted))
        except ApiError as e:
            msg = str(e)
            m = bad_metric(msg, wanted)
            if m is None:
                # 어떤 지표 탓인지 모르면 '개발 중' 지표부터 하나씩 뺀다
                for cand in ("reels_skip_rate", "ig_reels_video_view_total_time", "total_interactions", "views"):
                    if cand in wanted:
                        m = cand
                        break
            if m is None:
                return {}, msg
            unsupported[m] = msg[:160]
            print(f"  지표 '{m}' 안 됨: {msg[:120]}")
            wanted.remove(m)
            continue
        vals = {}
        for d in body.get("data", []):
            v = (d.get("values") or [{}])[0].get("value")
            if v is None:
                v = (d.get("total_value") or {}).get("value")
            vals[d["name"]] = v
        return vals, None
    return {}, "모든 지표가 안 됨"


def collect(store):
    if not TOKEN or not ME:
        sys.exit("IG_ACCESS_TOKEN, IG_USER_ID가 없다 (GitHub Actions에서만 돈다). --offline으로 md만 다시 쓸 수 있다.")
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    items = get(f"{ME}/media", fields="id,caption,timestamp,media_product_type,permalink", limit=50).get("data", [])
    reels = [m for m in items if m.get("media_product_type") == "REELS"
             and datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z") >= since]
    print(f"최근 {DAYS}일 릴스 {len(reels)}개")
    fmap = folder_map()
    unsupported = store["unsupported"] = {}  # 매번 다시 확인한다 (메타가 지표를 열거나 닫을 수 있음)
    durations = store.setdefault("durations", {})
    today = datetime.now(KST).strftime("%Y-%m-%d")
    rows = {}
    for m in reels:
        mid = m["id"]
        folder = fmap.get(mid)
        if durations.get(mid) is None:
            durations[mid] = duration_of(folder)
        row = {"timestamp": m["timestamp"], "permalink": m.get("permalink"),
               "folder": folder.name if folder else None,
               "title": title_of(folder, m.get("caption")), "duration": durations.get(mid)}
        try:
            vals, err = insights(mid, METRICS, unsupported)
        except Budget as e:
            print("멈춤:", e)
            break
        row.update(vals)
        if err:
            row["error"] = err[:160]
        rows[mid] = row
    store.setdefault("days", {})[today] = rows
    store["metrics_returned"] = sorted({k for r in rows.values() for k in r if k in METRICS})
    store["updated"] = datetime.now(KST).isoformat(timespec="minutes")
    print(f"API 호출 {CALLS['n']}회")
    return store


def fmt_s(ms):
    return "-" if ms is None else f"{ms / 1000:.1f}초"


def ratio(r):
    w, d = r.get("ig_reels_avg_watch_time"), r.get("duration")
    if w is None or not d:
        return None
    return w / 1000 / d


def pct(x):
    return "-" if x is None else f"{x * 100:.0f}%"


def write_md(store):
    days = store.get("days") or {}
    if not days:
        return
    day = max(days)
    rows = sorted(days[day].values(), key=lambda r: r["timestamp"], reverse=True)
    L = [f"# 우리 릴스 시청 지표 ({day} 기준)", "",
         "agent/reel_insights.py가 매일 만든다 (손으로 고치지 않는다). 평균 시청 시간·건너뛰기 비율은 메타가 '추정·개발 중'이라 밝힌 값.",
         "건너뛰기 = 처음 3초 안에 넘긴 비율.", ""]
    ratios = [(ratio(r), r) for r in rows if ratio(r) is not None]
    L.append("## 보이는 것")
    if ratios:
        med = statistics.median(x for x, _ in ratios)
        hi = max(ratios, key=lambda t: t[0])
        lo = min(ratios, key=lambda t: t[0])
        L.append(f"- 평균 시청 비율 중앙값 {pct(med)} (릴스 {len(ratios)}개, 평균 시청 시간 중앙값 "
                 f"{fmt_s(statistics.median(r['ig_reels_avg_watch_time'] for _, r in ratios))})")
        L.append(f"- 가장 오래 본 릴스: {hi[1]['title'][:30]} — {pct(hi[0])} ({fmt_s(hi[1]['ig_reels_avg_watch_time'])} / {hi[1]['duration']:.0f}초)")
        skips = [r for r in rows if r.get("reels_skip_rate") is not None]
        if skips:
            worst = max(skips, key=lambda r: r["reels_skip_rate"])
            L.append(f"- 가장 빨리 넘긴 릴스: {worst['title'][:30]} — 3초 안에 {worst['reels_skip_rate']:.0f}% 건너뜀 "
                     f"(건너뛰기 중앙값 {statistics.median(r['reels_skip_rate'] for r in skips):.0f}%)")
        else:
            L.append(f"- 가장 빨리 넘긴 릴스: {lo[1]['title'][:30]} — 시청 비율 {pct(lo[0])} ({fmt_s(lo[1]['ig_reels_avg_watch_time'])} / {lo[1]['duration']:.0f}초)")
    else:
        L.append("- 평균 시청 시간 값이 없다 (지표가 안 되거나 길이를 모름).")
    L += ["", "## 릴스별 (최근 것 먼저)", "",
          "| 게시 (KST) | 제목 | 길이 | 조회 | 도달 | 평균 시청 | 시청 비율 | 건너뛰기 | 저장 | 공유 | 좋아요 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t = datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(KST).strftime("%m-%d %H:%M")
        sk = r.get("reels_skip_rate")
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            t, (r.get("title") or "")[:34].replace("|", "/"),
            "-" if not r.get("duration") else f"{r['duration']:.0f}초",
            r.get("views", "-"), r.get("reach", "-"), fmt_s(r.get("ig_reels_avg_watch_time")), pct(ratio(r)),
            "-" if sk is None else f"{sk:.0f}%", r.get("saved", "-"), r.get("shares", "-"), r.get("likes", "-")))
    uns = store.get("unsupported") or {}
    L += ["", "받은 지표: " + ", ".join(store.get("metrics_returned") or []),
          "안 되는 지표: " + (", ".join(f"{k} ({v[:60]})" for k, v in uns.items()) if uns else "없음"), ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


def main():
    store = load()
    if "--offline" not in sys.argv:
        store = collect(store)
        # 오래된 날짜는 90일만 남긴다
        cut = (datetime.now(KST) - timedelta(days=90)).strftime("%Y-%m-%d")
        store["days"] = {d: v for d, v in store["days"].items() if d >= cut}
        OUT_JSON.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(store)
    print("→", OUT_MD.relative_to(ROOT))


if __name__ == "__main__":
    main()
