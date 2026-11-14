"""post.json 규칙 검사.

render.py가 이미지를 만들기 전에 호출한다. 문제가 있으면 목록을 돌려주고,
하나라도 있으면 렌더링을 멈춘다. 규칙의 근거는 STYLE_GUIDE.md에 있다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

SERIES = {"전황", "긴급", "생존 가이드", "오픈소스", "AI 용어"}
COVER_LAYOUTS = {"visual", "icon", "word", "number", "list"}
BODY_KINDS = {"body", "steps", "compare", "stat"}
VISUALS = {"image", "monogram", "tiles", "settings", "chat", "terminal", "bars", "timeline", "number"}
TYPES = {"carousel", "reel"}

# 낚시성·과장 표현 (STYLE_GUIDE.md 3장)
BANNED = ["충격", "경악", "소름", "실화냐", "미쳤다", "역대급", "무조건", "하면 끝", "필수템", "ㄷㄷ"]

# 번역투·과장 의심 (경고만)
AWKWARD = ["에 대한", "하는 것이다", "되어지", "에 있어서", "을 통해서", "100%", "완벽"]

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF]"
)


def _lines(text):
    return [l for l in str(text).split("\n")]


def _len(s):
    # 공백 제외 글자 수
    return len(re.sub(r"\s", "", s))


def check_post(post):
    """(errors, warnings) 반환."""
    errors, warnings = [], []
    lim = CONFIG["limits"]

    for key in ["id", "type", "series", "date", "publish_at", "slides", "sources", "caption"]:
        if key not in post:
            errors.append(f"필수 항목 없음: {key}")
    if errors:
        return errors, warnings

    if post["type"] not in TYPES:
        errors.append(f"type은 {TYPES} 중 하나: {post['type']}")
    if post["series"] not in SERIES:
        errors.append(f"series는 {SERIES} 중 하나: {post['series']}")

    slides = post["slides"]
    if not slides or slides[0].get("kind") != "cover":
        errors.append("첫 장은 kind=cover 여야 함")
    total = len(slides) + 1  # 마지막 장(outro)은 자동으로 붙음
    if post["type"] == "carousel" and not (lim["carousel_min"] <= total <= lim["carousel_max"]):
        errors.append(f"캐러셀은 마무리 장 포함 {lim['carousel_min']}~{lim['carousel_max']}장: 지금 {total}장")
    if post["type"] == "reel" and not (3 <= total <= lim["reel_max_frames"]):
        errors.append(f"릴스 장면은 마무리 포함 3~{lim['reel_max_frames']}개: 지금 {total}개")

    all_text = []
    for i, s in enumerate(slides, 1):
        kind = s.get("kind")
        tag = f"{i}번째 장"
        if i > 1 and kind == "cover":
            errors.append(f"{tag} 표지는 첫 장에만")
        if kind == "cover":
            layout = s.get("layout", "visual")
            if layout not in COVER_LAYOUTS:
                errors.append(f"{tag} layout은 {COVER_LAYOUTS} 중 하나: {layout}")
            if layout == "word" and not s.get("word"):
                errors.append(f"{tag} word 표지는 word 항목 필요")
            if layout != "word" and not s.get("title"):
                errors.append(f"{tag} 표지 제목(title) 필요")
            if layout in ("visual", "icon", "number", "list") and not s.get("visual"):
                errors.append(f"{tag} '{layout}' 표지는 visual 항목 필요")
            t = s.get("title", "")
            ls = _lines(t) if t else []
            if len(ls) > lim["cover_title_lines"]:
                errors.append(f"{tag} 표지 제목은 {lim['cover_title_lines']}줄 이하: {len(ls)}줄")
            for l in ls:
                if _len(l) > lim["cover_title_line_chars"]:
                    errors.append(f"{tag} 표지 제목 한 줄은 {lim['cover_title_line_chars']}자 이하: '{l}'")
            if _len(s.get("sub", "")) > lim["subtitle_chars"]:
                errors.append(f"{tag} 부제는 {lim['subtitle_chars']}자 이하")
            all_text += [t, s.get("sub", ""), s.get("word", ""), s.get("word_desc", "")]
            hl_src = t
        elif kind in BODY_KINDS:
            h = s.get("heading", "")
            if kind != "stat" and not h:
                errors.append(f"{tag} 소제목(heading) 필요")
            for l in _lines(h):
                if _len(l) > lim["heading_line_chars"]:
                    errors.append(f"{tag} 소제목 한 줄은 {lim['heading_line_chars']}자 이하: '{l}'")
            if len(_lines(h)) > 2:
                errors.append(f"{tag} 소제목은 2줄 이하")
            b = s.get("body", "")
            body_max = lim["body_chars"] if kind == "body" and not s.get("visual") else lim["body_chars_short"]
            if _len(b) > body_max:
                errors.append(f"{tag} 본문은 {body_max}자 이하 (이 유형 기준): {_len(b)}자")
            p = s.get("point", "")
            if p and _len(p) > lim["point_chars"]:
                errors.append(f"{tag} 포인트 박스는 {lim['point_chars']}자 이하")
            if kind == "steps":
                items = s.get("items", [])
                if not 2 <= len(items) <= 4:
                    errors.append(f"{tag} steps는 항목 2~4개")
                for it in items:
                    all_text += [it.get("title", ""), it.get("text", "")]
                    if _len(it.get("title", "")) > 18 or _len(it.get("text", "")) > 34:
                        errors.append(f"{tag} steps 항목은 제목 18자, 설명 34자 이하")
            if kind == "compare":
                for side in ("left", "right"):
                    c = s.get(side) or {}
                    if not c.get("label") or not c.get("items"):
                        errors.append(f"{tag} compare는 left/right에 label과 items 필요")
                    for x in c.get("items", []):
                        all_text.append(x)
                        if _len(x) > 22:
                            errors.append(f"{tag} compare 항목은 22자 이하: '{x}'")
            if kind == "stat" and not s.get("value"):
                errors.append(f"{tag} stat은 value 필요")
            all_text += [h, b, p, s.get("label", "")]
            hl_src = h
        else:
            errors.append(f"{tag} kind는 cover 또는 {BODY_KINDS}: {kind}")
            continue
        v = s.get("visual")
        if v and v.get("type") not in VISUALS:
            errors.append(f"{tag} visual.type은 {VISUALS} 중 하나")
        hl = s.get("highlight")
        if hl and hl not in hl_src:
            errors.append(f"{tag} highlight '{hl}'가 제목/소제목 안에 없음")

    joined = "\n".join(all_text)
    for w in BANNED:
        if w in joined or w in post["caption"]:
            errors.append(f"금지 표현: '{w}'")
    for w in AWKWARD:
        if w in joined:
            warnings.append(f"번역투 의심: '{w}'")
    if EMOJI_RE.search(joined):
        errors.append("카드 안에는 이모지를 쓰지 않음")
    if len(EMOJI_RE.findall(post["caption"])) > lim["caption_emoji_max"]:
        errors.append(f"캡션 이모지는 {lim['caption_emoji_max']}개 이하")

    tags = post.get("hashtags", [])
    if len(tags) > lim["hashtags_max"]:
        errors.append(f"해시태그는 {lim['hashtags_max']}개 이하: {len(tags)}개")
    cap = post["caption"] + "\n\n" + " ".join(tags)
    if len(cap) > 2200:
        errors.append("캡션+해시태그는 2,200자 이하")

    srcs = post["sources"]
    need = 1 if post["series"] in ("생존 가이드", "오픈소스", "AI 용어") else 2
    if len(srcs) < need:
        errors.append(f"'{post['series']}'는 출처 {need}개 이상 필요")
    for s in srcs:
        if not str(s.get("url", "")).startswith("http"):
            errors.append(f"출처 URL이 올바르지 않음: {s}")

    return errors, warnings
