"""새 AI 모델·큰 기능 발표 감시 (AI를 쓰지 않는 단순 검사). config.json `model_watch`.

1) 항상 보는 곳: OpenAI·구글(제미나이)·앤트로픽 공식 블로그·뉴스룸 (RSS, 없으면 목록 페이지 HTML).
   제목·요약 낱말로 "일반 사용자가 앱에서 쓸 새 모델·큰 기능"만 후보로 낸다. 개발자용 API의 작은 버전은 건너뛴다.
   애매하면 후보로 내고, 판단은 게시물을 만드는 Claude가 한다 (LOCAL.md 6장).
2) 화제일 때만: 그록·메타·딥시크·네이버·삼성 등은 data/hot.md의 여러 섹션(구글 트렌드·유튜브·해커뉴스·레딧 등)에
   동시에 뜨고, 그중 한 줄이라도 출시·모델 낱말이 있을 때만 후보. 같은 회사는 cooldown_days 동안 다시 내지 않는다.

이미 본 글은 data/model_watch.json(주소·제목·처음 본 시각)에 남겨 두 번 잡지 않는다.

사용법:
    py -3.12 agent/model_watch.py --init     지금 있는 글을 전부 '본 것'으로 기록만 (출력 없음)
    py -3.12 agent/model_watch.py            새 후보가 있으면 한 줄씩 "회사 | 제목 | 주소"
    py -3.12 agent/model_watch.py -v         출처별 읽은 수·거른 이유를 stderr로
    py -3.12 agent/model_watch.py --dry-run  기록 파일을 바꾸지 않음
종료 코드: 0 새 것 없음, 10 새 후보 있음, 2 모든 출처를 읽지 못함.
기록 파일이 없으면 --init처럼 동작한다 (처음 돌릴 때 옛 글이 한꺼번에 '새 것'으로 나오지 않게).
"""
import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("model_watch", {})
STATE = ROOT / "data" / "model_watch.json"
HOT = ROOT / "data" / "hot.md"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (tokenwar-bot; +https://github.com/vmvm0406/tokenwar-agent)"}
EXIT_NEW, EXIT_FAIL = 10, 2

# 새 모델 이름 (버전 번호가 붙은 것)
MODEL = re.compile(r"\b(GPT-?\d[\w.]*|o\d(-\w+)?|Gemini(\s[A-Z]\w+)?\s?\d[\w.]*|Gemini (Ultra|Pro|Flash)|Claude\s?(Opus|Sonnet|Haiku)?\s?\d[\w.]*|"
                   r"(Opus|Sonnet|Haiku)\s?\d[\w.]*|Sora\s?\d*|Veo\s?\d[\w.]*|Imagen\s?\d[\w.]*|Nano Banana[\w ]*|Genie\s?\d|"
                   r"new (AI )?models?|frontier model)\b", re.I)
# 발표 낱말 + 일반 사용자가 쓰는 제품 이름이 같이 있으면 '큰 기능' 후보
LAUNCH = re.compile(r"\b(introduc\w+|launch\w*|now available|rolling out|roll out|available (today|now|in)|comes? to|arriv\w+|"
                    r"meet|new in|now on|you can now|new features?|upgrade\w*|unveil\w*)\b", re.I)
CONSUMER = re.compile(r"\b(ChatGPT|Gemini( app)?|Claude( app| for)?|Google Search|AI Mode|NotebookLM|Sora|Chrome|Android|Pixel|"
                      r"Gmail|YouTube|app|iPhone|Mac|Windows|voice|images?|video|agent mode|deep research)\b", re.I)
# 개발자·기업·회사 소식 쪽
DEV = re.compile(r"\b(API|developers?|SDK|Codex|Vertex|Agent Builder|enterprise|for (business|government|education)|"
                 r"customer stor\w*|partner\w*|research|policy|safety|evals?|IPO|S-1|investor|funding|hiring|office|"
                 r"academy|foundation|commitment|Marketplace|AWS|Azure|GovCloud|Google Cloud|Workspace admins?|healthcare|benchmarks?)\b", re.I)
# 고객 사례 제목 ("Barclays scales Claude ...", "... builds more with Codex")
CUSTOMER = re.compile(r"\bwith (OpenAI|Claude|Codex)\b|^(?!Introducing)\S+( \S+)? (scales|delivers|builds|uses|helps|"
                      r"rethinks|ships|grows|elevates|transforms|doubles|searches)\b")
SMALL = re.compile(r"\b(mini|nano|lite|preview|snapshot|deprecat\w*|pricing|rate limits?|batch)\b", re.I)
SKIP_URL = re.compile(r"/(business|customer-stories|careers|policy|research|global-affairs|safety)/", re.I)
# 목록 페이지에서 글이 아닌 링크 (분류 페이지)
CATEGORY = {"announcements", "features", "partnerships", "policy", "product", "safeguards", "security", "research",
            "company", "news", "events", "societal-impacts", "interpretability", "alignment", "economic-research"}
RELEASE = re.compile(r"(출시|공개|발표|신모델|새 모델|모델|launch|release|model|introduc|unveil|\bv?\d+(\.\d+)?\b)", re.I)


def log(verbose, *a):
    if verbose:
        print(*a, file=sys.stderr)


def text(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"[‐-―]", "-", s)  # "GPT‑6"처럼 특수 하이픈을 보통 하이픈으로
    return re.sub(r"\s+", " ", s).strip()


def read_rss(src, limit):
    r = requests.get(src["url"], headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    items = root.iter("item")
    for it in items:
        link = (it.findtext("link") or "").strip()
        title = text(it.findtext("title"))
        if not link or not title:
            continue
        out.append({"url": link, "title": title, "summary": text(it.findtext("description"))[:300],
                    "tags": [text(c.text) for c in it.findall("category")]})
        if len(out) >= limit:
            break
    if not out:  # Atom
        A = "{http://www.w3.org/2005/Atom}"
        for e in root.iter(A + "entry"):
            link = next((l.get("href") for l in e.findall(A + "link") if l.get("rel", "alternate") == "alternate"), "")
            title = text(e.findtext(A + "title"))
            if link and title:
                out.append({"url": link, "title": title, "summary": text(e.findtext(A + "summary"))[:300], "tags": []})
            if len(out) >= limit:
                break
    return out


def read_html(src, limit):
    """목록 페이지에서 글 링크(link_prefix로 시작)를 찾고, 그 링크 안의 제목(h1~h4)·요약(p)을 모은다. 페이지 순서 = 최신 순."""
    r = requests.get(src["url"], headers=UA, timeout=30)
    r.raise_for_status()
    prefix = src.get("link_prefix", "/")
    found = {}
    for m in re.finditer(r'<a\b[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>', r.text, re.S | re.I):
        href, inner = m.group(1), m.group(2)
        path = re.sub(r"^https?://[^/]+", "", href)
        if not path.startswith(prefix):
            continue
        slug = path[len(prefix):].strip("/")
        if not slug or "/" in slug or slug in CATEGORY:
            continue
        url = urljoin(src["url"], path)
        d = found.setdefault(url, {"url": url, "title": "", "summary": "", "tags": []})
        h = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", inner, re.S | re.I)
        p = re.search(r"<p[^>]*>(.*?)</p>", inner, re.S | re.I)
        if h and not d["title"]:
            d["title"] = text(h.group(1))
        if p and not d["summary"]:
            d["summary"] = text(p.group(1))[:300]
        if not d["title"] and not h and not p:
            t = text(inner)
            if 8 <= len(t) <= 160:
                d["title"] = t
    out = [d for d in found.values() if d["title"]]
    return out[:limit]


def judge(item):
    """후보면 (True, 이유), 아니면 (False, 이유)."""
    if SKIP_URL.search(item["url"]):
        return False, "기업·연구·정책 주소"
    blob = " ".join([item["title"], item["summary"], " ".join(item.get("tags", []))])
    title = item["title"]
    if CUSTOMER.search(title):
        return False, "고객 사례"
    model = MODEL.search(title)
    launch = LAUNCH.search(blob)
    consumer = CONSUMER.search(blob) or MODEL.search(item["summary"])
    dev = DEV.search(title)
    if model:
        if dev and not CONSUMER.search(title) and SMALL.search(blob):
            return False, "개발자용 작은 버전"
        return True, "새 모델" + (" (개발자 쪽 낱말 있음, 애매)" if dev else "")
    if launch and consumer:
        if dev:
            return False, "개발자·기업 쪽 기능"
        return True, "큰 기능"
    return False, "모델·기능 발표 아님"


def hot_candidates(cfg, verbose):
    """data/hot.md에서 같은 회사가 min_sections곳 이상에 뜨고, 출시·모델 낱말이 있으면 후보."""
    if not HOT.exists():
        return []
    sections, cur = {}, None
    for line in HOT.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = []
        elif cur and line.startswith("- "):
            sections[cur].append(line[2:])
    out = []
    for company, pattern in (cfg.get("brands") or {}).items():
        rx = re.compile(pattern, re.I)
        hits = {s: [l for l in lines if rx.search(l)] for s, lines in sections.items()}
        hits = {s: l for s, l in hits.items() if l}
        lines = [l for ls in hits.values() for l in ls]
        log(verbose, f"  화제 {company}: {len(hits)}곳")
        if len(hits) < int(cfg.get("min_sections", 2)) or not any(RELEASE.search(l) for l in lines):
            continue
        first = next((l for l in lines if RELEASE.search(l)), lines[0])
        urls = [u for l in [first] + lines for u in re.findall(r"https?://[^\s)]+", l)]
        url = urls[0] if urls else ""
        title = re.sub(r"\s*\(https?://[^)]*\)", "", first).strip()
        title = f"[화제: {', '.join(hits)}] {title}"[:200]
        out.append({"company": company, "url": url, "title": title, "key": f"hot:{company}"})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="새 AI 모델·큰 기능 발표 감시")
    ap.add_argument("--init", action="store_true", help="지금 있는 글을 전부 본 것으로 기록만")
    ap.add_argument("--dry-run", action="store_true", help="기록 파일을 바꾸지 않음")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    state = json.loads(STATE.read_text(encoding="utf-8-sig")) if STATE.exists() else {"seen": {}}
    seen = state.setdefault("seen", {})
    init = args.init or not STATE.exists()
    if init and not args.init:
        log(True, "기록 파일이 없어 처음 실행으로 보고 --init처럼 기록만 합니다.")
    now = datetime.now(KST).replace(microsecond=0)
    limit = int(CONFIG.get("max_items_per_source", 40))
    new, ok = [], 0

    for src in CONFIG.get("sources", []):
        try:
            items = read_rss(src, limit) if src.get("type") == "rss" else read_html(src, limit)
            ok += 1
        except Exception as e:
            log(True, f"{src.get('name', src['url'])}: 읽지 못함 ({type(e).__name__}: {str(e)[:120]})")
            continue
        fresh = 0
        for it in items:
            if it["url"] in seen:
                continue
            fresh += 1
            hit, why = judge(it)
            seen[it["url"]] = {"source": src.get("name", ""), "company": src["company"], "title": it["title"],
                               "first_seen": now.isoformat(), "candidate": hit and not init, "why": why}
            log(args.verbose and not init, f"  {'후보' if hit else '건너뜀'} [{why}] {it['title']}")
            if hit and not init:
                new.append(f"{src['company']} | {it['title']} | {it['url']}")
        log(args.verbose or args.init, f"{src.get('name', src['url'])}: {len(items)}개 읽음, 처음 본 것 {fresh}개")

    hot_cfg = CONFIG.get("hot") or {}
    cool = timedelta(days=float(hot_cfg.get("cooldown_days", 7)))
    for c in hot_candidates(hot_cfg, args.verbose):
        prev = seen.get(c["key"])
        if prev and now - datetime.fromisoformat(prev["first_seen"]) < cool:
            continue
        seen[c["key"]] = {"source": "data/hot.md", "company": c["company"], "title": c["title"], "url": c["url"],
                          "first_seen": now.isoformat(), "candidate": not init, "why": "화제"}
        if not init:
            new.append(f"{c['company']} | {c['title']} | {c['url'] or 'data/hot.md'}")

    if not args.dry_run:
        state["updated"] = now.isoformat()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if ok == 0 and CONFIG.get("sources"):
        return EXIT_FAIL
    for line in new:
        print(line)
    return EXIT_NEW if new else 0


if __name__ == "__main__":
    sys.exit(main())
