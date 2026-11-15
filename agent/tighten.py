"""빠른 전환용 구간 만들기: 말 사이 쉬는 틈을 잘라낸 keep 목록을 만든다.

사용법:
    python agent/tighten.py <영상> <시작초> <끝초> [--gap 0.35] [--pad 0.12]

출력(JSON): {"keep": [[a, z], ...], "kept_seconds": .., "words": [[단어, 시작, 끝], ...]}
- 단어 사이가 gap초보다 길면 그 틈을 잘라낸다 (앞뒤 pad초는 남겨 말이 잘리지 않게).
- 결과의 keep을 post.json의 video.keep에 넣고, video.start/end는 원래 구간 그대로 둔다.
- 자막 start/end는 원본 시각 그대로 쓰면 된다 (렌더링할 때 자동으로 맞춰진다).
- 단어 목록으로 번역 자막의 시각을 정한다.
"""
import json
import subprocess
import sys

import numpy as np


def words_in(video, a, z):
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a}", "-to", f"{z}", "-i", video,
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, word_timestamps=True, vad_filter=False)
    return [[w.word.strip(), round(a + w.start, 2), round(a + w.end, 2)] for s in segs for w in s.words]


def keep_ranges(words, a, z, gap=0.35, pad=0.12):
    if not words:
        return [[a, z]]
    keep, cur_a = [], a
    for (w1, s1, e1), (w2, s2, e2) in zip(words, words[1:]):
        if s2 - e1 > gap:
            keep.append([round(cur_a, 2), round(e1 + pad, 2)])
            cur_a = s2 - pad
    keep.append([round(cur_a, 2), round(z, 2)])
    return keep


if __name__ == "__main__":
    args = sys.argv[1:]
    gap = float(args[args.index("--gap") + 1]) if "--gap" in args else 0.35
    pad = float(args[args.index("--pad") + 1]) if "--pad" in args else 0.12
    video, a, z = args[0], float(args[1]), float(args[2])
    ws = words_in(video, a, z)
    k = keep_ranges(ws, a, z, gap, pad)
    print(json.dumps({"keep": k, "kept_seconds": round(sum(e - s for s, e in k), 2), "words": ws}, ensure_ascii=False))
