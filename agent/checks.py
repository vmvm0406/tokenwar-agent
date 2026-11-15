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
COVER_LAYOUTS = {"big", "list", "image"}
BODY_KINDS = {"body", "steps", "compare", "stat"}
CLIP_FIELDS = ("src", "start", "end", "source", "source_url")
VISUALS = {"image", "bars", "timeline"}
TYPES = {"carousel", "reel", "video"}

# 낚시성·과장 표현 (STYLE_GUIDE.md 3장)
BANNED = ["충격", "경악", "소름", "실화냐", "미쳤다", "역대급", "무조건", "하면 끝", "필수템", "ㄷㄷ"]

# 번역투·과장 의심 (경고만)
AWKWARD = ["에 대한", "하는 것이다", "되어지", "에 있어서", "을 통해서", "100%", "완벽"]

# AI가 쓴 티가 나는 글투 (STYLE_GUIDE 4-1장). 오류로 막는다.
AI_PHRASES = [
    "는 시대", "시대가 열", "시대입니다", "새로운 지평", "게임 체인저", "판도를 바꾸", "판도가 바뀌",
    "한 단계 진화", "그야말로", "무려", "어디까지", "주목된다", "주목할 만", "귀추가", "라는 점에서",
    "가능성을 열", "혁신적", "차세대", "본격적인", "과연", "생각하시나요", "어떻게 생각", "여러분의 생각",
    "놀라운 점은", "흥미로운 점은", "중요한 건", "핵심은 바로", "바로 이것", "이제는 ", "새로운 시대",
]
# 서술어 없이 조사·부사로 툭 끊기는 문장 ("편집도 한 모델로", "빠른 동작까지 자연스럽게")
DANGLING_RE = re.compile(r"(으로|[가-힣]로|까지|에게|에서|부터|처럼|보다|만큼|[가-힣]게|[가-힣]히)$")


def ai_tone(text, where, translation=False):
    """AI 글투 검사. (errors, warnings)"""
    errs, warns = [], []
    t = str(text)
    for w in AI_PHRASES:
        if w in t:
            errs.append(f"{where}: AI 글투 '{w.strip()}' → 구체적인 사실로 바꿀 것")
    if "—" in t or "–" in t:
        errs.append(f"{where}: 대시(—) 쓰지 않음")
    if re.search(r"[가-힣]+도, [가-힣]+도, [가-힣]+도", t):
        errs.append(f"{where}: 'A도, B도, C도' 나열은 AI 글투")
    if not translation:
        # 한 글 안의 줄바꿈은 문장이 이어지는 것으로 본다. 문장 끝(. ! ?)과 빈 줄에서 나눈다.
        for line in re.split(r"\n\s*\n|[.!?]", t.replace("\r", "")):
            line = line.replace("\n", " ")
            w = line.strip().strip("\"'“”‘’)( ")
            if len(w) >= 2 and DANGLING_RE.search(w):
                errs.append(f"{where}: 문장이 '{w[-6:]}'로 끊김 → 서술어까지 쓸 것 (예: '~로 만듭니다', '~할 수 있습니다')")
    return errs, warns


EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF]"
)


def _lines(text):
    return [l for l in str(text).split("\n")]


def _len(s):
    # 공백 제외 글자 수
    return len(re.sub(r"\s", "", s))


RIGHTS = {"quote", "own", "permission", "license"}


def check_thumb(post):
    """릴스 썸네일 검사 (thumb.py). 릴스(video, reel)에는 썸네일이 있어야 한다."""
    t = post.get("thumb")
    if not t:
        return ["릴스에는 thumb(썸네일)이 필요: title, image {src, url 또는 prompt}"]
    errs = []
    ls = _lines(t.get("title", ""))
    if not ls or len(ls) > 2:
        errs.append("썸네일 제목은 1~2줄")
    for l in ls:
        if _len(l) > 13:
            errs.append(f"썸네일 제목 한 줄은 13자 이하: '{l}'")
    if t.get("highlight") and t["highlight"] not in t.get("title", ""):
        errs.append("썸네일 highlight가 제목 안에 없음")
    im = t.get("image") or {}
    if not im.get("src"):
        errs.append("썸네일 image.src 필요")
    if not (im.get("url") or im.get("prompt")):
        errs.append("썸네일 image에 url(실물 이미지) 또는 prompt(AI 생성) 중 하나는 있어야 함 (직접 넣은 파일이면 url에 원본 주소)")
    return errs


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
            d = float(v["end"]) - float(v.get("start", 0))   # 원본에서 쓰는 범위 (비율 계산용)
            keep = v.get("keep") or []
            out_d = sum(float(b) - float(a) for a, b in keep) if keep else d   # 완성 영상 길이
            target = lim.get("quote_target_seconds", 60)
            if out_d < lim.get("quote_min_seconds", 0):
                warnings.append(f"영상이 짧음 ({out_d:.1f}초). 1분({target}초) 언저리에서 끝나게, 이야기가 끝나는 곳까지 늘린다")
            if out_d > lim.get("quote_soft_max_seconds", 10**6):
                warnings.append(f"영상이 김 ({out_d:.1f}초). 1분({target}초) 언저리에서 이야기가 끝나는 곳을 찾는다")
            src_d = v.get("source_duration")
            if not src_d:
                errors.append("video.source_duration(원본 전체 길이, 초) 필요: 인용 비율 확인용")
            elif d > float(src_d) * lim.get("quote_max_ratio", 1):
                errors.append(f"원본 길이의 {int(lim['quote_max_ratio'] * 100)}% 이하만 인용: 원본 {float(src_d):.0f}초 중 {d:.1f}초")
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
    errors += check_thumb(post)
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
    # 번역 자막(발언)은 말투가 자유롭다. 우리 설명 자막·제목·캡션만 끊김 검사
    for i, s in enumerate(post.get("subtitles", []), 1):
        e, _ = ai_tone(s.get("text", ""), f"자막 {i}", translation=bool(s.get("speech", post.get("speech", False))))
        errors += e
    for key in ["title"]:
        errors += ai_tone(post.get(key, ""), "제목")[0]
    if post.get("thumb"):
        errors += ai_tone(post["thumb"].get("title", ""), "썸네일 제목")[0]
    errors += ai_tone(post["caption"].split("영상:")[0], "캡션")[0]
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
            layout = s.get("layout", "big")
            if layout not in COVER_LAYOUTS:
                errors.append(f"{tag} layout은 {COVER_LAYOUTS} 중 하나: {layout}")
            if layout == "big" and not s.get("big"):
                errors.append(f"{tag} big 표지는 big(크게 보일 숫자나 단어) 필요")
            if layout == "big" and len(str(s.get("big", ""))) > 7:
                errors.append(f"{tag} big은 7자 이하")
            if layout == "list" and not (2 <= len(s.get("items", [])) <= 5):
                errors.append(f"{tag} list 표지는 items 2~5개")
            for x in s.get("items", []) if layout == "list" else []:
                if _len(x) > 14:
                    errors.append(f"{tag} list 항목은 14자 이하: '{x}'")
            if layout == "image" and (s.get("visual") or {}).get("type") != "image":
                errors.append(f"{tag} image 표지는 visual.type=image 필요")
            if not s.get("title"):
                errors.append(f"{tag} 표지 제목(title) 필요")
            t = s.get("title", "")
            ls = _lines(t) if t else []
            if len(ls) > lim["cover_title_lines"]:
                errors.append(f"{tag} 표지 제목은 {lim['cover_title_lines']}줄 이하: {len(ls)}줄")
            for l in ls:
                if _len(l) > lim["cover_title_line_chars"]:
                    errors.append(f"{tag} 표지 제목 한 줄은 {lim['cover_title_line_chars']}자 이하: '{l}'")
            if _len(s.get("sub", "")) > lim["subtitle_chars"]:
                errors.append(f"{tag} 부제는 {lim['subtitle_chars']}자 이하")
            all_text += [t, s.get("sub", ""), str(s.get("big", "")), s.get("big_note", "")] + list(s.get("items", []))
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
    for t in all_text:
        errors += ai_tone(t, "카드")[0]
    errors += ai_tone(post["caption"].split("출처:")[0], "캡션")[0]
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
