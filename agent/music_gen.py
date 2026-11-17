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


def make_music(out_path, durs, fade=0.3, seed=7, hit_at=None):
    """hit_at(선택): 강한 타격음을 넣을 시각 목록. 없으면 장면 전환마다 (예전과 같음).
    목록형 릴스(listreel.py)처럼 장면이 1초 남짓으로 잦으면 박자는 전환에 맞추고 타격음은 큰 전환에만 넣는다."""
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
    hits = bounds if hit_at is None else [float(x) for x in hit_at]
    for t0 in hits:
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
    return {"bpm": bpm, "seconds": total, "bounds": bounds, "hits": hits}


# ---------- 후킹 비트 (목록형 자료 릴스, 운영자 요청 2026-11-17 "노래도 좀 후킹되게") ----------
# 0초부터 킥·스네어(클랩)가 바로 시작하고, 2마디짜리 짧은 멜로디 훅이 되풀이된다.
# 박자는 호출하는 쪽이 정한다 (listreel.py: 항목 길이 = 박자 간격의 정수배라 그림이 바뀌는 순간이 늘 박 위에 온다).
HOOK = [76, None, 76, 79, 81, None, 79, 76,   # 1마디 (8분음표): E5 . E5 G5 A5 . G5 E5
        74, None, 72, 74, 76, None, None, None]  # 2마디: D5 . C5 D5 E5 . . .
HOOK_END = [74, None, 72, 74, 69, None, None, None]  # 4마디째는 A4로 끝맺음


def snare(n, rng):
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 185 * t) * env(n, 0.001, 0.06) * 0.6
    noise = rng.standard_normal(n) * env(n, 0.001, 0.11)
    noise = noise - lowpass(noise, 6)  # 고역 위주 (스네어 줄 소리)
    return (body + noise * 0.9) * 0.9


def clap(n, rng):
    x = np.zeros(n)
    for k, d in enumerate((0, 0.011, 0.022)):  # 손뼉 세 번 겹치기
        i = int(d * SR)
        m = n - i
        x[i:] += rng.standard_normal(m) * env(m, 0.0005, 0.03 if k < 2 else 0.09)
    return (x - lowpass(x, 5)) * 0.5


def make_hook_music(out_path, bpm, total, accents=(), seed=7, drop_at=None):
    """bpm 고정, 0초가 첫 박. accents: 강한 박자(크래시)를 넣을 시각 목록(초). 끝 1.5초 페이드아웃.
    drop_at(초, 선택): 그 전까지는 킥(첫 박)·클랩·하이햇만 두고 베이스·패드·멜로디를 빼며, 바로 앞 반 박은 비운다.
    drop_at에서 전부 들어온다(비트 드롭, 목록형 릴스 첫 화면 후킹 list.hook_anim). 멜로디는 드롭에서 처음부터.
    반환 {"bpm", "beat", "seconds", "accents"}."""
    rng = np.random.default_rng(seed)
    drop_beat = int(round(drop_at / (60.0 / bpm))) if drop_at else 0
    beat = 60.0 / bpm
    n = int((total + 0.5) * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(round(t0 * SR))
        if i >= n:
            return
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr

    nb = int(total / beat) + 1
    for b in range(nb):
        t0 = b * beat
        if b < drop_beat:                                             # 드롭 전: 비운 소리(빌드업)
            if b == drop_beat - 1:
                add(hat(int(0.04 * SR), rng) * 0.6, t0)
                continue                                              # 드롭 바로 앞 한 박의 뒤쪽은 비운다
            if b == 0:
                add(kick(int(0.32 * SR)) * 1.0, t0)
            if b % 2 == 1:
                add(clap(int(0.2 * SR), rng) * 0.6, t0, 0.9, 1.0)
            for k in range(2):
                add(hat(int(0.04 * SR), rng) * (0.8 if k else 0.4), t0 + k * beat / 2, 0.8, 1.0)
            continue
        bar, pos = divmod(b - drop_beat, 4)
        chord = CHORDS[bar % 4]
        add(kick(int(0.32 * SR)) * 1.0, t0)                          # 킥: 매 박 (0초부터)
        if pos in (1, 3):                                             # 스네어 + 클랩: 2·4박
            add(snare(int(0.25 * SR), rng) * 0.75, t0)
            add(clap(int(0.2 * SR), rng) * 0.6, t0, 0.9, 1.0)
        for k in range(4):                                            # 하이햇: 16분, 뒷박 강조
            add(hat(int(0.04 * SR), rng) * (0.9 if k == 2 else 0.45), t0 + k * beat / 4, 0.8 if k % 2 else 1.0, 1.0 if k % 2 else 0.8)
        for k in range(2):                                            # 베이스: 근음 8분, 둘째는 옥타브 위
            m = chord[0] - 24 + (12 if k == 1 else 0)
            add(lowpass(tone(hz(m), int(beat / 2 * SR), "saw", r=0.1), 16) * 0.42, t0 + k * beat / 2)
        if pos == 0:                                                  # 패드: 마디 첫 박
            pad = sum(lowpass(tone(hz(mm), int(4 * beat * SR), "saw", r=2.0, a=0.05), 40) for mm in chord) / 3
            add(pad * 0.16, t0, 1.0, 0.8)
            add(pad * 0.16, t0 + 0.012, 0.8, 1.0)
        # 멜로디 훅: 2마디 모티프, 4마디째는 끝맺음. 첫 박부터 바로
        motif = HOOK if bar % 4 != 3 else HOOK[:8] + HOOK_END
        half = (bar % 2) * 8
        for k in range(2):
            note = motif[half + pos * 2 + k]
            if note is None:
                continue
            pl = tone(hz(note), int(beat / 2 * SR * 0.95), "square", r=0.16, a=0.004)
            pl += tone(hz(note + 12), int(beat / 2 * SR * 0.95), "sine", r=0.12, a=0.004) * 0.35
            add(lowpass(pl, 3) * 0.2, t0 + k * beat / 2, 0.85, 1.0)
            add(lowpass(pl, 3) * 0.07, t0 + k * beat / 2 + beat * 0.75, 1.0, 0.6)  # 짧은 메아리
    for t0 in accents:                                                # 크래시: 강한 박
        x = rng.standard_normal(int(1.2 * SR))
        x = (x - lowpass(x, 4)) * env(len(x), 0.001, 0.45) * 0.35
        add(x, t0)
    st = np.stack([L, R], axis=1)[: int(total * SR)]
    fo = int(min(1.5, total / 4) * SR)
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(st)) or 1.0
    st = np.tanh(st / peak * 2.0) / np.tanh(2.0) * 0.88
    pcm = (st * 32767).astype(np.int16)
    with wave.open(str(Path(out_path)), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"bpm": bpm, "beat": beat, "seconds": total, "accents": list(accents)}


# ---------- 첫 화면 후킹 효과음 (목록형 릴스 list.hook_anim, 운영자 요청 2026-11-17 "소리도 집중시킬 수 있게") ----------
# 샘플 없이 numpy로 합성: 쿵(0초), 제목 줄마다 짧은 타격 + 그 직전 휙(whoosh), 목록 시작 앞 상승음(riser) → 드롭(낮은 붐),
# 끝의 이름 쏟아지기(list.flood) 동안 커지는 스웰과 이름마다 작은 틱. 시각은 부르는 쪽이 프레임 시각으로 준다.

def _sweep_noise(n, f0, f1, rng):
    """잡음을 한 극 저역 필터로 거르며 차단 주파수를 f0→f1로 옮긴다 (휙 소리, 상승음)."""
    x = rng.standard_normal(n)
    fc = np.geomspace(f0, f1, n)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    y = np.empty(n)
    z = 0.0
    for i in range(n):
        z += a[i] * (x[i] - z)
        y[i] = z
    return y - lowpass(y, 40) * 0.5


def _boom(n, f0, f1, decay, click=0.4, rng=None):
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, decay)
    if rng is not None and click:
        c = rng.standard_normal(n) * env(n, 0.0005, 0.012) * click
        x = x + (c - lowpass(c, 4))
    return x


def make_hook_sfx(total, impacts=(), hits=(), whooshes=(), riser_to=None, riser_len=1.0, drop=None,
                  flood=None, ticks=(), seed=3):
    """효과음 트랙(44.1kHz 스테레오 float, 길이 total초). 크기는 부르는 쪽이 맞춘다(피크 1 기준으로 만든다).
    impacts: 큰 쿵 시각, hits: 작은 타격 시각, whooshes: 이 시각에 끝나는 휙(0.18초),
    riser_to: 이 시각에 끝나는 상승음(riser_len초, 끝에서 뚝 끊김), drop: 드롭 붐 시각,
    flood: (시작, 끝) 커지는 스웰, ticks: 이름 하나 떨어질 때마다 작은 틱.
    반환 (배열, {"onsets": {종류: [시각...]}})."""
    rng = np.random.default_rng(seed)
    n = int(round(total * SR))
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(round(t0 * SR))
        if i >= n or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr

    for t0 in impacts:
        add(_boom(int(1.1 * SR), 120, 38, 0.55, 0.9, rng) * 1.0, t0)
        c = rng.standard_normal(int(0.4 * SR))
        add((c - lowpass(c, 3)) * env(len(c), 0.0005, 0.08) * 0.45, t0, 1.0, 0.9)
    for t0 in hits:
        add(_boom(int(0.4 * SR), 180, 60, 0.16, 0.7, rng) * 0.6, t0)
    for t0 in whooshes:
        m = int(0.18 * SR)
        w = _sweep_noise(m, 400, 7000, rng) * np.linspace(0, 1, m) ** 2
        add(w / (np.max(np.abs(w)) or 1) * 0.35, t0 - m / SR, 0.8, 1.0)
    if riser_to is not None:
        m = int(riser_len * SR)
        r = _sweep_noise(m, 250, 9000, rng)
        r = r / (np.max(np.abs(r)) or 1)
        t = np.arange(m) / SR
        tone_ = np.sin(2 * np.pi * np.cumsum(np.geomspace(180, 900, m)) / SR) * 0.25
        add((r * 0.45 + tone_) * np.linspace(0, 1, m) ** 2.2, riser_to - riser_len, 0.9, 1.0)
    if drop is not None:
        add(_boom(int(1.2 * SR), 90, 34, 0.7, 0.5, rng) * 0.9, drop)
    if flood:
        t0, t1 = flood
        m = int((t1 - t0) * SR)
        s = _sweep_noise(m, 300, 6000, rng)
        s = s / (np.max(np.abs(s)) or 1)
        add(s * np.linspace(0.1, 1, m) ** 1.6 * 0.4, t0, 1.0, 0.9)
        add(_boom(int(0.9 * SR), 110, 40, 0.4, 0.6, rng) * 0.7, t0)
    for k, t0 in enumerate(ticks):
        m = int(0.05 * SR)
        f = 1400 + 500 * ((k * 7) % 5)
        tk = np.sin(2 * np.pi * f * np.arange(m) / SR) * env(m, 0.0005, 0.015) * 0.18
        pan = 0.6 + 0.4 * ((k * 3) % 4) / 3
        add(tk, t0, pan, 1.6 - pan)
    st = np.stack([L, R], axis=1)
    peak = np.max(np.abs(st)) or 1.0
    onsets = {"impact": list(impacts), "hit": list(hits), "whoosh_end": list(whooshes),
              "riser_end": [riser_to] if riser_to is not None else [], "drop": [drop] if drop is not None else [],
              "flood": list(flood) if flood else [], "ticks": len(ticks)}
    return st / peak, {"onsets": onsets}


# ---------- 긴장감 배경음 (게임·액션 화면 밑에 작게 까는 곡, 운영자 요청 2026-11-17 "배경에 작게 음악") ----------
# 낮은 베이스 펄스(16분), 빠른 하이햇(16분), 어두운 신스 패드(Am-Am-F-E), 박마다 킥. 멜로디 없음(게임 소리가 주인공).
DARK_CHORDS = [(45, 48, 52), (45, 48, 52), (41, 45, 48), (40, 44, 47)]  # Am Am F E (낮은 음역)


def make_tension_music(out_path, bpm, total, accents=(), seed=11):
    """bpm 고정, 0초가 첫 박. accents: 낮은 타격음을 넣을 시각(장면 이음새 등). 끝 1.5초 페이드아웃.
    반환 {"bpm", "beat", "seconds", "accents"}. 섞을 때 크기는 부르는 쪽이 정한다(게임 소리보다 12~18dB 낮게)."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    n = int((total + 0.5) * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(round(t0 * SR))
        if i >= n:
            return
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr

    nb = int(total / beat) + 1
    for b in range(nb):
        t0 = b * beat
        bar, pos = divmod(b, 4)
        chord = DARK_CHORDS[bar % 4]
        add(kick(int(0.3 * SR)) * 0.8, t0)
        for k in range(4):  # 16분 베이스 펄스: 근음, 박 머리 강조
            g = 0.5 if k == 0 else 0.32
            add(lowpass(tone(hz(chord[0] - 12), int(beat / 4 * SR * 0.9), "saw", r=0.05, a=0.003), 24) * g, t0 + k * beat / 4)
        for k in range(4):  # 빠른 하이햇
            add(hat(int(0.03 * SR), rng) * (0.7 if k % 2 else 0.35), t0 + k * beat / 4, 0.8 if k % 2 else 1.0, 1.0 if k % 2 else 0.8)
        if pos == 0:  # 어두운 패드: 살짝 어긋난 두 톱니파를 강하게 깎아 탁하게
            d = int(4 * beat * SR)
            pad = sum(lowpass(tone(hz(m), d, "saw", r=3.0, a=0.4) + tone(hz(m) * 1.006, d, "saw", r=3.0, a=0.4), 60)
                      for m in chord) / 6
            add(pad * 0.3, t0, 1.0, 0.8)
            add(pad * 0.3, t0 + 0.015, 0.8, 1.0)
    for t0 in accents:
        add(hit(int(0.9 * SR), rng) * 0.5, max(0.0, t0 - 0.02))
    st = np.stack([L, R], axis=1)[: int(total * SR)]
    fo = int(min(1.5, total / 4) * SR)
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    fi = int(0.05 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    peak = np.max(np.abs(st)) or 1.0
    st = np.tanh(st / peak * 1.8) / np.tanh(1.8) * 0.85
    pcm = (st * 32767).astype(np.int16)
    with wave.open(str(Path(out_path)), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"bpm": bpm, "beat": beat, "seconds": total, "accents": list(accents)}


# ---------- 가볍고 밝은 배경음 (운영자 요청 2026-11-17 "배경음악이 너무 긴장감있고") ----------
# 장조(Cmaj7-G-Am7-Fmaj7) 일렉트릭 피아노 화음, 부드러운 사인 베이스, 살짝 스윙한 하이햇, 작은 킥·클랩, 펜타토닉 플럭.
LIGHT_CHORDS = [(60, 64, 67, 71), (55, 59, 62, 67), (57, 60, 64, 67), (53, 57, 60, 64)]  # Cmaj7 G Am7 Fmaj7
LIGHT_PLUCK = [76, 79, 81, 79, 84, 81, 79, 76]  # C장조 펜타토닉 E G A G C A G E


def _epiano(freq, n, r=1.2):
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 6) \
        + 0.12 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t * 10)
    return x * env(n, 0.006, r)


def make_light_music(out_path, bpm, total, accents=(), seed=5, swing=0.12):
    """bpm 고정, 0초가 첫 박. accents: 장면 이음새 등에 넣는 부드러운 심벌 스웰 시각. 끝 1.5초 페이드아웃.
    반환 {"bpm", "beat", "seconds", "accents"}."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    n = int((total + 0.5) * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(round(t0 * SR))
        if i >= n:
            return
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * gl
        R[i:i + m] += sig[:m] * gr

    nb = int(total / beat) + 1
    for b in range(nb):
        t0 = b * beat
        bar, pos = divmod(b, 4)
        chord = LIGHT_CHORDS[bar % 4]
        if pos in (0, 2):
            add(kick(int(0.25 * SR)) * 0.55, t0)
        if pos in (1, 3):
            add(clap(int(0.18 * SR), rng) * 0.28, t0, 0.9, 1.0)
        for k in range(2):  # 8분 하이햇, 뒷박은 살짝 늦게(스윙)
            add(hat(int(0.035 * SR), rng) * (0.45 if k else 0.25), t0 + k * beat / 2 + (swing * beat / 2 if k else 0), 0.85, 1.0)
        add(_epiano(hz(chord[0] - 24), int(beat * SR), r=0.5) * 0.5, t0)  # 사인 베이스: 박마다 근음
        if pos == 0:  # 일렉트릭 피아노 화음: 마디 첫 박 + 셋째 박 뒤에 가볍게 한 번 더
            for k, m in enumerate(chord):
                add(_epiano(hz(m), int(3 * beat * SR)) * 0.13, t0 + k * 0.012, 1.0 - 0.1 * k, 0.7 + 0.1 * k)
        if pos == 2:
            for m in chord[1:]:
                add(_epiano(hz(m), int(1.5 * beat * SR), r=0.4) * 0.07, t0 + beat / 2, 0.8, 1.0)
        if bar % 2 == 1:  # 플럭: 짝수 마디에 8분음표로 가볍게
            for k in range(2):
                note = LIGHT_PLUCK[(pos * 2 + k) % len(LIGHT_PLUCK)]
                pl = tone(hz(note), int(beat / 2 * SR), "sine", r=0.18, a=0.003)
                add(pl * 0.12, t0 + k * beat / 2, 0.7, 1.0)
                add(pl * 0.04, t0 + k * beat / 2 + beat * 0.75, 1.0, 0.6)  # 메아리
    for t0 in accents:  # 부드러운 심벌 스웰(앞으로 커지다 박에서 끝)
        m = int(beat * SR)
        x = rng.standard_normal(m)
        x = (x - lowpass(x, 6)) * np.linspace(0, 1, m) ** 2 * 0.18
        add(x, max(0.0, t0 - beat))
    st = np.stack([L, R], axis=1)[: int(total * SR)]
    fo = int(min(1.5, total / 4) * SR)
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    fi = int(0.05 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    peak = np.max(np.abs(st)) or 1.0
    st = np.tanh(st / peak * 1.5) / np.tanh(1.5) * 0.85
    pcm = (st * 32767).astype(np.int16)
    with wave.open(str(Path(out_path)), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"bpm": bpm, "beat": beat, "seconds": total, "accents": list(accents)}


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
