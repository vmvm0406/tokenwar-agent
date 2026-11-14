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
CLIP_FIELDS = ("src", "start", "end", "source", "source_url")
VISUALS = {"image", "monogram", "tiles", "settings", "chat", "terminal", "bars", "timeline", "number"}
TYPES = {"carousel", "reel", "video"}

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


RIGHTS = {"quote", "own", "permission", "license"}


def check_video(post):
    """영상 프레임 릴스(type=video) 검사."""
    errors, warnings = [], []
    lim = CONFIG["limits"]
    for key in ["id", "series", "date", "publish_at", "video", "title", "rights", "sources", "caption"]:
        if key not in post:
            errors.append(f"필수 항목 없음: {key}")
    if errors:
        return errors, warnings
    if post["rights"] not in RIGHTS:
        errors.append(f"rights는 {RIGHTS} 중 하나: own(직접 만듦), permission(원작자 허락), license(이용 허락 라이선스)")
    if post["rights"] == "quote":
        v = post["video"]
        if v.get("end") in (None, ""):
            errors.append("인용은 video.start와 video.end를 직접 정해야 함")
        else:
            d = float(v["end"]) - float(v.get("start", 0))
            if d > lim["quote_max_seconds"]:
                errors.append(f"인용 영상은 {lim['quote_max_seconds']}초 이하: 지금 {d:.1f}초")
            subs = post.get("subtitles", [])
            covered = sum(float(s["end"]) - float(s["start"]) for s in subs if "start" in s and "end" in s)
            if len(subs) < 2 or covered < d * 0.6:
                errors.append("인용 영상에는 우리 설명 자막이 2개 이상, 영상 길이의 60% 이상 깔려야 함")
        if not post.get("credit"):
            errors.append("인용은 credit(원작자 이름이나 채널) 필수")
        if not str(post.get("source_url", "")).startswith("http"):
            errors.append("인용은 source_url(원본 영상 링크) 필수")
        if len(post["caption"]) < 80:
            errors.append("인용 게시물 캡션에는 맥락과 의미를 설명할 것 (80자 이상)")
    if post["rights"] in ("permission", "license"):
        if not post.get("credit"):
            errors.append("남의 영상은 credit(원작자 계정이나 이름) 필수")
        if not post.get("rights_note"):
            errors.append("rights_note에 허락받은 날짜·경로나 라이선스 이름을 적을 것")
    ls = _lines(post["title"])
    if len(ls) > lim["cover_title_lines"]:
        errors.append(f"제목은 {lim['cover_title_lines']}줄 이하")
    for l in ls:
        if _len(l) > lim["video_title_line_chars"]:
            errors.append(f"제목 한 줄은 {lim['video_title_line_chars']}자 이하: '{l}'")
    if len(post.get("title_en", "")) > 48:
        errors.append("영어 부제는 48자 이하")
    hl = post.get("highlight")
    if hl and hl not in post["title"]:
        errors.append(f"highlight '{hl}'가 제목 안에 없음")
    v = post["video"]
    if not v.get("src"):
        errors.append("video.src 필요")
    prev_end = -1
    texts = [post["title"]]
    for i, s in enumerate(post.get("subtitles", []), 1):
        a, z = float(s.get("start", -1)), float(s.get("end", -1))
        if not (0 <= a < z):
            errors.append(f"자막 {i}: start < end 여야 함")
        if a < prev_end - 0.01:
            errors.append(f"자막 {i}: 앞 자막과 시간이 겹침")
        prev_end = z
        for l in _lines(s.get("text", "")):
            if _len(l) > lim["subtitle_line_chars"]:
                errors.append(f"자막 {i}: 한 줄 {lim['subtitle_line_chars']}자 이하 ('{l}')")
        if len(_lines(s.get("text", ""))) > 2:
            errors.append(f"자막 {i}: 2줄 이하")
        texts.append(s.get("text", ""))
    joined = "\n".join(texts)
    for w in BANNED:
        if w in joined or w in post["caption"]:
            errors.append(f"금지 표현: '{w}'")
    if EMOJI_RE.search(joined):
        errors.append("영상 위 글자에는 이모지를 쓰지 않음")
    if len(EMOJI_RE.findall(post["caption"])) > lim["caption_emoji_max"]:
        errors.append(f"캡션 이모지는 {lim['caption_emoji_max']}개 이하")
    if len(post.get("hashtags", [])) > lim["hashtags_max"]:
        errors.append(f"해시태그는 {lim['hashtags_max']}개 이하")
    if post.get("credit") and post["credit"] not in post["caption"]:
        errors.append("캡션에도 원작자(credit)를 밝힐 것")
    if not post["sources"]:
        errors.append("출처 1개 이상 (원본 영상 링크)")
    return errors, warnings


def check_post(post):
    """(errors, warnings) 반환."""
    if post.get("type") == "video":
        return check_video(post)
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
    clip_secs = []
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
        elif kind == "clip":
            if post["type"] != "reel":
                errors.append(f"{tag} 인용 영상(clip)은 릴스에서만")
            miss = [f for f in CLIP_FIELDS if s.get(f) in (None, "")]
            if miss:
                errors.append(f"{tag} clip 필수 항목 없음: {miss}")
                continue
            d = float(s["end"]) - float(s["start"])
            clip_secs.append(d)
            if not 0 < d <= lim["clip_max_seconds"]:
                errors.append(f"{tag} 인용 영상은 한 번에 {lim['clip_max_seconds']}초 이하: {d:.1f}초")
            if not str(s["source_url"]).startswith("http"):
                errors.append(f"{tag} 인용 영상 출처 URL 필요")
            h = s.get("heading", "")
            for l in _lines(h):
                if _len(l) > lim["heading_line_chars"]:
                    errors.append(f"{tag} 소제목 한 줄은 {lim['heading_line_chars']}자 이하: '{l}'")
            if _len(s.get("caption", "")) > lim["body_chars_short"]:
                errors.append(f"{tag} 인용 장면 자막은 {lim['body_chars_short']}자 이하")
            all_text += [h, s.get("caption", "")]
            hl_src = h
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

    if clip_secs:
        rc = CONFIG["reel"]
        others = rc["cover_seconds"] + rc["seconds_per_frame"] * (len(slides) - len(clip_secs)) + rc["seconds_per_frame"]
        ratio = sum(clip_secs) / (sum(clip_secs) + others)
        if ratio > lim["clip_max_ratio"]:
            errors.append(f"인용 영상이 릴스의 {ratio:.0%}: {lim['clip_max_ratio']:.0%} 이하로 줄이고 해설 장면을 늘릴 것")
        if len(slides) - len(clip_secs) < 3:
            errors.append("인용 영상 외에 표지 포함 해설 장면이 3개 이상 있어야 함")

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
