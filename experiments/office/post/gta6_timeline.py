"""GTA 6 편 타임라인 (컷·동작·표정·화면·효과음) → scripts/gta6.json에 써 넣음. 대사·목소리는 gta6.json에서 고친다."""
import json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "scripts" / "gta6.json"
d = json.loads(p.read_text(encoding="utf-8"))
ais = ["claude", "chatgpt", "gemini"]


def E(line, dt, who, do=None, end=False, **k):
    e = {"line": line, "dt": dt, "who": who, **k}
    if do:
        e["do"] = do
    if end:
        e["end"] = True
    return e


ev = [E(0, 0, a, "look", at="man") for a in ais] + [E(0, 0, "man", "look", at="monitor")]
ev += [E(1, 0, "man", "look", at="claude"), E(1, 0.9, "man", "look", at="gemini"), E(1, 1.8, "man", "look", at="chatgpt")]
ev += [E(2, 0, "man", "look", at="chatgpt"), E(2, 0, "claude", "look", at="chatgpt"), E(2, 0, "gemini", "look", at="chatgpt"),
       E(2, 0.1, "chatgpt", "hop"), E(2, 2.85, "chatgpt", "hop"), E(2, 3.9, "claude", "tilt", d=1.3)]
ev += [E(3, 0, "man", "look", at="gemini"), E(3, 0, "chatgpt", "look", at="gemini"), E(3, 0, "claude", "look", at="gemini"),
       E(3, 0, "gemini", "look", at="monitor"), E(3, 0.7, "gemini", "work", d=1.5),
       E(3, 2.3, "man", "look", at="monitor"), E(3, 2.3, "chatgpt", "look", at="monitor"), E(3, 2.3, "claude", "look", at="monitor"),
       E(3, 4.6, "gemini", "look", at="claude"), E(3, 4.6, "gemini", "tremble", d=1.2)]
ev += [E(4, -0.1, "man", "startle")] + [E(4, 0, a, "look", at="man") for a in ais]
ev += [E(5, 0, "man", "look", at="chatgpt"), E(5, 0.05, "chatgpt", "hop"), E(5, 0.6, "gemini", "look", at="chatgpt")]
ev += [E(6, 0, w, "look", at="claude") for w in ("man", "chatgpt", "gemini")] + [E(6, 0.3, "claude", "look", at="man")]
ev += [E(7, 0, w, "look", at="gemini") for w in ("man", "claude", "chatgpt")] + [E(7, 0.05, "gemini", "hop"), E(7, 0, "gemini", "look", at="man")]
ev += [E(7, 0.1, w, "look", end=True, at="monitor") for w in ("man", *ais)]
ev += [E(7, 0.3, "gemini", "work", end=True, d=1.0),
       E(7, 4.15, "man", "startle", end=True), E(7, 4.15, "man", end=True, emo="surprised"),
       E(7, 4.3, "chatgpt", "startle", end=True), E(7, 4.3, "chatgpt", end=True, emo="surprised"),
       E(7, 4.4, "claude", end=True, emo="embarrassed"), E(7, 4.4, "gemini", end=True, emo="embarrassed")]
ev += [E(8, 0, "man", "sigh"), E(8, 0, "man", "look", at="camera")] + [E(8, 0.1, a, "look", at="man") for a in ais]
ev += [E(8, 0, "chatgpt", emo="sad"), E(8, 0, "gemini", emo="sad")]
ev += [E(9, 0, w, "look", at="claude") for w in ("man", "chatgpt", "gemini")]
ev += [E(9, 0.1, "claude", "nod"), E(9, 1.6, "claude", "look", at="monitor"), E(9, 1.7, "claude", "work", d=2.2),
       E(9, 1.8, "man", "look", at="monitor"), E(9, 3.9, "claude", "look", at="man")]
ev += [E(9, 0.3, w, end=True, emo="happy") for w in ("man", "chatgpt", "gemini")]
ev += [E(9, 0.6 + 0.1 * i, w, "look", end=True, at="camera") for i, w in enumerate(("man", "claude", "chatgpt", "gemini"))]
d["events"] = ev
d["screens"] = [{"t": 0, "screen": "monitor", "clip": "countdown", "hold": True},
                {"line": 3, "dt": 2.2, "screen": "monitor", "clip": "calendar", "hold": True},
                {"line": 7, "end": True, "dt": 0.1, "screen": "monitor", "clip": "ladder", "hold": True},
                {"line": 9, "dt": 1.1, "screen": "monitor", "clip": "shorts", "hold": True}]
d["shots"] = [{"t": 0, "cam": "mon", "z0": 1.1, "z1": 1.4},
              {"line": 0, "dt": 0.8, "cam": "close:man"},
              {"line": 1, "dt": -0.1, "cam": "wide"},
              {"line": 2, "dt": -0.1, "cam": "close:chatgpt"},
              {"line": 3, "dt": -0.1, "cam": "close:gemini"},
              {"line": 3, "dt": 2.3, "cam": "mon", "z0": 1.0, "z1": 1.2},
              {"line": 4, "dt": -0.15, "cam": "close:man"},
              {"line": 5, "dt": -0.1, "cam": "close:chatgpt"},
              {"line": 6, "dt": -0.1, "cam": "close:claude"},
              {"line": 7, "dt": -0.1, "cam": "close:gemini"},
              {"line": 7, "end": True, "dt": 0.15, "cam": "mon", "z0": 1.0, "z1": 1.25},
              {"line": 7, "end": True, "dt": 4.9, "cam": "close:man"},
              {"line": 9, "dt": -0.1, "cam": "close:claude"},
              {"line": 9, "dt": 1.4, "cam": "mon", "z0": 1.0, "z1": 1.15},
              {"line": 9, "end": True, "dt": 0.45, "cam": "wide"}]
d["cards"] = [{"line": 9, "end": True, "dt": 2.2, "kind": "end", "text": "긴 영상, 쇼츠로 자동으로 자르는 법!|프로필에 정리해 뒀어요.|팔로우하고 AI를 재밌게 배워 보세요!"}]
sfx = [{"line": 2, "dt": 0.1, "kind": "boing"}, {"line": 2, "dt": 2.85, "kind": "boing"}, {"line": 3, "dt": 0.7, "kind": "click"},
       {"line": 5, "dt": 0.05, "kind": "boing"}, {"line": 7, "dt": 0.05, "kind": "boing"}]
sfx += [{"line": 3, "dt": round(2.2 + 0.55 + 0.45 * j, 2), "kind": "pop"} for j in range(5)]
sfx += [{"line": 7, "end": True, "dt": round(0.8 + 0.4 * j, 2), "kind": "tiptoe"} for j in range(8)]
sfx += [{"line": 7, "end": True, "dt": 4.1, "kind": "boom", "vol": 0.6}, {"line": 7, "end": True, "dt": 4.1, "kind": "pop"}]
sfx += [{"line": 9, "dt": round(1.4 + 2.1 * x, 2), "kind": "click"} for x in (0.23, 0.57, 0.86)] + [{"line": 9, "dt": 5.0, "kind": "ding"}]
d["sfx"] = sfx
d["tail"] = 5.6
d["lead"] = 1.0
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok")
