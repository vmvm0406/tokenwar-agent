"""따라 하기·질문 게시물의 댓글 자동 DM 준비물 만들기.

post.json에 `dm`이 있으면 두 가지를 만든다 (STYLE_GUIDE 7-1, TEMPLATES "댓글 자동 DM"):
  1. 게시물 폴더의 dm.md — 외부 자동 DM 도구(config.json dm.tool, 지금은 Zorcha)에 붙여 넣을 설정 메모.
     운영자가 게시 후 이 메모대로 도구에 자동화를 하나 만든다. (도구 계정·비밀번호는 여기에 없다)
  2. 자료 안내 페이지 — 공개 저장소 GitHub Pages(docs/p/<게시물 id>/index.html).
     카드에 나온 프롬프트 전체 + dm.page의 추가 자료. DM 안 링크가 이 페이지를 가리킨다.
     목록형 자료 릴스(post.list)는 복사용 프롬프트 없이 '쓰는 법'(용어를 요청 문장 어디에 넣는지) + 용어 목록 + 예시 그림.
     예시 폴더(samples/)는 docs에 올리지 않고 폴더 안 page.html로만 만든다(미리보기).
  안내 페이지 목록(자료실)은 만들지 않는다 (운영자 결정 2026-11-16: 팔로우 안 한 사람도 받게 되므로).
  주소는 DM으로만 알리고, 검색 제외(noindex, docs/robots.txt).

사용법: py -3.12 agent/dm.py <게시물 폴더>   (render.py가 렌더링할 때 자동으로 부른다)
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
    # 공개 답글은 여러 개를 돌려 쓴다 (같은 말만 반복하면 스팸처럼 보임, 운영자 결정 2026-11-16)
    # 말투: 친근하지만 정돈되게 '~드려요/~해 보세요'. '~하십시오/~바랍니다' 금지, 느낌표 금지, 이모지는 문구마다 1개, '안 보이면' 대신 '보이지 않으시면' (운영자 결정 2026-11-17, STYLE_GUIDE 7-1)
    "comment_reply": [
        "DM으로 보내 드렸어요 📩 보이지 않으시면 메시지 요청함을 확인해 주세요.",
        "자료 보내 드렸어요 🙌 DM에서 확인해 보세요.",
        "방금 DM 드렸어요 ✉️ 처음 받으시면 요청함에 있을 수 있어요.",
        "보내 드렸어요 😊 직접 만들어 보시고 결과도 들려주세요.",
    ],
    # 반응 조건이 '아무 댓글'이라 키워드를 다시 쓰라고 하지 않는다 (운영자 결정 2026-11-16)
    "follow_text": "자료는 팔로우한 분께 보내 드려요 🙏 팔로우하신 뒤 이 게시물에 댓글을 한 번 더 남겨 주시면 바로 보내 드릴게요.",
}
REPLIES_MAX = 4

# 자료 페이지에 쓰지 않는 말 (운영자 지적 2026-11-16, STYLE_GUIDE 7-1): 날짜·제작 과정·테스트 환경.
# 페이지에는 따라 할 문장, 준비물, 단계, 결과 예시만. 이런 문장이 post.json에 남아 있어도 페이지에서는 문장째 뺀다
# (프롬프트·명령 상자는 건드리지 않는다). checks.py도 같은 표현을 경고한다.
PROCESS_RE = re.compile(
    r"\d+\s*월\s*\d+\s*일\s*(?:에|기준|확인|테스트|현재)"
    r"|직접\s*(?:넣어|돌려|실행해|만들어|해|써|플레이해)\s*(?:본|봤|보았)"
    r"|(?:넣어|돌려|실행해)\s*봤"
    r"|저희"
    r"|테스트\s*(?:환경|일자|결과)|테스트(?:했|하지|에서|에\s*사용|한\s*결과)"
    r"|확인\s*(?:일자|환경)|미확인\s*범위|확인하지\s*않았|해\s*보지\s*않았"
    r"|걸렸습니다|작성\s*시점")
# 출처 목록에서 빼는 우리 제작 기록, 이름에서 지우는 확인 날짜
OWN_SRC_RE = re.compile(r"직접\s*(?:실행|사용|제작)|로\s*실행\s*\(|제작\s*기록")
OWN_DATE_RE = re.compile(r"\s*\(\d+\s*월\s*\d+\s*일\s*확인\)")
# 예전 항목형 결과([{"k": "테스트 일자:", "v": ...}])에서 통째로 빼는 항목 이름
META_KEY_RE = re.compile(r"일자|날짜|환경|미확인|범위|버전|실행|등록|제작")


# 목록형 자료 릴스(post.list) 자료 페이지: 복사해 붙이는 완성 프롬프트는 싣지 않고, 용어를 요청 문장에 어떻게 넣는지만
# 설명한다 (운영자 결정 2026-11-17, STYLE_GUIDE 7-1). 종류별 '쓰는 법' 기본 문구. 게시물 id의 'list-<종류>'로 고르고,
# post.json dm.page.usage(문장 하나나 목록)가 있으면 그것을 쓴다. dm.page.kind로 종류를 직접 정해도 된다.
LIST_USAGE = {
    "lighting": [
        "요청 문장에는 장면(누가, 어디서, 무엇을 하는지)을 먼저 쓰고, 끝에 조명 용어를 영어로 붙여 보세요.",
        "조명 용어는 한두 개면 충분해요. 하나씩 바꿔 넣으면 같은 장면에서 분위기만 달라져요.",
        "이미 만든 그림의 조명만 바꾸고 싶다면 그 그림을 함께 올리고, 조명만 바꿔 달라는 말 뒤에 용어를 붙여 보세요.",
        "AI 영상 도구에서도 똑같아요. 장면 설명 끝에 조명 용어를 붙이면 돼요.",
    ],
    "camera": [
        "요청 문장에는 장면(누가, 어디서, 무엇을 하는지)을 먼저 쓰고, 끝에 카메라 용어를 영어로 붙여 보세요.",
        "화면 크기(클로즈업, 와이드 샷), 앵글(로우 앵글, 하이 앵글), 초점(얕은 심도) 가운데 한두 개만 골라 보세요.",
        "이미 만든 그림의 구도만 바꾸고 싶다면 그 그림을 함께 올리고, 카메라만 바꿔 달라는 말 뒤에 용어를 붙여 보세요.",
        "AI 영상 도구에서도 똑같아요. 카메라 움직임 용어도 장면 설명 끝에 붙이면 돼요.",
    ],
    "art-style": [
        "사진을 바꿀 때는 사진을 올리고, 이 사진을 다른 그림으로 다시 그려 달라는 말 뒤에 그림체 이름을 영어로 붙여 보세요.",
        "새로 그릴 때는 장면(누가, 어디서, 무엇을 하는지)을 먼저 쓰고, 끝에 그림체 이름을 붙이면 돼요.",
        "그림체는 한 번에 하나만 넣어 보세요. 이름만 바꿔 넣어도 같은 장면이 전혀 다른 그림이 돼요.",
        "AI 영상 도구에서도 똑같아요. 장면 설명 끝에 그림체 이름을 붙이면 돼요.",
    ],
    "luxury-photo": [
        "요청 문장에는 찍을 대상(상품, 인물)과 장면을 먼저 쓰고, 끝에 촬영 용어를 영어로 붙여 보세요.",
        "사진 느낌(시네마틱), 배경(대리석, 벨벳), 렌즈(85mm)처럼 성격이 다른 용어 가운데 한두 개만 골라 보세요.",
        "가지고 있는 상품 사진을 바꾸고 싶다면 사진을 함께 올리고, 배경이나 분위기만 바꿔 달라는 말 뒤에 용어를 붙여 보세요.",
        "AI 영상 도구에서도 똑같아요. 장면 설명 끝에 촬영 용어를 붙이면 돼요.",
    ],
}
LIST_USAGE_DEFAULT = [
    "요청 문장에는 장면(누가, 어디서, 무엇을 하는지)을 먼저 쓰고, 끝에 영어 용어를 붙여 보세요.",
    "용어는 한두 개면 충분해요. 하나씩 바꿔 넣으면 같은 장면에서 그 부분만 달라져요.",
    "AI 영상 도구에서도 똑같아요. 장면 설명 끝에 용어를 붙이면 돼요.",
]
# 자료 페이지 낱말 (운영자 결정 2026-11-17: '만드는 사람' 말고 '제작자'). 뒤 조사도 받침 없는 말에 맞춘다.
WORD_RE = re.compile(r"만드는\s*사람(이|은|을|과)?(?![가-힣])|만드는\s*사람")
WORD_JOSA = {"이": "가", "은": "는", "을": "를", "과": "와"}
# 목록형 페이지 글에서 빼는 복사 안내: "(복사 버튼)"은 지우고, '복사'가 남은 문장은 문장째 뺀다
COPY_PAREN_RE = re.compile(r"\s*\(\s*복사\s*버튼\s*\)")


def words(text):
    """자료 페이지 낱말 바꾸기: 만드는 사람 → 제작자."""
    return WORD_RE.sub(lambda m: "제작자" + WORD_JOSA.get(m.group(1) or "", m.group(1) or ""), str(text or ""))


def no_copy(text):
    """목록형 자료 페이지 글에서 복사 안내를 뺀다 (복사해 붙이는 프롬프트를 싣지 않으므로)."""
    t = COPY_PAREN_RE.sub("", str(text or ""))
    parts = re.split(r"(?<=[.!?])\s+", t.strip())
    return " ".join(x for x in parts if x and "복사" not in x).strip()


def list_kind(post):
    k = ((post.get("dm") or {}).get("page") or {}).get("kind")
    if k:
        return k
    m = re.search(r"list-(.+)$", str(post.get("id", "")))
    return m.group(1) if m else ""


def list_usage(post):
    """목록형 자료 페이지 '쓰는 법' 문장 목록. dm.page.usage(문장 하나나 목록)가 있으면 그것, 없으면 종류별 기본."""
    u = ((post.get("dm") or {}).get("page") or {}).get("usage")
    if u:
        return [u] if isinstance(u, str) else list(u)
    return LIST_USAGE.get(list_kind(post), LIST_USAGE_DEFAULT)


def process_phrases(text):
    """글 안의 날짜·제작 과정·테스트 환경 표현 목록 (checks.py 경고용)."""
    return [m.group(0) for m in PROCESS_RE.finditer(str(text or ""))]


# 딱딱한 명령 말투 → 친근한 말투 (운영자 결정 2026-11-17: DM·자료 페이지는 '~해 보세요/~드려요', STYLE_GUIDE 7-1).
# '확인하십시오' → '확인하세요', '닫지 마십시오' → '닫지 마세요', '확인하시기 바랍니다' → '확인하세요'.
# 승인된 post.json을 고치지 않고도 페이지에서는 바뀌게 clean()에서 함께 바꾼다. checks.py는 원문을 경고한다.
STIFF_RE = re.compile(r"십시오|시기\s*바랍니다")
STIFF_WARN_RE = re.compile(r"십시오|바랍니다|하시오")


def soften(text):
    return STIFF_RE.sub("세요", str(text or ""))


def stiff_phrases(text):
    """글 안의 딱딱한 명령 말투 목록 (checks.py 경고용)."""
    return [m.group(0) for m in STIFF_WARN_RE.finditer(str(text or ""))]


def clean(text):
    """자료 페이지 글에서 날짜·제작 과정·테스트 환경이 든 문장을 빼고, 딱딱한 명령 말투를 친근하게 바꾼다.
    문장은 . ! ? 뒤에서 나눈다."""
    t = soften(text).strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    return " ".join(x for x in parts if x and not PROCESS_RE.search(x)).strip()


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
    # 예전 게시물의 "다시 '자료'라고 댓글을" → "다시 댓글을" (이제 아무 댓글에나 반응)
    d["follow_text"] = re.sub(r"다시\s*['‘\"“]" + re.escape(d["keyword"]) + r"['’\"”]\s*(?:이?라고\s*)?댓글", "다시 댓글", d["follow_text"])
    d["comment_replies"] = replies_of(d.get("comment_reply"))
    return d


def replies_of(v):
    """공개 답글 문구 목록. 게시물에 한두 개만 있으면 기본 문구로 채워 3~4개를 돌려 쓰게 한다."""
    mine = [v] if isinstance(v, str) else list(v or [])
    out = []
    for x in [str(x).strip() for x in mine] + DEFAULTS["comment_reply"]:
        if x and x not in out:
            out.append(x)
    return out[:max(REPLIES_MAX, len([x for x in mine if x]))]


def cover_of(post):
    """제목을 가져올 표지. 장이 없는 릴스(목록형 자료 릴스 등)는 post.title로 만든다."""
    c = next((s for s in post.get("slides") or [] if s.get("kind") == "cover"), None)
    return c or {"title": post.get("title", ""), "highlight": post.get("highlight"), "sub": ""}


def steps_from_slides(post):
    """카드의 순서 장(num이 있는 body·prompt 장)을 안내 페이지 단계로."""
    out = []
    for s in post.get("slides") or []:
        if s.get("kind") not in ("body", "prompt") or not (s.get("num") or s.get("kind") == "prompt"):
            continue
        prompts = [p for p in (s.get("prompts") or [s.get("prompt")]) if p]
        out.append({"num": s.get("num"), "label": s.get("prompt_label") or s.get("num_note") or "",
                    "title": (s.get("heading") or "").replace("\n", " "),
                    "text": s.get("body", ""), "prompts": prompts})
    return out


def page_steps(post):
    """카드 순서 장 + dm.page의 페이지 전용 단계(모두 선택)를 합친다.
    setup: {"before": <카드 장 num>, "steps": [{label, title, text, prompts, groups: [{name, text, prompts, src: {name, url} 또는 그 목록}]}]}
           여러 곳에 넣으려면 이런 묶음의 목록. before가 없거나 맞는 장이 없으면 맨 앞.
    skip: [카드 장 num] 페이지에서 뺄 장 (카드·영상은 그대로)
    append: [{"num": 카드 장 num, "text": 덧붙일 글, "groups": [...]}] 카드 장 단계 뒤에 페이지에서만 덧붙임"""
    pg = dm_conf(post).get("page") or {}
    skip = set(pg.get("skip") or [])
    adds = {a.get("num"): a for a in pg.get("append") or []}
    steps = []
    for st in steps_from_slides(post):
        if st.get("num") in skip:
            continue
        a = adds.get(st.get("num"))
        if a:
            st = dict(st, more=a.get("text", ""), groups=a.get("groups") or [])
        steps.append(st)
    setup = pg.get("setup") or []
    for blk in ([setup] if isinstance(setup, dict) else setup):
        extra = blk.get("steps") or []
        if not extra:
            continue
        at = next((i for i, st in enumerate(steps) if st.get("num") == blk.get("before")), 0)
        steps = steps[:at] + extra + steps[at:]
    return steps


# ---------- 1. 도구에 붙여 넣을 설정 메모 ----------

def memo_md(post, permalink=""):
    """도구에 붙여 넣을 설정 메모 (dm.md). 게시 직후 알림(이슈 본문)에도 그대로 쓴다: permalink가 있으면 넣는다."""
    d = dm_conf(post)
    url = page_url(post)
    cover = cover_of(post)
    title = cover.get("title", "").replace("\n", " ")
    tool = DMC.get("tool", "Zorcha")
    when = post.get("publish_at", "")[:16].replace("T", " ")
    target = f"{when} 게시물 「{title}」" + (f" {permalink}" if permalink else "")
    replies = d["comment_replies"]
    lines = [
        f"# DM 설정 메모 — {post['id']}",
        "",
        f"게시물이 올라간 뒤 {tool}에서 이 게시물용 자동화(Comment to DM)를 하나 만든다. 아래 칸을 그대로 붙여 넣는다.",
        "",
        f"| {tool} 칸 | 넣을 값 |",
        "|---|---|",
        f"| 게시물 | {target} |",
        "| 반응 조건 | 아무 댓글(Any comment). 키워드를 맞추지 않아도 된다 |",
        f"| (참고) 화면·캡션 안내 키워드 | `{d['keyword']}` (다른 말을 써도 받는다) |",
        "| Ask for Follow | 켬 |",
        f"| 팔로우 안 한 사람에게 보낼 확인 DM | {d['follow_text']} |",
        "| 팔로우 요청 버튼 | 프로필 보기 |",
        "| 댓글 공개 답글 | 켬. 아래 \"공개 답글 문구\"를 모두 넣어 돌려 쓴다 (같은 말만 반복하면 스팸처럼 보임) |",
        "| 보낼 DM 문구 | 아래 \"DM 문구\" 전체 |",
        f"| 링크 버튼 이름 | {d.get('button', '자료 보기')} |",
        f"| 링크 주소 (자료 페이지) | {url} |",
        "",
        "## 공개 답글 문구 (돌려 쓰기)",
        "",
        *[f"{'①②③④⑤⑥⑦⑧'[i] if i < 8 else str(i + 1) + '.'} {r}" for i, r in enumerate(replies)],
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
        "- 다른 계정(팔로우 안 한 계정)으로 아무 댓글이나 달아, 확인 DM(팔로우하고 다시 댓글)이 오는지, 팔로우 뒤 다시 댓글을 달면 자료가 오는지 본다.",
        "- 공개 답글이 달리는지, 문구가 돌아가며 바뀌는지 본다.",
        "- DM 끝에 도구 홍보 문구가 붙는지 본다 (붙으면 NEXT.md에 적는다).",
        "",
    ]
    return "\n".join(lines)


def notice(post, permalink="", memo_path=""):
    """게시 직후 운영자 알림 (publish.py가 GitHub 이슈·data/zorcha_todo.md로 보낸다). (제목, 본문) 반환."""
    title = cover_of(post).get("title", "").replace("\n", " ").strip() or post["id"]
    head = [f"인스타에 올라갔습니다: {permalink or '(주소 확인 실패, 계정에서 확인)'}", "",
            f"지금 {DMC.get('tool', 'Zorcha')}에서 이 게시물용 자동화를 만들어 주세요. 그 전에 달린 댓글에는 DM이 가지 않습니다.",
            "다 만들면 이 이슈를 닫아 주세요 (닫으면 이 컴퓨터의 알림 목록에서도 빠집니다)."]
    if memo_path:
        head.append(f"설정 메모 파일: `{memo_path}`")
    return f"Zorcha 설정 필요: {title}", "\n".join(head) + "\n\n" + memo_md(post, permalink)


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
.kv{list-style:none;padding:0;margin:6px 0}
.kv li{margin:4px 0}
.kv b{color:var(--fg);margin-right:6px}
.notice{border-left:4px solid var(--ac);padding:4px 0 4px 14px;margin:0 0 28px}
.notice ul{margin:6px 0}
.notice a{color:var(--ac)}
.grp{margin:18px 0 0}
.grp h4{margin:0 0 2px;font-size:17px;font-weight:700;color:var(--ac)}
.grp .gs{font-size:13px;color:var(--mu);margin:2px 0 0}
.grp .gs a{color:var(--mu)}
.foot{margin-top:28px;font-weight:700}
.step.li{padding:14px 0}
.step.li .lb{color:var(--fg);font-size:18px}
.step.li .ex{display:block;width:100%;max-width:360px;margin:10px 0 0}
.step.li .pr pre{padding:12px 96px 12px 16px;font-size:17px}
.foot a{color:var(--ac)}
.step.li .en{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;color:var(--ac);font-size:16px;margin-left:10px}
.usage{margin:6px 0 0}
.usage li{margin:6px 0}
"""


# 섹션 이름. 날짜·테스트 환경·제작 과정 섹션은 두지 않는다 (운영자 지적 2026-11-16):
# 결과는 '결과 예시', 꼭 필요한 조건(운영체제·요금제·프로그램)은 '준비물'.
HEADINGS = {
    "casual": {"result": "결과 예시", "extra": "더 써 볼 문장", "prep": "준비물", "caution": "참고"},
    "default": {"result": "결과 예시", "extra": "추가 명령어", "prep": "준비물", "caution": "참고"},
}
HEADINGS["formal"] = HEADINGS["default"]  # 예전 dm.page.style = "formal" 게시물 호환


def page_html(post, folder=None):
    d = dm_conf(post)
    pg = d.get("page") or {}
    cover = cover_of(post)
    cover = dict(cover, title=words(cover.get("title", "")), sub=words(cover.get("sub", "")))
    title = esc(cover.get("title", "")).replace("\n", "<br>")
    if cover.get("highlight"):
        h = esc(cover["highlight"])
        title = title.replace(h, f'<span class="hl">{h}</span>', 1)
    # 섹션 이름: 기본은 회사 안내서 말투(운영자 결정 2026-11-16), 예전 말투는 dm.page.style = "casual"
    # 글(소개·설명·결과·준비물)은 clean()으로 날짜·제작 과정 문장을 뺀다. 프롬프트 상자는 그대로.
    H = HEADINGS.get(pg.get("style") or "default", HEADINGS["default"])
    css = PAGE_CSS
    for k in ("ACCENT", "MUTED", "TEXT", "BG"):
        css = css.replace(k, B[k.lower()])

    def prompt_box(p):
        return (f'<div class="pr"><pre>{esc(p)}</pre>'
                '<button type="button" onclick="cp(this)">복사</button></div>')

    def group(g):
        txt = f'<p>{esc(clean(g["text"]))}</p>' if clean(g.get("text")) else ""
        srcs = g.get("src") or []
        srcs = [x for x in ([srcs] if isinstance(srcs, dict) else srcs) if x.get("url")]
        gs = ('<p class="gs">출처: ' + " · ".join(
            f'<a href="{esc(x["url"])}" rel="noopener">{esc(x.get("name") or x["url"])}</a>' for x in srcs) + '</p>'
              if srcs else "")
        return (f'<div class="grp">{"<h4>" + esc(g["name"]) + "</h4>" if g.get("name") else ""}{txt}'
                f'{"".join(prompt_box(p) for p in g.get("prompts") or [])}{gs}</div>')

    parts = []
    for i, st in enumerate(page_steps(post), 1):
        # 카드 장 제목이 제작 이야기("직접 돌려 봤습니다")면 페이지에서는 단계 이름(label)을 제목으로 쓴다
        if PROCESS_RE.search(st.get("title", "")) and st.get("label"):
            st = dict(st, title=st["label"], label="")
        lb = f'<span class="lb">{esc(st["label"])}</span>' if st.get("label") else ""
        boxes = "".join(prompt_box(p) for p in st.get("prompts") or [])
        text = "".join(f'<p>{esc(clean(st[k]))}</p>' for k in ("text", "more") if clean(st.get(k)))
        groups = "".join(group(g) for g in st.get("groups") or [])
        parts.append(f'<section class="step"><span class="k">{i:02d}</span>{lb}<h2>{esc(st["title"])}</h2>'
                     f'{boxes}{text}{groups}</section>')
    # 목록형 자료 릴스(post.list): '쓰는 법' + 전체 목록(번호·한국어 이름·영어 용어·뜻과 분위기 한 줄·예시 그림).
    # 복사해 붙이는 완성 프롬프트(복사 상자, template, extra)는 싣지 않는다 (운영자 결정 2026-11-17, STYLE_GUIDE 7-1).
    # 화면에는 한국어 이름만 나온다. 소개 글의 복사 안내는 no_copy()로 뺀다 (승인된 post.json을 고치지 않고 페이지에서만).
    lst = ""
    L = post.get("list") or {}
    is_list = bool(L.get("items"))
    if is_list:
        def txt(v):
            return words(no_copy(clean(v)))
        usage = [x for x in (txt(u) for u in list_usage(post)) if x]
        usage_html = (f'<div class="rule"></div><h3>{esc(pg.get("usage_title") or "쓰는 법")}</h3>'
                      '<ul class="usage">' + "".join(f"<li>{esc(x)}</li>" for x in usage) + "</ul>" if usage else "")

        def term(i, it):
            # 번호·한국어 이름·영어 용어(글자로만, 복사 상자 없음)·뜻과 분위기 한 줄(사실만)·직접 만든 예시 그림(있을 때만)
            img = ""
            if folder and it.get("src") and (Path(folder) / it["src"]).exists():
                img = f'<img class="ex" loading="lazy" alt="{esc(it.get("name", ""))} 예시" src="{esc(it["src"])}">'
            en = f'<span class="en" lang="en">{esc(it["en"])}</span>' if it.get("en") else ""
            return (f'<section class="step li"><span class="k">{i:02d}</span><span class="lb">{esc(it.get("name", ""))}</span>{en}'
                    f'{"<p>" + esc(txt(it["desc"])) + "</p>" if txt(it.get("desc")) else ""}{img}'
                    f'{"<p>" + esc(txt(it["note"])) + "</p>" if txt(it.get("note")) else ""}</section>')
        n = len(L["items"])
        rows = "".join(term(i, it) for i, it in enumerate(L["items"], 1))
        more = pg.get("more") or []
        more_html = ""
        if more:
            more_html = (f'<div class="rule"></div><h3>{esc(pg.get("more_title") or "추가 용어")}</h3>'
                         f'{"<p>" + esc(txt(pg["more_intro"])) + "</p>" if txt(pg.get("more_intro")) else ""}'
                         + "".join(term(n + i, it) for i, it in enumerate(more, 1)))
        lst = (f'{usage_html}<div class="rule"></div><h3>{esc(pg.get("list_title") or "전체 목록")}</h3>'
               f'{"<p>" + esc(txt(pg["list_intro"])) + "</p>" if txt(pg.get("list_intro")) else ""}{rows}{more_html}')
    extra = ""
    if pg.get("extra") and not is_list:
        rows = "".join(
            f'<section class="step"><h2>{esc(x.get("title", ""))}</h2>{prompt_box(x["prompt"])}'
            f'{"<p>" + esc(clean(x["note"])) + "</p>" if clean(x.get("note")) else ""}</section>' for x in pg["extra"])
        extra = f'<div class="rule"></div><h3>{esc(pg.get("extra_title") or H["extra"])}</h3>{rows}'
    # 결과 예시: 문장 하나(권장) 또는 예전 항목형 [{"k", "v"}] (테스트 일자·환경·미확인 범위 같은 항목은 뺀다)
    res = pg.get("result")
    if isinstance(res, list):
        kv = [(str(x.get("k", "")).strip().rstrip(":").strip(), clean(x.get("v", ""))) for x in res
              if not META_KEY_RE.search(str(x.get("k", "")))]
        kv = [(k, v) for k, v in kv if v]
        if len(kv) == 1:
            res_html = f'<p>{esc(kv[0][1])}</p>'
        else:
            res_html = ("<ul class=\"kv\">" + "".join(f'<li><b>{esc(k)}</b> {esc(v)}</li>' for k, v in kv) + "</ul>"
                        if kv else "")
    else:
        res_html = f'<p>{esc(clean(res))}</p>' if clean(res) else ""
    result = f'<div class="rule"></div><h3>{H["result"]}</h3>{res_html}' if res_html else ""
    # 준비물(dm.page.prep): 따라 하는 데 꼭 필요한 조건(운영체제·요금제·프로그램·라이선스)만. 흠·주의할 점은 쓰지 않는다.
    # 예전 dm.page.caution(흠·주의할 점)은 페이지에 싣지 않는다 (운영자 결정 2026-11-16: 흠·주의할 점은 어디에도 넣지 않음).
    # 필드가 있어도 오류 없이 넘긴다. 꼭 필요한 조건은 prep으로.
    def bullets(items, head):
        items = [c for c in (clean(x) for x in items or []) if c]
        return ("<div class=\"rule\"></div><h3>" + head + "</h3><ul>" + "".join(f"<li>{esc(c)}</li>" for c in items) + "</ul>"
                if items else "")
    prep_html = bullets(pg.get("prep"), H["prep"])
    caut = ""
    # 출처: 우리가 직접 돌려 본 기록(예: "클로드 코드 직접 사용 (11월 16일)")은 제작 이야기라 빼고, "(11월 16일 확인)"도 뺀다.
    # 기사·발표의 날짜는 출처 정보라 그대로 둔다.
    srcs = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(OWN_DATE_RE.sub("", s["name"]))}</a></li>'
                   for s in post["sources"] if not OWN_SRC_RE.search(s.get("name", "")))
    handle = CONFIG["handle"]
    intro_t = words(clean(pg.get("intro") or cover.get("sub", "")))
    if is_list:
        intro_t = no_copy(intro_t)
    intro = esc(intro_t)
    nt = pg.get("notice") or {}
    notice = ""
    if nt:
        links = "".join(f'<li><a href="{esc(x["url"])}" rel="noopener">{esc(x.get("name") or x["url"])}</a>'
                        f'{" · " + esc(clean(x["note"])) if clean(x.get("note")) else ""}</li>' for x in nt.get("links") or [])
        notice = (f'<div class="notice">{"<h3>" + esc(nt["title"]) + "</h3>" if nt.get("title") else ""}'
                  f'{"<p>" + esc(clean(nt["text"])) + "</p>" if clean(nt.get("text")) else ""}'
                  f'{"<ul>" + links + "</ul>" if links else ""}</div>')
    desc = esc(intro_t[:120])
    body = "".join(parts) + lst + result + extra + caut
    script = ("""<script>
function cp(b){const t=b.previousElementSibling.innerText;
(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>{b.textContent='복사됨';setTimeout(()=>b.textContent='복사',1500)})
.catch(()=>{const r=document.createRange();r.selectNodeContents(b.previousElementSibling);const s=getSelection();s.removeAllRanges();s.addRange(r)})}
</script>
""" if 'class="pr"' in body + notice + prep_html else "")
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
{notice}
{prep_html}
{body}
<div class="src">출처<ul>{srcs}</ul></div>
<p class="foot">매일 AI 소식은 <a href="https://www.instagram.com/{esc(handle.lstrip("@"))}/">{esc(handle)}</a></p>
</main>
{script}</body></html>
"""


def page_images(post):
    """자료 페이지에 붙는 예시 그림 경로 (목록형 릴스 항목·추가 용어의 src)."""
    L = post.get("list") or {}
    items = list(L.get("items") or []) + list(((post.get("dm") or {}).get("page") or {}).get("more") or [])
    return [it["src"] for it in items if it.get("src")]


def copy_page_images(post, folder, out_dir, width=540):
    """예시 그림을 안내 페이지 폴더(docs/p/<id>/)에 작게(가로 540px JPEG) 복사한다. 없는 그림은 건너뛴다."""
    from PIL import Image
    for rel in page_images(post):
        src = Path(folder) / rel
        if not src.exists():
            continue
        dst = Path(out_dir) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((width, width * 2))
        im.save(dst, "JPEG", quality=82, optimize=True)


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
    page.write_text(page_html(post, folder), encoding="utf-8")
    if not is_sample(folder):
        copy_page_images(post, folder, page.parent)
    return [memo, page]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    f = Path(sys.argv[1])
    for p in make_dm(json.loads((f / "post.json").read_text(encoding="utf-8")), f):
        print("만듦:", p)
