"""실제 음원(라이선스 확인한 곡)을 릴스 박에 맞춘 짧은 조각으로 만든다 (운영자 결정 2026-11-17 "노래가 너무 다 진부해").

- 곡 전체는 저장소에 넣지 않는다. 이 도구로 40초 이하 조각(music.m4a)만 게시물 폴더에 둔다.
- 템포를 재서(스펙트럼 변화 → 자기상관) 릴스 BPM(기본 120)에 가장 가까운 배수 관계로 atempo 늘이기/줄이기
  (0.85~1.21배 안에서만, sped-up 폰크 정도, 음높이 유지), 시작점을 박 위치에 맞춰 0초가 박이 되게 한다 → 장면 전환이 박에 맞는다.
- 끝 1초 페이드 아웃. 크기는 렌더러가 -14 LUFS로 맞춘다.

사용법: py -3.12 agent/music_fit.py <원곡.mp3> <출력.m4a> [--bpm 120] [--start 30] [--dur 40]
  --start: 원곡에서 대략 어디부터(초). 그 근처 박에 맞춘다. 인트로를 건너뛰고 비트가 꽉 찬 곳을 고른다.
post.json: "music": {"src": "music.m4a", "title", "artist", "url", "license", "credit"} (STYLE_GUIDE 0 원칙 적용 세부)
"""
import subprocess
import sys

import numpy as np

SR = 22050
HOP = 256


def _read_mono(path, start, dur):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                          "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def onset_env(x):
    n = 1024
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::HOP] * np.hanning(n)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)) * 10)
    flux = np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)
    flux = flux - np.convolve(flux, np.ones(16) / 16, mode="same")
    return np.maximum(flux, 0)


def tempo_and_phase(x):
    """(bpm, 첫 박 시각 초). 60~190 BPM에서 자기상관 최대, 박 위치는 빗살 합 최대."""
    e = onset_env(x)
    fps = SR / HOP
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lags = np.arange(len(ac))
    ok = (lags >= fps * 60 / 190) & (lags <= fps * 60 / 60)
    w = np.exp(-0.5 * (np.log2((60 * fps / np.maximum(lags, 1)) / 120)) ** 2)   # 120 근처를 약간 선호
    lag = int(np.argmax(np.where(ok, ac * w, 0)))
    # 소수 lag 보정 (포물선)
    if 1 <= lag < len(ac) - 1:
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
        lagf = lag + 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else lag
    else:
        lagf = lag
    bpm = 60 * fps / lagf
    period = lagf
    best, ph = -1, 0
    for p in range(int(period)):
        idx = np.round(p + np.arange(0, (len(e) - p) / period) * period).astype(int)
        idx = idx[idx < len(e)]
        s = e[idx].sum()
        if s > best:
            best, ph = s, p
    return bpm, ph / fps


def fit(src, out, bpm=120.0, start=30.0, dur=40.0):
    x = _read_mono(src, max(0.0, start - 2), 24)
    tb, phase = tempo_and_phase(x)
    # 릴스 BPM과 가장 가까운 관계 (같음·2배·절반·1.5배·2/3)
    best = min(((bpm / (tb * r), r) for r in (1, 2, 0.5, 1.5, 2 / 3)), key=lambda t: abs(np.log(t[0])))
    factor = best[0]
    if not 0.85 <= factor <= 1.21:
        print(f"경고: 템포 {tb:.1f} → {bpm:g}에 맞추려면 {factor:.2f}배라 늘이지 않음 (박 정렬만)")
        factor = 1.0
    beat = 60 / tb
    t0 = max(0.0, start - 2) + phase
    k = round((start - t0) / beat)
    s0 = t0 + k * beat
    need = dur * factor + 0.5
    af = f"atempo={factor:.5f}," if abs(factor - 1) > 0.002 else ""
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", f"{s0:.3f}", "-t", f"{need:.3f}", "-i", str(src),
                    "-af", f"{af}atrim=0:{dur:.3f},afade=t=out:st={dur - 1:.3f}:d=1",
                    "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    print(f"원곡 템포 {tb:.1f} BPM → {factor:.3f}배 (릴스 {bpm:g} BPM), 시작 {s0:.2f}초, 길이 {dur:g}초 → {out}")
    return {"tempo": tb, "factor": factor, "start": s0}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(1)
    kw = {}
    for name in ("bpm", "start", "dur"):
        if f"--{name}" in a:
            i = a.index(f"--{name}")
            kw[name] = float(a[i + 1])
            del a[i:i + 2]
    fit(a[0], a[1], **kw)
