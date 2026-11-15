"""인스타에서 조회수가 잘 나온 주제 모으기.

1) 벤치마크 계정(config.json benchmarks.accounts)의 최근 게시물: 조회수·좋아요·댓글 (Business Discovery API)
2) 우리 계정 게시물의 성과: 조회수·도달·저장·공유 (Insights API)
→ data/benchmarks/<계정>.json, data/performance.json, data/trends.md

Business Discovery는 'Instagram API with Facebook Login'(graph.facebook.com)에서만 된다.
환경 변수: IG_ACCESS_TOKEN(페이지 토큰), IG_USER_ID(우리 인스타 비즈니스 계정 ID), IG_API_VERSION
GitHub Actions(benchmarks.yml)가 매일 아침 실행한다.
저장된 데이터로 trends.md·hot_topics.md 다시 쓰기: python agent/benchmarks.py --offline
잘 터진 주제 묶음(data/hot_topics.md)만: python agent/benchmarks.py --hot-topics-only
"""
import json
import os
import re
import sys
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


def fetch_account(username, pages=4):
    """최근 게시물을 최대 pages×50개까지 가져온다 (표본을 크게)."""
    now = datetime.now(timezone.utc).isoformat()
    path = DATA / "benchmarks" / f"{username}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"media": {}}
    media = old.get("media", {})
    after, info = None, {}
    for _ in range(pages):
        edge = f"media.after({after}).limit(50)" if after else "media.limit(50)"
        q = f"business_discovery.username({username}){{username,followers_count,media_count,{edge}{{{FIELDS}}}}}"
        bd = get(ME, fields=q)["business_discovery"]
        info = info or bd
        page = bd.get("media", {})
        for m in page.get("data", []):
            cap = (m.get("caption") or "").strip()
            media[m["id"]] = {
                "timestamp": m.get("timestamp"), "type": m.get("media_product_type") or m.get("media_type"),
                "views": m.get("view_count"), "likes": m.get("like_count"), "comments": m.get("comments_count"),
                "caption": cap[:1500], "permalink": m.get("permalink"), "fetched_at": now,
            }
        after = page.get("paging", {}).get("cursors", {}).get("after")
        if not after or len(page.get("data", [])) < 50:
            break
    out = {"username": username, "followers": info.get("followers_count"), "media_count": info.get("media_count"),
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
               "caption": (m.get("caption") or "")[:1500], "permalink": m.get("permalink")}
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
    for acc in [a for a in accounts if (a.get("followers") or 0) >= 1000]:
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


TAG_RE = re.compile(r"#[0-9A-Za-z_가-힣]+")


def _mult(m, med):
    """그 계정 같은 유형 중간값 대비 배수. 릴스는 조회수, 카드뉴스는 좋아요."""
    v = m.get("views") if (m.get("type") or "").upper().startswith("REEL") else m.get("likes")
    return v / med if v is not None and med else None


def hashtag_section(accounts, top=25, min_uses=3):
    """벤치마크 계정 캡션(1,500자까지 저장)에서 해시태그를 모아 사용 횟수와 반응 배수를 표로 (STYLE_GUIDE 7장)."""
    stats = {}
    for acc in accounts:
        media = list(acc["media"].values())
        for kind in ["REELS", "FEED"]:
            ms = [m for m in media if (m.get("type") or "").upper().startswith(kind[:4])]
            vals = [(m.get("views") if kind == "REELS" else m.get("likes")) for m in ms]
            vals = [v for v in vals if v is not None]
            med = statistics.median(vals) if vals else None
            for m in ms:
                tags = {x.lower() for x in TAG_RE.findall(m.get("caption") or "")}
                r = _mult(m, med)
                for tg in tags:
                    s = stats.setdefault(tg, {"n": 0, "acc": set(), "r": []})
                    s["n"] += 1
                    s["acc"].add(acc["username"])
                    if r is not None:
                        s["r"].append(r)
    rows = sorted(((k, v) for k, v in stats.items() if v["n"] >= min_uses), key=lambda kv: (-kv[1]["n"], kv[0]))[:top]
    if not rows:
        return []
    banned = set()
    try:
        sys.path.insert(0, str(ROOT / "agent"))
        from checks import BANNED_TAGS
        banned = {x.lower() for x in BANNED_TAGS}
    except Exception:
        pass
    out = ["", "## 많이 쓰는 해시태그 (벤치마크 계정 캡션)", "",
           "매일 작업은 여기서 분야 태그를 고른다 (STYLE_GUIDE 7장: 주제 이름 1~2 + 한국어 분야 1~2 + #토큰전쟁, 모두 3~5개). "
           "계정 수가 1이면 그 계정만 쓰는 태그다(계정 이름·연재 이름일 수 있으니 그대로 따라 쓰지 않는다). #광고는 광고 표시라 쓰지 않는다. 배수는 그 태그를 쓴 게시물의 반응(릴스 조회수, 카드뉴스 좋아요)을 "
           "그 계정 평소 중간값으로 나눈 값의 중간값. 캡션이 1,500자에서 잘려 끝의 태그가 빠진 게시물이 있을 수 있다.", "",
           "| 태그 | 쓴 게시물 | 계정 수 | 반응 배수 중간값 | 비고 |", "|---|---|---|---|---|"]
    for k, v in rows:
        r = f"{statistics.median(v['r']):.2f}x" if v["r"] else "-"
        note = ("금지 태그" if k in banned else "광고 표시, 쓰지 않음" if k == "#광고"
                else "한 계정만" if len(v["acc"]) == 1 else "")
        out.append(f"| {k} | {v['n']} | {len(v['acc'])} | {r} | {note} |")
    return out


def write_trends(accounts, own):
    now = datetime.now(timezone.utc)
    lines = [f"# 인스타 반응 분석 ({datetime.now(KST):%Y-%m-%d %H:%M} 기준)", "",
             "에이전트는 주제를 고를 때 이 파일을 먼저 읽는다 (STYLE_GUIDE 3장, 6-1장 '인스타 반응').",
             "배수 = 그 계정의 최근 60일 같은 유형(릴스/피드) 중간값 대비. 2배 이상이면 '먹힌 주제'.", ""]
    hits = []
    accounts = [a for a in accounts if (a.get("followers") or 0) >= 1000]  # 너무 작은 계정은 기준이 흔들린다
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
            if kind == "REELS":  # 계정별 조회수 상위 릴스 첫 줄 (썸네일·제목 말투 참고, STYLE_GUIDE 3-3)
                for m in sorted(ms, key=lambda m: -score(m))[:3]:
                    lines.append(f"  - {score(m):,}조회 {score(m) / med:.1f}x: [{first_line(m['caption'])}]({m['permalink']})")
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
    lines += hashtag_section(accounts)
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


# 잘 터진 주제 묶음 (data/hot_topics.md). 캡션 키워드 규칙으로 나눈다 (AI 안 씀, API 호출 없음).
# 캡션 첫 줄에 걸린 묶음(최대 2개, 목록 순서 우선). 첫 줄에 없으면 앞부분 300자에서 가장 앞 순서 묶음 1개.
# 분류 안 된 상위 게시물이 hot_topics.md 끝에 나오면 여기 키워드를 보강한다.
HOT_TOPICS = [
    ("AI 영상·영화 만들기", "창작",
     r"ai\s?(로|가)?\s?만든.{0,20}(영상|영화|단편|드라마|애니|작품)|ai (영상|영화|단편|드라마|애니)|"
     r"영상 스타일|단편|예고편|일드|애니메이션|모션그래픽|뮤직비디오|ugc|sora|소라 ?2|veo|kling|클링 ?ai|"
     r"영상을? (만들|뽑)|영상 (만드는|제작)|식전 영상|\d+초짜리|(?<!\d)[1-9]편"),
    ("AI 음악·목소리", "창작", r"노래|가사|음악|작곡|판소리|ai 목소리|suno|수노|커버곡|신곡"),
    ("AI 게임 만들기", "창작", r"게임(을|도)? ?(만들|만든|개발)|게임.{0,20}만든 사람|유니티|unity|언리얼|unreal|"
     r"게임 엔진|(만든|만들어 준) 게임|3d 게임|로블록스|roblox"),
    ("AI로 광고·디자인 만들기", "창작", r"광고 (이미지|시안|소재|\d+장|한 세트|컷)|광고가? .{0,6}\d+장|"
     r"광고 올릴|카피(라이터| 공식|를)|시안|상세페이지|앱 화면을 그리"),
    ("챗GPT·제미나이 사진·그림 변환", "창작", r"사진|그림|배경화면|이미지 ?(생성|만들)|셀카|프사|화보|레고|ootd|"
     r"그림책|스케치|나노\s?바나나|nano\s?banana|/droneview|/goldenhour|일러스트"),
    ("MCP·스킬·클로드 코드 자동화", "연결 도구", r"mcp|ai가 짠 코드|바이브 코딩|스킬|skill|클로드 코드|claude code|코덱스|codex|"
     r"코딩 에이전트|ai 에이전트|자동화|오픈소스|깃허브|github|플러그인"),
    ("유명인·CEO 발언", "인용", r"젠슨 ?황|올트먼|머스크|알렉스 카프|저커버그|순다르|피차이|아모데이|힌턴|"
     r"드워?케시|dwarkesh|나델라|빌 게이츠|래리 핑크|에드 지트론|팟캐스트|인터뷰|청문회|기조연설|대담|ceo"),
    ("돈·일자리·교육", "생활", r"일자리|직업|직장|연봉|월급|돈을? 버|버블|거품|적자|흑자|비용|상장|주가|해고|"
     r"취업|가격|비싸|구독료|실업|배워야|공부|교육|학교|수능"),
    ("AI 안전·논란", "논란", r"부정행위|편법|거짓말|안전성|위험|규제|저작권|논란|해킹|유출|딥페이크|사기|절박"),
    ("미중 경쟁·반도체·데이터센터", "산업", r"중국|패권|반도체|엔비디아|데이터센터|gpu|하이닉스|tsmc|"
     r"메모리 (가격|반도체|칩)|전력|물이 사용"),
    ("챗GPT 질문·대화 활용법", "따라 하기", r"연애|이상형|어떤 사람이었|새해 계획|내 정보|개인정보|물어봤|"
     r"대화 기록|질문 (세|네|\d)|고쳐줘|대충 답|명령어만|"
     r"이력서|자소서|ai로 쓴 글|맞다고|잘했다고만"),
    ("주간 요약", "묶음", r"이번 주|\d+주 ?차|주간"),
    ("대회·무료 지원", "생활", r"대회|해커톤|상금|무료로 (줍|준|풀)|무료 제공|과학자에게|연구자"),
    ("생활 앱·무료 도구", "생활", r"앱입니다|무료 앱|변환기|다운로드 앱|오픈소스 앱|크롬 확장|창 미리보기|유틸리티"),
    ("새 모델·기능 출시", "소식", r"공개했|출시|내놨|선보였|새 모델|gpt-?\d|적용하면서|발표했"),
]
HOT_TOPIC_RES = [(n, kind, re.compile(p, re.I)) for n, kind, p in HOT_TOPICS]


def classify_topics(cap, limit=2, body_chars=300):
    """캡션 → 주제 묶음 이름 목록 (해시태그는 뺀다). 본문 곳곳의 낱말에 끌려가지 않게 첫 줄을 먼저 본다."""
    text = TAG_RE.sub(" ", cap or "").strip()
    head = text.split("\n")[0]
    body = text[:body_chars]
    first = [n for n, _, rx in HOT_TOPIC_RES if rx.search(head)]
    if first:
        return first[:limit]
    return [n for n, _, rx in HOT_TOPIC_RES if rx.search(body)][:1]


def hot_topic_rows(accounts, days=180, min_posts=5):
    """계정·유형(릴스/피드)별 중간값 대비 배수. [(배수, 계정, 유형, 게시물)] (팔로워 1천 미만·표본 작은 계정 제외)."""
    now = datetime.now(timezone.utc)
    rows = []
    for acc in accounts:
        if (acc.get("followers") or 0) < 1000:
            continue
        recent = [m for m in acc.get("media", {}).values() if m.get("timestamp") and
                  datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) > now - timedelta(days=days)]
        for kind in ["REELS", "FEED"]:
            ms = [m for m in recent if (m.get("type") or "").upper().startswith(kind[:4]) and score(m)]
            if len(ms) < min_posts:
                continue
            med = statistics.median(score(m) for m in ms) or 1
            rows += [(score(m) / med, acc["username"], kind, m) for m in ms]
    return rows


def write_hot_topics(accounts, days=180, cap=30):
    """벤치마크 계정의 잘 터진 게시물을 주제 묶음으로 → data/hot_topics.md (저장된 데이터만, API 호출 없음).

    배수 = 그 계정 같은 유형 최근 days일 중간값 대비 (릴스 조회수, 카드는 좋아요+3×댓글).
    묶음 순위 = 묶음 안 상위 3개 배수(cap배로 자름, 없으면 1)의 기하평균. 작은 계정 한 게시물이 판을 뒤집지 않게.
    """
    rows = hot_topic_rows(accounts, days=days)
    groups = {n: [] for n, _, _ in HOT_TOPICS}
    unclassified = []
    for r in rows:
        names = classify_topics(r[3].get("caption"))
        for n in names:
            groups[n].append(r)
        if not names:
            unclassified.append(r)
    kinds = {n: k for n, k, _ in HOT_TOPICS}
    ranked = []
    for n, rs in groups.items():
        if not rs:
            continue
        rs.sort(key=lambda r: -r[0])
        top = [min(r[0], cap) for r in rs[:3]] + [1.0] * max(0, 3 - len(rs))
        rank = (top[0] * top[1] * top[2]) ** (1 / 3)
        ranked.append((rank, n, rs))
    ranked.sort(key=lambda x: -x[0])
    label = {"REELS": "릴스", "FEED": "카드"}
    fl = lambda m: first_line(m.get("caption")).replace("|", "/").strip() or "(캡션 없음)"
    total = len(rows)
    lines = [f"# 잘 터진 주제 ({datetime.now(KST):%Y-%m-%d %H:%M} 기준)", "",
             "주제를 고를 때 이 표의 위쪽 주제와 **같거나 비슷한 것**을 먼저 고른다 (STYLE_GUIDE 3장). "
             "PR 본문에 \"참고한 잘 터진 주제: …\" 한 줄을 적는다.", "",
             f"- 자료: `data/benchmarks/*.json`에 저장된 벤치마크 계정 최근 {days}일 게시물 {total}개 (팔로워 1천 이상, "
             "API 새로 부르지 않음). `agent/benchmarks.py`가 매일 갱신, 단독: `py -3.12 agent/benchmarks.py --hot-topics-only`.",
             "- 배수 = 그 계정 같은 유형(릴스/카드) 중간값 대비. 릴스는 조회수, 카드는 좋아요+3×댓글.",
             f"- 순위 = 묶음 안 상위 3개 배수({cap}배로 자름)의 기하평균. 묶음은 캡션 키워드 규칙(`HOT_TOPICS`)이라 대략이다. "
             "한 게시물이 두 묶음에 들 수 있다.", "",
             "| 순위 | 주제 | 대표 게시물 (첫 줄) | 반응 배수 | 형식 | 묶음 크기 (2배 이상) |",
             "|---|---|---|---|---|---|"]
    for i, (rank, n, rs) in enumerate(ranked, 1):
        b = rs[0]
        hits = sum(1 for r in rs if r[0] >= 2)
        lines.append(f"| {i} | {n} ({kinds[n]}) | @{b[1]}: [{fl(b[3])}]({b[3].get('permalink')}) | {b[0]:.1f}x | "
                     f"{label[b[2]]} | {len(rs)}개 ({hits}) |")
    lines += ["", "## 주제별 상위 3개", ""]
    for rank, n, rs in ranked:
        reels = sum(1 for r in rs if r[2] == "REELS")
        lines.append(f"### {n} — 순위 점수 {rank:.1f}, 릴스 {reels}·카드 {len(rs) - reels}, "
                     f"배수 중간값 {statistics.median(r[0] for r in rs):.2f}x")
        for r in rs[:3]:
            lines.append(f"- {r[0]:.1f}x {label[r[2]]} @{r[1]}: [{fl(r[3])}]({r[3].get('permalink')})")
        lines.append("")
    top_un = sorted((r for r in unclassified if r[0] >= 2), key=lambda r: -r[0])[:10]
    lines += ["## 분류 안 된 2배 이상 게시물 (키워드 보강 대상)", ""]
    lines += [f"- {r[0]:.1f}x {label[r[2]]} @{r[1]}: {fl(r[3])}" for r in top_un] or ["- 없음"]
    (DATA / "hot_topics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ranked


def load_saved_accounts():
    order = CONFIG.get("benchmarks", {}).get("accounts", [])
    files = sorted((DATA / "benchmarks").glob("*.json"), key=lambda f: order.index(f.stem) if f.stem in order else 99)
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def offline():
    """저장된 data/benchmarks/*.json, data/performance.json으로 trends.md만 다시 쓴다 (API 호출 없음)."""
    accounts = load_saved_accounts()
    pf = DATA / "performance.json"
    own = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    write_trends(accounts, own)
    write_hot_topics(accounts)
    print("data/trends.md, data/hot_topics.md 작성 (저장된 데이터)")


def main():
    if "--hot-topics-only" in sys.argv:
        write_hot_topics(load_saved_accounts())
        return print("data/hot_topics.md 작성 (저장된 데이터, API 호출 없음)")
    if "--offline" in sys.argv:
        return offline()
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
            saved = DATA / "benchmarks" / f"{u}.json"
            if saved.exists():  # 토큰이 끊겨도 trends.md가 비지 않게 지난번 데이터로
                accounts.append(json.loads(saved.read_text(encoding="utf-8")))
                print(f"@{u}: 저장된 데이터로 대신 ({accounts[-1].get('updated_at', '')[:10]})")
    own = {}
    try:
        own = fetch_own()
    except Exception as e:
        print("우리 계정 성과 가져오기 실패:", e)
        pf = DATA / "performance.json"
        own = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    write_trends(accounts, own)
    write_hot_topics(accounts)
    print("data/trends.md, data/hot_topics.md 작성")


if __name__ == "__main__":
    main()
