"""목록형 자료 릴스의 영어 용어 읽기 목소리 만들기 (운영자 결정 2026-11-17: "그림이 바뀔 때 그 영어 용어를 목소리로").

엔진: Kokoro-82M (Apache-2.0). pip 패키지 `kokoro`(PyPI) + 모델·음성은 Hugging Face hexgrad/Kokoro-82M에서 처음 쓸 때 자동으로 받는다.
       출처·라이선스 기록: assets/voice/README.md. 유료 API·계정 없음.
GitHub Actions에는 Kokoro가 없다. 그래서 이 컴퓨터에서 미리 만들어 게시물 폴더 voice/<번호>.wav(24kHz 모노, 작게)로 넣고,
listreel.py는 그 파일을 박자에 맞춰 섞기만 한다. voice/가 없으면 목소리 없이 예전처럼 동작한다.

사용법:
    py -3.12 agent/tts.py posts/queue/<폴더> [--voice af_heart] [--force]
  - list.items[].en(영어 용어)을 읽는다. list.voice(선택)에 {"voice": "af_heart", "speed": 1.0, "say": {"07": "split lighting"}}로
    목소리·빠르기·읽을 문장을 바꿀 수 있다 (say: 번호별로 화면 글자와 다르게 읽을 때, 예: 약자).
  - 말 앞뒤 무음을 잘라 그림이 바뀌는 박에 바로 말이 시작되게 하고, 항목 길이보다 길면 빠르기를 올려 다시 만든다.
"""
import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

SR = 24000
DEFAULT_VOICE = "af_heart"      # 차분하고 또렷한 미국 영어 여성 내레이터 (Kokoro 음성 중 품질 등급이 가장 높음)
MAX_SPEED = 1.4


def trim(x, thr=0.012, pad=0.01):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    a = max(0, idx[0] - int(pad * SR))
    z = min(len(x), idx[-1] + int(0.06 * SR))
    y = x[a:z].copy()
    f = int(0.008 * SR)
    y[:f] *= np.linspace(0, 1, f)
    y[-f * 3:] *= np.linspace(1, 0, f * 3)
    return y


def save(path, x):
    path.parent.mkdir(parents=True, exist_ok=True)
    x = x / (np.max(np.abs(x)) or 1) * 0.9
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--voice")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 만든다")
    a = ap.parse_args()
    folder = Path(a.folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    from listreel import rows_of, timeline
    tl = timeline(post)
    cfg = (post.get("list") or {}).get("voice") or {}
    voice = a.voice or cfg.get("voice", DEFAULT_VOICE)
    speed0 = float(cfg.get("speed", 1.0))
    say = cfg.get("say") or {}
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    limit = tl["item"] - 0.15     # 다음 그림 전에 말이 끝나게
    report = []
    for row in rows_of(post):
        text = say.get(row["num"]) or row["en"]
        if row["base"] or not text:
            continue
        out = folder / "voice" / f"{row['num']}.wav"
        if out.exists() and not a.force:
            continue
        speed = speed0
        while True:
            chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipe(text, voice=voice, speed=speed)]
            x = trim(np.concatenate(chunks))
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
