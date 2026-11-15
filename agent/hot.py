"""지금 사람들이 가장 관심 갖는 AI 주제 모으기 → data/hot.md

모으는 곳 (되는 것만 쓰고, 막히면 건너뛴다):
1) 구글 트렌드 한국 급상승 검색어 (RSS) 중 AI·테크 관련
2) 유튜브: 최근 올라온 AI 영상의 시간당 조회수 (yt-dlp 필요, 회원님 컴퓨터에서만 됨)
3) 해커뉴스 첫 화면의 AI 글 (점수·댓글 수)
4) 레딧 AI 커뮤니티의 오늘 인기 글 (r/OpenAI, r/ClaudeAI, r/singularity, r/LocalLLaMA, r/artificial)
5) 인스타 벤치마크 계정의 최근 72시간 게시물 중 평소보다 잘 된 것 (data/benchmarks)

사용법: python agent/hot.py   (LOCAL.md 0단계와 GitHub Actions benchmarks.yml에서 매일 실행)
"""
import json
import re
import shutil
import statistics
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (tokenwar-bot; +https://github.com/vmvm0406/tokenwar-agent)"}
AI_WORDS = re.compile(
    r"(AI|인공지능|챗GPT|ChatGPT|GPT|오픈AI|OpenAI|클로드|Claude|앤트로픽|Anthropic|제미나이|Gemini|구글 ?AI|"
    r"엔비디아|NVIDIA|젠슨|올트먼|Altman|머스크|xAI|Grok|그록|딥시크|DeepSeek|LLM|에이전트|agent|로봇|robot|"
    r"Sora|소라|Veo|미드저니|Midjourney|코파일럿|Copilot|라마|Llama|메타 ?AI|반도체|HBM|하이닉스|딥페이크|deepfake)",
    re.I)


def google_trends():
    out = []
    r = requests.get("https://trends.google.com/trending/rss?geo=KR", headers=UA, timeout=20)
    r.raise_for_status()
    ns = {"ht": "https://trends.google.com/trending/rss"}
    for it in ET.fromstring(r.content).iter("item"):
        title = it.findtext("title") or ""
        traffic = it.findtext("ht:approx_traffic", namespaces=ns) or ""
        news = [n.findtext("ht:news_item_title", namespaces=ns) or "" for n in it.findall("ht:news_item", ns)]
        if AI_WORDS.search(title + " " + " ".join(news)):
            out.append({"title": title, "traffic": traffic, "news": [x for x in news if x][:2]})
    return out


def youtube():
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp 없음 (회원님 컴퓨터에서만 수집)")
    out = []
    for q in ["AI", "ChatGPT", "Claude AI", "OpenAI", "AI 뉴스"]:
        url = f"https://www.youtube.com/results?search_query={requests.utils.quote(q)}&sp=EgQIAhAB"  # 이번 주, 동영상
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--playlist-end", "15", "--print",
                            "%(id)s\t%(channel)s\t%(view_count)s\t%(title)s", url],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        for line in r.stdout.splitlines():
            vid, ch, views, title = (line.split("\t") + ["", "", "", ""])[:4]
            if views.isdigit():
                out.append({"id": vid, "channel": ch, "views": int(views), "title": title, "q": q})
    # 업로드 시각은 영상별로 따로 받아야 해서 조회수 상위 10개만 시간당 조회수를 계산
    seen, top = set(), []
    for v in sorted(out, key=lambda x: -x["views"]):
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        top.append(v)
        if len(top) >= 10:
            break
    for v in top:
        r = subprocess.run(["yt-dlp", "--skip-download", "--print", "%(timestamp)s",
                            f"https://www.youtube.com/watch?v={v['id']}"],
                           capture_output=True, text=True, timeout=60)
        ts = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if ts.isdigit():
            hours = max(1, (datetime.now(timezone.utc).timestamp() - int(ts)) / 3600)
            v["per_hour"] = int(v["views"] / hours)
            v["hours"] = int(hours)
    return sorted(top, key=lambda x: -x.get("per_hour", 0))


def hackernews():
    r = requests.get("https://hn.algolia.com/api/v1/search", params={"tags": "front_page", "hitsPerPage": 60}, timeout=20)
    r.raise_for_status()
    hits = [h for h in r.json().get("hits", []) if AI_WORDS.search(h.get("title") or "")]
    return [{"title": h["title"], "points": h.get("points", 0), "comments": h.get("num_comments", 0),
             "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"}
            for h in sorted(hits, key=lambda h: -(h.get("points") or 0))[:10]]


def reddit():
    out = []
    for sub in ["OpenAI", "ClaudeAI", "singularity", "LocalLLaMA", "artificial"]:
        r = requests.get(f"https://www.reddit.com/r/{sub}/top.json", params={"t": "day", "limit": 5}, headers=UA, timeout=20)
        if r.status_code != 200:
            continue
        for c in r.json().get("data", {}).get("children", []):
            d = c["data"]
            out.append({"sub": sub, "title": d.get("title"), "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0), "url": "https://www.reddit.com" + d.get("permalink", "")})
    if not out:
        raise RuntimeError("레딧 응답 없음")
    return sorted(out, key=lambda x: -x["score"])[:12]


def instagram_recent():
    out = []
    now = datetime.now(timezone.utc)
    for f in (ROOT / "data" / "benchmarks").glob("*.json"):
        acc = json.loads(f.read_text(encoding="utf-8"))
        if (acc.get("followers") or 0) < 1000:
            continue
        ms = list(acc["media"].values())
        for kind in ["REELS", "FEED"]:
            k = [m for m in ms if (m.get("type") or "").upper().startswith(kind[:4])]
            sc = lambda m: m["views"] if m.get("views") is not None else (m.get("likes") or 0) + 3 * (m.get("comments") or 0)
            k = [m for m in k if sc(m)]
            if len(k) < 5:
                continue
            med = statistics.median(sc(m) for m in k) or 1
            for m in k:
                ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
                if now - ts < timedelta(hours=72) and sc(m) / med >= 1.5:
                    out.append({"account": acc["username"], "kind": kind, "ratio": round(sc(m) / med, 1),
                                "caption": (m.get("caption") or "").split("\n")[0][:80], "url": m.get("permalink")})
    return sorted(out, key=lambda x: -x["ratio"])


def main():
    sections, now = [], datetime.now(KST)
    for name, fn in [("구글 트렌드 한국 급상승 (AI·테크만)", google_trends), ("유튜브 이번 주 AI 영상 (시간당 조회수 순)", youtube),
                     ("인스타 최근 72시간 평소보다 잘 된 게시물", instagram_recent), ("해커뉴스 첫 화면 AI 글", hackernews),
                     ("레딧 AI 커뮤니티 오늘 인기", reddit)]:
        try:
            sections.append((name, fn(), None))
        except Exception as e:  # 막히면 건너뛴다
            sections.append((name, [], str(e)[:120]))
    lines = [f"# 지금 관심 주제 ({now:%Y-%m-%d %H:%M} 기준)", "",
             "주제를 고를 때 가장 먼저 본다 (STYLE_GUIDE 3장, 6-1장 '지금 관심도'). 여러 곳에 동시에 뜬 주제가 가장 뜨겁다.", ""]
    for name, items, err in sections:
        lines.append(f"## {name}")
        if err:
            lines.append(f"(수집 못 함: {err})")
        elif not items:
            lines.append("(해당 없음)")
        for it in items:
            if "traffic" in it:
                lines.append(f"- {it['title']} ({it['traffic']}) — {' / '.join(it['news'])}")
            elif "per_hour" in it or "views" in it:
                lines.append(f"- 시간당 {it.get('per_hour', '?'):,} · 총 {it['views']:,} · {it['channel']} — {it['title']} "
                             f"(https://www.youtube.com/watch?v={it['id']})" if isinstance(it.get('per_hour'), int) else
                             f"- 총 {it['views']:,} · {it['channel']} — {it['title']} (https://www.youtube.com/watch?v={it['id']})")
            elif "ratio" in it:
                lines.append(f"- {it['ratio']}x · @{it['account']} {it['kind']} — {it['caption']} ({it['url']})")
            elif "points" in it:
                lines.append(f"- {it['points']}점 · 댓글 {it['comments']} — {it['title']} ({it['url']})")
            elif "sub" in it:
                lines.append(f"- {it['score']}점 · r/{it['sub']} — {it['title']} ({it['url']})")
        lines.append("")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "hot.md").write_text("\n".join(lines), encoding="utf-8")
    print("data/hot.md 작성:", ", ".join(f"{n.split(' ')[0]} {len(i)}" for n, i, _ in sections))


if __name__ == "__main__":
    main()
