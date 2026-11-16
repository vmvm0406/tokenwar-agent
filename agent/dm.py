"""따라 하기·질문 게시물의 댓글 자동 DM 준비물 만들기.

post.json에 `dm`이 있으면 두 가지를 만든다 (STYLE_GUIDE 7-1, TEMPLATES "댓글 자동 DM"):
  1. 게시물 폴더의 dm.md — 외부 자동 DM 도구(config.json dm.tool, 지금은 Zorcha)에 붙여 넣을 설정 메모.
     운영자가 게시 후 이 메모대로 도구에 자동화를 하나 만든다. (도구 계정·비밀번호는 여기에 없다)
  2. 자료 안내 페이지 — 공개 저장소 GitHub Pages(docs/p/<게시물 id>/index.html).
     카드에 나온 프롬프트 전체 + dm.page의 추가 자료. DM 안 링크가 이 페이지를 가리킨다.
     예시 폴더(samples/)는 docs에 올리지 않고 폴더 안 page.html로만 만든다(미리보기).
  3. 자료실 — docs/p/index.html. docs/p/<id>/ 안내 페이지 전체 목록(최신순, 제목·날짜·한 줄 설명).
     인스타 프로필 링크에 거는 주소(<pages_base>/p/). 안내 페이지를 만들 때마다 다시 만든다(예시 폴더는 빼고).

사용법: py -3.12 agent/dm.py <게시물 폴더>   (render.py가 렌더링할 때 자동으로 부른다)
        py -3.12 agent/dm.py --index       (자료실만 다시 만들기)
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DMC = CONFIG.get("dm", {})
B = CONFIG["brand"]

DEFAULTS = {
    "keyword": DMC.get("keyword", "자료"),
    "comment_reply": "DM으로 보내 드렸어요. 안 보이면 메시지 요청함을 확인해 주세요.",
    "follow_text": "팔로우한 분께만 자료를 보내 드려요. 팔로우하신 뒤 이 게시물에 다시 '{kw}'라고 댓글을 남겨 주시면 바로 보내 드릴게요.",
}


def esc(s):
    return html.escape(str(s or ""))


def page_url(post):
    return f"{DMC.get('pages_base', '').rstrip('/')}/p/{post['id']}/"


def is_sample(folder):
    return "/samples/" in str(Path(folder).resolve()).replace("\\", "/")


def dm_conf(post):
    d = dict(DEFAULTS)
    d.update({k: v for k, v in (post.get("dm") or {}).items() if v not in (None, "")})
    d["follow_text"] = d["follow_text"].replace("{kw}", d["keyword"])
    return d


def steps_from_slides(post):
    """카드의 순서 장(num이 있는 body·prompt 장)을 안내 페이지 단계로."""
    out = []
    for s in post["slides"]:
        if s.get("kind") not in ("body", "prompt") or not (s.get("num") or s.get("kind") == "prompt"):
            continue
        prompts = [p for p in (s.get("prompts") or [s.get("prompt")]) if p]
        out.append({"label": s.get("prompt_label") or s.get("num_note") or "",
                    "title": (s.get("heading") or "").replace("\n", " "),
                    "text": s.get("body", ""), "prompts": prompts})
    return out


def checklist_from_slides(post):
    items = []
    for s in post["slides"]:
        if s.get("kind") == "steps":
            items += [f'{it["title"]}: {it.get("text", "")}'.rstrip(": ") for it in s["items"]]
    return items


# ---------- 1. 도구에 붙여 넣을 설정 메모 ----------

def memo_md(post):
    d = dm_conf(post)
    url = page_url(post)
    cover = next(s for s in post["slides"] if s["kind"] == "cover")
    title = cover.get("title", "").replace("\n", " ")
    tool = DMC.get("tool", "Zorcha")
    lines = [
        f"# DM 설정 메모 — {post['id']}",
        "",
        f"게시물이 올라간 뒤 {tool}에서 이 게시물용 자동화(Comment to DM)를 하나 만든다. 아래 칸을 그대로 붙여 넣는다.",
        "",
        f"| {tool} 칸 | 넣을 값 |",
        "|---|---|",
        f"| 게시물 | {post.get('publish_at', '')[:16].replace('T', ' ')} 게시물 「{title}」 |",
        f"| 키워드 (댓글에 이 말이 들어가면) | `{d['keyword']}` |",
        f"| 댓글 공개 답글 | {d['comment_reply']} |",
        "| Ask for Follow | 켬 |",
        f"| 팔로우 안 한 사람에게 보낼 확인 DM | {d['follow_text']} |",
        "| 팔로우 요청 버튼 | 프로필 보기 |",
        "| 보낼 DM 문구 | 아래 \"DM 문구\" 전체 |",
        f"| 링크 버튼 이름 | {d.get('button', '자료 보기')} |",
        f"| 링크 주소 | {url} |",
        "",
        "## DM 문구",
        "",
        "```",
        d.get("message", "").strip(),
        "```",
        "",
        "## 확인",
        "",
        f"- 링크가 열리는지: {url} (게시물이 main에 합쳐지고 GitHub Pages가 갱신된 뒤 1~2분)",
        "- 다른 계정(팔로우 안 한 계정)으로 댓글을 달아, 확인 DM(팔로우하고 다시 댓글)이 오는지, 팔로우 뒤 다시 댓글을 달면 자료가 오는지 본다.",
        "- DM 끝에 도구 홍보 문구가 붙는지 본다 (붙으면 NEXT.md에 적는다).",
        "",
    ]
    return "\n".join(lines)


# ---------- 2. 자료 안내 페이지 ----------

PAGE_CSS = """
:root{--bg:BG;--fg:TEXT;--ac:ACCENT;--mu:MUTED}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font-family:'Wanted Sans Variable','Wanted Sans',-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  line-height:1.65;word-break:keep-all;overflow-wrap:break-word}
main{max-width:680px;margin:0 auto;padding:40px 16px 64px}
.brand{font-family:'Black Han Sans',sans-serif;color:var(--ac);font-size:20px;letter-spacing:.01em}
h1{font-family:'Black Han Sans',sans-serif;font-weight:400;font-size:clamp(30px,8vw,44px);line-height:1.2;margin:18px 0 12px}
h1 .hl{color:var(--ac)}
.intro{color:#CFD6D2;font-size:18px;margin:0 0 28px}
.rule{height:4px;background:var(--ac);margin:28px 0}
.step{border-top:2px solid #2A3530;padding:22px 0}
.step .k{font-family:'Black Han Sans',sans-serif;color:var(--ac);font-size:32px;line-height:1}
.step .lb{color:var(--mu);font-weight:700;font-size:15px;margin-left:10px}
h2{font-family:'Black Han Sans',sans-serif;font-weight:400;font-size:24px;line-height:1.3;margin:10px 0 6px}
h3{font-family:'Black Han Sans',sans-serif;font-weight:400;font-size:22px;margin:0 0 10px}
p{margin:6px 0;color:#CFD6D2}
.pr{position:relative;margin:12px 0 4px;border:2px solid var(--ac);background:#0E1310}
.pr pre{margin:0;padding:16px 16px 52px;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere;
  font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-size:15px;line-height:1.6;color:var(--fg)}
.pr button{position:absolute;right:0;bottom:0;border:0;background:var(--ac);color:var(--bg);
  font-family:inherit;font-weight:700;font-size:15px;line-height:1;padding:12px 16px;cursor:pointer}
ul{padding-left:20px;color:#CFD6D2}
.src{color:var(--mu);font-size:14px;border-top:2px solid #2A3530;padding-top:16px;margin-top:32px}
.src a{color:var(--mu)}
.foot{margin-top:28px;font-weight:700}
.foot a{color:var(--ac)}
"""


def page_html(post):
    d = dm_conf(post)
    pg = d.get("page") or {}
    cover = next(s for s in post["slides"] if s["kind"] == "cover")
    title = esc(cover.get("title", "")).replace("\n", "<br>")
    if cover.get("highlight"):
        h = esc(cover["highlight"])
        title = title.replace(h, f'<span class="hl">{h}</span>', 1)
    css = PAGE_CSS
    for k in ("ACCENT", "MUTED", "TEXT", "BG"):
        css = css.replace(k, B[k.lower()])

    def prompt_box(p):
        return (f'<div class="pr"><pre>{esc(p)}</pre>'
                '<button type="button" onclick="cp(this)">복사</button></div>')

    parts = []
    for i, st in enumerate(steps_from_slides(post), 1):
        lb = f'<span class="lb">{esc(st["label"])}</span>' if st["label"] else ""
        boxes = "".join(prompt_box(p) for p in st["prompts"])
        parts.append(f'<section class="step"><span class="k">{i:02d}</span>{lb}<h2>{esc(st["title"])}</h2>'
                     f'{boxes}<p>{esc(st["text"])}</p></section>')
    extra = ""
    if pg.get("extra"):
        rows = "".join(
            f'<section class="step"><h2>{esc(x.get("title", ""))}</h2>{prompt_box(x["prompt"])}'
            f'{"<p>" + esc(x["note"]) + "</p>" if x.get("note") else ""}</section>' for x in pg["extra"])
        extra = f'<div class="rule"></div><h3>더 써 볼 문장</h3>{rows}'
    result = f'<div class="rule"></div><h3>직접 해 본 결과</h3><p>{esc(pg["result"])}</p>' if pg.get("result") else ""
    cautions = list(pg.get("caution") or []) + checklist_from_slides(post)
    caut = ("<div class=\"rule\"></div><h3>주의할 점</h3><ul>" + "".join(f"<li>{esc(c)}</li>" for c in cautions) + "</ul>"
            if cautions else "")
    srcs = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a></li>' for s in post["sources"])
    handle = CONFIG["handle"]
    intro = esc(pg.get("intro") or cover.get("sub", ""))
    desc = esc((pg.get("intro") or cover.get("sub", ""))[:120])
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cover.get("title", "").replace(chr(10), " "))} · 토큰전쟁</title>
<meta name="description" content="{desc}">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main>
<div class="brand">TOKEN WAR</div>
<h1>{title}</h1>
<p class="intro">{intro}</p>
{"".join(parts)}
{result}{extra}{caut}
<div class="src">출처<ul>{srcs}</ul>{esc(post["date"].replace("-", "."))} 기준. 결과는 직접 해 본 것이고, AI 답은 그때그때 달라질 수 있습니다.</div>
<p class="foot">다른 자료는 <a href="../">자료실</a>에서. 매일 AI 소식은 <a href="https://www.instagram.com/{esc(handle.lstrip("@"))}/">{esc(handle)}</a></p>
</main>
<script>
function cp(b){{const t=b.previousElementSibling.innerText;
(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>{{b.textContent='복사됨';setTimeout(()=>b.textContent='복사',1500)}})
.catch(()=>{{const r=document.createRange();r.selectNodeContents(b.previousElementSibling);const s=getSelection();s.removeAllRanges();s.addRange(r)}})}}
</script>
</body></html>
"""


# ---------- 3. 자료실 (안내 페이지 목록) ----------

PAGES_DIR = ROOT / "docs" / "p"

INDEX_CSS = """
:root{--bg:BG;--fg:TEXT;--ac:ACCENT;--mu:MUTED}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font-family:'Wanted Sans Variable','Wanted Sans',-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  line-height:1.6;word-break:keep-all;overflow-wrap:break-word}
main{max-width:680px;margin:0 auto;padding:40px 16px 64px}
.brand{font-family:'Black Han Sans',sans-serif;color:var(--ac);font-size:20px;letter-spacing:.01em}
h1{font-family:'Black Han Sans',sans-serif;font-weight:400;font-size:clamp(34px,9vw,48px);line-height:1.15;margin:18px 0 10px}
.intro{color:#CFD6D2;font-size:17px;margin:0}
.rule{height:4px;background:var(--ac);margin:24px 0 0}
ol{list-style:none;margin:0;padding:0}
li{border-bottom:2px solid #2A3530}
li a{display:block;padding:18px 0;color:inherit;text-decoration:none}
li a:hover h2,li a:focus h2{color:var(--ac)}
.d{color:var(--ac);font-weight:700;font-size:14px;letter-spacing:.02em}
h2{font-family:'Black Han Sans',sans-serif;font-weight:400;font-size:22px;line-height:1.3;margin:4px 0}
p{margin:0;color:#CFD6D2;font-size:15px}
.foot{margin-top:28px;font-weight:700;color:var(--fg);font-size:16px}
.foot a{color:var(--ac)}
"""


def _meta(text, pat):
    m = re.search(pat, text, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def one_line(desc, limit=70):
    """설명의 첫 문장, 길면 자른다."""
    first = re.split(r"(?<=[.!?])\s", desc.strip(), maxsplit=1)[0]
    return first if len(first) <= limit else first[:limit - 1].rstrip() + "…"


def page_entries(pages_dir=PAGES_DIR):
    """docs/p/<id>/index.html에서 제목·날짜·설명을 읽어 최신순 목록으로."""
    out = []
    for f in sorted(Path(pages_dir).glob("*/index.html")):
        t = f.read_text(encoding="utf-8")
        pid = f.parent.name
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", pid)
        out.append({
            "id": pid,
            "href": f"{pid}/",
            "date": f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else "",
            "title": re.sub(r"\s*·\s*토큰전쟁\s*$", "", _meta(t, r"<title>(.*?)</title>")),
            "desc": one_line(_meta(t, r'<meta name="description" content="(.*?)">')),
        })
    return sorted(out, key=lambda e: e["id"], reverse=True)


def index_html(entries):
    css = INDEX_CSS
    for k in ("ACCENT", "MUTED", "TEXT", "BG"):
        css = css.replace(k, B[k.lower()])
    handle = CONFIG["handle"]
    rows = "".join(
        f'<li><a href="{esc(e["href"])}"><span class="d">{esc(e["date"])}</span>'
        f'<h2>{esc(e["title"])}</h2><p>{esc(e["desc"])}</p></a></li>' for e in entries)
    if not rows:
        rows = "<li><p>아직 올린 자료가 없습니다.</p></li>"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>자료실 · 토큰전쟁</title>
<meta name="description" content="토큰전쟁 게시물에서 소개한 프롬프트·순서·자료를 모았습니다. 최신순.">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main>
<div class="brand">TOKEN WAR</div>
<h1>자료실</h1>
<p class="intro">게시물에서 소개한 프롬프트와 순서를 모았습니다. 최신순으로 {len(entries)}개. 댓글 DM을 못 받으셨어도 여기서 보실 수 있습니다.</p>
<div class="rule"></div>
<ol>{rows}</ol>
<p class="foot">매일 AI 소식은 <a href="https://www.instagram.com/{esc(handle.lstrip("@"))}/">{esc(handle)}</a></p>
</main></body></html>
"""


def write_index(pages_dir=PAGES_DIR):
    """docs/p/index.html(자료실)을 다시 만든다."""
    pages_dir = Path(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    out = pages_dir / "index.html"
    out.write_text(index_html(page_entries(pages_dir)), encoding="utf-8")
    return out


def make_dm(post, folder):
    """dm이 있으면 dm.md와 안내 페이지를 만든다. 만든 파일 경로 목록 반환."""
    if not post.get("dm"):
        return []
    folder = Path(folder)
    memo = folder / "dm.md"
    memo.write_text(memo_md(post), encoding="utf-8")
    if is_sample(folder):
        page = folder / "page.html"
    else:
        page = ROOT / "docs" / "p" / post["id"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(page_html(post), encoding="utf-8")
    made = [memo, page]
    if not is_sample(folder):
        made.append(write_index())
    return made


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--index":
        print("만듦:", write_index())
        sys.exit(0)
    f = Path(sys.argv[1])
    for p in make_dm(json.loads((f / "post.json").read_text(encoding="utf-8")), f):
        print("만듦:", p)
