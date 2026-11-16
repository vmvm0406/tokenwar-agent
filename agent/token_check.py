"""인스타 토큰 점검. 결과를 data/token_status.json에 남긴다 (토큰 값은 남기지 않음).

문제가 있으면 종료 코드 1 → GitHub Actions가 이슈를 열어 메일로 알린다.
- 토큰이 무효
- 데이터 액세스 만료(data_access_expires_at)가 14일 안
- 스레드 토큰(THREADS_ACCESS_TOKEN, 있을 때만)이 무효이거나 만료(expires_at)가 14일 안.
  스레드 장기 토큰은 60일짜리라 갱신해야 한다. 자동 갱신은 하지 않는다 (운영자 결정 남음).
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
TH_API = "https://graph.threads.net/" + os.environ.get("THREADS_API_VERSION", "v1.0")
TH = os.environ.get("THREADS_ACCESS_TOKEN", "")
WARN_DAYS = 14


def ts(v):
    return datetime.fromtimestamp(v, timezone.utc).isoformat() if v else "never"


def soon(v):
    return bool(v) and datetime.fromtimestamp(v, timezone.utc) < datetime.now(timezone.utc) + timedelta(days=WARN_DAYS)


def check_threads(out):
    """스레드 토큰 점검. 토큰이 없으면 건너뛴다 (스레드는 선택)."""
    if not TH:
        out["threads"] = {"skipped": "THREADS_ACCESS_TOKEN 없음"}
        return
    th = {}
    try:
        d = requests.get(f"{TH_API}/debug_token", params={"input_token": TH, "access_token": TH}, timeout=30).json()
    except (requests.RequestException, ValueError) as e:
        d = {"error": {"message": type(e).__name__}}  # 예외 문구엔 토큰 든 주소가 섞일 수 있어 이름만
    data = d.get("data", {}) if isinstance(d, dict) else {}
    if data:
        th.update({"valid": data.get("is_valid"), "expires_at": ts(data.get("expires_at")),
                   "data_access_expires_at": ts(data.get("data_access_expires_at")), "scopes": data.get("scopes")})
        if not data.get("is_valid"):
            out["problems"].append("스레드 토큰이 무효: " + str((data.get("error") or {}).get("message", ""))[:200])
        if soon(data.get("expires_at")):
            out["problems"].append(f"스레드 토큰이 {ts(data.get('expires_at'))}에 만료됨 → 새 장기 토큰으로 THREADS_ACCESS_TOKEN 바꾸기 (README '토큰 갱신')")
    else:
        th["debug_error"] = str(d.get("error", {}).get("message", ""))[:200]
    # debug_token이 안 되더라도 실제로 쓸 수 있는지는 /me로 확인한다
    try:
        me = requests.get(f"{TH_API}/me", params={"fields": "id,username"},
                          headers={"Authorization": f"Bearer {TH}"}, timeout=30).json()
    except (requests.RequestException, ValueError) as e:
        me = {"error": {"message": type(e).__name__}}
    if "error" in me:
        out["problems"].append("스레드 계정 조회 실패: " + str(me["error"].get("message", ""))[:200])
    else:
        th["username"] = me.get("username")
    out["threads"] = th


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
    check_threads(out)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "token_status.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shown = {k: v for k, v in out.items() if k != "scopes"}
    if isinstance(shown.get("threads"), dict):
        shown["threads"] = {k: v for k, v in shown["threads"].items() if k != "scopes"}
    print(json.dumps(shown, ensure_ascii=False, indent=2))
    sys.exit(1 if out["problems"] else 0)


if __name__ == "__main__":
    main()
