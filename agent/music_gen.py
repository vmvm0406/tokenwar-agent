"""소리 없는 릴스에 까는 배경음악을 코드로 만든다 (외부 음원 0, 운영자 결정 2026-11-16 "소리 없는 영상은 반드시 소리로 채운다").

장면 길이 목록을 받아 박자(BPM)를 장면 전환에 맞춘 짧은 일렉트로닉 루프를 만든다:
  - 킥(4분음표)·하이햇(8분 뒷박)·베이스·패드 화음(Am-F-C-G)
  - 장면이 바뀌는 순간마다 강한 타격음(전환 강조), 마지막은 페이드 아웃
결과는 44.1kHz 스테레오 wav. numpy만 쓴다 (윈도우·리눅스 공통).

사용법: py -3.12 agent/music_gen.py <출력.wav> <장면1초> <장면2초> ... [--fade 0.3]
"""
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
CHORDS = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]  # Am F C G (MIDI)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, r=None):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) if a > 0 else np.ones(n)
    if r:
        e *= np.exp(-t / r)
    return e


def kick(n):
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.18)


def hat(n, rng):
    x = rng.standard_normal(n)
    x = np.diff(x, prepend=0)  # 고역만
    return x * env(n, 0.001, 0.03) * 0.25


def hit(n, rng):
    """전환 강조: 낮은 붐 + 짧은 노이즈."""
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-t * 12)) * t) * env(n, 0.002, 0.5)
    noise = rng.standard_normal(n) * env(n, 0.001, 0.12) * 0.5
    return boom + noise


def tone(freq, n, shape="saw", r=None, a=0.01):
    t = np.arange(n) / SR
    ph = (freq * t) % 1.0
    if shape == "saw":
        x = 2 * ph - 1
    elif shape == "square":
        x = np.where(ph < 0.5, 1.0, -1.0)
    else:
        x = np.sin(2 * np.pi * ph)
    return x * env(n, a, r)


def lowpass(x, k=8):
    if k <= 1:
        return x
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, y[0]), y])


def pick_bpm(bounds, lo=96, hi=124):
    """장면 전환 시각들이 박자에 가장 가깝게 떨어지는 BPM."""
    if not bounds:
        return 110
    best, err = 110, 1e9
    for bpm in np.arange(lo, hi + 0.01, 0.5):
        beat = 60 / bpm
        e = sum(min(b % beat, beat - b % beat) for b in bounds)
        if e < err:
            best, err = float(bpm), e
    return best


def make_music(out_path, durs, fade=0.3, seed=7):
    rng = np.random.default_rng(seed)
    total = sum(durs) - fade * (len(durs) - 1)
    bounds, acc = [], 0.0
    for d in durs[:-1]:
        acc += d - fade
        bounds.append(acc + fade / 2)  # 페이드 가운데
    bpm = pick_bpm(bounds)
    beat = 60 / bpm
    n = int((total + 0.5) * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(t0 * SR)
        if i >= n:
            return
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr

    nb = int(total / beat) + 1
    for b in range(nb):
        t0 = b * beat
        bar = b // 4
        chord = CHORDS[bar % 4]
        add(kick(int(0.3 * SR)) * 0.9, t0)
        add(hat(int(0.08 * SR), rng), t0 + beat / 2, 0.8, 1.0)
        if b % 2 == 1:
            add(hat(int(0.05 * SR), rng) * 0.6, t0 + beat * 0.75, 1.0, 0.7)
        # 베이스: 근음 8분음표
        for k in range(2):
            add(lowpass(tone(hz(chord[0] - 24), int(beat / 2 * SR), "saw", r=0.12), 20) * 0.35, t0 + k * beat / 2)
        # 패드: 마디 첫 박에 화음
        if b % 4 == 0:
            pad = sum(lowpass(tone(hz(m), int(4 * beat * SR), "saw", r=2.5, a=0.3), 40) for m in chord) / 3
            add(pad * 0.22, t0, 1.0, 0.85)
            add(pad * 0.22, t0 + 0.012, 0.85, 1.0)
        # 리드 아르페지오(16분 한 번씩 건너)
        if bar % 2 == 1:
            m = chord[b % 3] + 12
            add(tone(hz(m), int(beat / 2 * SR), "square", r=0.09) * 0.07, t0 + beat / 4, 0.7, 1.0)
    for t0 in bounds:
        add(hit(int(0.9 * SR), rng) * 0.6, max(0.0, t0 - 0.02))

    st = np.stack([L, R], axis=1)[: int(total * SR)]
    fo = int(min(1.5, total / 4) * SR)
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    fi = int(0.05 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    peak = np.max(np.abs(st)) or 1.0
    st = st / peak
    st = np.tanh(st * 2.2) / np.tanh(2.2) * 0.85  # 부드럽게 눌러 소리를 키움 (휴대폰 스피커에서도 들리게)
    pcm = (st * 32767).astype(np.int16)
    out_path = Path(out_path)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"bpm": bpm, "seconds": total, "bounds": bounds}


if __name__ == "__main__":
    args = sys.argv[1:]
    fade = 0.3
    if "--fade" in args:
        i = args.index("--fade")
        fade = float(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    print(make_music(args[0], [float(x) for x in args[1:]], fade))
