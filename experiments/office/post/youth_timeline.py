"""신입 자리 편 타임라인 (컷·동작·표정·화면·효과음·배경음·카드) → scripts/youth_newbie.json에 써 넣음. 대사·목소리는 json에서 고친다.
2차 (운영자 2026-11-19): 남자 + 클로드 단독, 결말은 클로드가 자기에게 배움(RSI). 컷은 말하는 사람이 바뀔 때·정보가 나올 때만,
모니터는 세 번(불합격 6·경력 2년·AI 처리), 배경음 pad(쓸쓸)→정적→warm(문서 모임)→whum(깨달음)→rise(가속)→빗소리만."""
import json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "scripts" / "youth_newbie.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["cast"] = [{"key": "man", "human": True}, {"key": "claude", "x": -0.28, "z": 0.24, "yaw": 0.3, "size": 0.38}]
d["lines"][8].pop("break", None)   # 1차 타임라인이 넣던 것 (묶음이 바뀌면 다시 녹음됨)
d["tail"] = 3.6
d["clips"] = {k: {"file": f"experiments/office/out/clips/youth_{k}.mp4", "from": 0, "to": n, "land": True, "res": 1920}
              for k, n in (("inbox", 5), ("posting", 7), ("stamp", 6))}


def E(line, dt, who, do=None, end=False, **k):
    e = {"line": line, "dt": dt, "who": who, **k}
    if do:
        e["do"] = do
    if end:
        e["end"] = True
    return e


BEAT = -1.15     # 10번 대사 1.15초 전: 깨닫는 순간
UP = 1.4         # 10번 대사 '저는 저한테'부터 업그레이드 시작
ev = [{"t": 0, "who": "man", "do": "look", "at": "monitor"}, {"t": 0, "who": "claude", "do": "look", "at": "monitor"}]
ev += [E(0, 2.0, "man", "slump", d=9.9, amt=0.8)]
ev += [E(1, 0.2, "man", "look", at="claude"), E(1, 0.5, "claude", "look", at="man")]
ev += [E(2, 0, "claude", "hop"), E(2, 0.6, "claude", "look", at="monitor"), E(2, 0.6, "claude", "work", d=1.4),
       E(2, 2.4, "claude", "look", at="man"), E(2, 2.4, "claude", emo="awkward")]
ev += [E(3, 0, "man", "look", at="claude")]
ev += [E(4, 0, "claude", "look", at="man"), E(4, 0.8, "claude", "look", at="monitor"), E(4, 2.9, "claude", "look", at="man"), E(4, 3.0, "claude", "tremble", d=0.6)]
ev += [E(5, -0.3, "man", "look", at="claude"), E(5, 0, "claude", emo="down"), E(5, 0.2, "man", end=True, emo="sad")]
ev += [E(6, 0.2, "claude", "look", at="camera"), E(6, 0, "man", "look", at="claude")]
ev += [E(7, 3.0, "claude", "tilt", d=1.6)]
ev += [E(8, 0, "man", "look", at="claude"), E(8, 0, "man", "sigh")]
ev += [E(9, 0, "claude", "look", at="camera")]
ev += [E(10, BEAT, "claude", emo="surprised"), E(10, BEAT + 0.05, "claude", "tremble", d=0.35),
       E(10, UP, "claude", "grow", d=4.0, amt=0.45), E(10, 2.0, "man", emo="blank")]
d["events"] = ev

d["screens"] = [{"t": 0, "screen": "monitor", "clip": "inbox", "hold": True},
                {"line": 2, "dt": 1.0, "screen": "monitor", "clip": "posting", "hold": True},
                {"line": 4, "dt": 0.8, "screen": "monitor", "clip": "stamp", "hold": True}]

d["shots"] = [{"t": 0, "cam": "mon", "z0": 1.15, "z1": 1.4},
              {"line": 1, "dt": -0.1, "cam": "close:man"},
              {"line": 2, "dt": -0.1, "cam": "close:claude"},
              {"line": 2, "dt": 2.3, "cam": "mon", "z0": 1.0, "z1": 1.2},
              {"line": 3, "dt": -0.1, "cam": "close:man"},
              {"line": 4, "dt": -0.1, "cam": "close:claude"},
              {"line": 4, "dt": 1.2, "cam": "mon", "z0": 1.0, "z1": 1.15},
              {"line": 4, "dt": 3.0, "cam": "close:claude", "push": 0.22},          # '제가 하거든요' 툭 확대
              {"line": 5, "dt": -0.2, "cam": "close:man"},
              {"line": 6, "dt": -0.1, "cam": "close:claude"},
              {"line": 8, "dt": -0.15, "cam": "close:man"},
              {"line": 9, "dt": -0.2, "cam": "close:claude"},
              {"line": 10, "dt": BEAT + 0.05, "cam": "close:claude", "push": 0.12},  # 깨달음
              {"line": 10, "dt": UP, "cam": "close:claude", "push": 0.0}]            # 업그레이드 (커지는 클로드 + 뒤의 굳은 남자)

black = {"line": 10, "end": True, "dt": 1.4}
d["cards"] = [{"line": 6, "dt": 0.3, "kind": "gather", "who": "claude", "stop": 6.45, "d": 10.3},   # 문서가 클로드에게 모이다 '사람이 일을 못 배우면'에서 끊김
              {"line": 10, "dt": UP, "kind": "selfloop", "who": "claude", "d": 4.2},
              dict(black, kind="black", d=0.6),
              dict(black, dt=1.8, kind="end", text="팔로우하고 AI를 재밌게 배워 보세요!")]

d["sfx"] = [{"t": 0, "kind": "rain", "vol": 1.0},
            {"t": 0.35, "kind": "ding", "vol": 0.6}, {"t": 0.35, "kind": "boom", "vol": 0.35},     # 불합격 6 쾅
            {"t": 0.0, "kind": "pad", "d": 18.2, "fo": 0.25, "vol": 0.7},                         # 쓸쓸한 패드 → '제가 하거든요'에서 뚝
            {"line": 2, "dt": 1.0 + 2.4, "kind": "click"},
            {"line": 3, "end": True, "dt": 0.1, "kind": "ding", "vol": 0.5}]
d["sfx"] += [{"line": 4, "dt": 0.8 + 0.6 + 0.55 * i, "kind": "pop"} for i in range(4)]
d["sfx"] += [{"line": 6, "dt": 0.0, "kind": "warm", "d": 8.5, "fo": 2.2, "vol": 0.7},             # 문서가 모이는 따뜻함 → 끊기며 사라짐
             {"line": 10, "dt": BEAT, "kind": "whum", "vol": 0.35},
             {"line": 10, "dt": UP, "kind": "rise", "d": 4.0 + 1.4 - UP + 0.02, "fo": 0.05, "vol": 0.6},
             dict(black, kind="click", vol=1.2)]
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(ev), "events")
