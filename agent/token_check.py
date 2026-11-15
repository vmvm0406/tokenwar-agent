"""인스타 토큰 점검. 결과를 data/token_status.json에 남긴다 (토큰 값은 남기지 않음).

문제가 있으면 종료 코드 1 → GitHub Actions가 이슈를 열어 메일로 알린다.
- 토큰이 무효
- 데이터 액세스 만료(data_access_expires_at)가 14일 안
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = f"https://{os.environ.get('IG_API_HOST') or 'graph.facebook.com'}/" + os.environ.get("IG_API_VERSION", "v27.0")
T = os.environ.get("IG_ACCESS_TOKEN", "")
IG = os.environ.get("IG_USER_ID", "")


def ts(v):
    return datetime.fromtimestamp(v, timezone.utc).isoformat() if v else "never"


def main():
    out = {"checked_at": datetime.now(timezone.utc).isoformat(), "problems": []}
    if not T or not IG:
        out["problems"].append("IG_ACCESS_TOKEN 또는 IG_USER_ID 시크릿이 없음")
    else:
        d = requests.get(f"{API}/debug_token", params={"input_token": T, "access_token": T}, timeout=30).json()
        data = d.get("data", {})
        out.update({"type": data.get("type"), "valid": data.get("is_valid"),
                    "expires_at": ts(data.get("expires_at")),
                    "data_access_expires_at": ts(data.get("data_access_expires_at")),
                    "scopes": data.get("scopes")})
        if "error" in d or not data.get("is_valid"):
            out["problems"].append("토큰이 무효: " + str(d.get("error", {}).get("message") or data.get("error", {}).get("message", ""))[:200])
        dae = data.get("data_access_expires_at")
        if dae and datetime.fromtimestamp(dae, timezone.utc) < datetime.now(timezone.utc) + timedelta(days=14):
            out["problems"].append(f"데이터 액세스가 {ts(dae)}에 만료됨 → 토큰을 새로 받을 것 (README '토큰 갱신')")
        me = requests.get(f"{API}/{IG}", params={"fields": "username,followers_count,media_count", "access_token": T}, timeout=30).json()
        if "error" in me:
            out["problems"].append("인스타 계정 조회 실패: " + me["error"].get("message", "")[:200])
        else:
            out["instagram"] = {k: me.get(k) for k in ("username", "followers_count", "media_count")}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "token_status.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "scopes"}, ensure_ascii=False, indent=2))
    sys.exit(1 if out["problems"] else 0)


if __name__ == "__main__":
    main()
