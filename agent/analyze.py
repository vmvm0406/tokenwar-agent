"""영상 분석: 에이전트가 인용할 구간(start~end)을 고르도록 돕는다.

사용법:
    python agent/analyze.py <영상 파일> [출력 폴더]

만드는 것 (출력 폴더, 기본은 영상 옆 _analysis/):
    sheet_01.jpg ...   일정 간격 장면을 시간표시와 함께 모은 한 장짜리 그림 (에이전트가 직접 열어 본다)
    analysis.json      길이, 장면 전환 시각, 말소리가 있는 구간, (가능하면) 받아쓰기

받아쓰기는 faster-whisper와 모델을 받을 수 있을 때만 된다. 안 되면 그림과 소리 구간만으로 고른다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLS, ROWS = 6, 4
THUMB_W = 320


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return d["streams"][0]["width"], d["streams"][0]["height"], float(d["format"]["duration"])


def scene_changes(path, thresh=0.3):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{thresh})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def speech_regions(path, dur):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "silencedetect=noise=-35dB:d=0.4",
                        "-vn", "-f", "null", "-"], capture_output=True, text=True)
    if "Audio" not in r.stderr:
        return []
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    regions, cur = [], 0.0
    for s, e in zip(starts, ends + [dur] * (len(starts) - len(ends))):
        if s - cur > 0.3:
            regions.append([round(cur, 2), round(s, 2)])
        cur = e
    if dur - cur > 0.3:
        regions.append([round(cur, 2), round(dur, 2)])
    return regions


def transcribe(path):
    try:
        import numpy as np
        from faster_whisper import WhisperModel
        # 오디오는 ffmpeg로 직접 16kHz 모노로 풀어서 넘긴다 (PyAV 버전 차이 회피)
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                              "-f", "f32le", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, dtype=np.float32)
        if audio.size == 0:
            return {"error": "소리 없음"}
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segs, info = model.transcribe(audio, vad_filter=True)
        return {"language": info.language,
                "segments": [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]}
    except Exception as e:  # 패키지나 모델을 못 받는 환경
        return {"error": f"받아쓰기 불가: {type(e).__name__}"}


def contact_sheets(path, dur, w, h, out_dir):
    n = COLS * ROWS
    step = max(1.0, dur / n)
    times = [round(i * step, 2) for i in range(int(dur / step) + 1) if i * step < dur]
    th = int(THUMB_W * h / w)
    sheets = []
    try:
        font = ImageFont.truetype(str(Path(__file__).resolve().parent.parent / "assets/fonts/Pretendard-Bold.otf"), 22)
    except OSError:
        font = ImageFont.load_default()
    for k in range(0, len(times), n):
        chunk = times[k:k + n]
        sheet = Image.new("RGB", (COLS * (THUMB_W + 6) + 6, ((len(chunk) - 1) // COLS + 1) * (th + 36) + 6), (20, 20, 20))
        for i, t in enumerate(chunk):
            fp = out_dir / f"_f{t:.2f}.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(path), "-frames:v", "1",
                            "-vf", f"scale={THUMB_W}:{th}", str(fp)], check=True)
            x, y = 6 + (i % COLS) * (THUMB_W + 6), 6 + (i // COLS) * (th + 36)
            sheet.paste(Image.open(fp), (x, y + 30))
            ImageDraw.Draw(sheet).text((x + 4, y + 4), f"{int(t // 60)}:{t % 60:05.2f}", fill=(0, 255, 102), font=font)
            fp.unlink()
        name = out_dir / f"sheet_{k // n + 1:02d}.jpg"
        sheet.save(name, quality=85)
        sheets.append(name.name)
    return sheets, step


def main(video, out=None):
    video = Path(video).resolve()
    out_dir = Path(out) if out else video.parent / "_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h, dur = probe(video)
    sheets, step = contact_sheets(video, dur, w, h, out_dir)
    result = {
        "file": video.name, "duration": round(dur, 2), "width": w, "height": h,
        "sheet_interval_seconds": round(step, 2), "sheets": sheets,
        "scene_changes": scene_changes(video),
        "speech_regions": speech_regions(video, dur),
        "transcript": transcribe(video),
    }
    (out_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "transcript"}, ensure_ascii=False))
    print("받아쓰기:", "있음" if "segments" in result["transcript"] else result["transcript"].get("error"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:3])
