"""인스타에서 조회수가 잘 나온 주제 모으기.

1) 벤치마크 계정(config.json benchmarks.accounts)의 최근 게시물: 조회수·좋아요·댓글 (Business Discovery API)
2) 우리 계정 게시물의 성과: 조회수·도달·저장·공유 (Insights API)
→ data/benchmarks/<계정>.json, data/performance.json, data/trends.md

Business Discovery는 'Instagram API with Facebook Login'(graph.facebook.com)에서만 된다.
환경 변수: IG_ACCESS_TOKEN(페이지 토큰), IG_USER_ID(우리 인스타 비즈니스 계정 ID), IG_API_VERSION
GitHub Actions(benchmarks.yml)가 매일 아침 실행한다.
"""
import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
API = "https://graph.facebook.com/" + os.environ.get("IG_API_VERSION", "v27.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
ME = os.environ.get("IG_USER_ID", "")
KST = timezone(timedelta(hours=9))
FIELDS = "id,caption,timestamp,media_type,media_product_type,like_count,comments_count,view_count,permalink"


def get(path, **params):
    r = requests.get(f"{API}/{path}", params={**params, "access_token": TOKEN}, timeout=60)
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"].get("message", str(body)[:200]))
    return body


def fetch_account(username):
    q = (f"business_discovery.username({username})"
         f"{{username,followers_count,media_count,media.limit(50){{{FIELDS}}}}}")
    bd = get(ME, fields=q)["business_discovery"]
    now = datetime.now(timezone.utc).isoformat()
    path = DATA / "benchmarks" / f"{username}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"media": {}}
    media = old.get("media", {})
    for m in bd.get("media", {}).get("data", []):
        cap = (m.get("caption") or "").strip()
        media[m["id"]] = {
            "timestamp": m.get("timestamp"), "type": m.get("media_product_type") or m.get("media_type"),
            "views": m.get("view_count"), "likes": m.get("like_count"), "comments": m.get("comments_count"),
            "caption": cap[:150], "permalink": m.get("permalink"), "fetched_at": now,
        }
    out = {"username": username, "followers": bd.get("followers_count"), "media_count": bd.get("media_count"),
           "updated_at": now, "media": media}
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def fetch_own():
    items = get(f"{ME}/media", fields="id,caption,timestamp,media_product_type,like_count,comments_count,permalink",
                limit=50).get("data", [])
    perf = {}
    for m in items:
        row = {"timestamp": m.get("timestamp"), "type": m.get("media_product_type"),
               "likes": m.get("like_count"), "comments": m.get("comments_count"),
               "caption": (m.get("caption") or "")[:150], "permalink": m.get("permalink")}
        try:
            ins = get(f"{m['id']}/insights", metric="views,reach,saved,shares,total_interactions")
            for d in ins.get("data", []):
                row[d["name"]] = (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value"))
        except RuntimeError as e:
            row["insights_error"] = str(e)[:120]
        perf[m["id"]] = row
    try:
        of = get(f"{ME}/insights", metric="online_followers", period="lifetime")
        vals = (of.get("data") or [{}])[0].get("values") or []
        if vals:
            perf["_online_followers"] = vals[-1].get("value")  # 시간(UTC 0~23) → 접속 팔로워 수
    except RuntimeError as e:
        perf["_online_followers_error"] = str(e)[:120]  # 팔로워 100명 미만이면 안 나온다
    (DATA / "performance.json").write_text(json.dumps(perf, ensure_ascii=False, indent=1), encoding="utf-8")
    return perf


def score(m):
    return m.get("views") if m.get("views") is not None else (m.get("likes") or 0) + 3 * (m.get("comments") or 0)


def first_line(cap):
    return (cap.split("\n")[0] if cap else "")[:80]


def _block(h):
    for a, z in [(0, 6), (6, 9), (9, 12), (12, 15), (15, 18), (18, 21), (21, 24)]:
        if a <= h < z:
            return f"{a:02d}-{z:02d}시"


def time_section(accounts):
    """게시 시각별 성과 (그 계정 평소 대비 배수의 중간값). 표본이 작으면 참고만."""
    rows = []
    for acc in accounts:
        media = list(acc["media"].values())
        for kind in ["REELS", "FEED"]:
            ms = [m for m in media if (m.get("type") or "").upper().startswith(kind[:4]) and score(m)]
            if not ms:
                continue
            med = statistics.median(score(m) for m in ms) or 1
            for m in ms:
                ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).astimezone(KST)
                rows.append((kind, ts, score(m) / med))
    if not rows:
        return []
    out = ["", "## 언제 올린 게시물이 잘 됐나 (한국 시간, 평소 대비 배수 중간값 · 게시물 수)", "",
           "| 시간대 | 릴스 | 카드뉴스(피드) |", "|---|---|---|"]
    for blk in [_block(h) for h in (0, 6, 9, 12, 15, 18, 21)]:
        cells = []
        for kind in ["REELS", "FEED"]:
            v = [r[2] for r in rows if r[0] == kind and _block(r[1].hour) == blk]
            cells.append(f"{statistics.median(v):.2f}x · {len(v)}" if v else "-")
        out.append(f"| {blk} | {cells[0]} | {cells[1]} |")
    out += ["", "| 요일 | 배수 · 수 |", "|---|---|"]
    for i, dname in enumerate("월화수목금토일"):
        v = [r[2] for r in rows if r[1].weekday() == i]
        if v:
            out.append(f"| {dname} | {statistics.median(v):.2f}x · {len(v)} |")
    out += ["", "게시물 수가 10개 미만인 칸은 우연일 수 있다. 우리 계정 팔로워가 100명을 넘으면 아래 '우리 팔로워 접속 시간'을 더 믿는다."]
    return out


def write_trends(accounts, own):
    now = datetime.now(timezone.utc)
    lines = [f"# 인스타 반응 분석 ({datetime.now(KST):%Y-%m-%d %H:%M} 기준)", "",
             "에이전트는 주제를 고를 때 이 파일을 먼저 읽는다 (STYLE_GUIDE 3장, 6-1장 '인스타 반응').",
             "배수 = 그 계정의 최근 60일 같은 유형(릴스/피드) 중간값 대비. 2배 이상이면 '먹힌 주제'.", ""]
    hits = []
    for acc in accounts:
        media = list(acc["media"].values())
        recent = [m for m in media if m.get("timestamp") and
                  datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) > now - timedelta(days=60)]
        lines.append(f"## @{acc['username']} (팔로워 {acc.get('followers') or '?'})")
        for kind in ["REELS", "FEED"]:
            ms = [m for m in recent if (m.get("type") or "").upper().startswith(kind[:4]) and score(m)]
            if not ms:
                continue
            med = statistics.median(score(m) for m in ms) or 1
            unit = "조회" if kind == "REELS" else "반응"
            lines.append(f"- {kind} 중간값 {med:,.0f}{unit}, 게시물 {len(ms)}개")
            for m in ms:
                ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
                if ts > now - timedelta(days=30):
                    hits.append((score(m) / med, acc["username"], kind, ts, score(m), m))
        lines.append("")
    hits.sort(key=lambda x: -x[0])
    lines += ["## 최근 30일 잘 된 게시물 TOP 20", "", "| 배수 | 계정 | 유형 | 날짜 | 수치 | 첫 줄 |", "|---|---|---|---|---|---|"]
    for r, u, k, ts, v, m in hits[:20]:
        lines.append(f"| {r:.1f}x | @{u} | {k} | {ts.astimezone(KST):%m-%d} | {v:,} | [{first_line(m['caption'])}]({m['permalink']}) |")
    lines += ["", "## 잘 안 된 게시물 (하위 10)", "", "| 배수 | 계정 | 첫 줄 |", "|---|---|---|"]
    for r, u, k, ts, v, m in (hits[20:][-10:] if len(hits) > 20 else []):
        lines.append(f"| {r:.1f}x | @{u} | {first_line(m['caption'])} |")
    lines += time_section(accounts)
    if own:
        lines += ["", "## 우리 계정 성과", "", "| 날짜 | 유형 | 조회 | 도달 | 저장 | 공유 | 첫 줄 |", "|---|---|---|---|---|---|---|"]
        of = own.get("_online_followers")
        if isinstance(of, dict) and of:
            kst = {(int(h) + 9) % 24: v for h, v in of.items()}
            top = sorted(kst.items(), key=lambda x: -x[1])[:5]
            lines += ["", "## 우리 팔로워 접속 시간 (한국 시간, 많은 순)", "",
                      ", ".join(f"{h}시({v}명)" for h, v in top), ""]
        for m in sorted((v for k, v in own.items() if not k.startswith("_")),
                        key=lambda m: m.get("timestamp") or "", reverse=True)[:30]:
            ts = (m.get("timestamp") or "")[:10]
            lines.append(f"| {ts} | {m.get('type')} | {m.get('views', '')} | {m.get('reach', '')} | "
                         f"{m.get('saved', '')} | {m.get('shares', '')} | {first_line(m.get('caption'))} |")
    (DATA / "trends.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if not TOKEN or not ME:
        print("IG_ACCESS_TOKEN / IG_USER_ID가 없어 건너뜀 (README '인스타 연결' 참고)")
        return
    (DATA / "benchmarks").mkdir(parents=True, exist_ok=True)
    accounts = []
    for u in CONFIG.get("benchmarks", {}).get("accounts", []):
        try:
            accounts.append(fetch_account(u))
            print(f"@{u}: 게시물 {len(accounts[-1]['media'])}개")
        except Exception as e:
            print(f"@{u}: 실패 ({e}) — 비즈니스/크리에이터 계정이 아니거나 이름이 바뀌었을 수 있음")
    own = {}
    try:
        own = fetch_own()
    except Exception as e:
        print("우리 계정 성과 가져오기 실패:", e)
    write_trends(accounts, own)
    print("data/trends.md 작성")


if __name__ == "__main__":
    main()
