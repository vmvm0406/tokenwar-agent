"""릴스 소리 크기 맞추기 (STYLE_GUIDE 6장 "릴스 소리").

휴대폰으로 듣기 편하게: 통합 -14 LUFS 안팎, 순간 최대(true peak) -1.5 dBTP 이하.
총소리·북소리처럼 짧게 튀는 소리는 먼저 눌러 준다(압축 + 리미터), 그 뒤 두 번 재는 loudnorm(linear)으로 맞춘다.
ffmpeg 필터가 실패하면 원래 파일을 그대로 두고 경고만 낸다.

사용법: python agent/loudness.py <mp4 ...>          재기만 (I / TP / LRA)
        python agent/loudness.py --fix <mp4 ...>    맞추기
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TARGET_I = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
# render.py 검사 범위 (이 밖이면 경고)
OK_I = (-16.0, -12.0)
OK_TP = -1.0

# 짧게 튀는 소리(총소리·북·종이 소리)를 누르는 압축: 문턱을 높게 두고 빠르게 잡고 빨리 놓아 말소리는 거의 안 건드린다
COMP = "acompressor=threshold=-10dB:ratio=3:attack=1:release=120:knee=4:makeup=1"


def _limit(ceiling_db):
    """마지막 리미터. 천장은 AAC로 바꾸며 솟는 만큼 목표(-1.5)보다 낮게 시작해 재 보고 더 낮춘다."""
    return f"alimiter=limit={10 ** (ceiling_db / 20):.4f}:attack=1:release=60:level=disabled"


def _ffmpeg():
    return shutil.which("ffmpeg")


def measure(path, pre=""):
    """loudnorm 측정값(dict: input_i, input_tp, input_lra, input_thresh, target_offset). 실패하면 None."""
    ff = _ffmpeg()
    if not ff:
        return None
    af = (pre + "," if pre else "") + f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json"
    r = subprocess.run([ff, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if r.returncode or not m:
        return None
    d = json.loads(m.group(0))
    try:
        if float(d["input_i"]) < -70:  # 무음
            return None
    except ValueError:
        return None
    return d


def stats(path):
    """(I LUFS, TP dBTP, LRA LU) 또는 None."""
    d = measure(path)
    if not d:
        return None
    return float(d["input_i"]), float(d["input_tp"]), float(d["input_lra"])


def normalize(mp4, target_i=TARGET_I, target_tp=TARGET_TP, comp=True):
    """mp4의 소리만 바꿔 다시 쓴다 (영상은 그대로 복사). 성공하면 (전, 후) 수치, 실패하면 None.
    comp=False: 1단계 압축(COMP)을 건너뛴다. 이미 섞을 때 소리를 다듬어 총소리 어택을 살려야 하는 릴스용 (post.json video.keep_transients)."""
    mp4 = Path(mp4)
    ff = _ffmpeg()
    if not ff or not mp4.exists():
        return None
    try:
        before = stats(mp4)
        if before is None:
            return None  # 소리 없음: 손대지 않는다
        # 1단계: 대략 목표 크기로 올리고(내리고) 튀는 소리를 압축으로 누른다
        pre = f"volume={target_i - before[0]:.2f}dB" + (f",{COMP}" if comp else "")
        # 2단계: 누른 결과를 다시 재서(loudnorm 측정) 남은 차이만큼 맞추고, 마지막 리미터로 봉우리를 자른다.
        # 결과를 재서 크기가 모자라거나 봉우리가 솟으면 보정해 다시 만든다 (최대 4번, 기준을 넘는 결과는 쓰지 않는다)
        m = measure(mp4, pre)
        if not m:
            raise RuntimeError("측정 실패")
        trim, ceiling = target_i - float(m["input_i"]), target_tp - 1.5
        tmp, best = mp4.with_name(mp4.stem + "_loud.mp4"), None
        for k in range(4):
            out = mp4.with_name(f"{mp4.stem}_loud{k}.mp4")
            r = subprocess.run([ff, "-nostdin", "-y", "-loglevel", "error", "-i", str(mp4),
                                "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                                "-af", f"{pre},volume={trim:.2f}dB,{_limit(ceiling)}",
                                "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode or not out.exists():
                raise RuntimeError(r.stderr.strip()[-300:])
            got = stats(out)
            if got is None:
                raise RuntimeError("결과 측정 실패")
            ok_tp = got[1] <= target_tp
            if ok_tp and (best is None or abs(got[0] - target_i) < abs(best[1][0] - target_i)):
                best = (out, got)
            if ok_tp and abs(got[0] - target_i) <= 0.5:
                break
            if not ok_tp:
                ceiling -= got[1] - target_tp + 0.3
            trim += min(3.0, target_i - got[0])  # 리미터를 너무 세게 누르지 않게 한 번에 3dB까지만
        if best is None:
            raise RuntimeError("순간 최대를 기준 아래로 못 맞춤")
        tmp, after = best
        for k in range(4):
            f = mp4.with_name(f"{mp4.stem}_loud{k}.mp4")
            if f != tmp:
                f.unlink(missing_ok=True)
        shutil.move(str(tmp), str(mp4))
        print(f"소리 맞춤: {before[0]:.1f} LUFS / {before[1]:.1f} dBTP → {after[0]:.1f} LUFS / {after[1]:.1f} dBTP")
        return before, after
    except Exception as e:  # 실패하면 원래 파일 그대로
        for k in range(4):
            mp4.with_name(f"{mp4.stem}_loud{k}.mp4").unlink(missing_ok=True)
        print(f"경고: 소리 크기 맞추기 실패, 원래 소리로 둔다 ({e})")
        return None


def check(mp4):
    """범위 밖이면 경고 문장 목록."""
    s = stats(mp4)
    if s is None:
        return []
    i, tp, _ = s
    out = []
    if not (OK_I[0] <= i <= OK_I[1]):
        out.append(f"소리 크기 {i:.1f} LUFS (기준 {OK_I[0]:g}~{OK_I[1]:g})")
    if tp > OK_TP:
        out.append(f"순간 최대 {tp:.1f} dBTP (기준 {OK_TP:g} 이하)")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    fix = "--fix" in args
    for a in [x for x in args if x != "--fix"]:
        if fix:
            normalize(a)
        else:
            s = stats(a)
            print(a, "소리 없음" if s is None else f"I {s[0]:.1f} LUFS  TP {s[1]:.1f} dBTP  LRA {s[2]:.1f} LU")
