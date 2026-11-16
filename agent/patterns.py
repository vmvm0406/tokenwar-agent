"""벤치마크 계정에서 '무엇이 평소보다 잘 됐나'를 형식·첫 줄 모양·시간·자료 DM·시리즈별로 → data/benchmark_patterns.md

AI도 API도 쓰지 않는다. data/benchmarks/*.json(benchmarks.py가 저장)과 data/followers_peers.csv(peer_followers.py)만 읽는다.
analysis.yml이 매일 benchmarks 뒤에 돌린다. 로컬: py -3.12 agent/patterns.py

배수 = 그 계정 같은 유형(릴스/피드) 최근 180일 중간값 대비 (benchmarks.hot_topic_rows 그대로: 릴스 조회수, 피드 좋아요+3×댓글).
특징 효과(lift) = 그 특징이 있는 게시물 배수 중간값 ÷ 없는 게시물 배수 중간값.
'계정 일치' = 양쪽 다 3개 이상인 계정 중 특징 쪽이 더 높았던 계정 수. 한 계정이 판을 뒤집는지 보는 용도.
"""
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmarks as B  # noqa: E402  (함수만 쓴다. API는 부르지 않는다)
import peer_followers as PF  # noqa: E402

OUT = B.DATA / "benchmark_patterns.md"
DAYS = 180
MIN_N = 8          # 특징 쪽 게시물이 이보다 적으면 표에서 뺀다
LABEL = {"REELS": "릴스", "FEED": "피드(카드·사진)"}

TAG = re.compile(r"#[0-9A-Za-z_가-힣]+")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
NUM_PROMISE = re.compile(r"\d+\s*(개|가지|단계|장|초|분|명|배|%|원|년|일|시간|줄|문장|편|곳|번)")
LIST_PROMISE = re.compile(r"\d+\s*(개|가지|단계|선|종|줄)")
QUESTION = re.compile(r"\?|까요|나요|ㄹ까|을까|일까|인가요|는지|었다고요|다고요")
IMPERATIVE = re.compile(r"(하세요|해보세요|해 보세요|보세요|지우세요|쓰세요|만드세요|마세요|드세요|받으세요|저장|따라 ?해|"
                        r"바꿔보세요|꼭|당장|지금 바로|이제 그만|하지 마)")
PROVOKE = re.compile(r"(아직도|모르면|안 하면|손해|끝났|망했|충격|미쳤|역대급|진짜|소름|이게 된다|실화|난리|큰일|버블|사라질)")
QUOTE = re.compile(r"^[\"“'‘]|\((?:[가-힣A-Za-z .]+(?:,\s*[^)]*)?)\)\s*$|\b(CEO|대표|창업자)\b")
RESULT_FIRST = re.compile(r"(만들었|만든|바꿔|바뀌|변신|됩니다|돼요|됐어요|생겼|나왔)")
DM = re.compile(r"댓글.{0,40}(DM|디엠|보내|드려|드릴|발송)|(DM|디엠)으로.{0,20}(보내|드려|드릴)|"
                r"댓글에?\s*['‘\"“].{1,12}['’\"”]", re.S)
SERIES = re.compile(r"(\d+\s*편|[Ee][Pp]\.?\s*\d+|#\d+\b|시리즈|[Dd]ay\s*\d+|\d+\s*일\s*차|\d+\s*탄|\d+\s*주\s*차|^\[[^\]]{1,15}\])")
FOLLOW = re.compile(r"팔로우")


def _ts(m):
    return datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).astimezone(B.KST)


def features(m):
    """게시물 → {특징 이름: True/False 또는 값}."""
    cap = m.get("caption") or ""
    text = TAG.sub(" ", cap)
    head = (text.strip().split("\n") or [""])[0].strip()
    n = len(head)
    f = {
        "첫 줄 20자 이하": n <= 20,
        "첫 줄 21~40자": 21 <= n <= 40,
        "첫 줄 41자 이상": n > 40,
        "첫 줄 질문형": bool(QUESTION.search(head)),
        "첫 줄 숫자 약속(N개·N초 등)": bool(NUM_PROMISE.search(head)),
        "첫 줄 목록 숫자(N개·N가지)": bool(LIST_PROMISE.search(head)),
        "첫 줄 권유·명령(~하세요)": bool(IMPERATIVE.search(head)),
        "첫 줄 자극어(아직도·충격 등)": bool(PROVOKE.search(head)),
        "첫 줄 인용·인물 표기": bool(QUOTE.search(head)),
        "첫 줄 결과 먼저(만들었·바뀌)": bool(RESULT_FIRST.search(head)),
        "첫 줄 이모지": bool(EMOJI.search(head)),
        "댓글 키워드→DM 자료": bool(DM.search(cap)),
        "캡션에 '팔로우'": bool(FOLLOW.search(cap)),
        "시리즈 표시(N편·EP·Day)": bool(SERIES.search(head)),
        "캡션 300자 이상": len(text.strip()) >= 300,
        "캡션 80자 미만": len(text.strip()) < 80,
    }
    t = _ts(m)
    f["_hour"] = B._block(t.hour)
    f["_wd"] = "월화수목금토일"[t.weekday()]
    f["_topics"] = B.classify_topics(cap)
    f["_head"] = head
    return f


def _med(v):
    return statistics.median(v) if v else 0.0


def lift_table(rows, kind=None):
    """[(특징, n, 특징 중간 배수, 나머지 중간 배수, lift, 2배 이상 비율, 계정 일치 'a/b')]"""
    rs = [r for r in rows if kind is None or r[2] == kind]
    names = [k for k in rs[0][4] if not k.startswith("_")] if rs else []
    out = []
    for name in names:
        yes = [r for r in rs if r[4][name]]
        no = [r for r in rs if not r[4][name]]
        if len(yes) < MIN_N or len(no) < MIN_N:
            continue
        my, mn = _med([r[0] for r in yes]), _med([r[0] for r in no])
        agree = total = 0
        for acc in {r[1] for r in rs}:
            a = [r[0] for r in yes if r[1] == acc]
            b = [r[0] for r in no if r[1] == acc]
            if len(a) >= 3 and len(b) >= 3:
                total += 1
                agree += _med(a) > _med(b)
        out.append((name, len(yes), my, mn, (my / mn) if mn else 0, sum(r[0] >= 2 for r in yes) / len(yes),
                    f"{agree}/{total}"))
    return sorted(out, key=lambda x: -x[4])


def group_table(rows, key, kind):
    rs = [r for r in rows if r[2] == kind]
    allm = _med([r[0] for r in rs]) or 1
    g = defaultdict(list)
    for r in rs:
        vals = r[4][key] if isinstance(r[4][key], list) else [r[4][key]]
        for v in vals or ["(분류 안 됨)"]:
            g[v].append(r[0])
    return sorted(((k, len(v), _med(v), _med(v) / allm, sum(x >= 2 for x in v) / len(v)) for k, v in g.items()),
                  key=lambda x: -x[2])


def account_table(accounts, rows):
    out = []
    for acc in accounts:
        media = list(acc.get("media", {}).values())
        if not media:
            continue
        now = datetime.now(timezone.utc)
        recent = [m for m in media if m.get("timestamp") and _ts(m) > now - timedelta(days=30)]
        reels = [m for m in media if (m.get("type") or "").upper().startswith("REEL")]
        rv = [m["views"] for m in reels if m.get("views") is not None]
        dm = sum(bool(DM.search(m.get("caption") or "")) for m in media)
        fol = acc.get("followers") or 0
        out.append((acc["username"], fol, len(recent), len(reels) / len(media), _med(rv),
                    (_med(rv) / fol) if fol and rv else 0, dm / len(media)))
    return sorted(out, key=lambda x: -x[1])


def account_tops(rows, k=2):
    """계정마다 lift가 가장 큰 특징 k개 (양쪽 5개 이상)."""
    out = {}
    for acc in sorted({r[1] for r in rows}):
        rs = [r for r in rows if r[1] == acc]
        best = []
        for name in [n for n in rs[0][4] if not n.startswith("_")]:
            a = [r[0] for r in rs if r[4][name]]
            b = [r[0] for r in rs if not r[4][name]]
            if len(a) >= 5 and len(b) >= 5 and _med(b):
                best.append((_med(a) / _med(b), name, len(a)))
        out[acc] = sorted(best, reverse=True)[:k]
    return out


def own_summary():
    p = B.DATA / "performance.json"
    if not p.exists():
        return []
    import json
    perf = {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    lines = []
    for kind in ["REELS", "FEED"]:
        ms = [m for m in perf.values() if (m.get("type") or "").upper().startswith(kind[:4])]
        if ms:
            v = [m.get("views") or 0 for m in ms]
            lines.append(f"- 우리 {LABEL[kind]} {len(ms)}개: 조회 중간값 {_med(v):,.0f}, 최고 {max(v):,}, "
                         f"공유 합 {sum(m.get('shares') or 0 for m in ms)}, 저장 합 {sum(m.get('saved') or 0 for m in ms)}")
    return lines


def fmt_pct(x):
    return f"{x * 100:.0f}%"


def top_bullets(lt_reel, lt_feed, hours_reel, topics_reel, topics_feed, growth):
    """'지금 우리에게 맞는 것': 우리가 바로 바꿀 수 있는 것만, 근거 숫자와 함께."""
    b = []
    def consistent(x, want_high):
        a, t = map(int, x[6].split("/"))
        return t == 0 or (a * 2 > t if want_high else a * 3 <= t)  # 계정 대부분이 같은 방향일 때만

    good = lambda t: [x for x in t if x[4] >= 1.15 and x[1] >= MIN_N and consistent(x, True)]
    bad = lambda t: sorted([x for x in t if x[4] <= 0.85 and x[1] >= MIN_N and consistent(x, False)],
                           key=lambda x: x[4])
    for kind, t in [("릴스", lt_reel), ("피드", lt_feed)]:
        for name, n, my, mn, lift, hit, agree in good(t)[:2]:
            b.append(f"**{kind} — {name}**: 평소 대비 {my:.2f}x (나머지 {mn:.2f}x, 효과 {lift:.2f}배), "
                     f"n={n}, 2배 이상 {fmt_pct(hit)}, 계정 일치 {agree}")
    for kind, t in [("릴스", lt_reel), ("피드", lt_feed)]:
        for name, n, my, mn, lift, hit, agree in bad(t)[:1]:
            b.append(f"**{kind} 피할 것 — {name}**: {my:.2f}x (나머지 {mn:.2f}x, 효과 {lift:.2f}배), n={n}, 계정 일치 {agree}")
    tr = [x for x in topics_reel if x[1] >= MIN_N and x[0] != "(분류 안 됨)"][:2]
    if tr:
        b.append("**릴스 주제**: " + ", ".join(f"{k} {m:.2f}x(n={n}, 2배 이상 {fmt_pct(h)})" for k, n, m, _, h in tr))
    tf = [x for x in topics_feed if x[1] >= MIN_N and x[0] != "(분류 안 됨)"][:2]
    if tf:
        b.append("**피드 주제**: " + ", ".join(f"{k} {m:.2f}x(n={n})" for k, n, m, _, h in tf))
    hr = [x for x in hours_reel if x[1] >= 10][:1]
    if hr:
        k, n, m, rel, h = hr[0]
        b.append(f"**릴스 시간대**: {k} 게시가 {m:.2f}x (전체 대비 {rel:.2f}배, n={n})")
    if growth:
        acc, n, d7, p7, *_rest, span = growth[0]
        b.append(f"**가장 빨리 크는 계정**: @{acc} {n:,}명, 최근 {min(span, 7)}일 {d7:+,} ({p7:+.1f}%) — 그 계정 최근 게시물 형식을 먼저 본다")
    return b[:8]


def main():
    accounts = [a for a in B.load_saved_accounts() if (a.get("followers") or 0) >= 1000]
    raw = B.hot_topic_rows(accounts, days=DAYS)
    rows = [(mult, acc, kind, m, features(m)) for mult, acc, kind, m in raw]
    if not rows:
        return print("자료 없음: data/benchmarks/*.json")
    lt_all, lt_reel, lt_feed = lift_table(rows), lift_table(rows, "REELS"), lift_table(rows, "FEED")
    hours_reel, hours_feed = group_table(rows, "_hour", "REELS"), group_table(rows, "_hour", "FEED")
    wd_reel = group_table(rows, "_wd", "REELS")
    topics_reel, topics_feed = group_table(rows, "_topics", "REELS"), group_table(rows, "_topics", "FEED")
    growth = PF.growth_rows()
    nR = sum(r[2] == "REELS" for r in rows)
    L = [f"# 벤치마크 패턴 ({datetime.now(B.KST):%Y-%m-%d %H:%M} 기준)", "",
         "주제·형식을 고르기 전에 이 파일 위쪽과 `data/weekly_insights.md`를 본다. `agent/patterns.py`가 매일 코드로 계산한다 (AI·API 없음).", "",
         f"- 자료: 팔로워 1천 이상 벤치마크 {len({r[1] for r in rows})}개 계정 최근 {DAYS}일 게시물 {len(rows)}개 "
         f"(릴스 {nR}, 피드 {len(rows) - nR}). 배수 = 그 계정 같은 유형 중간값 대비.",
         "- 효과 = 특징 있는 게시물 배수 중간값 ÷ 없는 게시물. 계정 일치 a/b = 양쪽 3개 이상인 b개 계정 중 a곳에서 특징 쪽이 높았다. "
         "a/b가 절반 이하면 한두 계정 효과일 수 있다.", "",
         "## 지금 우리에게 맞는 것", ""]
    L += [f"- {x}" for x in top_bullets(lt_reel, lt_feed, hours_reel, topics_reel, topics_feed, growth)]
    own = own_summary()
    if own:
        L += ["", "### 우리 계정 (data/performance.json)"] + own

    def lt_md(title, t):
        out = ["", f"## {title}", "", "| 특징 | n | 특징 배수 | 나머지 | 효과 | 2배 이상 | 계정 일치 |", "|---|---|---|---|---|---|---|"]
        out += [f"| {a} | {n} | {my:.2f}x | {mn:.2f}x | {lf:.2f} | {fmt_pct(h)} | {ag} |" for a, n, my, mn, lf, h, ag in t]
        return out

    L += lt_md("릴스: 첫 줄·캡션 특징", lt_reel)
    L += lt_md("피드(카드·사진): 첫 줄·캡션 특징", lt_feed)

    def grp_md(title, t, min_n=3):
        out = ["", f"## {title}", "", "| 값 | n | 배수 중간값 | 전체 대비 | 2배 이상 |", "|---|---|---|---|---|"]
        out += [f"| {k} | {n} | {m:.2f}x | {rel:.2f} | {fmt_pct(h)} |" for k, n, m, rel, h in t if n >= min_n]
        return out

    L += grp_md("릴스 주제 묶음 (benchmarks.HOT_TOPICS 규칙)", topics_reel)
    L += grp_md("피드 주제 묶음", topics_feed)
    L += grp_md("릴스 게시 시간대 (한국 시간)", sorted(hours_reel))
    L += grp_md("피드 게시 시간대", sorted(hours_feed))
    L += grp_md("릴스 요일", wd_reel)

    L += ["", "## 계정별 형식", "", "| 계정 | 팔로워 | 최근 30일 게시 | 릴스 비율 | 릴스 조회 중간값 | 조회/팔로워 | 자료 DM 비율 |",
          "|---|---|---|---|---|---|---|"]
    L += [f"| @{a} | {f:,} | {n30} | {fmt_pct(rr)} | {rv:,.0f} | {vf:.2f} | {fmt_pct(dm)} |"
          for a, f, n30, rr, rv, vf, dm in account_table(accounts, rows)]
    L += ["", "## 계정별 가장 잘 먹힌 특징 (양쪽 5개 이상)", ""]
    for acc, best in account_tops(rows).items():
        if best:
            L.append(f"- @{acc}: " + ", ".join(f"{name} {lf:.2f}배(n={n})" for lf, name, n in best))

    L += ["", "## 빠르게 크는 계정 (data/followers_peers.csv)", ""]
    if growth:
        L += ["| 계정 | 팔로워 | 7일 증가 | 7일 % | 30일 증가 | 30일 % | 기록 일수 |", "|---|---|---|---|---|---|---|"]
        L += [f"| @{a} | {n:,} | {d7:+,} | {p7:+.2f}% | {d30:+,} | {p30:+.2f}% | {s} |" for a, n, d7, p7, d30, p30, s in growth]
        L += ["", "기록 일수가 7·30일보다 짧으면 그 기간 안의 가장 오래된 기록과 비교한 값이다."]
    else:
        L.append("- 날짜가 2개 이상 쌓이면 나온다 (`agent/peer_followers.py`가 매일 기록).")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(B.ROOT)} 작성: 게시물 {len(rows)}개")


if __name__ == "__main__":
    main()
