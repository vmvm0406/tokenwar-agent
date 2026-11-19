"""기본소득 편 타임라인 (컷·동작·표정·화면·효과음·카드) → scripts/ubi.json에 써 넣음. 대사·목소리는 json에서 고친다.
2차 (운영자 2026-11-19 "긴장감 없고 집중도 낮다, 말 빠르게 보완"): 첫 0.5초부터 뉴스 '2035.03.02 AI가 번 돈으로 전 국민 기본소득'
+ "일 안 해도 돈이 들어온다고?!" → "제가 사용자님 일을 맡게 됐거든요!" → "…내 일을?" → 3초 빠른 반복(입금 띵·게임·늦잠)
→ "나 이젠 뭐 하고 살지?" → "음… 그건 제가 정해 드릴 순 없네요." → 끝 그림: 쉬지 않고 일하는 클로드 + 멍한 남자."""
import json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "scripts" / "ubi.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["props"] = {"dorm": True, "box": True}
d["clips"] = {k: {"file": f"experiments/office/out/clips/ubi_{k}.mp4", "from": 0, "to": n, "land": True, "res": 1920}
              for k, n in (("resign", 6), ("news", 6), ("deposit", 5), ("game", 8), ("pause", 6), ("work", 6))}
d["lines"][3]["sub_at"] = [1.65]
d["lines"][4]["sub_at"] = [1.05]


def E(line, dt, who, do=None, end=False, **k):
    e = {"line": line, "dt": dt, "who": who, **k}
    if do:
        e["do"] = do
    if end:
        e["end"] = True
    return e


def T(t, **k):
    return {"t": t, **k}


def M(dt, **k):   # 2번 대사 끝 기준 (빠른 반복 구간)
    return {"line": 2, "end": True, "dt": dt, **k}


DAY = {"top": [110, 170, 235], "bot": [190, 222, 250], "d": 0.05}
NIGHT = {"top": [8, 12, 32], "bot": [20, 26, 52], "d": 0.15}
DUSK = {"top": [44, 40, 92], "bot": [232, 122, 74], "d": 0.2}

ev = [T(0, who="man", do="sky", **DAY), T(0, who="man", do="look", at="monitor"), T(0, who="claude", do="look", at="monitor")]
ev += [E(0, 0.0, "man", "startle"), E(0, 0.3, "man", "look", at="claude"), E(0, 0.6, "man", emo="happy"),
       E(1, 0, "claude", "look", at="man"), E(1, 0, "claude", "hop"),
       E(2, 0, "man", emo="happy"), E(2, 0.55, "man", emo="blank"), E(2, 0.55, "man", "tremble", d=0.4), E(2, 0.6, "claude", emo="smile")]
# 빠른 반복: 입금 띵 → 게임 → 늦잠 → 입금 띵 → 게임 (상자 치움, 낮밤 휙휙)
ev += [M(0.25, who="man", do="unbox"), M(0.25, who="man", emo="happy"), M(1.0, who="man", do="look", at="monitor"), M(1.0, who="man", emo="half"),
       M(1.0, who="man", do="type", d=0.9), M(1.0, who="man", do="sky", **NIGHT), M(1.7, who="man", do="slump", d=0.7, amt=0.8),
       M(1.7, who="man", emo="sleepy"), M(1.7, who="man", do="sky", **DAY), M(2.9, who="man", do="type", d=0.9), M(2.9, who="man", do="sky", **DUSK),
       M(1.0, who="claude", do="look", at="man"), M(1.0, who="claude", emo="worried")]
ev += [E(3, -0.3, "man", "look", at="claude"), E(3, 0, "man", emo="blank"), E(3, 0.3, "claude", "look", at="man"),
       E(4, 0, "claude", "tilt", d=1.0), E(4, 0.5, "man", emo="sad"),
       E(4, 0.1, "claude", "look", end=True, at="monitor"), E(4, 0.2, "claude", "work", end=True, d=7.0), E(5, 0, "claude", "look", at="camera"), E(4, 0.2, "claude", end=True, emo="neutral"),
       E(4, 0.2, "man", "look", end=True, at="camera"), E(4, 0.2, "man", end=True, emo="blank")]
d["events"] = ev

d["screens"] = [T(0, screen="monitor", clip="news", hold=True),
                {"line": 1, "dt": 0.7, "screen": "monitor", "clip": "resign", "hold": True},
                M(0.25, screen="monitor", clip="deposit", hold=True), M(1.0, screen="monitor", clip="game", hold=True),
                M(2.2, screen="monitor", clip="deposit", hold=True), M(2.9, screen="monitor", clip="game", hold=True),
                {"line": 3, "dt": -0.3, "screen": "monitor", "clip": "pause", "hold": True},
                {"line": 4, "end": True, "dt": 0.1, "screen": "monitor", "clip": "work", "hold": True}]

d["shots"] = [T(0, cam="mon", z0=1.02, z1=1.18),                                     # 첫 화면부터 뉴스 (훅)
              {"line": 0, "dt": 0.25, "cam": "close:man", "push": 0.08},
              {"line": 1, "dt": -0.1, "cam": "close:claude"},
              {"line": 1, "dt": 0.7, "cam": "mon", "z0": 1.0, "z1": 1.2},              # 퇴사 메일: 클로드가 일을 이어받음
              {"line": 2, "dt": -0.1, "cam": "close:man"},
              {"line": 2, "dt": 0.55, "cam": "close:man", "push": 0.2},               # 웃다가 멈칫 (리훅)
              M(0.25, cam="mon", z0=1.05, z1=1.15),                                    # 입금 띵
              M(1.0, cam="wide", dx=0.1),                                              # 게임 (밤)
              M(1.7, cam="close:man"),                                                 # 늦잠 (낮)
              M(2.2, cam="mon", z0=1.05, z1=1.15),                                     # 또 입금 띵
              M(2.9, cam="wide", dx=0.1),                                              # 또 게임 (저녁)
              {"line": 3, "dt": -0.2, "cam": "close:man"},
              {"line": 4, "dt": -0.1, "cam": "close:claude", "push": 0.06},
              {"line": 4, "end": True, "dt": 0.1, "cam": "mon", "z0": 1.0, "z1": 1.2},  # 쉬지 않고 일하는 클로드: 처리 건수·번 돈이 계속 오름
              {"line": 4, "end": True, "dt": 1.5, "cam": "two:claude:man"}]           # 일하는 클로드 옆 멍한 남자

black = {"line": 4, "end": True, "dt": 3.0}   # 일하는 클로드 장면 뒤 → 끝 화면에서 클로드가 질문 (운영자 2026-11-19 "질문은 바뀐 마지막 화면에서")
d["cards"] = [dict(black, kind="end", text="일이 필요 없는 세상.\n여러분은 어떤 삶을 살고 싶으신가요?|팔로우하고 AI를 재밌게 배워 보세요!")]
d["tail"] = 0.5   # 질문 끝나면 바로 끝 (운영자 "뒤에 남는 정적 없게")

d["sfx"] = [T(0.05, kind="boom", vol=0.35),
            {"line": 1, "dt": 0.7, "kind": "click", "vol": 0.7},
            {"line": 2, "dt": 0.55, "kind": "boom", "vol": 0.45},                     # 멈칫
            M(0.37, kind="ding", vol=0.55), M(1.0, kind="typing", d=0.8, fo=0.1, vol=0.6), M(1.7, kind="swipe", vol=0.6),
            M(2.32, kind="ding", vol=0.55), M(2.9, kind="typing", d=0.8, fo=0.1, vol=0.6),
            {"line": 3, "dt": -0.4, "kind": "pad", "d": 16.0, "fo": 1.5, "vol": 0.55},
            {"line": 4, "end": True, "dt": 0.2, "kind": "typing", "d": 2.8, "fo": 0.4, "vol": 0.4},   # 클로드 작업 소리
            dict(black, kind="click", vol=1.1)]
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(ev), "events")
