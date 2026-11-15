"""s10 드와케시 클립 → Caption News 세로 릴스 재료 (프레임, 소리, 타임라인)."""
import json, subprocess, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = str(REPO / "samples/s10-dwarkesh-ai-rnd/clips/source.mp4")
POST = json.load(open(REPO / "samples/s10-dwarkesh-ai-rnd/post.json", encoding="utf-8"))
keep = [[6.6, 37.1]]   # 중간에 자르지 않고 한 구간 그대로
FF = shutil.which("ffmpeg") or "ffmpeg"   # ffmpeg 7 이상
out = HERE / "frames"; shutil.rmtree(out, ignore_errors=True); out.mkdir()

def remap(t):
    acc = 0.0
    for a, z in keep:
        if t < a: return acc
        if t <= z: return acc + (t - a)
        acc += z - a
    return acc

# 1) 빠른 전환으로 이어 붙인 영상 → 30fps 프레임 (1440x810, 확대 여유) + 소리
parts = "".join(f"[0:v]trim={a}:{z},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{z},asetpts=PTS-STARTPTS[a{i}];" for i, (a, z) in enumerate(keep))
cat = "".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]"
subprocess.run([FF, "-v", "error", "-y", "-i", SRC, "-filter_complex", parts + cat + ";[v]fps=30,scale=1440:810:flags=lanczos,unsharp=5:5:0.4[vo]",
                "-map", "[vo]", "-q:v", "3", str(out / "%05d.jpg"), "-map", "[a]", "-ar", "48000", "-ac", "2", str(HERE / "voice.wav")], check=True)
n = len(list(out.glob("*.jpg")))
dur = round(sum(z - a for a, z in keep), 3)

# 2) 장면: 인물(head) / 그래프(chart) — 원본 시각 기준 구간
src_shots = [(6.6, 9.9, "head"), (9.9, 23.2, "chart"), (23.2, 27.5, "head"), (27.5, 37.1, "chart")]
shots = []
for a, z, k in src_shots:
    shots.append({"t0": round(remap(a), 3), "t1": round(remap(z), 3), "kind": k})
# 빠른 전환 컷 시각 (출력 기준)
cuts, acc = [], 0.0
for a, z in keep:
    cuts.append(round(acc, 3)); acc += z - a

en = ["OpenAI published a blog post about this in September,",
      "the heaviest 10% of AI users amongst OpenAI's researchers",
      "went from about $1,000 a day of internal coding agents",
      "to over $7,000 a day by the end of August.",
      "And also in September, Anthropic put out a similar post.",
      "Claude now leads 26% of Anthropic's AI R&D work,",
      "up from under 1% as recently as February."]
# 한국어 자막: 덩어리는 |, 강조 한 단어는 {}
ko = ["OpenAI가 {9월}에|이걸 보여 주는 글을 올렸는데요",
      "OpenAI 연구원 중|AI를 가장 많이 쓰는|{상위 10%}가",
      "여름 초에는 하루 약 {1,000달러}어치|코딩 에이전트를 쓰다가",
      "8월 말에는 하루|{7,000달러} 넘게|쓰게 됐다고 해요",
      "{앤트로픽}도 9월에|비슷한 글을 냈는데요",
      "지금은 앤트로픽 AI 연구개발의|{26%}를 Claude가 이끌고 있대요",
      "2월만 해도|{1% 미만}이었는데 말이죠"]
cues = []
for s, k, e in zip(POST["subtitles"], ko, en):
    cues.append({"t0": round(remap(s["start"]), 3), "t1": round(remap(s["end"]), 3), "ko": k, "en": e})
tl = {"dur": dur, "frames": n, "fps": 30, "shots": shots, "cuts": cuts, "cues": cues,
      "title": "AI가 AI 연구를|{이미} 하고 있습니다",
      "speaker": {"t0": 0.0, "t1": 3.2, "name": "드와케시 파텔", "role": "AI 팟캐스트 진행자"},
      "pops": [{"t0": round(remap(19.6), 3), "t1": round(remap(22.88), 3), "pre": "하루", "num": 7000, "fmt": "$", "suf": "", "src": "출처 OpenAI · 2026.09"},
               {"t0": round(remap(29.6), 3), "t1": round(remap(37.1), 3), "pre": "", "num": 26, "fmt": "", "suf": "%", "src": "출처 Anthropic · 2026.09"}],
      "hook": {"t0": 0.0, "t1": 1.9, "kicker": "OpenAI 연구원 한 명이 AI에 쓰는 돈", "num": 7000, "unit": "하루"},
      "credit": "영상 Dwarkesh Patel"}
# 주의: timeline.json에는 손으로 고친 beats/term/sub가 들어 있다. 덮어쓰지 않게 기존 값을 살린다
old = json.load(open(HERE / "timeline.json", encoding="utf-8")) if (HERE / "timeline.json").exists() else {}
for k in ("beats", "term"):
    if k in old: tl[k] = old[k]
for c, oc in zip(tl["cues"], old.get("cues", [])):
    if "sub" in oc: c["sub"] = oc["sub"]
json.dump(tl, open(HERE / "timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(n, dur, shots, cues[3])
