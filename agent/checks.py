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
BODY_KINDS = {"body", "steps", "compare", "stat", "prompt"}
# 게시물 형식 (선택). howto: 따라 하기, ask: 나를 알려 주는 질문, weekly: 주간 요약, news: 소식 (STYLE_GUIDE 3-1)
# buzz: 가벼운 화제 (연예인·예능·유명인이 나오는 AI 이야기, STYLE_GUIDE 3-2). 주당 개수는 dupes.py가 센다
FORMATS = {"news", "howto", "ask", "weekly", "buzz"}
BUZZ_MIN_SOURCES = 2
# 가벼운 화제는 AI 화제에 빗댄 패러디·밈도 된다. 농담임을 캡션 앞부분에서 풀어 줘야 한다 (실제 논란으로 오해 금지)
BUZZ_REVEAL = ["사실은", "사실 ", "실제로는", "실제론", "패러디", "농담", "밈", "알고 보니", "진짜는", "빗댄", "합성"]
# 가벼운 화제에서 쓰면 안 되는 쪽 (확인 안 된 의혹, 사생활, 조롱). 경고로 알리고 사람이 판단
BUZZ_RISKY = ["의혹", "카더라", "루머", "열애", "사생활", "폭로", "저격", "망신", "굴욕"]
PROMPT_MAX = 320  # 프롬프트 상자 하나 글자 수 (넘치면 render.py가 레이아웃 오류로도 막는다)
CLIP_FIELDS = ("src", "start", "end", "source", "source_url")
VISUALS = {"image", "bars", "timeline"}
TYPES = {"carousel", "reel", "video"}

# 낚시성·과장 표현 (STYLE_GUIDE.md 3장)
BANNED = ["충격", "경악", "소름", "실화냐", "미쳤다", "역대급", "무조건", "하면 끝", "필수템", "ㄷㄷ"]

# 아무 게시물에나 붙는 뻔한 질문 (STYLE_GUIDE 7장). 캡션 어디에 있든 오류.
# 질문은 의견이 실제로 갈리는 소식에만, 그 소식에 맞는 양자택일로 ("AI 안경 65만 원, 사시겠어요?")
GENERIC_Q = ["여러분 생각은", "여러분의 생각", "여러분은 어떻게", "여러분은 어떠", "어떻게 생각하", "생각하시나요",
             "어떠신가요", "어떻게 보시나요", "의견을 남겨", "의견 남겨", "의견을 들려", "어디에 써 보고 싶",
             "어떤 걸 해 보고 싶", "가장 써 보고 싶은"]

# 해시태그 (STYLE_GUIDE 7장): 3~5개 = 주제 이름 1~2 + 한국어 분야 1~2 + #토큰전쟁. 흔한 태그 금지
TAG_BRAND = "#토큰전쟁"
BANNED_TAGS = {"#reels", "#reel", "#reelsinstagram", "#explore", "#explorepage", "#fyp", "#foryou", "#foryoupage",
               "#viral", "#trending", "#instagood", "#follow", "#followme", "#like", "#likeforlike", "#l4l", "#f4f",
               "#좋아요", "#좋반", "#팔로우", "#팔로우미", "#선팔", "#맞팔", "#선팔맞팔", "#소통", "#소통해요",
               "#일상", "#데일리", "#인친", "#좋아요반사", "#팔로우환영"}

# 번역투·과장 의심 (경고만)
AWKWARD = ["에 대한", "하는 것이다", "되어지", "에 있어서", "을 통해서", "100%", "완벽"]

# AI가 쓴 티가 나는 글투 (STYLE_GUIDE 4-1장). 오류로 막는다.
AI_PHRASES = [
    "는 시대", "시대가 열", "시대입니다", "새로운 지평", "게임 체인저", "판도를 바꾸", "판도가 바뀌",
    "한 단계 진화", "그야말로", "무려", "어디까지", "주목된다", "주목할 만", "귀추가", "라는 점에서",
    "가능성을 열", "혁신적", "차세대", "본격적인", "과연", "생각하시나요", "어떻게 생각", "여러분의 생각",
    "놀라운 점은", "흥미로운 점은", "만 알면 됩니다", "만 알면 돼요", "만 기억하세요", "중요한 건", "핵심은 바로", "바로 이것", "이제는 ", "새로운 시대",
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


CAPTION_EMOJI_MAX = 10  # 캡션 줄머리 표시용 (운영자 결정 2026-11-16). 줄마다 1개
ENDING_RE = re.compile(r"([가-힣]{1,3})[.!?~…]*\s*$")


def _ending(sentence):
    """문장 끝 어미 대략 (마지막 두 글자). '했어요', '합니다' 같은 반복을 잡는 용도."""
    m = ENDING_RE.search(sentence.strip())
    return m.group(1)[-2:] if m else None


def caption_style(caption):
    """캡션 문체 검사 (운영자 지적 2026-11-16).
    - 이모지는 줄머리 표시로만: 한 줄에 1개, 전체 CAPTION_EMOJI_MAX개 이하 (카드·썸네일 안 이모지 금지는 그대로)
    - 같은 문장 끝(예: '~했어요')이 3번 연속이면 경고"""
    errs, warns = [], []
    if len(EMOJI_RE.findall(caption)) > CAPTION_EMOJI_MAX:
        errs.append(f"캡션 이모지는 {CAPTION_EMOJI_MAX}개 이하 (줄머리 표시로 줄마다 1개)")
    for l in caption.splitlines():
        if len(EMOJI_RE.findall(l)) > 1:
            warns.append(f"캡션 이모지는 줄마다 1개, 줄머리에만: '{l[:30]}'")
    body = "\n".join(l for l in caption.splitlines() if not l.lstrip().startswith("#"))
    sents = [s for s in re.split(r"(?<=[.!?])\s+|\n+", body) if re.search(r"[가-힣]", s)]
    run, prev = 1, None
    for s in sents:
        e = _ending(s)
        run = run + 1 if e and e == prev else 1
        prev = e
        if run == 3:
            warns.append(f"캡션 문장 끝 '~{e}'가 3번 연속 → 끝맺음을 섞는다 (~합니다/~했습니다/명사형 요점/질문) (STYLE_GUIDE 7)")
    return errs, warns


def _lines(text):
    return [l for l in str(text).split("\n")]


def _len(s):
    # 공백 제외 글자 수
    return len(re.sub(r"\s", "", s))


RIGHTS = {"quote", "own", "permission", "license"}


# 릴스 제목·썸네일 제목은 "누가/무엇이 + 무엇을 했다"가 끝까지 들어간 문장으로 (STYLE_GUIDE 4장 "제목은 알아듣기 쉽게").
# "3년 만에 밀레니엄 난제"처럼 서술어 없이 명사로 압축하면 무슨 일인지 알 수 없다.
PREDICATE_RE = re.compile(r"(다|요|죠|까|나|네)[\s\"'”’.!?…]*$")


def body_sentences(text, where):
    """카드 본문 설명은 문장을 끝까지 쓴다. "전 세계 모든 사용자 대상.", "미국부터 베타."처럼 명사로 툭 끝나면 어색하다
    (운영자 지적 2026-11-15). 숫자만 있는 짧은 조각은 봐준다."""
    errs = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", str(text)):
        w = sent.strip().rstrip(".!?").strip("\"'“”‘’)( ")
        if len(w) < 6 or re.fullmatch(r"[\d\s,.%·~-]+", w):
            continue
        if not PREDICATE_RE.search(w):
            errs.append(f"{where}: 문장이 명사로 툭 끝남 '{w[-14:]}' → '~습니다'로 끝까지 (예: '사용자 대상' → '사용자에게 적용됩니다')")
    return errs


# 구어체 반박·강조 끝맺음 (STYLE_GUIDE 3-3, 운영자 결정 2026-11-16): "아니 컴공 안 죽었다니까?", "끝났다고? 아니거든",
# "안 죽었잖아", "아니야". 물음표가 붙어도 답이 정해진 반박이면 서술어로 본다.
COLLOQUIAL_RE = re.compile(r"(거든|거든요|[다라냐]고|니까|니까요|잖아|잖아요|는데|는데요|[이거니]야|[았었였했겠]지)[\s\"'”’.!?…]*$")
_TAIL = r"[\s\"'”’.!?…]*$"


def _jong(ch):
    """한글 음절의 받침 번호 (0 = 받침 없음, 8 = ㄹ, 17 = ㅂ). 한글이 아니면 -1."""
    c = ord(ch) - 0xAC00
    return c % 28 if 0 <= c < 11172 else -1


def is_real_question(text):
    """답을 독자에게 미루는 진짜 질문형인지: "~일까요?", "~할까?", "~인가요?", "~나요?", "~습니까?".
    "안 죽었다니까?"(다니까), "끝났다고?"는 반박이라 질문으로 보지 않는다."""
    w = re.sub(_TAIL, "", str(text).strip())
    if not w:
        return False
    if re.search(r"(나요|가요|는가|ㄴ가|은가|인가|던가)$", w):
        return True
    m = re.search(r"(.)(까요|까)$", w)   # 받침 ㄹ + 까(요): 할까, 일까요, 될까 / 받침 ㅂ + 니까: 합니까, 입니까
    if m and _jong(m.group(1)) == 8:
        return True
    m = re.search(r"(.)니까(요)?$", w)
    if m and (_jong(m.group(1)) == 17 or m.group(1) == "습"):
        return True
    return False


def title_sentence(title, where, no_question=True):
    """제목이 서술어로 끝나는지. 따옴표 인용("~했다")도 서술어로 본다.
    구어체 반박("안 죽었다니까?", "아니거든", "끝났다고?")은 통과, 진짜 질문("~일까요?", "~할까?")은 막는다."""
    one = " ".join(_lines(title)).strip()
    if not one:
        return []
    if no_question and is_real_question(one):   # 카드 표지("토큰, 정확히 뭘까")는 설명형 질문을 허용
        return [f"{where}이 질문형: '{one}' → 답을 미루는 질문 대신 단정이나 구어체 반박으로 "
                "(예: '컴공은 끝났을까요?' 대신 '아니 컴공 안 죽었다니까?', STYLE_GUIDE 3-3)"]
    if not (PREDICATE_RE.search(one) or COLLOQUIAL_RE.search(one)):
        return [f"{where}이 서술어 없이 끝남: '{one}' → 누가·무엇이 어떻게 했는지 끝까지 쓴다 "
                "(예: '3년 만에 밀레니엄 난제' 대신 'AI가 3년 만에 수학 최대 난제를 풀었다')"]
    return []


def check_thumb(post):
    """릴스 썸네일 검사 (thumb.py). 릴스(video, reel)에는 썸네일이 있어야 한다."""
    t = post.get("thumb")
    if not t:
        return ["릴스에는 thumb(썸네일)이 필요: title, image {src, url 또는 prompt}"]
    errs = []
    ls = _lines(t.get("title", ""))
    most = 3 if t.get("max_lines") == 3 else 2  # max_lines 3: 운영자가 직접 고른 3줄 제목만 (2026-11-16 힌턴)
    if not ls or len(ls) > most:
        errs.append(f"썸네일 제목은 1~{most}줄")
    for l in ls:
        if _len(l) > 13:
            errs.append(f"썸네일 제목 한 줄은 13자 이하: '{l}'")
    if t.get("highlight") and t["highlight"] not in t.get("title", ""):
        errs.append("썸네일 highlight가 제목 안에 없음")
    errs += title_sentence(t.get("title", ""), "썸네일 제목")
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
            if len(keep) > 1:
                warnings.append("video.keep으로 중간을 잘라 붙임: 급해 보여서 지금은 쓰지 않는다. start~end 한 구간 그대로 (STYLE_GUIDE 6-1)")
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
    errors += title_sentence(post["title"], "릴스 제목")
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
    e_ce, w_ce = caption_style(post["caption"])
    errors += e_ce
    warnings += w_ce
    e_h, w_h = check_hashtags(post.get("hashtags", []))
    errors += e_h
    warnings += w_h
    if post.get("credit") and post["credit"] not in post["caption"]:
        errors.append("캡션에도 원작자(credit)를 밝힐 것")
    if not post["sources"]:
        errors.append("출처 1개 이상 (원본 영상 링크)")
    f = post.get("format")
    if f is not None and f not in FORMATS:
        errors.append(f"format은 {FORMATS} 중 하나: {f}")
    e_b, w_b = check_buzz(post)
    errors += e_b
    warnings += w_b
    # 따라 하기 영상 릴스(format howto + dm)도 카드형처럼 DM 자료를 검사하고 '받기' 안내를 허용한다
    kw = None
    if post.get("dm"):
        e_d, w_d = check_dm(post)
        errors += e_d
        warnings += w_d
        kw = post["dm"].get("keyword") or CONFIG.get("dm", {}).get("keyword", "받기")
    e_c, w_c = check_caption_hooks(post["caption"], kw)
    errors += e_c
    warnings += w_c
    e_r, w_r = check_reach(post)
    errors += e_r
    warnings += w_r
    return errors, warnings


IMAGE_RULE = "사진 규칙"


def check_images(slides):
    """카드뉴스 사진: 다른 AI 정보 계정처럼 실제 화면·사진을 넣는다 (STYLE_GUIDE 2-1).
    표지 포함 사진 장이 2장 이상 (6장 넘는 카드뉴스는 3장 이상). 표지는 사진 표지를 기본으로."""
    errors, warnings = [], []
    lim = CONFIG["limits"]
    imgs = []
    for i, s in enumerate(slides, 1):
        v = s.get("visual") or {}
        if v.get("type") == "image":
            imgs.append((i, v))
    srcs = [v.get("src") for _, v in imgs if v.get("src")]
    for src in sorted(set(x for x in srcs if srcs.count(x) > 1)):
        errors.append(f"같은 사진({src})을 여러 장에 반복함 → 장마다 다른 사진이나 다른 부분을 잘라 쓸 것")
    need = lim.get("carousel_min_images", 2) + (1 if len(slides) > 6 else 0)
    if len(imgs) < need:
        errors.append(f"{IMAGE_RULE}: 사진(실제 화면 캡처·공식 이미지) 장이 {need}장 이상 필요: 지금 {len(imgs)}장. "
                      "서비스 화면, 공식 발표 페이지, 논문 그림, X 게시물 등을 agent/shot.py로 찍어 본문 장 visual에 넣는다")
    # 첫 장은 무조건 눈길을 끄는 사진 (운영자 결정, STYLE_GUIDE 2-1 "표지는 후킹 사진")
    if slides and slides[0].get("kind") == "cover":
        cv = slides[0].get("visual") or {}
        if slides[0].get("layout") != "image":
            errors.append("표지는 사진 표지(layout: image)만: 큰 숫자·목록 표지는 쓰지 않는다. 눈길을 끄는 사진을 넣을 것")
        elif cv.get("shot") or cv.get("screen"):
            errors.append("표지에 화면 캡처·표·문서를 쓰지 않는다: 사람 얼굴·표정, 강한 장면, 결과물처럼 눈길을 끄는 사진으로")
        if slides[0].get("layout") == "image" and not cv.get("hook"):
            errors.append("표지 사진 visual.hook에 이 사진이 왜 눈길을 끄는지 한 줄 적을 것 (예: '아이와 여행 가는 가족 사진: 바로 내 얘기')")
    for i, v in imgs:
        if i > 1 and not v.get("credit") and not v.get("prompt"):
            warnings.append(f"{i}번째 장 사진에 credit(예: '화면: Lovable 공식 문서') 없음")
    return errors, warnings


def _prompts(slides):
    out = []
    for s in slides:
        if s.get("kind") == "prompt":
            out += [x for x in (s.get("prompts") or [s.get("prompt")]) if x and str(x).strip()]
    return out


def check_buzz(post):
    """가벼운 화제(format buzz): 출처 2곳 이상(오류), 캡션 앞에서 실제 사정 밝히기·위험한 표현(경고) (STYLE_GUIDE 3-2)."""
    errors, warnings = [], []
    if post.get("format") != "buzz":
        return errors, warnings
    srcs = [s for s in post.get("sources", []) if str(s.get("url", "")).startswith("http")]
    if len(srcs) < BUZZ_MIN_SOURCES:
        errors.append(f"가벼운 화제(format buzz)는 출처 {BUZZ_MIN_SOURCES}곳 이상으로 사실 확인: 지금 {len(srcs)}곳 (STYLE_GUIDE 3-2)")
    head = " / ".join([l for l in post.get("caption", "").splitlines() if l.strip()][:3])
    if not any(w in head for w in BUZZ_REVEAL):
        warnings.append("가벼운 화제: 캡션 앞 3줄에 실제 사정을 밝히는 말('사실은', '실제로는', '패러디' 등)이 없음 → 농담·패러디면 앞에서 풀어 줄 것 (STYLE_GUIDE 3-2)")
    text = json.dumps({k: post.get(k) for k in ("title", "slides", "video", "thumb", "caption")}, ensure_ascii=False)
    hit = [w for w in BUZZ_RISKY if w in text]
    if hit:
        warnings.append(f"가벼운 화제에 조심할 표현 {hit}: 확인 안 된 의혹·사생활·조롱은 다루지 않는다 (STYLE_GUIDE 3-2)")
    return errors, warnings


def check_format(post):
    """따라 하기·질문 형식이면 복사해 쓸 프롬프트가 장 안에 있어야 한다 (STYLE_GUIDE 3-1)."""
    errors, warnings = [], []
    f = post.get("format")
    if f is None:
        return errors, warnings
    if f not in FORMATS:
        return [f"format은 {FORMATS} 중 하나: {f}"], warnings
    errors, warnings = check_buzz(post)
    prs = _prompts(post.get("slides", []))
    if f in ("howto", "ask") and not prs:
        errors.append(f"format '{f}'에는 복사해 쓸 프롬프트 장(kind: prompt)이 1개 이상 필요")
    if f == "ask" and prs and not 3 <= len(prs) <= 4:
        warnings.append(f"질문 형식은 질문 3~4개가 좋음: 지금 {len(prs)}개")
    if f in ("howto", "ask") and post.get("type") == "carousel":
        missing = [p for p in prs if p.strip()[:40] not in post.get("caption", "")]
        if missing:
            warnings.append("프롬프트를 캡션에도 적어 두면 복사하기 쉬움 (STYLE_GUIDE 3-1)")
    return errors, warnings


NEWSY_RE = re.compile(r"(공개|출시|발표|선보|내놨|소식|업데이트됐|가지)")
GAIN_RE = re.compile(r"(세요|수 있|하는 법|방법|해 보|해보|됩니다|만들어|바꿔|아끼|찾아)")


def check_dm(post):
    """댓글 자동 DM 준비물 (STYLE_GUIDE 7-1). dm이 있으면 문구 길이·키워드 안내를 본다."""
    errors, warnings = [], []
    d = post.get("dm")
    f = post.get("format")
    if not d:
        if f in ("howto", "ask") and post.get("type") in ("carousel", "reel"):
            warnings.append("따라 하기·질문 게시물에 dm(댓글 자동 DM 자료)이 없음 → STYLE_GUIDE 7-1")
        return errors, warnings
    kw = d.get("keyword") or CONFIG.get("dm", {}).get("keyword", "받기")
    msg = (d.get("message") or "").strip()
    if not msg:
        errors.append("dm.message(보낼 DM 문구) 필요")
    elif _len(msg) > 900:
        errors.append(f"dm.message는 900자 이하 (인스타 DM 1,000자 제한, 링크 자리 남김): {_len(msg)}자")
    for key, mx in (("follow_text", 300), ("comment_reply", 150)):
        if d.get(key) and _len(d[key]) > mx:
            errors.append(f"dm.{key}는 {mx}자 이하")
    for x in [msg, d.get("follow_text", ""), d.get("comment_reply", "")]:
        if EMOJI_RE.search(str(x)) and len(EMOJI_RE.findall(str(x))) > 1:
            warnings.append("DM 문구 이모지는 1개 이하")
    if "http" in msg:
        warnings.append("dm.message 안에 주소를 쓰지 않음. 안내 페이지 링크는 도구의 링크 버튼으로 붙는다(dm.md)")
    pg = d.get("page") or {}
    for x in pg.get("extra") or []:
        if not x.get("prompt") or not x.get("title"):
            errors.append("dm.page.extra 항목은 title과 prompt 필요")
    if f"'{kw}'" not in post.get("caption", "") and f"‘{kw}’" not in post.get("caption", ""):
        warnings.append(f"캡션에 댓글 키워드 안내가 없음 (예: \"댓글에 '{kw}' 남기면 프롬프트 전체를 DM으로 보내 드려요\")")
    for t in [msg, d.get("follow_text", "")] + [x.get("note", "") for x in pg.get("extra") or []] + [pg.get("result", ""), pg.get("intro", "")]:
        if t:
            e_t, _ = ai_tone(t, "DM 자료")
            errors += e_t
    return errors, warnings


# 음슴체 끝맺음 ("CCTV는 없었음", "자술서를 냄", "표가 나옴")은 어색하다. 카드 글은 "~습니다" 또는 짧은 명사로.
EUMSEUM_RE = re.compile(r"(았음|었음|였음|했음|됐음|없음|있음|했음|함|냄|됨|나옴|봄|씀|줌|짐|옴)$")
EUMSEUM_OK = {"처음", "마음", "다음", "이름", "포함", "지금", "함께", "소음", "느낌", "가짐", "모임", "질문함"}


def eumseum(text, where):
    errs = []
    for sent in re.split(r"[.!?\n]", str(text)):
        w = sent.strip().strip("\"'“”‘’)( ")
        if not w:
            continue
        last = w.split()[-1]
        if EUMSEUM_RE.search(last) and last not in EUMSEUM_OK and (len(last) >= 2 or last in "냄함됨봄씀줌짐옴"):
            errs.append(f"{where}: 음슴체 끝맺음 '{last}' → '~습니다'로 끝까지 쓰거나 짧은 명사로 (예: '없었음' → '없었습니다')")
    return errs


def check_caption_hooks(caption, dm_keyword=None):
    """캡션 첫 줄은 '얻는 것'으로 (STYLE_GUIDE 3-1, 경고). 캡션 끝 질문은 필수가 아니다 (7장).
    (errors, warnings) 반환: 뻔한 질문은 오류, dm이 없는데 '받기' 안내가 있으면 오류."""
    errors, warnings = [], []
    lines = [l.strip() for l in caption.split("영상:")[0].splitlines() if l.strip()]
    if lines:
        first = lines[0]
        if any(is_real_question(q) for q in re.findall(r"[^?.!]*\?", first)):  # 반박형("못 만든다고요?")은 질문으로 보지 않음
            warnings.append(f"캡션 첫 줄이 질문임 → 읽는 사람이 얻는 것으로 시작할 것: '{first[:40]}'")
        elif NEWSY_RE.search(first) and not GAIN_RE.search(first):
            warnings.append(f"캡션 첫 줄이 소식 전달임 → 얻는 것을 먼저 (예: '~하는 법', '~해 보세요'): '{first[:40]}'")
    for q in GENERIC_Q:
        if q in caption:
            errors.append(f"캡션에 아무 데나 붙는 질문 '{q}' → 빼거나, 의견이 갈리는 소식이면 그 소식에 맞는 양자택일로 "
                          "(예: 'AI 안경 65만 원, 사시겠어요?')")
    kw = CONFIG.get("dm", {}).get("keyword", "받기")
    if not dm_keyword and re.search(rf"['‘\"“]{re.escape(kw)}['’\"”]", caption):
        errors.append(f"dm이 없는 게시물 캡션에 '{kw}' 안내가 있음 → 자동 DM은 따라 하기·질문 게시물(dm 있음)에만")
    return errors, warnings


def check_hashtags(tags):
    """해시태그 3~5개, 흔한 태그 금지, #토큰전쟁 1개 (STYLE_GUIDE 7장)."""
    errors, warnings = [], []
    mx = CONFIG["limits"].get("hashtags_max", 5)
    if len(tags) > mx:
        errors.append(f"해시태그는 {mx}개 이하 (인스타 제한): {len(tags)}개")
    elif len(tags) <= 2:
        warnings.append(f"해시태그가 {len(tags)}개: 주제 이름 1~2 + 분야 1~2 + {TAG_BRAND}, 모두 3~5개")
    for x in tags:
        if not str(x).startswith("#") or " " in str(x):
            errors.append(f"해시태그 형식: '{x}' (#로 시작, 띄어쓰기 없이)")
        if str(x).lower() in BANNED_TAGS:
            errors.append(f"흔한 해시태그 금지: {x}")
    if len(set(map(str.lower, map(str, tags)))) != len(tags):
        errors.append("해시태그가 중복됨")
    if tags and TAG_BRAND not in tags:
        warnings.append(f"해시태그에 {TAG_BRAND} 없음")
    return errors, warnings
    first = lines[0]
    if any(is_real_question(q) for q in re.findall(r"[^?.!]*\?", first)):  # 반박형("못 만든다고요?")은 질문으로 보지 않음
        warnings.append(f"캡션 첫 줄이 질문임 → 읽는 사람이 얻는 것으로 시작할 것: '{first[:40]}'")
    elif NEWSY_RE.search(first) and not GAIN_RE.search(first):
        warnings.append(f"캡션 첫 줄이 소식 전달임 → 얻는 것을 먼저 (예: '~하는 법', '~해 보세요'): '{first[:40]}'")
    tail = [l for l in lines if not l.startswith("#")][-2:]
    if dm_keyword and any(dm_keyword in l and "댓글" in l for l in tail):
        return warnings  # 댓글 키워드 안내(자동 DM)로 끝나면 충분
    if not any("?" in l and "댓글" in l for l in tail):
        warnings.append("캡션 끝에 댓글을 부르는 질문이 없음 (예: '어디에 써 보고 싶나요? 댓글로 알려 주세요')")
    return warnings


# ---- 인스타 추천 체크리스트 (STYLE_GUIDE 9장) ----
REEL_REC_MAX_SECONDS = 180      # 3분이 넘는 릴스는 추천(둘러보기·릴스 탭)에 못 나간다 (Instagram for Creators)
CAPTION_FOLD = 125              # 피드에서 '더 보기' 전에 보이는 첫 부분
HASHTAG_RE = re.compile(r"(?<![\w&])#[0-9A-Za-z가-힣_]+")
# 다른 플랫폼·다른 인스타 계정의 영상: 재업로드는 '원본 아님'으로 추천에서 빠진다
REPOST_HOSTS = ("instagram.com", "tiktok.com", "facebook.com/reel", "fb.watch")
# 반응 구걸(engagement bait): 좋아요·공유·태그를 조르는 말
BAIT = ["좋아요 눌러", "좋아요 부탁", "좋아요 꾹", "공유 부탁", "공유해 주세요", "공유해주세요", "친구 태그", "친구를 태그",
        "태그해 주세요", "태그해주세요", "팔로우 부탁", "맞팔"]
TOPIC_ALIAS = {"챗gpt": ["chatgpt", "gpt", "오픈ai", "openai"], "chatgpt": ["챗gpt", "gpt"], "openai": ["오픈ai", "챗gpt", "chatgpt"],
               "제미나이": ["gemini", "구글"], "gemini": ["제미나이"], "클로드": ["claude", "앤트로픽"], "claude": ["클로드"],
               "앤트로픽": ["anthropic", "클로드"], "엔비디아": ["nvidia"], "구글": ["google", "제미나이"]}


def _norm(x):
    return re.sub(r"\s+", "", str(x)).lower()


def check_reach(post):
    """인스타 추천에 걸리는 것 (STYLE_GUIDE 9장). (errors, warnings)
    - 캡션 본문 해시태그 + hashtags 합이 5개 넘으면 오류 (인스타 제한, 2025-12)
    - 릴스 3분 초과 오류 (추천 대상 아님)
    - 인용 원본이 인스타·틱톡 등 다른 계정 영상이면 오류 (재업로드 = 원본 아님)
    - 캡션 첫 125자에 주제 이름(해시태그 주제어)이 없으면 경고 (검색은 캡션 키워드로 찾는다)
    - 좋아요·공유·태그 구걸 문구 경고"""
    errors, warnings = [], []
    cap = post.get("caption", "")
    tags = post.get("hashtags", []) or []
    in_cap = HASHTAG_RE.findall(cap)
    if in_cap:
        total = len({_norm(t) for t in list(tags) + in_cap})
        mx = CONFIG["limits"].get("hashtags_max", 5)
        if total > mx:
            errors.append(f"캡션 본문 해시태그 {len(in_cap)}개 + hashtags 합이 {total}개: 인스타는 게시물당 {mx}개까지 (STYLE_GUIDE 9장)")
        else:
            warnings.append(f"캡션 본문에 해시태그 {in_cap}: 해시태그는 hashtags 필드에만 (게시할 때 캡션 끝에 붙는다)")
    v = post.get("video") or {}
    if post.get("type") == "video" and v.get("end") not in (None, ""):
        keep = v.get("keep") or []
        d = sum(float(b) - float(a) for a, b in keep) if keep else float(v["end"]) - float(v.get("start", 0))
        if d > REEL_REC_MAX_SECONDS:
            errors.append(f"릴스 {d:.0f}초: 3분({REEL_REC_MAX_SECONDS}초)이 넘으면 추천에 못 나간다 (STYLE_GUIDE 9장)")
    if post.get("rights") == "quote":
        urls = [str(post.get("source_url", "")), str(v.get("source_url", ""))]
        bad = [u for u in urls if any(h in u.lower() for h in REPOST_HOSTS)]
        if bad:
            errors.append(f"인용 원본이 다른 SNS 계정 영상({bad[0][:60]}): 재업로드는 '원본 아님'으로 추천에서 빠지고 "
                          "워터마크가 남는다. 공식 유튜브·공식 사이트 원본에서 받을 것 (STYLE_GUIDE 9장)")
    first = cap.strip()[:CAPTION_FOLD]
    topics = [t.lstrip("#") for t in tags if str(t) != TAG_BRAND]
    if first and topics:
        f = _norm(first)
        names = set()
        for t in topics:
            n = _norm(t)
            names.add(n)
            names.update(TOPIC_ALIAS.get(n, []))
        if not any(n and n in f for n in names):
            warnings.append(f"캡션 첫 {CAPTION_FOLD}자에 주제 이름이 없음 (해시태그 {topics} 중 하나라도): "
                            "인스타 검색은 캡션 키워드로 찾는다. 첫 줄에 서비스·회사·인물 이름을 (STYLE_GUIDE 9장)")
    hit = [w for w in BAIT if w in cap]
    if hit:
        warnings.append(f"반응 구걸 문구 {hit}: 좋아요·공유·태그를 조르지 말고, 보낼 이유를 구체적으로 (예: '다음 주 회의 전에 팀에 보내 두세요') (STYLE_GUIDE 9장)")
    return errors, warnings


NC_RE = re.compile(r"(?i)\bBY[- ]?(SA[- ])?NC\b|\bNC[- ]?(SA|ND)\b|non[- ]?commercial|비상업|비영리\s*(전용|라이선스)|상업\s*(적\s*)?이용\s*(금지|불가)")


def _license_texts(node, path=""):
    """license·rights_note·credit·sources 이름처럼 소재 출처를 적는 자리의 글만 모은다."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            if k in ("license", "rights_note", "credit", "name") and isinstance(v, str):
                yield p, v
            else:
                yield from _license_texts(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _license_texts(v, f"{path}[{i}]")


def check_license(post):
    """비상업(NC) 라이선스 소재 금지 (운영자 결정 2026-11-16: "상업적으로 이용되는 것만").
    화풍·스킬·글꼴·음악·사진·코드 어느 것이든 license/rights_note/credit/sources에 NC가 보이면 오류. 캡션 출처 줄도 본다."""
    errs = []
    texts = list(_license_texts({k: post.get(k) for k in ("license", "rights_note", "credit", "sources", "slides", "thumb", "video", "assets")}))
    texts += [("caption", l) for l in (post.get("caption") or "").splitlines() if re.match(r"\s*(\S{1,2}\s*)?(출처|사진|화면|음악|글꼴|화풍|이미지)\s*[:：]", l)]
    for where, t in texts:
        m = NC_RE.search(t)
        if m:
            errs.append(f"비상업(NC) 라이선스 소재는 쓰지 않는다 ({where}: '{m.group(0)}') → 직접 만든 것이나 상업 이용이 되는 것(CC0, CC BY, MIT 등)으로 바꿀 것 (STYLE_GUIDE 2-1)")
    return errs


def _ends_l_geot(line):
    """'넘어야 할 것', '알아둘 것'처럼 ㄹ 받침 + '것'으로 끝나는지."""
    t = re.sub(r"[\s.!?…'\"’”]+$", "", line)
    m = re.search(r"([가-힣])\s*것$", t)
    return bool(m) and (ord(m.group(1)) - 0xAC00) % 28 == 8


def awkward_titles(post):
    """제목·소제목이 '~할 것'으로 끝나면 경고 (운영자 지적 2026-11-16: '돌아가려면 넘어야 할 것')."""
    out = []
    cands = [("제목", post.get("title", "")), ("썸네일 제목", (post.get("thumb") or {}).get("title", ""))]
    for i, s in enumerate(post.get("slides", []) or [], 1):
        for k in ("title", "heading"):
            cands.append((f"{i}번째 장 {k}", s.get(k, "")))
    for where, t in cands:
        ls = _lines(t or "")
        if ls and _ends_l_geot(ls[-1]):
            out.append(f"{where}이 '~할 것'으로 끝남: '{ls[-1]}' → 서술로 풀기 (예: '복귀하려면 이사회·주주·정부를 설득해야 합니다', '복귀를 막는 세 가지') (STYLE_GUIDE 4)")
    return out


def check_post(post):
    """(errors, warnings) 반환."""
    e, w = _check_post(post)
    return e + check_license(post), w + awkward_titles(post)


def _check_post(post):
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
            errors += title_sentence(t, f"{tag} 표지 제목", no_question=False)
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
            if kind == "prompt":
                prs = s.get("prompts") or ([s["prompt"]] if s.get("prompt") else [])
                if not prs or not all(str(x).strip() for x in prs):
                    errors.append(f"{tag} prompt 장은 복사해 쓸 프롬프트(prompt 또는 prompts) 필요")
                for x in prs:
                    if _len(x) > PROMPT_MAX:
                        errors.append(f"{tag} 프롬프트는 {PROMPT_MAX}자 이하 (길면 장을 나눌 것): {_len(x)}자")
                    if EMOJI_RE.search(str(x)):
                        errors.append(f"{tag} 프롬프트 안에도 이모지를 쓰지 않음")
            if kind == "stat" and not s.get("value"):
                errors.append(f"{tag} stat은 value 필요")
            all_text += [h, b, p, s.get("label", "")]
            if b:
                errors += body_sentences(b, f"{tag} 본문")
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

    e_f, w_f = check_format(post)
    errors += e_f
    warnings += w_f
    e_d, w_d = check_dm(post)
    errors += e_d
    warnings += w_d
    kw = ((post.get("dm") or {}).get("keyword") or CONFIG.get("dm", {}).get("keyword", "받기")) if post.get("dm") else None
    e_c, w_c = check_caption_hooks(post["caption"], kw)
    errors += e_c
    warnings += w_c

    if post["type"] == "carousel":
        errors_img, warnings_img = check_images(slides)
        errors += errors_img
        warnings += warnings_img

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
        errors += eumseum(t, "카드")
    errors += ai_tone(post["caption"].split("출처:")[0], "캡션")[0]
    for w in BANNED:
        if w in joined or w in post["caption"]:
            errors.append(f"금지 표현: '{w}'")
    for w in AWKWARD:
        if w in joined:
            warnings.append(f"번역투 의심: '{w}'")
    if EMOJI_RE.search(joined):
        errors.append("카드 안에는 이모지를 쓰지 않음")
    e_ce, w_ce = caption_style(post["caption"])
    errors += e_ce
    warnings += w_ce

    tags = post.get("hashtags", [])
    e_h, w_h = check_hashtags(tags)
    errors += e_h
    warnings += w_h
    cap = post["caption"] + "\n\n" + " ".join(tags)
    if len(cap) > 2200:
        errors.append("캡션+해시태그는 2,200자 이하")
    e_r, w_r = check_reach(post)
    errors += e_r
    warnings += w_r

    srcs = post["sources"]
    need = 1 if post["series"] in ("생존 가이드", "오픈소스", "AI 용어") else 2
    if len(srcs) < need:
        errors.append(f"'{post['series']}'는 출처 {need}개 이상 필요")
    for s in srcs:
        if not str(s.get("url", "")).startswith("http"):
            errors.append(f"출처 URL이 올바르지 않음: {s}")

    return errors, warnings
