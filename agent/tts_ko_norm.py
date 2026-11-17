"""한국어 TTS 읽기 정규화 + 받아쓰기 검증 (운영자 2026-11-17 "2주(이주)로 읽을 건지 2주(두주) 읽을 건지 … 실수 안 나게").

ElevenLabs에 보내기 전에 대본을 '말하는 그대로의 한글'로 바꾼다. 숫자는 뒤에 붙는 단위(셈 단위)를 보고 고유어(한·두·세·스무)와
한자어(일·이·삼)를 고르고, 영어·약자·브랜드는 assets/voice/ko_words.json 사전으로 한글로 바꾼다. 애매한 경우와 고른 읽기·이유는
assets/voice/reading_cases.md.

    from tts_ko_norm import normalize
    normalize("GPT-5가 2주 만에 9,680억 달러")  # → '지피티 파이브가 이 주 만에 구천육백팔십억 달러'

명령줄:
    py -3.12 agent/tts_ko_norm.py "오픈AI가 2주 만에 3개 모델"          # 읽을 글 보기 (모르는 영어는 경고)
    py -3.12 agent/tts_ko_norm.py --verify voice/01.mp3 --text "대본"   # faster-whisper로 받아써서 비교
    py -3.12 agent/tts_ko_norm.py --verify voice/01.mp3 --text-file 대본.txt --gate   # 다르면 종료 코드 1 (렌더링 전 관문)

검증은 받아쓰기가 숫자를 아라비아 숫자로 적는 경우(예: '2주')에는 이·두 중 무엇으로 읽었는지 구분하지 못한다(둘 다 맞음으로 본다).
한글로 적힌 곳(예: '두 주')은 글자 그대로 비교한다. 사람 귀 확인을 대신하지는 않는다.
"""
import argparse
import difflib
import json
import re
import sys
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS_FILE = ROOT / "assets" / "voice" / "ko_words.json"

# ---------------- 숫자 읽기 ----------------
DIG = "영일이삼사오육칠팔구"
N1 = ["", "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉"]
N1A = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]       # 단위 앞 (관형형)
N10 = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
EN_NUM = ["제로", "원", "투", "쓰리", "포", "파이브", "식스", "세븐", "에잇", "나인", "텐", "일레븐", "트웰브",
          "써틴", "포틴", "피프틴", "식스틴", "세븐틴", "에이틴", "나인틴", "트웬티"]
MONTH = {6: "유", 10: "시"}      # 6월 → 유월, 10월 → 시월
# 붙어 있는 두 수 범위 (3~4개 → 서너 개)
NATIVE_PAIR = {(1, 2): "한두", (2, 3): "두세", (3, 4): "서너", (4, 5): "네다섯", (5, 6): "대여섯",
               (6, 7): "예닐곱", (7, 8): "일고여덟", (8, 9): "여덟아홉"}


def _sino4(n):
    s = ""
    for unit, val in (("천", 1000), ("백", 100), ("십", 10)):
        d = n // val % 10
        if d:
            s += ("" if d == 1 else DIG[d]) + unit
    if n % 10:
        s += DIG[n % 10]
    return s


def sino(n):
    """정수 → 한자어 수: 9680 → 구천육백팔십, 10000 → 만, 100000000 → 일억."""
    n = int(n)
    if n == 0:
        return "영"
    if n < 0:
        return "마이너스 " + sino(-n)
    parts, units, i = [], ["", "만", "억", "조", "경", "해"], 0
    while n:
        g = n % 10000
        if g:
            w = "" if (i == 1 and g == 1) else _sino4(g)     # 10000은 '일만'이 아니라 '만'
            parts.append(w + units[i])
        n //= 10000
        i += 1
    return "".join(reversed(parts))


def native(n, attrib=True):
    """1~99 고유어 (attrib: 단위 앞 형태 한·두·세·네·스무). 100 이상·0은 한자어."""
    n = int(n)
    if not 1 <= n <= 99:
        return sino(n)
    t, o = divmod(n, 10)
    if o == 0:
        return "스무" if (t == 2 and attrib) else N10[t]
    return N10[t] + (N1A if attrib else N1)[o]


def en_num(s):
    """모델 버전 숫자를 영어로: '5' → 파이브, '4.5' → 포 점 파이브, '35' → 쓰리파이브."""
    def whole(w):
        w = w.lstrip("0") or "0"
        n = int(w)
        return EN_NUM[n] if n <= 20 else "".join(EN_NUM[int(c)] for c in w)
    a, _, b = s.partition(".")
    out = whole(a)
    if b:
        out += " 점 " + " ".join(EN_NUM[int(c)] for c in b)
    return out


def decimal_read(intpart, frac):
    """3.25 → 삼 점 이오 (소수점 아래는 한 자씩)."""
    return sino(int(intpart)) + " 점 " + "".join(DIG[int(c)] for c in frac)


# ---------------- 셈 단위 ----------------
# s: 한자어, n: 고유어(1~99, 100부터 한자어). 특수: hour(시), month(월), beon(번), dae(대), nth(번째), jjae(째)
COUNTERS = {}
for c in ("년", "일", "분", "초", "원", "달러", "유로", "엔", "위안", "파운드", "퍼센트", "퍼센트포인트", "위", "등", "배",
          "층", "호", "회", "회차", "개월", "개국", "개사", "개년", "주", "주년", "주차", "년대", "년도", "차", "세", "세대",
          "분기", "점", "학년", "기", "인", "인분", "부", "도", "킬로미터", "킬로그램", "미터", "그램", "리터", "톤", "페이지",
          "쪽", "프로", "명당", "억", "만", "조", "포인트", "비트", "바이트", "기가", "테라", "메가", "와트", "헤르츠", "나노"):
    COUNTERS[c] = "s"
for c in ("개", "명", "살", "마리", "가지", "달", "군데", "잔", "시간", "권", "병", "벌", "채", "척", "송이", "그루",
          "켤레", "장", "곡", "쌍", "판", "통", "마디", "사람", "줄", "끼", "모금", "걸음", "바퀴", "팀", "편", "자루",
          "개비", "알", "방울", "숟가락", "그릇", "봉지", "상자", "박스", "덩어리", "글자", "단어", "문장"):
    COUNTERS[c] = "n"
COUNTERS.update({"시": "hour", "월": "month", "번": "beon", "대": "dae", "번째": "nth", "째": "jjae"})
COUNTERS.pop("억"), COUNTERS.pop("만"), COUNTERS.pop("조")      # 큰 단위는 수의 일부로 따로 처리
_COUNTER_RE = "|".join(sorted(map(re.escape, COUNTERS), key=len, reverse=True))
# 한 글자 단위 뒤에 다른 글자가 붙으면 다른 낱말일 수 있다(2시즌, 3세계, 1등급). 이 글자들(조사 등)만 허용.
_FOLLOW_OK = set("이가을를은는에의도만과와로으까부씩째쯤간량정동전후뒤안내당께엔요야란며면서지고다랑밖보치중짜만")
# '번' 뒤에 이 낱말이 오면 번호(한자어): 3번 출구, 1번 문제
BEON_SINO = ("출구", "문제", "타자", "선수", "버스", "채널", "트랙", "게이트", "항목", "카드", "질문", "프롬프트", "선택지",
             "국도", "방", "홀", "레인", "슬라이드", "장면", "후보", "답", "줄", "칸", "열차", "노선", "기사", "영상", "사진")
# '대' 뒤에 이 낱말이 오면 순위·묶음(한자어): 3대 기업, 10대 뉴스
DAE_SINO = ("기업", "강국", "그룹", "은행", "도시", "과제", "원칙", "빅테크", "테크", "남성", "여성", "남녀", "청년", "직장인",
            "이슈", "뉴스", "트렌드", "플랫폼", "메이저", "회사", "거래소", "통신사", "대통령", "의원", "핵심", "분야", "산업",
            "업종", "요소", "기술", "제품", "서비스", "모델", "국가", "시장", "부자", "재벌", "명문", "학생", "자녀", "엄마", "아빠")

# 수: 1,234 / 1234 / 1.5, 뒤에 천·백·십(선택)과 만·억·조(선택). 앞에 글자·숫자·점이 붙어 있으면 수가 아님(버전 3.5.1 등)
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:(천|백|십)(?=[만억조경]|[^가-힣]|$|[원명개달년]))?([만억조경])?"
NUM_RE = re.compile(r"(?<![\dA-Za-z.])" + _NUM + r"(?:(\s?)(" + _COUNTER_RE + r"))?")


def _int(s):
    return int(s.replace(",", ""))


def num_core(intpart, frac=None, small=None, big=None):
    """수 부분만 한자어로 (큰 단위 포함): ('9,680', None, None, '억') → 구천육백팔십억, ('1', '2', None, '조') → 일 점 이 조."""
    n = _int(intpart)
    if frac:
        s = decimal_read(n, frac)
        if small:
            s += " " + small
        return s + (" " + big if big else "")
    if small:
        s = ("" if n == 1 else sino(n)) + small        # 1천 → 천
    else:
        s = sino(n) if n else "영"
    if big:
        if s == "일" and big == "만":                  # 1만 → 만
            s = ""
        s += big
    if len(intpart) > 1 and intpart.startswith("0") and not frac and not small and not big:
        s = "".join("공" if c == "0" else DIG[int(c)] for c in intpart)    # 007 → 공공칠
    return s


def _next_word(text, pos):
    m = re.match(r"\s*([가-힣A-Za-z]+)", text[pos:])
    return m.group(1) if m else ""


def read_count(intpart, frac, small, big, counter, text="", end=0, bare=False):
    """수 + 셈 단위 → (수 읽기, 단위 읽기, 붙여 쓰기 여부)."""
    kind = COUNTERS.get(counter)
    plain = not (frac or small or big)
    n = _int(intpart) if plain else None
    if kind is None:
        return num_core(intpart, frac, small, big), "", False
    if not plain:
        if kind == "month":
            kind = "s"
        return num_core(intpart, frac, small, big), counter, False
    if kind == "s":
        return num_core(intpart), counter, False
    if kind == "month":
        return (MONTH.get(n) or sino(n)), "월", True
    if kind == "hour":
        return (native(n, not bare) if 1 <= n <= 12 else sino(n)), "시", False
    if kind == "beon":
        if _next_word(text, end).startswith(BEON_SINO):
            return sino(n), "번", False
        return native(n, not bare), "번", False
    if kind == "dae":
        w = _next_word(text, end)
        if (n >= 10 and n % 10 == 0) or w.startswith(DAE_SINO):
            return sino(n), "대", False                 # 20대(나이대), 3대 기업
        return native(n, not bare), "대", False          # 차 두 대
    if kind == "nth":
        return ("첫" if n == 1 else native(n)), "번째", False
    if kind == "jjae":
        if n <= 4:
            return ["", "첫째", "둘째", "셋째", "넷째"][n], "", True
        return native(n), "째", True
    return native(n, not bare), counter, False          # 고유어 셈 단위


def _join(num, counter, attached):
    if not counter:
        return num
    return num + counter if attached else num + " " + counter


def _count_sub(m, text):
    intpart, frac, small, big, _sp, counter = m.groups()
    if counter and len(counter) == 1 and counter not in ("째",):
        nxt = text[m.end():m.end() + 1]
        if nxt and "가" <= nxt <= "힣" and nxt not in _FOLLOW_OK:
            # 2시즌, 3세계처럼 단위가 아니라 낱말의 첫 글자: 수만 읽는다
            return num_core(intpart, frac, small, big) + (_sp or "") + counter
    num, c, att = read_count(intpart, frac, small, big, counter, text, m.end())
    return _join(num, c, att)


def _range_sub(m, text):
    a_int, a_frac, a_small, a_big, sep, b_int, b_frac, b_small, b_big, _sp, counter = m.groups()
    b_m_end = m.end()
    if counter and len(counter) == 1:
        nxt = text[b_m_end:b_m_end + 1]
        if nxt and "가" <= nxt <= "힣" and nxt not in _FOLLOW_OK:
            counter = None
    rest = ""
    if counter is None and m.group(11):
        rest = (_sp or "") + m.group(11)
    kind = COUNTERS.get(counter)
    b_num, c, att = read_count(b_int, b_frac, b_small, b_big, counter, text, b_m_end)
    plain = not (a_frac or a_small or a_big or b_frac or b_small or b_big)
    if plain and kind in ("n", "hour", "dae", "beon") and b_num != sino(_int(b_int)):
        a, b = _int(a_int), _int(b_int)
        if (a, b) in NATIVE_PAIR:
            return _join(NATIVE_PAIR[(a, b)], c, att) + rest
        a_num = native(a, attrib=False)
    elif kind == "month" and plain:
        a_num = (MONTH.get(_int(a_int)) or sino(_int(a_int))) + "월"
    else:
        a_num = num_core(a_int, a_frac, a_small, a_big)
    return a_num + "에서 " + _join(b_num, c, att) + rest


RANGE_RE = re.compile(r"(?<![\dA-Za-z.])" + _NUM + r"\s?([~∼〜–])\s?" + _NUM + r"(?:(\s?)(" + _COUNTER_RE + r"))?")
RANGE_HY_RE = re.compile(r"(?<![\dA-Za-z.\-])" + _NUM + r"(-)" + _NUM + r"(?:(\s?)(" + _COUNTER_RE + r"))(?![\d])")


# ---------------- 사전 ----------------
@lru_cache(maxsize=None)
def _load_words(path=str(WORDS_FILE)):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d.get("words", {}), tuple(d.get("models", []))


def _word_re(key):
    k = re.escape(key).replace(r"\ ", r"[\s\-]?")
    return r"(?<![A-Za-z0-9])" + k + r"(?![A-Za-z0-9])"


def _case_sensitive(key):
    return key.isupper() and len(key.replace("&", "")) <= 5


@lru_cache(maxsize=64)
def _compiled(extra_items):
    words, models = _load_words()
    words = dict(words)
    words.update(dict(extra_items))
    pats = []
    for k in sorted(words, key=len, reverse=True):
        flags = 0 if _case_sensitive(k) else re.I
        pats.append((re.compile(_word_re(k), flags), words[k], bool(re.search(r"[\s\-·&.0-9]", k))))
    lower = {k.lower(): v for k, v in words.items()}                 # 모델 이름용 (대소문자 무시)
    loose = {k.lower(): v for k, v in words.items() if not _case_sensitive(k)}   # 남은 낱말용
    model_alt = "|".join(sorted(map(re.escape, models), key=len, reverse=True))
    model_re = re.compile(r"(?<![A-Za-z0-9])(" + model_alt + r")[\s\-]?(\d{1,2}(?:\.\d{1,2})?)([a-z])?(?![\d.]?\d)", re.I)
    return pats, lower, loose, model_re


_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    "에이 비 씨 디 이 에프 지 에이치 아이 제이 케이 엘 엠 엔 오 피 큐 알 에스 티 유 브이 더블유 엑스 와이 제트".split()))


def spell(w):
    return "".join(_LETTERS[c] for c in w.upper() if c in _LETTERS)


# ---------------- 전체 ----------------
MULT = {"K": 10 ** 3, "k": 10 ** 3, "M": 10 ** 6, "B": 10 ** 9, "T": 10 ** 12, "천": 10 ** 3, "만": 10 ** 4,
        "억": 10 ** 8, "조": 10 ** 12}
CURRENCY = {"$": "달러", "US$": "달러", "₩": "원", "€": "유로", "£": "파운드", "¥": "엔"}
UNITS_EN = {"km": "킬로미터", "kg": "킬로그램", "cm": "센티미터", "mm": "밀리미터", "nm": "나노미터", "GB": "기가바이트",
            "TB": "테라바이트", "MB": "메가바이트", "GHz": "기가헤르츠", "kW": "킬로와트", "MW": "메가와트",
            "GW": "기가와트", "kWh": "킬로와트시", "fps": "에프피에스", "°C": "도", "℃": "도", "%p": "퍼센트포인트",
            "%": "퍼센트", "x": "배", "X": "배", "×": "배", "B": "비", "m": "미터", "g": "그램", "W": "와트"}


def _money(m):
    sym, intpart, frac, mult = m.group(1), m.group(2), m.group(3), m.group(4)
    unit = CURRENCY[sym]
    if mult:
        v = Decimal(intpart.replace(",", "") + ("." + frac if frac else "")) * MULT[mult]
        if v == v.to_integral_value():
            return sino(int(v)) + " " + unit
    if frac:
        return decimal_read(_int(intpart), frac) + " " + unit
    return sino(_int(intpart)) + " " + unit


def _date(m):
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{sino(y)} 년 {MONTH.get(mo) or sino(mo)}월 {sino(d)} 일"


def _time(m):
    h, mi = int(m.group(1)), int(m.group(2))
    s = (native(h) if 1 <= h <= 12 else sino(h)) + " 시"
    return s + (f" {sino(mi)} 분" if mi else "")


def normalize(text, words=None, numbers=True, warn=None):
    """대본 → 읽을 한글. words: 게시물별 추가 사전 {영어: 한글}. numbers=False면 숫자는 그대로(검증용).
    warn: 리스트를 넘기면 사전에 없는 영어 낱말을 담는다."""
    if not text:
        return text
    pats, lower, loose, model_re = _compiled(tuple(sorted((words or {}).items())))
    t = text.replace(" ", " ")
    t = re.sub(r"[☀-➿\U0001F000-\U0001FAFF️‍]", "", t)        # 이모지

    # 1) 사전의 여러 단어·브랜드 (GPT-5보다 'o4-mini'·'Open AI'가 먼저)
    for p, v, multi in pats:
        if multi:
            t = p.sub(v, t)
    # 2) 모델 이름 + 버전: GPT-5 → 지피티 파이브, GPT-4o → 지피티 포오, Claude Opus 4.5 → … 포 점 파이브
    def model(m):
        name = lower.get(m.group(1).lower(), m.group(1))
        tail = (" " + en_num(m.group(2))) if numbers else (" " + m.group(2))
        if m.group(3):
            tail += lower.get(m.group(3).lower()) or spell(m.group(3))
        return name + tail
    t = model_re.sub(model, t)
    for p, v, _ in pats:
        t = p.sub(v, t)

    if numbers:
        # 3) 돈·날짜·시각·비율
        t = re.sub(r"(US\$|[$₩€£¥])\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s?([KMBT천만억조](?![A-Za-z]))?", _money, t)
        t = re.sub(r"(?<!\d)(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)\.?", _date, t)
        t = re.sub(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?![\d:])", _time, t)
        t = re.sub(r"(?<![\d:])(\d+):(\d+)(?![\d:])", lambda m: f"{sino(m.group(1))} 대 {sino(m.group(2))}", t)
        # 3-1) 음수 (-3% → 마이너스 삼 퍼센트)
        t = re.sub(r"(?:(?<=\s)|^)[-−](?=\d)", "마이너스 ", t)
        # 4) 영어 단위·배수·K/M (70B 모델 → 칠십 비, 10x → 십 배, 1M 토큰 → 백만 토큰)
        def km(m):
            v = Decimal(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else "")) * MULT[m.group(3)]
            return sino(int(v)) if v == v.to_integral_value() else m.group(0)
        t = re.sub(r"(?<![\dA-Za-z.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?([KkMT])(?![A-Za-z])", km, t)
        ualt = "|".join(sorted(map(re.escape, UNITS_EN), key=len, reverse=True))
        t = re.sub(r"(?<![\dA-Za-z.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s?(" + ualt + r")(?![A-Za-z])",
                   lambda m: num_core(m.group(1), m.group(2)) + " " + UNITS_EN[m.group(3)], t)
        # 6) 범위 (70~78달러 → 칠십에서 칠십팔 달러, 3~4개 → 서너 개)
        t = RANGE_RE.sub(lambda m: _range_sub(m, m.string), t)
        t = RANGE_HY_RE.sub(lambda m: _range_sub(m, m.string), t)
        # 7) 수 + 셈 단위
        t = NUM_RE.sub(lambda m: _count_sub(m, m.string), t)

    # 8) 남은 영어: 글자+숫자(H100 → 에이치백), 대문자 약자는 한 글자씩, 나머지는 그대로 두고 경고
    def letnum(m):
        n = int(m.group(2))
        return spell(m.group(1)) + (EN_NUM[n] if n <= 10 else sino(n))
    if numbers:
        t = re.sub(r"(?<![A-Za-z0-9])([A-Z]{1,2})(\d{1,4})(?![A-Za-z0-9])", letnum, t)

    def eng(m):
        w = m.group(0)
        if w.lower() in loose:
            return loose[w.lower()]
        if w.isupper() and len(w) <= 6:
            return spell(w)
        if warn is not None:
            warn.append(w)
        return w
    t = re.sub(r"[A-Za-z]+", eng, t)

    # 9) 기호
    t = re.sub(r"\s*&\s*", " 앤드 ", t)
    t = re.sub(r"(?<=[가-힣])\s*\+\s*(?=[가-힣])", " 플러스 ", t)
    t = t.replace("%", " 퍼센트").replace("#", "").replace("@", " 앳 ")
    t = re.sub(r"\s*[→⇒➡]\s*", ", ", t)
    t = re.sub(r"(?<=\S)[~∼〜]\s?(?=\S)", "에서 ", t)
    t = re.sub(r"(?<=[가-힣])-(?=[가-힣])", " ", t)       # 칠십 달러~칠십팔 달러
    t = re.sub(r"[~∼〜]", "", t)                                # ~2029년쯤 → 이천이십구 년쯤
    t = re.sub(r"[\"“”‘’'「」『』<>《》\[\]{}*_|]", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t).strip()
    return t


def unknown_words(text, words=None):
    w = []
    normalize(text, words, warn=w)
    return sorted(set(w))


# ---------------- 받아쓰기 검증 ----------------
def _compact(s):
    return re.sub(r"[^가-힣0-9]", "", s)


NUM_SYL = set("영일이삼사오육칠팔구십백천만억조공한두세네섯여곱덟홉열스무물서른마흔쉰예순흔첫둘셋넷유시")


def _num_candidates(digits):
    n = int(digits)
    c = {sino(n), native(n, True), native(n, False), en_num(digits).replace(" ", "")}
    if n in MONTH:
        c.add(MONTH[n])
    if n == 1:
        c |= {"첫", "첫째", ""}
    if n <= 4:
        c.add(["", "첫째", "둘째", "셋째", "넷째"][n])
    if n in (3, 4):
        c |= {"서", "너", "석", "넉"}
    return c


def compare(expected_text, heard, words=None, min_ratio=0.9, min_len=2):
    """expected_text(대본, 정규화 전이든 후든) vs heard(받아쓰기 글) → dict(ok, ratio, diffs, expected, heard).
    받아쓰기에 아라비아 숫자가 있으면 그 자리를 한자어·고유어 중 대본에 가장 맞는 읽기로 본다(숫자 읽기는 구분 못 함)."""
    exp = _compact(normalize(expected_text, words))
    h = normalize(heard, words, numbers=False)
    h = re.sub(r"(\d+)\.(\d+)", lambda m: sino(m.group(1)) + "점" + "".join(DIG[int(c)] for c in m.group(2)), h)
    h = re.sub(r"(?<=\d),(?=\d{3})", "", h)
    h = h.replace("%", "퍼센트")
    hc = _compact(h)
    for _ in range(50):
        m = re.search(r"\d+", hc)
        if not m:
            break
        best = max(_num_candidates(m.group()),
                   key=lambda c: difflib.SequenceMatcher(None, exp, hc[:m.start()] + c + hc[m.end():]).ratio())
        hc = hc[:m.start()] + best + hc[m.end():]
    sm = difflib.SequenceMatcher(None, exp, hc, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if max(i2 - i1, j2 - j1) >= min_len or set(exp[i1:i2] + hc[j1:j2]) & NUM_SYL:   # 숫자 읽기는 한 글자도
            diffs.append({"expected": exp[i1:i2], "heard": hc[j1:j2],
                          "context": exp[max(0, i1 - 6):i1] + "[" + exp[i1:i2] + "]" + exp[i2:i2 + 6]})
    ratio = sm.ratio()
    return {"ok": ratio >= min_ratio and not diffs, "ratio": round(ratio, 3), "diffs": diffs,
            "expected": exp, "heard": hc}


_whisper = {}


def transcribe(path, model="small", prompt=None):
    """faster-whisper(이 컴퓨터, 무료)로 한국어 받아쓰기."""
    from faster_whisper import WhisperModel
    if model not in _whisper:
        _whisper[model] = WhisperModel(model, device="cpu", compute_type="int8")
    import shutil
    import subprocess

    import numpy as np
    ff = shutil.which("ffmpeg") or sys.exit("ffmpeg가 없다")        # av 버전과 상관없이 ffmpeg로 16kHz 모노
    raw = subprocess.run([ff, "-nostdin", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32).copy()
    segs, _ = _whisper[model].transcribe(audio, language="ko", beam_size=5, initial_prompt=prompt,
                                          condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segs)


def verify_audio(path, text, words=None, model="small", min_ratio=0.9):
    """만든 음성 파일을 받아써서 대본과 비교. 반환: compare() 결과 + 'asr'."""
    heard = transcribe(path, model)
    r = compare(text, heard, words, min_ratio=min_ratio)
    r["asr"] = heard
    return r


def print_verify(r, out=sys.stdout):
    print(f"받아쓰기: {r['asr']}", file=out)
    print(f"일치율 {r['ratio']:.3f} → {'통과' if r['ok'] else '확인 필요'}", file=out)
    for d in r["diffs"]:
        print(f"  ! 대본 '{d['expected']}' / 들림 '{d['heard']}'  ({d['context']})", file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", help="정규화해 볼 글")
    ap.add_argument("--verify", help="받아써서 비교할 음성 파일 (mp3/wav)")
    ap.add_argument("--text", dest="text_opt", help="--verify의 대본")
    ap.add_argument("--text-file", help="--verify의 대본 파일 (utf-8)")
    ap.add_argument("--words", help="추가 사전 JSON, 예: {\"Foo\": \"푸\"}")
    ap.add_argument("--model", default="small", help="faster-whisper 모델 (기본 small)")
    ap.add_argument("--min-ratio", type=float, default=0.9)
    ap.add_argument("--gate", action="store_true", help="다르면 종료 코드 1")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    words = json.loads(a.words) if a.words else None
    script = a.text_opt or (Path(a.text_file).read_text(encoding="utf-8") if a.text_file else None) or a.text
    if a.verify:
        if not script:
            ap.error("--verify에는 --text나 --text-file이 필요하다")
        r = verify_audio(a.verify, script, words, a.model, a.min_ratio)
        print(f"읽을 글: {normalize(script, words)}")
        print_verify(r)
        if a.gate and not r["ok"]:
            sys.exit(1)
        return
    if not script:
        ap.error("글이 필요하다")
    w = []
    print(normalize(script, words, warn=w))
    if w:
        print(f"  ! 사전에 없는 영어(그대로 둠, assets/voice/ko_words.json에 추가): {', '.join(sorted(set(w)))}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
