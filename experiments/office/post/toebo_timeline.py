"""퇴보 vs 퇴화 편 타임라인 (컷·동작·표정·화면·효과음·카드) → scripts/toebo.json에 써 넣음. 대사·목소리는 json에서 고친다.
운영자 2026-11-19 확정 대본 toebo_toehwa.md. 3차 (운영자 "중간은 과제, 기말은 시험만", "장면 전환 때 언제인지 몰라서 → 짧은 안내 + 소리·소품으로 확실하게"):
밤샘 → 제출 완료 → [검은 화면 '2주 뒤, 성적 발표 날' + 달력 넘김, 낮 하늘·새소리] 성적 로딩 → C → 단톡방 → 채점: 클로드
→ "기말은… 클로드, 너만 믿는다" → 기말 공지 → [‘기말고사 당일’, 딩동·연필 소리, 칠판 '기말고사'] 시험장 → 숨기 → 경보 → 모두 쳐다봄
→ [‘그날 저녁’, 저녁 하늘·귀뚜라미] 집: 기말 성적 로딩 → 부정행위 적발 → F → "뭐 어쩌라는 거야"."""
import json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "scripts" / "toebo.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["lines"][6]["sub"] = "하...|기말은... 클로드, 너만 믿는다."
d["props"] = {"night": True, "dorm": True, "exam": True}
d["clips"] = {k: {"file": f"experiments/office/out/clips/toebo_{k}.mp4", "from": 0, "to": n, "land": True, "res": 1920}
              for k, n in (("notice1", 5), ("allnight", 6.6), ("gradec", 7), ("grader", 6), ("notice2", 7), ("caught", 4.6))}


def E(line, dt, who, do=None, end=False, **k):
    e = {"line": line, "dt": dt, "who": who, **k}
    if do:
        e["do"] = do
    if end:
        e["end"] = True
    return e


def S(line, dt, end=False, **k):
    e = {"line": line, "dt": dt, **k}
    if end:
        e["end"] = True
    return e


def at(base, plus, **k):          # base 시각 + plus초
    return dict(base, dt=base["dt"] + plus, **k)


FADE = 1.4
F1 = S(1, 2.5, end=True)          # 밤샘 → 2주 뒤 성적 발표 날
F2 = S(6, 0.9, end=True)          # → 기말고사 일주일 전 (공지)
F3 = S(7, 0.3, end=True)          # 집 → 기말고사 당일 시험장
F4 = S(9, 0.9, end=True)          # 시험장 → 그날 저녁 집
MID = 0.7                         # 전환 가운데 (가장 어두울 때 장면 바꿈)
HIDE, SIREN, SD = 0.1, 0.55, 1.9  # 8번 대사 끝 기준
DAY = {"top": [110, 170, 235], "bot": [190, 222, 250], "d": 0.05}
DUSK = {"top": [44, 40, 92], "bot": [232, 122, 74], "d": 0.05}

ev = [{"t": 0, "who": "man", "do": "look", "at": "monitor"}, {"t": 0, "who": "claude", "do": "look", "at": "monitor"}]
ev += [E(0, 0, "man", emo="worried"), E(1, 0, "man", "sigh"), E(1, 0.5, "man", "type", d=3.4), E(1, 0.2, "man", "pile", d=3.0), E(1, 0.6, "man", "dawn", d=2.6),
       E(1, 0.3, "claude", "look", at="man"), E(1, 0.9, "man", "slump", end=True, d=0.35, amt=0.45), E(1, 1.4, "man", "startle", end=True)]
ev += [at(F1, MID, who="man", do="sky", **DAY)]
ev += [E(2, -0.6, "man", emo="worried"), E(2, 0, "man", emo="blank"), E(2, 1.3, "man", emo="sad")]
ev += [E(3, 0, "man", "look", at="claude"), E(3, 0, "man", emo="angry"), E(3, 0.4, "claude", emo="awkward"), E(3, 0.4, "claude", "look", at="man")]
ev += [E(4, 1.0, "claude", "look", at="monitor"), E(5, 0, "claude", "look", at="man"), E(5, 0, "man", emo="blank"), E(5, 0.3, "claude", "tremble", d=0.5)]
ev += [E(6, 0, "man", "look", at="claude"), E(6, 0, "man", emo="bitter"), E(6, 0.1, "claude", "hop", end=True), E(6, 0.1, "claude", end=True, emo="excited")]
ev += [at(F2, MID, who="man", do="look", at="monitor"), at(F2, MID, who="claude", do="look", at="monitor"), at(F2, MID, who="claude", emo="smile"), E(7, 0, "man", emo="surprised")]
ev += [at(F3, MID, who="man", do="exam"), E(8, -0.8, "man", "look", at="claude"), E(8, -0.8, "man", emo="worried"),
       E(8, 0, "claude", "look", at="man"), E(8, 0.2, "claude", emo="awkward"),
       E(8, HIDE, "claude", "hide", end=True, d=4.6),   # 집에 올 때까지 숨어 있음
       E(8, SIREN, "man", "startle", end=True), E(8, SIREN, "man", end=True, emo="surprised"), E(8, SIREN + 0.15, "man", "stare", end=True)]
ev += [E(9, 0, "man", "look", at="camera"), E(9, 0, "man", "tremble", d=0.6), E(9, 0.4, "man", emo="awkward"),   # 9번: 남자 "헉...!" (운영자 2026-11-19)
       at(F4, MID, who="man", do="home"), at(F4, MID, who="man", do="sky", **DUSK)]
ev += [at(F4, MID, who="man", do="look", at="monitor"), E(10, 0, "man", "look", at="camera"), E(10, 0, "man", emo="meh"),
       E(10, 2.4, "man", "slump", d=3.5, amt=0.9), E(10, 2.4, "claude", emo="awkward"), E(10, 2.4, "claude", "look", at="man")]
d["events"] = ev

d["screens"] = [{"t": 0, "screen": "monitor", "clip": "notice1", "hold": True},
                {"line": 0, "end": True, "dt": -1.0, "screen": "monitor", "clip": "allnight", "hold": True},
                at(F1, 1.7, screen="monitor", clip="gradec", hold=True),
                {"line": 4, "dt": 1.0, "screen": "monitor", "clip": "grader", "hold": True},
                at(F2, MID, screen="monitor", clip="notice2", hold=True),
                at(F4, 1.0, screen="monitor", clip="caught", hold=True)]

d["shots"] = [{"t": 0, "cam": "mon", "z0": 1.1, "z1": 1.35},
              {"line": 0, "dt": 1.3, "cam": "close:man"},
              {"line": 1, "dt": -0.1, "cam": "wide", "dx": 0.3},                         # 밤샘: 책 쌓임·창밖 새벽
              {"line": 1, "end": True, "dt": 0.3, "cam": "mon", "z0": 1.0, "z1": 1.25},  # 새벽 시계 → 제출 완료
              at(F1, MID, cam="wide", dx=-0.2),                                          # 2주 뒤 낮: 창밖 파란 하늘
              at(F1, 1.6, cam="mon", z0=1.05, z1=1.2),                                   # 성적 로딩 → C → 단톡방
              {"line": 3, "dt": -0.1, "cam": "close:man", "push": 0.12},
              {"line": 4, "dt": -0.1, "cam": "close:claude"},
              {"line": 4, "dt": 1.0, "cam": "mon", "z0": 1.0, "z1": 1.15},               # 채점: 클로드 → C
              {"line": 5, "dt": -0.1, "cam": "close:claude", "push": 0.15},
              {"line": 6, "dt": -0.1, "cam": "close:man"},
              {"line": 6, "end": True, "dt": 0.05, "cam": "close:claude"},               # 신난 클로드
              at(F2, MID, cam="mon", z0=1.0, z1=1.25),                                    # 기말 일주일 전: 재난문자 공지
              {"line": 7, "dt": 1.3, "cam": "close:man", "push": 0.15},
              at(F3, MID, cam="wide", back=1.7),                                         # 시험장: 칠판 '기말고사', 조용히 시험 → 숨기 → 경보 → 모두 쳐다봄
              {"line": 9, "dt": -0.1, "cam": "close:man", "push": 0.15},
              {"line": 9, "end": True, "dt": 0.1, "cam": "wide", "back": 1.7},          # 1초 정적: 모두 쳐다봄
              at(F4, MID, cam="wide", dx=-0.2),                                          # 그날 저녁: 노을 창밖
              at(F4, 1.6, cam="mon", z0=1.0, z1=1.2),                                    # 기말 성적 로딩 → 부정행위 적발 → F
              {"line": 10, "dt": -0.1, "cam": "close:man"},
              {"line": 10, "dt": 2.3, "cam": "two:claude:man"}]

black = S(10, 0.9, end=True)
d["cards"] = [dict(F1, kind="fade", d=FADE, text="2주 뒤, 성적 발표 날", day=3),
              dict(F2, kind="fade", d=FADE, text="기말고사 일주일 전", day=8),
              dict(F3, kind="fade", d=FADE, text="기말고사 당일", day=15),
              dict(F4, kind="fade", d=FADE, text="그날 저녁", day=15),
              S(8, SIREN, end=True, kind="alert", d=SD, text="위급재난문자|[기말고사] 휴대폰 검사 중. 울리면 부정행위"),
              dict(black, kind="black", d=0.5),
              dict(black, dt=1.3, kind="end", text="팔로우하고 AI를 재밌게 배워 보세요!")]
d["tail"] = 3.4

d["sfx"] = [{"line": 0, "dt": 0.0, "kind": "click", "vol": 0.8},
            {"line": 1, "dt": 0.4, "kind": "typing", "d": 3.0, "fo": 0.3, "vol": 0.8},
            {"line": 0, "end": True, "dt": -1.0 + 5.4, "kind": "ding", "vol": 0.5},                            # 제출 완료
            dict(F1, kind="swipe", vol=0.7), at(F1, MID + 0.1, kind="birds", d=4.0, fo=0.8, vol=0.7),          # 아침 새소리
            {"line": 2, "dt": -0.2, "kind": "boom", "vol": 0.45}]                                              # C
d["sfx"] += [at(F1, 1.7 + 2.1 + 0.6 * i, kind="ding", vol=0.45) for i in range(3)]                            # 단톡 알림
d["sfx"] += [{"line": 4, "dt": 1.0 + 2.6, "kind": "boom", "vol": 0.35},                                       # 채점 C
             {"line": 6, "end": True, "dt": 0.1, "kind": "boing", "vol": 0.7},
             dict(F2, kind="swipe", vol=0.7),
             {"line": 7, "dt": -0.3, "kind": "tension", "d": 3.4, "fo": 0.4, "vol": 0.45},
             dict(F3, kind="swipe", vol=0.7), at(F3, MID + 0.1, kind="bell", vol=0.6),
             at(F3, MID + 0.6, kind="scribble", vol=0.5),                                                      # 연필 사각사각
             S(8, HIDE, end=True, kind="swipe", vol=0.8),
             S(8, SIREN, end=True, kind="siren", d=SD, fo=0.08, vol=0.55),
             dict(F4, kind="swipe", vol=0.7), at(F4, MID + 0.1, kind="crickets", d=6.0, fo=1.0, vol=0.8),     # 저녁 귀뚜라미
             at(F4, 1.0 + 0.9 + 0.15, kind="slam", vol=0.9),                                                   # 부정행위 적발
             at(F4, 1.0 + 0.9 + 1.55, kind="fail", vol=0.7),                                                   # F
             dict(black, kind="click", vol=1.1)]
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(ev), "events")
