"""업계 큰 소식 모으기 (AI 안 씀). config.json `model_watch.news`.

빅테크 CEO 사임·복귀, 대형 인수, 규제·소송, 주요 모델 발표처럼 공식 블로그에는 안 나오는 업계 뉴스를
주요 언론에서 직접 찾는다.

1) Google News RSS 검색 (최근 `hours`시간, `when:` 조건)
   - 주요 매체 묶음: 영어 site: 조건(FT·블룸버그·로이터·WSJ·더 버지·테크크런치·CNBC 등) + AI·빅테크 낱말,
     한국어 site: 조건(연합뉴스·조선·중앙·동아·한경·매경·KBS·MBC 등) + AI·빅테크 낱말
   - 회사·인물별 검색 (엔비디아/젠슨 황, 오픈AI/샘 올트먼, 구글, 메타, 머스크/xAI/테슬라, 앤트로픽, MS, 애플, 삼성, 네이버, SK하이닉스) 한·영
2) 같은 소식은 제목 낱말 겹침으로 묶는다 (언어별). 회사 이름 자체는 겹침 계산에서 뺀다.
3) 묶음마다 매체 수, 주요 매체 수, 큰 사건 종류(인사·인수·규제·상장·감원·모델)를 센다.
   주요 매체가 많은 순으로 줄 세운다.

쓰는 곳: agent/hot.py("업계 큰 소식" 절), agent/model_watch.py(15분 감시, `breaking()`이 속보 기준을 넘는 것만).
같은 검색을 15분마다 반복하지 않게 결과를 임시 폴더(%TEMP%/tokenwar/news_cache.json)에 `refresh_minutes` 동안 둔다.

단독 실행: py -3.12 agent/news.py [-v] [--fresh]   묶음 상위 20개를 보여 준다 (기록 안 바꿈)
"""
import argparse
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("model_watch", {}).get("news", {})
UA = {"User-Agent": "Mozilla/5.0 (tokenwar-bot; +https://github.com/vmvm0406/tokenwar-agent)"}
CACHE = Path(tempfile.gettempdir()) / "tokenwar" / "news_cache.json"
RSS = "https://news.google.com/rss/search"
LANG = {"ko": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}, "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"}}

# 큰 사건 낱말 (제목에 있어야 "큰 소식"). 종류 이름은 hot.md·감시 출력에 그대로 나온다
BIG = {
    "인사": r"CEO|최고경영자|사임|사퇴|퇴진|퇴임|복귀|해임|경질|축출|선임|교체|물러|후임|resign\w*|step(s|ped)? down|oust\w*|fired|"
            r"comeback|return\w* as|reinstat\w*|successor|appoint\w*|names? new",
    "인수": r"인수|합병|매각|M&A|acquir\w+|acquisition|merger|takeover|buy(s|ing)? (out )?\w+ for",
    "규제": r"규제|소송|제소|고소|벌금|과징금|반독점|독점|제재|금지|청문회|기소|조사 착수|lawsuit|sues?|sued|antitrust|"
            r"ban(s|ned)?|fine[sd]?|probe|investigat\w+|regulat\w+|indict\w*|subpoena\w*|hearing",
    "상장·투자": r"상장|IPO|기업공개|투자 유치|시가총액|valuation|funding round|raises? \$",
    "감원": r"감원|해고|구조조정|정리해고|layoffs?|job cuts|cuts? \d[\d,]* jobs",
    "모델": r"새 모델|신모델|모델 (출시|공개)|(출시|공개)한 .{0,10}모델|launch\w* .{0,30}model|unveil\w*|"
            r"GPT-?\d|Gemini \d|Claude \w* ?\d|Grok \d|Llama \d",
}
BIG_RX = {k: re.compile(v, re.I) for k, v in BIG.items()}

# 겹침 계산에서 빼는 흔한 낱말 (어느 기사에나 나오는 것)
STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "with", "as", "at", "by", "is", "its", "his", "her",
        "from", "after", "over", "says", "say", "said", "report", "reports", "reportedly", "new", "how", "what", "why",
        "ai", "ceo", "inc", "co", "be", "it", "this", "that", "are", "was", "will", "could", "may", "us", "has", "have",
        "보도", "단독", "종합", "속보", "뉴스", "기자", "오늘", "이번", "지난", "관련", "위해", "통해"}


def _norm_source(s):
    return re.sub(r"[\s.]", "", (s or "").lower())


MAJOR = [(x, _norm_source(x)) for x in CFG.get("major_outlets", [])]
SAME = {"Wall Street Journal": "WSJ", "ZDNet Korea": "지디넷코리아"}


def major_name(source):
    """주요 매체면 대표 이름 (연합뉴스TV·연합뉴스 한민족센터 → 연합뉴스, Bloomberg.com → Bloomberg), 아니면 ''."""
    s = _norm_source(source)
    if s.startswith("미주"):  # 미주중앙일보 등 해외판은 빼고 본사만
        return ""
    for name, m in MAJOR:
        if m and m in s:
            return SAME.get(name, name)
    return ""


def _query(q, lang, hours):
    p = dict(LANG[lang], q=f"{q} when:{max(1, round(hours / 24))}d")
    r = requests.get(RSS, params=p, headers=UA, timeout=25)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
        src = it.find("source")
        source = (src.text or "").strip() if src is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        try:
            at = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            at = ""
        if title and link:
            out.append({"title": title, "url": link, "source": source, "at": at, "lang": lang})
    return out


def _searches():
    """(회사, 언어, 검색어) 목록. 회사 '' = 주요 매체 묶음 (회사는 제목에서 찾는다)."""
    out = []
    for lang in ("en", "ko"):
        sites = CFG.get(f"major_sites_{lang}") or []
        words = CFG.get(f"topic_words_{lang}") or []
        if sites and words:
            out.append(("", lang, f"({' OR '.join(words)}) ({' OR '.join('site:' + s for s in sites)})"))
    for company, q in (CFG.get("companies") or {}).items():
        for lang in ("ko", "en"):
            if q.get(lang):
                out.append((company, lang, q[lang]))
    return out


def _alias_rx():
    """회사 → 제목에서 그 회사를 찾는 정규식 (검색어의 낱말들)."""
    out = {}
    for company, q in (CFG.get("companies") or {}).items():
        words = set()
        for lang in ("ko", "en"):
            for w in re.findall(r'"([^"]+)"|([^\s()"]+)', q.get(lang, "")):
                w = (w[0] or w[1]).strip()
                if w and w.upper() not in ("OR", "AND"):
                    words.add(re.escape(w))
        if words:
            out[company] = re.compile("|".join(sorted(words, key=len, reverse=True)), re.I)
    return out


def tokens(title, drop=None):
    """제목 → 낱말 집합. 영어는 단어, 한글은 두 글자씩(조사가 붙어도 겹치게). drop(회사 이름)은 지운다."""
    t = title.lower()
    if drop:
        t = drop.sub(" ", t)
    t = re.sub(r"[^\w가-힣]+", " ", t)
    out = set()
    for w in t.split():
        if w in STOP:
            continue
        if re.search(r"[가-힣]", w):
            if len(w) == 1:
                continue
            out.update(w[i:i + 2] for i in range(len(w) - 1))
        elif len(w) >= 2 and not w.isdigit():
            out.add(w)
    return out - STOP


def similar(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b)) if inter >= 2 else 0.0


def fetch(fresh=False, verbose=False):
    """검색 결과 기사 목록 (캐시 refresh_minutes)."""
    hours = float(CFG.get("hours", 36))
    ttl = timedelta(minutes=float(CFG.get("refresh_minutes", 30)))
    now = datetime.now(timezone.utc)
    if not fresh and CACHE.exists():
        try:
            c = json.loads(CACHE.read_text(encoding="utf-8"))
            if now - datetime.fromisoformat(c["at"]) < ttl:
                if verbose:
                    print(f"  뉴스: 캐시 사용 ({c['at'][:16]}, 기사 {len(c['items'])}개)", file=sys.stderr)
                return c["items"]
        except (ValueError, KeyError, OSError):
            pass
    searches = _searches()
    items, fails = [], 0

    def run(s):
        company, lang, q = s
        try:
            return company, _query(q, lang, hours), None
        except Exception as e:
            return company, [], f"{type(e).__name__}: {str(e)[:80]}"

    with ThreadPoolExecutor(max_workers=6) as ex:
        for (company, got, err), s in zip(ex.map(run, searches), searches):
            if err:
                fails += 1
                if verbose:
                    print(f"  뉴스 검색 실패 [{s[1]}] {s[2][:40]}: {err}", file=sys.stderr)
            for it in got:
                it["company"] = company
            items += got
    if fails == len(searches):
        raise RuntimeError("Google News 검색을 하나도 읽지 못함")
    cut = now - timedelta(hours=hours)
    items = [it for it in items if not it["at"] or datetime.fromisoformat(it["at"]) >= cut]
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"at": now.isoformat(), "items": items}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    if verbose:
        print(f"  뉴스: 검색 {len(searches)}개, 기사 {len(items)}개 (실패 {fails})", file=sys.stderr)
    return items


def cluster(items):
    """같은 소식 묶기. 돌려주는 것: 묶음 목록 (주요 매체 수 → 매체 수 순)."""
    alias = _alias_rx()
    any_alias = re.compile("|".join(r.pattern for r in alias.values()), re.I) if alias else None
    # 기사마다 회사 정하기 (회사 검색이면 그 회사, 주요 매체 묶음이면 제목에서)
    seen_url, arts = set(), []
    for it in items:
        if it["url"] in seen_url:
            continue
        seen_url.add(it["url"])
        company = it.get("company") or next((c for c, rx in alias.items() if rx.search(it["title"])), "")
        if not company:
            continue  # 주요 매체 묶음인데 우리가 보는 회사가 아님
        it = dict(it, company=company, major=major_name(it["source"]))
        it["tok"] = tokens(it["title"], any_alias)
        arts.append(it)
    arts.sort(key=lambda a: (not a["major"], a["at"]), reverse=False)
    thr = float(CFG.get("similar", 0.5))
    groups = []
    for a in arts:
        for g in groups:
            if g["lang"] == a["lang"] and similar(a["tok"], g["tok"]) >= thr:
                g["items"].append(a)
                break
        else:
            groups.append({"lang": a["lang"], "tok": a["tok"], "items": [a]})
    out = []
    for g in groups:
        its = g["items"]
        sources = {_norm_source(i["source"]) for i in its if i["source"]}
        majors = sorted({i["major"] for i in its if i["major"]})
        # 제목에 나온 회사·인물 (기사 수 순). 대표 회사 = 가장 많이 나온 것, entities = 1/3 이상 기사에 나온 것
        companies = {c: sum(1 for i in its if rx.search(i["title"])) for c, rx in alias.items()}
        companies = {c: n for c, n in companies.items() if n}
        if not companies:
            companies = {its[0]["company"]: 1}
        entities = sorted(c for c, n in companies.items() if n >= max(1, len(its) / 3))
        lead = next((i for i in its if i["major"]), its[0])
        kinds = [k for k, rx in BIG_RX.items() if sum(1 for i in its if rx.search(i["title"])) >= max(1, len(its) // 3)]
        out.append({"company": max(companies, key=companies.get), "entities": entities or [max(companies, key=companies.get)],
                    "lang": g["lang"], "title": lead["title"],
                    "url": lead["url"], "source": lead["source"], "outlets": len(sources), "majors": majors,
                    "kinds": kinds, "tok": sorted(g["tok"]), "first": min(i["at"] for i in its if i["at"]) if any(i["at"] for i in its) else "",
                    "titles": [f"{i['source']}: {i['title']}" for i in its[:4]]})
    out.sort(key=lambda c: (len(c["majors"]), c["outlets"]), reverse=True)
    return out


def collect(fresh=False, verbose=False):
    return cluster(fetch(fresh=fresh, verbose=verbose))


def breaking(clusters):
    """속보 기준을 넘는 묶음: 큰 사건 낱말이 있고, 주요 매체 min_majors곳 이상 (또는 매체 min_outlets곳 이상 + 주요 매체 1곳)."""
    mm, mo = int(CFG.get("min_majors", 3)), int(CFG.get("min_outlets", 8))
    return [c for c in clusters if c["kinds"] and (len(c["majors"]) >= mm or (c["outlets"] >= mo and c["majors"]))]


def line(c):
    kinds = "·".join(c["kinds"]) or "-"
    return (f"{c['company']} · 매체 {c['outlets']}곳(주요 {len(c['majors'])}: {', '.join(c['majors'][:5])}) · {kinds} — "
            f"{c['title']} ({c['url']})")


def main():
    ap = argparse.ArgumentParser(description="업계 큰 소식 묶음 보기")
    ap.add_argument("--fresh", action="store_true", help="캐시 무시하고 다시 검색")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-n", type=int, default=20)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cl = collect(fresh=args.fresh, verbose=args.verbose)
    br = {id(c) for c in breaking(cl)}
    for c in cl[: args.n]:
        print(("[속보 기준] " if id(c) in br else "") + line(c))
        if args.verbose:
            for t in c["titles"]:
                print("     ", t)


if __name__ == "__main__":
    main()
