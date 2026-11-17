"""목소리(TTS) 만들기: 목록형 자료 릴스의 영어 용어 읽기(운영자 결정 2026-11-17) + 한국어 내레이션.

엔진(영어): Kokoro-82M (Apache-2.0). pip 패키지 `kokoro`(PyPI) + 모델·음성은 Hugging Face hexgrad/Kokoro-82M에서 처음 쓸 때 자동으로 받는다.
엔진(한국어): MeloTTS 한국어 (코드·모델 MIT, myshell-ai). 코드 github.com/myshell-ai/MeloTTS, 모델 Hugging Face myshell-ai/MeloTTS-Korean,
       단어 분석용 BERT kykim/bert-kor-base(Apache-2.0)도 처음 쓸 때 자동으로 받는다. 여자 목소리 하나, 44.1kHz.
       출처·라이선스 기록: assets/voice/README.md. 설치: MIGRATION.md. 유료 API·계정 없음.
       ※ 운영자가 MeloTTS 한국어를 쓰지 않기로 함(2026-11-17 "읽는법이 좀 그래서"). 한국어 내레이션은 아래 ElevenLabs.
엔진(한국어 내레이션, 기본): ElevenLabs (유료 Starter, 상업 이용 가능, 운영자 결정 2026-11-17). 남자 목소리 기본 'Deok'(예능 내레이션).
       내레이션 모션 릴스(narrated)는 agent/narrated_reel.py --voice가 이 모듈로 장면마다 만든다.
       API 키는 사용자 환경 변수 ELEVENLABS_API_KEY (윈도우는 레지스트리 HKCU\\Environment에서도 읽음). 키는 출력·기록·커밋하지 않는다.
       글자 수로 요금이 나가므로(Starter 월 약 3만 자) 같은 글·목소리·설정이면 사용자 캐시
       (%USERPROFILE%\\.cache\\tokenwar-tts\\elevenlabs\\<해시>.mp3)를 다시 쓰고, 빠르기를 올릴 때도 다시 부르지 않고 ffmpeg atempo로 늘린다.
GitHub Actions에는 세 엔진 다 없다. 그래서 이 컴퓨터에서 미리 만들어 게시물 폴더 voice/<번호>.wav(목록형은 24kHz 모노, 작게)로 넣고,
listreel.py는 그 파일을 박자에 맞춰 섞기만 한다. voice/가 없으면 목소리 없이 예전처럼 동작한다.

사용법:
    py -3.12 agent/tts.py posts/queue/<폴더> [--voice af_heart] [--force]
    py -3.12 agent/tts.py --text "만약 AI에게 내 돈을 맡겨 투자시킨다면, 어떤 일이 벌어질까요?" --out <폴더>/voice/01.wav [--lang ko] [--speed 1.1]
  - list.items[].en(영어 용어)을 읽는다. list.voice(선택)에 {"voice": "af_heart", "speed": 1.0, "say": {"07": "split lighting"}}로
    목소리·빠르기·읽을 문장을 바꿀 수 있다 (say: 번호별로 화면 글자와 다르게 읽을 때, 예: 약자).
  - list.voice.lang = "ko"(선택, 없으면 "en" 예전 그대로)면 MeloTTS로 한국어를 읽는다. 읽는 글은 say > 항목 name.
  - --text: 문장 하나를 바로 wav로 (내레이션 릴스용). --lang 기본 ko, en이면 Kokoro. 한국어는 44.1kHz.
    py -3.12 agent/tts.py --engine elevenlabs --voice Hyuk --text "..." --out <폴더>/voice/01.mp3   (.mp3면 받은 그대로, .wav면 무음 자르고 44.1kHz)
    py -3.12 agent/tts.py --engine elevenlabs --list-voices     # 계정 목소리 + 라이브러리 한국어 남자 목소리
    ElevenLabs는 보내기 전에 agent/tts_ko_norm.py로 숫자·영어를 읽는 그대로의 한글로 바꾼다(2주 → 이 주, GPT-5 → 지피티 파이브).
    끄기 --no-norm / voice.normalize: false, 게시물별 추가 사전 --words / voice.words. --verify [--gate]: 받아써서 대본과 비교.
  - list.voice.engine = "elevenlabs"(선택)면 ElevenLabs로 읽는다: {"engine": "elevenlabs", "voice_id": "...", "settings": {"stability": 0.5}}.
    voice_id가 없으면 ELEVEN_DEFAULT_VOICE. 게시물 맨 위 "voice"(같은 모양, 선택)도 기본값으로 읽는다.
  - 한국어 글: 숫자·%·연도는 그대로 써도 된다(10% → 십 퍼센트). 영어는 아는 이름(챗GPT, 오픈AI 등)과 약자만 한글로 바꾸고,
    모르는 영어 단어는 글자 하나씩 읽으니 대본에 한글로 쓴다 (예: "Sora" 대신 "소라").
  - 말 앞뒤 무음을 잘라 그림이 바뀌는 박에 바로 말이 시작되게 하고, 항목 길이보다 길면 빠르기를 올려 다시 만든다.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import types
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

SR = 24000
DEFAULT_VOICE = "af_heart"      # 차분하고 또렷한 미국 영어 여성 내레이터 (Kokoro 음성 중 품질 등급이 가장 높음)
MAX_SPEED = 1.4


def trim(x, thr=0.012, pad=0.01, sr=SR):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    a = max(0, idx[0] - int(pad * sr))
    z = min(len(x), idx[-1] + int(0.06 * sr))
    y = x[a:z].copy()
    f = int(0.008 * sr)
    y[:f] *= np.linspace(0, 1, f)
    y[-f * 3:] *= np.linspace(1, 0, f * 3)
    return y


def frame_db(x, sr, win=0.01):
    """10ms 창 RMS(dBFS) 배열."""
    n = int(win * sr)
    m = len(x) // n
    if not m:
        return np.array([-120.0])
    r = np.sqrt(np.mean(np.square(x[:m * n].reshape(m, n)), axis=1))
    return 20 * np.log10(np.maximum(r, 1e-6))


def trim_breath(x, sr, floor_db=-45.0, head=0.03, tail=0.06, offset=False):
    """앞뒤 무음만 자른다 (말끝·숨 끝을 자르지 않게): 10ms 에너지가 floor_db(최대 대비)보다 큰 첫·끝 창을 찾고
    앞 30ms, 뒤 60ms를 남긴 뒤 짧게 페이드 (운영자 2026-11-17 "호흡이 어색한 부분")."""
    db = frame_db(x, sr)
    on = np.where(db > db.max() + floor_db)[0]
    if not len(on):
        return (x, 0.0) if offset else x
    a = max(0, int((on[0] * 0.01 - head) * sr))
    z = min(len(x), int(((on[-1] + 1) * 0.01 + tail) * sr))
    y = x[a:z].copy()
    f = int(0.005 * sr)
    y[:f] *= np.linspace(0, 1, f)
    g = int(0.03 * sr)
    y[-g:] *= np.linspace(1, 0, g)
    return (y, a / sr) if offset else y


def remap_time(t, trim_offset, fixes):
    """원래 음성 시각 → trim_breath(offset)·tighten_pauses(fixes) 뒤 시각."""
    t = t - trim_offset
    shift = 0.0
    for pos, dur, keep in fixes:
        if t >= pos + dur:
            shift += dur - keep
        elif t > pos + keep / 2:
            shift += t - pos - keep / 2
    return max(0.0, t - shift)


def tighten_pauses(x, sr, max_gap=0.35, keep=0.22, floor_db=-40.0):
    """문장 안 긴 쉼(max_gap초 넘는 무음)을 keep초로 줄인다 (가운데를 잘라 20ms 크로스페이드). 반환 (오디오, [(위치초, 원래초, 줄인초)])."""
    db = frame_db(x, sr)
    quiet = db < db.max() + floor_db
    out, last, fixes = [], 0, []
    i = 0
    n = len(quiet)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            dur = (j - i) * 0.01
            if dur > max_gap and i > 0 and j < n:
                cut_a = int((i * 0.01 + keep / 2) * sr)
                cut_z = int((j * 0.01 - keep / 2) * sr)
                out.append(x[last:cut_a])
                last = cut_z
                fixes.append((round(i * 0.01, 2), round(dur, 2), keep))
            i = j
        else:
            i += 1
    out.append(x[last:])
    if not fixes:
        return x, []
    y = out[0]
    c = int(0.02 * sr)
    for seg in out[1:]:
        if len(y) > c and len(seg) > c:
            y = np.concatenate([y[:-c], y[-c:] * np.linspace(1, 0, c) + seg[:c] * np.linspace(0, 1, c), seg[c:]])
        else:
            y = np.concatenate([y, seg])
    return y, fixes


def save(path, x, sr=SR):
    path.parent.mkdir(parents=True, exist_ok=True)
    x = x / (np.max(np.abs(x)) or 1) * 0.9
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


# ---------------- 한국어 (MeloTTS) ----------------
KO_SR = 44100
# 영어 이름 → 한글 읽기 (대소문자 무시). 없으면 MeloTTS 사전(AI, CEO 등) → 그래도 없으면 글자 하나씩.
KO_WORDS = {
    "chatgpt": "챗지피티", "gpt": "지피티", "openai": "오픈에이아이", "google": "구글", "gemini": "제미나이",
    "claude": "클로드", "anthropic": "앤트로픽", "nvidia": "엔비디아", "samsung": "삼성", "naver": "네이버",
    "kakao": "카카오", "apple": "애플", "iphone": "아이폰", "microsoft": "마이크로소프트", "meta": "메타",
    "tesla": "테슬라", "youtube": "유튜브", "instagram": "인스타그램", "grok": "그록", "sora": "소라",
    "copilot": "코파일럿", "deepseek": "딥시크", "app": "앱", "pro": "프로", "max": "맥스", "mini": "미니",
}
_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    "에이 비 씨 디 이 에프 지 에이치 아이 제이 케이 엘 엠 엔 오 피 큐 알 에스 티 유 브이 더블유 엑스 와이 제트".split()))


def ko_text(text):
    """MeloTTS가 못 읽거나 잘못 읽는 것을 한글로: 영어 낱말, 소수점(3.5 → 3 점 5)."""
    text = re.sub(r"(\d)\.(\d)", r"\1 점 \2", text)

    def word(m):
        w = m.group()
        if w.lower() in KO_WORDS:
            return KO_WORDS[w.lower()]
        try:
            from melo.text.ko_dictionary import english_dictionary
            if len(w) > 1 and w.upper() in english_dictionary:
                return english_dictionary[w.upper()]
        except ImportError:
            pass
        if len(w) > 4 and not w.isupper():
            print(f"  ! 모르는 영어 단어 {w!r}: 글자 하나씩 읽음. 대본에 한글로 쓰세요", file=sys.stderr)
        return "".join(_LETTERS[c] for c in w.upper())
    return re.sub(r"[A-Za-z]+", word, text)


def _melo_shims():
    """MeloTTS는 import할 때 모든 언어(중국어·일본어 등) 모듈을 불러 무거운 패키지를 요구한다.
    한국어만 쓰므로 다른 언어 모듈은 빈 모듈로 막고, 윈도우에서 g2pkk가 찾는 eunjeon(빌드 안 됨)은 python-mecab-ko로 대신한다
    (g2pkk는 eunjeon이 없으면 스스로 pip install을 돌리므로 반드시 먼저 넣는다)."""
    from importlib.machinery import ModuleSpec

    def stub(name, **attrs):
        m = types.ModuleType(name)
        m.__spec__ = ModuleSpec(name, None)
        m.__dict__.update(attrs)
        sys.modules.setdefault(name, m)
    for n in ["chinese", "japanese", "english", "chinese_mix", "french", "spanish",
              "chinese_bert", "english_bert", "spanish_bert", "french_bert"]:
        stub("melo.text." + n, get_bert_feature=None)
    for n in ["torchaudio", "cached_path"]:          # 한국어 합성에서는 쓰지 않는다
        if importlib.util.find_spec(n) is None:
            stub(n, cached_path=None)
    if sys.platform == "win32" and importlib.util.find_spec("eunjeon") is None:
        import mecab

        class Mecab:
            def __init__(self):
                self.m = mecab.MeCab()

            def pos(self, s):
                return self.m.pos(s)
        stub("eunjeon", Mecab=Mecab)


_ko = None


def ko_engine():
    global _ko
    if _ko is None:
        _melo_shims()
        import logging
        import warnings
        logging.getLogger("transformers").setLevel(logging.ERROR)
        warnings.filterwarnings("ignore")
        from melo.api import TTS
        _ko = TTS(language="KR", device="cpu")
    return _ko


def synth_ko(text, speed=1.0):
    """한국어 문장 → 44.1kHz float32 (앞뒤 무음은 그대로)."""
    tts = ko_engine()
    x = tts.tts_to_file(ko_text(text), tts.hps.data.spk2id["KR"], None, speed=speed, quiet=True)
    return np.asarray(x, dtype=np.float32)


def to_sr(x, sr_from, sr_to):
    if sr_from == sr_to:
        return x
    import librosa
    return librosa.resample(x, orig_sr=sr_from, target_sr=sr_to).astype(np.float32)


# ---------------- 한국어 내레이션 (ElevenLabs) ----------------
ELEVEN_API = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_FORMAT = "mp3_44100_128"
# 목소리 별칭 (assets/voice/README.md "쓰는 목소리"). 라이브러리 목소리는 ID로 바로 부른다.
# 운영자 2026-11-17: "어그로가 잘 끌리는 목소리" → 쇼츠형 후킹 목소리 2차 후보(deok·gapdragon·kangjun). 1차(hyuk·krys·kyle)는 반려.
ELEVEN_VOICES = {
    "deok": "wisKdlUQEBMjkKqNAa3c",       # Deok - Energetic Korean Narrator: 예능 자막 톤, 첫마디부터 높고 빠름
    "gapdragon": "VwlplMyq7s8eoNKYEgcd",  # GapDragon - Social media: 썰 쇼츠 이야기꾼, 친근하고 몰입시키는 톤
    "kangjun": "sIyywe2M6JEImQgP1LTX",    # Kang Jun - Powerful Announcer: 힘 있는 아나운서·예고편 톤
    "hyuk": "ZJCNdZEjYwkOElxugmW2",       # (반려) Hyuk - Cold and Clear: 차분한 중년 내레이터
    "krys": "1W00IGEmNmwmsDeYy7ag",       # (반려) Krys - Cheerful, Clear and Measured
    "kyle": "RU7aSi6lT4uQBXMLgDxK",       # (반려) Kyle - Friendly, Natural and Guttural
}
ELEVEN_DEFAULT_VOICE = ELEVEN_VOICES["deok"]   # 기본 (운영자 결정 2026-11-17 "예능이 좋은듯", STYLE_GUIDE 6장)
# 쇼츠 후킹용: 안정성 낮게(억양 출렁), 스타일 높게(과장), 조금 빠르게 (speed 0.7~1.2, ElevenLabs가 직접 조절)
ELEVEN_SETTINGS = {"stability": 0.35, "similarity_boost": 0.75, "style": 0.6, "use_speaker_boost": True, "speed": 1.1}
ELEVEN_CACHE = Path.home() / ".cache" / "tokenwar-tts" / "elevenlabs"


def eleven_key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k and sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = winreg.QueryValueEx(h, "ELEVENLABS_API_KEY")[0]
        except OSError:
            k = None
    if not k:
        sys.exit("ELEVENLABS_API_KEY가 없다 (MIGRATION.md: setx ELEVENLABS_API_KEY 뒤 앱 다시 시작)")
    return k.strip()


def _mask(s, key):
    return str(s).replace(key, "***") if key else str(s)


def _eleven(path, key, body=None, accept="application/json"):
    import urllib.error
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(ELEVEN_API + path, data=data, method="POST" if data else "GET",
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 2:
                continue
            sys.exit(f"ElevenLabs {e.code}: {_mask(detail, key)}")
        except (urllib.error.URLError, TimeoutError) as e:     # 연결 실패는 과금되지 않으니 다시
            if attempt == 2:
                sys.exit(f"ElevenLabs 연결 실패: {_mask(e, key)}")


def eleven_voice_id(name_or_id, key=None):
    """이름(Hyuk, 계정 목소리 이름 앞부분) 또는 ID → voice_id."""
    if not name_or_id:
        return ELEVEN_DEFAULT_VOICE
    if name_or_id.lower() in ELEVEN_VOICES:
        return ELEVEN_VOICES[name_or_id.lower()]
    if re.fullmatch(r"[A-Za-z0-9]{20}", name_or_id):
        return name_or_id
    key = key or eleven_key()
    for v in json.loads(_eleven("/voices", key))["voices"]:
        if v["name"].lower().startswith(name_or_id.lower()):
            return v["voice_id"]
    sys.exit(f"ElevenLabs 목소리 {name_or_id!r}를 못 찾음 (--list-voices로 확인)")


def eleven_text(text, normalize=True, words=None):
    """ElevenLabs에 보낼 글. 기본으로 tts_ko_norm 정규화(숫자 읽기·영어 → 말하는 그대로의 한글, STYLE_GUIDE 6장 'TTS 읽기')."""
    if not normalize:
        return text
    from tts_ko_norm import normalize as ko_norm
    unknown = []
    out = ko_norm(text, words, warn=unknown)
    if unknown:
        print(f"  ! 사전에 없는 영어(그대로 읽음): {', '.join(sorted(set(unknown)))} "
              f"→ assets/voice/ko_words.json이나 voice.words에 추가", file=sys.stderr)
    return out


def eleven_mp3(text, voice_id=None, settings=None, model=ELEVEN_MODEL, normalize=True, words=None,
                previous_text=None, next_text=None):
    """문장 → mp3 파일 경로. 같은 글·목소리·설정·모델이면 캐시를 쓴다 (다시 과금되지 않게).
    normalize(기본 켬): tts_ko_norm으로 읽을 글로 바꾼 뒤 보내고, 캐시 키도 바꾼 글로 잡는다. words: 추가 사전.
    previous_text/next_text(선택): 앞뒤 문장을 함께 넘겨 억양이 이어지게 한다 (줄마다 따로 만들 때 호흡이 끊기지 않게,
    운영자 2026-11-17 "호흡이 어색한 부분"). 읽지는 않는다. 넘기면 캐시 키에도 들어간다."""
    text = eleven_text(text, normalize, words)
    ctx = {}
    if previous_text:
        ctx["previous_text"] = eleven_text(previous_text, normalize, words)
    if next_text:
        ctx["next_text"] = eleven_text(next_text, normalize, words)
    vs = dict(ELEVEN_SETTINGS, **(settings or {}))
    voice_id = voice_id or ELEVEN_DEFAULT_VOICE
    key_parts = [text, voice_id, vs, model, ELEVEN_FORMAT] + ([ctx] if ctx else [])
    h = hashlib.sha256(json.dumps(key_parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    out = ELEVEN_CACHE / f"{h}.mp3"
    if out.exists() and out.stat().st_size > 0:
        return out
    key = eleven_key()
    audio = _eleven(f"/text-to-speech/{voice_id}?output_format={ELEVEN_FORMAT}", key,
                    dict({"text": text, "model_id": model, "voice_settings": vs}, **ctx), accept="audio/mpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio)
    print(f"  ElevenLabs {len(text)}자 사용 ({voice_id})", file=sys.stderr)
    return out


def eleven_mp3_ts(text, voice_id=None, settings=None, model=ELEVEN_MODEL, normalize=True, words=None,
                   previous_text=None, next_text=None):
    """eleven_mp3와 같고 /with-timestamps로 글자별 시각도 받는다 → (mp3 경로, {"text", "chars", "starts", "ends"}).
    글자 시각은 보낸 글(정규화한 글) 기준. 같은 캐시 규칙 (키에 'ts'), 시각은 mp3 옆 .json."""
    import base64
    text = eleven_text(text, normalize, words)
    ctx = {}
    if previous_text:
        ctx["previous_text"] = eleven_text(previous_text, normalize, words)
    if next_text:
        ctx["next_text"] = eleven_text(next_text, normalize, words)
    vs = dict(ELEVEN_SETTINGS, **(settings or {}))
    voice_id = voice_id or ELEVEN_DEFAULT_VOICE
    h = hashlib.sha256(json.dumps([text, voice_id, vs, model, ELEVEN_FORMAT, ctx, "ts"], ensure_ascii=False,
                                  sort_keys=True).encode()).hexdigest()[:24]
    out = ELEVEN_CACHE / f"{h}.mp3"
    js = out.with_suffix(".json")
    if out.exists() and js.exists():
        return out, json.loads(js.read_text(encoding="utf-8"))
    key = eleven_key()
    raw = _eleven(f"/text-to-speech/{voice_id}/with-timestamps?output_format={ELEVEN_FORMAT}", key,
                  dict({"text": text, "model_id": model, "voice_settings": vs}, **ctx))
    d = json.loads(raw)
    al = d.get("alignment") or d.get("normalized_alignment") or {}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(d["audio_base64"]))
    meta = {"text": text, "chars": al.get("characters", []), "starts": al.get("character_start_times_seconds", []),
            "ends": al.get("character_end_times_seconds", [])}
    js.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"  ElevenLabs {len(text)}자 사용 ({voice_id}, 시각 포함)", file=sys.stderr)
    return out, meta


def decode(path, sr, tempo=1.0):
    """오디오 파일 → 모노 float32 (ffmpeg). tempo > 1이면 atempo로 빠르게 (다시 합성하지 않음)."""
    import subprocess
    ff = shutil.which("ffmpeg") or sys.exit("ffmpeg가 없다")
    cmd = [ff, "-nostdin", "-loglevel", "error", "-i", str(path)]
    if abs(tempo - 1.0) > 1e-3:
        cmd += ["-af", f"atempo={tempo:.3f}"]
    raw = subprocess.run(cmd + ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def synth_eleven(text, sr, voice_id=None, settings=None, speed=1.0, normalize=True, words=None):
    return decode(eleven_mp3(text, voice_id, settings, normalize=normalize, words=words), sr, tempo=speed)


def list_eleven_voices():
    key = eleven_key()
    print("[계정 목소리]")
    for v in json.loads(_eleven("/voices", key))["voices"]:
        lb = v.get("labels") or {}
        print(f"  {v['voice_id']}  {v['name']}  ({v.get('category')}, {lb.get('gender')}, {lb.get('age')})")
    print("[라이브러리 한국어 남자 목소리, 많이 쓰는 순]")
    q = "/shared-voices?page_size=30&language=ko&gender=male&sort=usage_character_count_1y"
    for v in json.loads(_eleven(q, key))["voices"]:
        print(f"  {v['voice_id']}  {v['name']}  ({v.get('age')}, {v.get('use_case')}, {v.get('descriptive')})")


def kokoro_pipe():
    from kokoro import KPipeline
    return KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")


def kokoro_synth(pipe, text, voice, speed):
    return np.concatenate([np.asarray(audio, dtype=np.float32) for _, _, audio in pipe(text, voice=voice, speed=speed)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--voice")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 만든다")
    ap.add_argument("--text", help="문장 하나를 바로 --out 파일로")
    ap.add_argument("--out", help="--text의 출력 wav")
    ap.add_argument("--lang", choices=["ko", "en"], help="--text의 언어 (기본 ko)")
    ap.add_argument("--speed", type=float, default=1.0, help="--text의 빠르기")
    ap.add_argument("--engine", choices=["melo", "kokoro", "elevenlabs"],
                    help="--text 엔진 (기본: ko는 melo, en은 kokoro). elevenlabs는 --voice에 이름(Hyuk/Krys/Kyle) 또는 ID")
    ap.add_argument("--list-voices", action="store_true", help="ElevenLabs 목소리 목록")
    ap.add_argument("--settings", help="ElevenLabs voice_settings 덮어쓰기 JSON, 예: {\"stability\": 0.3, \"style\": 0.7}")
    ap.add_argument("--no-norm", action="store_true", help="ElevenLabs에 보내기 전 읽기 정규화(tts_ko_norm)를 끈다")
    ap.add_argument("--words", help="읽기 추가 사전 JSON, 예: {\"Foobar\": \"푸바\"}")
    ap.add_argument("--verify", action="store_true", help="만든 음성을 faster-whisper로 받아써 대본과 비교 (ElevenLabs --text)")
    ap.add_argument("--gate", action="store_true", help="--verify에서 다르면 종료 코드 1")
    a = ap.parse_args()
    if a.list_voices:
        list_eleven_voices()
        return
    if a.text and a.engine == "elevenlabs":
        if not a.out:
            ap.error("--text에는 --out이 필요하다")
        out = Path(a.out)
        vid = eleven_voice_id(a.voice)
        words = json.loads(a.words) if a.words else None
        mp3 = eleven_mp3(a.text, vid, json.loads(a.settings) if a.settings else None,
                         normalize=not a.no_norm, words=words)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".mp3" and abs(a.speed - 1.0) < 1e-3:
            shutil.copyfile(mp3, out)
            x, sr = decode(mp3, KO_SR), KO_SR
        else:
            x, sr = trim(decode(mp3, KO_SR, tempo=a.speed), sr=KO_SR), KO_SR
            save(out, x, sr)
        print(f"{a.out}: {len(x) / sr:.2f}초, ElevenLabs {vid}, 빠르기 {a.speed:g}")
        if a.verify:
            from tts_ko_norm import print_verify, verify_audio
            r = verify_audio(out, a.text, words)
            print_verify(r)
            if a.gate and not r["ok"]:
                sys.exit(1)
        return
    if a.text:
        if not a.out:
            ap.error("--text에는 --out이 필요하다")
        if (a.lang or "ko") == "ko" and a.engine != "kokoro":
            x, sr = trim(synth_ko(a.text, a.speed), sr=KO_SR), KO_SR
        else:
            x, sr = trim(kokoro_synth(kokoro_pipe(), a.text, a.voice or DEFAULT_VOICE, a.speed)), SR
        save(Path(a.out), x, sr)
        print(f"{a.out}: {len(x) / sr:.2f}초, {sr}Hz, 빠르기 {a.speed:g}")
        return
    if not a.folder:
        ap.error("게시물 폴더나 --text가 필요하다")
    folder = Path(a.folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    from listreel import rows_of, timeline
    tl = timeline(post)
    cfg = dict(post.get("voice") or {}, **((post.get("list") or {}).get("voice") or {}))
    lang = cfg.get("lang", "en")
    speed0 = float(cfg.get("speed", 1.0))
    say = cfg.get("say") or {}
    if cfg.get("engine") == "elevenlabs":
        lang = cfg.get("lang", "ko")
        vid = eleven_voice_id(a.voice or cfg.get("voice_id"))
        voice = f"ElevenLabs {vid}"

        def gen(text, speed):      # 빠르기를 올려도 다시 합성하지 않는다 (캐시 + atempo)
            return synth_eleven(text, SR, vid, cfg.get("settings"), speed,
                                normalize=cfg.get("normalize", True) and not a.no_norm, words=cfg.get("words"))
    elif lang == "ko":
        voice = "MeloTTS KR"

        def gen(text, speed):
            return to_sr(synth_ko(text, speed), KO_SR, SR)     # listreel은 24kHz 파일을 섞는다
    else:
        voice = a.voice or cfg.get("voice", DEFAULT_VOICE)
        pipe = kokoro_pipe()

        def gen(text, speed):
            return kokoro_synth(pipe, text, voice, speed)
    limit = tl["item"] - 0.15     # 다음 그림 전에 말이 끝나게
    report = []
    for row in rows_of(post):
        text = say.get(row["num"]) or (row["name"] if lang == "ko" else row["en"])
        if row["base"] or not text:
            continue
        out = folder / "voice" / f"{row['num']}.wav"
        if out.exists() and not a.force:
            continue
        speed = speed0
        while True:
            x = trim(gen(text, speed))
            secs = len(x) / SR
            if secs <= limit or speed >= MAX_SPEED:
                break
            speed = min(MAX_SPEED, round(speed * secs / limit * 1.02 + 0.02, 2))   # 길수록 빠르게
        save(out, x)
        flag = "" if secs <= limit else f"  (항목 {tl['item']:.2f}초보다 김)"
        report.append(f"{row['num']} {text!r}: {secs:.2f}초, 빠르기 {speed:g}{flag}")
    print(f"목소리 {voice}, 항목 {tl['item']:.2f}초 (말은 {limit:.2f}초 안)")
    for r in report:
        print(" ", r)


if __name__ == "__main__":
    main()
