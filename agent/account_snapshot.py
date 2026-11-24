"""계정 상태 한 번에 보기 (운영자 2026-11-24 '계정 분석 좀 해봐 접근해서').

인스타 Graph API로 받는 것:
  - 계정: 팔로워·팔로잉·게시물 수
  - 최근 게시물 50개: 시각, 종류, 좋아요·댓글 수
  - 최근 14일 날마다: reach, views, profile_views, follows_and_unfollows, accounts_engaged, total_interactions
  - online_followers(팔로워가 접속한 시간대), follower_demographics(나이·성별·도시): 팔로워 100명 미만이면 메타가 안 줄 수 있음 → 오류만 기록
→ data/account_snapshot.json
환경 변수: IG_ACCESS_TOKEN, IG_USER_ID, (선택) IG_API_HOST, IG_API_VERSION. GitHub Actions(account-snapshot.yml)에서만 돈다.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "account_snapshot.json"
API = f"https://{os.environ.get('IG_API_HOST') or 'graph.facebook.com'}/" + os.environ.get("IG_API_VERSION", "v27.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
ME = os.environ.get("IG_USER_ID", "")
KST = timezone(timedelta(hours=9))
DAILY = ["reach", "views", "profile_views", "follows_and_unfollows", "accounts_engaged", "total_interactions"]


def get(path, **params):
    r = requests.get(f"{API}/{path}", params={**params, "access_token": TOKEN}, timeout=60)
    body = r.json()
    if "error" in body:
        msg = str(body["error"].get("message", ""))[:200]
        raise RuntimeError(msg.replace(TOKEN, "***") if TOKEN else msg)
    return body


def tryget(errors, key, path, **params):
    try:
        return get(path, **params)
    except Exception as e:  # noqa: BLE001
        errors[key] = str(e)
        return None


def main():
    if not TOKEN or not ME:
        raise SystemExit("IG_ACCESS_TOKEN, IG_USER_ID가 없다 (GitHub Actions에서만 돈다)")
    out = {"updated": datetime.now(KST).isoformat(timespec="minutes"), "errors": {}}
    err = out["errors"]
    out["account"] = tryget(err, "account", ME, fields="username,followers_count,follows_count,media_count")
    media = tryget(err, "media", f"{ME}/media", fields="id,timestamp,media_product_type,like_count,comments_count,permalink,caption", limit=50)
    out["media"] = [{**{k: m.get(k) for k in ("id", "timestamp", "media_product_type", "like_count", "comments_count", "permalink")},
                     "caption": (m.get("caption") or "")[:60]} for m in (media or {}).get("data", [])]
    days = {}
    today = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(14, 0, -1):
        d0 = today - timedelta(days=i)
        body = tryget(err, f"daily_{d0:%m%d}", f"{ME}/insights", metric=",".join(DAILY), period="day", metric_type="total_value",
                      since=int(d0.timestamp()), until=int((d0 + timedelta(days=1)).timestamp()))
        if body:
            row = {}
            for m in body.get("data", []):
                tv = m.get("total_value") or {}
                row[m["name"]] = tv.get("value")
                if tv.get("breakdowns"):
                    row[m["name"] + "_breakdown"] = tv["breakdowns"]
            days[f"{d0:%Y-%m-%d}"] = row
    out["daily"] = days
    on = tryget(err, "online_followers", f"{ME}/insights", metric="online_followers", period="lifetime")
    out["online_followers"] = (on or {}).get("data")
    out["demographics"] = {}
    for b in ("age", "gender", "city", "country"):
        body = tryget(err, f"demo_{b}", f"{ME}/insights", metric="follower_demographics", period="lifetime",
                      metric_type="total_value", breakdown=b, timeframe="this_month")
        if body:
            out["demographics"][b] = body.get("data")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", OUT, "오류:", list(err))


if __name__ == "__main__":
    main()
