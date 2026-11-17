"""목록형 자료 릴스 (post type "video" + "list", 운영자 결정 2026-11-16, 참고 형식 '34가지 조명 코드').

결과 그림이 세로 화면 전체(1080x1920)를 꽉 채우고, 항목마다 그림과 영화 자막 같은 이름 띠가 박자에 맞춰 바뀐다
(운영자 수정 2026-11-17: "아래 하단이 비어있잖아", "썸네일처럼 화면 가득", "있어 보이게", "노래도 후킹되게").
길이 20~35초 (끝 화면 포함).

그림: 4:5(1088x1360)로 만든 그림에서 슬라임(마스코트) 중심을 찾아 세로 9:16(약 765x1360)만 잘라
      1080x1920으로 Lanczos 확대한다 (fill_frame). 그림 생성 크기는 4:5 그대로.
레이아웃 (1080x1920, 읽을 것은 모두 안전 영역 config.json reel_safe 안):
    0초~        첫 화면: 가장 눈에 띄는 결과 그림(list.hook) + 제목(2줄, 위쪽 띠, 안전 영역 맨 위)
                list.hook_anim(기본 true, 운영자 요청 2026-11-17 "처음 자막을 확 강조하면서 시작"): 제목 줄마다 1.3배에서
                쾅 박히며(0.95 넘침 → 1.0) 8분음표 간격으로 차례로 들어오고, 강조어(highlight)는 녹색 면으로 한 박 번쩍,
                그림은 줄이 박힐 때마다 짧게 흔들린다. 소리: 0초 쿵, 줄마다 휙+타격, 목록 시작 앞 상승음 → 비트 드롭.
    목록 쌓기   list.stack(기본 true, 운영자 요청 2026-11-17 "다음은? 궁금증", "목록에 ?로 15개 더"): 이름 띠 아래에
                번호 목록. 왼쪽 열 = 영상 항목(지난 것 흐리게, 지금 것 녹색, 아직 안 나온 것 "NN ?"), 오른쪽 열 = 자료 페이지
                추가 용어 자리 "16 ?" … (dm.page.more 수, list.stack_more false면 뺌).
    쏟아지기    list.flood(기본 true, dm.page.more가 있을 때): 끝 화면 앞 4박 동안 화면이 어두워지고 추가 용어 이름이 뒤에
                흐리게 쏟아지며, 오른쪽 열 "?" 자리가 빠르게 차례로 녹색으로 번쩍 채워진다(스웰 + 자리마다 틱). 그 뒤 바로 끝 화면.
                가운데 문구는 기본 없음 (list.flood_text로 한 줄 넣을 수 있음. '15개 더'처럼 개수 문구는 쓰지 않는다, 운영자 2026-11-17).
    항목 화면   그림 + 이름 띠: 작은 녹색 번호 / 큰 영어 이름(대문자, 자간 넓게). 한국어 이름은 DM 자료 페이지에만
                (운영자 결정 2026-11-17). list.label "ko"면 한국어 크게 + 영어 작게, "both"면 영어 크게 + 한국어 작게.
                띠는 단색 반투명 검정, 위쪽('자료' 안내 띠 바로 아래). 마스코트(화면 가운데~아래)를 가리지 않게.
                voice/<번호>.wav가 있으면 그림이 바뀌는 박에 맞춰 그 영어 용어 읽는 목소리를 넣는다 (agent/tts.py, Kokoro-82M).
                나타날 때 0.27초 동안 아래에서 올라오며 자간이 좁혀진다.
    3초~본편 끝 '자료' 안내 띠(dm.banner, 안전 영역 맨 위 285px)
    끝          dm.cta 끝 화면 2.5초 (video.py append_cta_card)

박자: 항목 길이 = 박자 간격의 정수배(기본 2박). BPM은 전체 길이가 29초 안팎이 되게 96~128에서 고른다.
      장면이 바뀌는 시각은 박 위에 오도록 프레임(30fps)으로 맞춘다(오차 1/60초 이하).
소리: music_gen.make_hook_music (0초부터 킥·스네어, 2마디 멜로디 훅, 목록 시작·8개마다 크래시) → -14 LUFS.
전체 목록·영어 용어·추가 용어는 화면에 다 쓰지 않고 DM 자료 페이지(dm.py)에 둔다.
그림은 마스코트 슬라임 AI 그림 (list.items[].prompt + "mascot": true → render.yml의 gen_images가 만든다).
그림이 아직 없으면 render.py가 회색 자리표시(번호만)로 틀만 렌더링한다 (with_placeholders, Actions에서는 멈춤).
"""
import asyncio
import html
import json
import random
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)
RAIL_TOP = _SAFE.get("rail_top", 1150)   # 오른쪽 아래 버튼 줄 시작. 이름 띠는 이 위에서 끝난다

TARGET_TOTAL = 29.0     # 기본 목표 길이(끝 화면 포함)
ITEM_RANGE = (0.9, 1.7)  # 항목 하나 길이(초)
BPM_RANGE = (94, 129)  # 실제 후보: 128.6·120·112.5·105.9·100·94.7 (한 박 = 14~19프레임)
HOOK_BEATS = 4          # 첫 화면 박 수
END_BEATS = 2           # 마지막 항목에 더 주는 박 수
LENGTH_RANGE = (20.0, 35.0)   # 끝 화면 포함 (STYLE_GUIDE 6장 "목록형 자료 릴스", checks.py)
ACCENT_EVERY = 8        # 크래시(강한 박자) 넣는 항목 간격
ANIM_FRAMES = 8         # 이름 띠 등장 모션 (8프레임 = 0.27초)
EN_FONT, EN_MIN = 92, 52        # 큰 영어 이름 (Pretendard Black, 대문자)
KO_BIG, KO_BIG_MIN = 96, 60     # list.label "ko"일 때 큰 한국어 이름 (검은고딕)
TITLE_FONT = 80         # 첫 화면 제목
CROP_W = 765            # 1360 높이에서 9:16로 남길 너비 (1360 x 9/16)
HOOK_SCALE = 1.3        # 첫 화면 제목 줄이 박히기 시작하는 배율 (한 줄이 양옆 안전 영역을 넘으면 그만큼 줄인다)
HOOK_STEP = (0.15, 0.27)  # 제목 줄 사이 간격(초): 8분음표가 이 안이면 8분, 아니면 16분
FLOOD_BEATS = 4         # 끝의 이름 쏟아지기 박 수
FLOOD_REPEAT = 2        # 쏟아지는 이름을 몇 번 돌려 쏟나 (둘째부터는 작고 흐리게)
STACK_C2_RIGHT = 840    # 목록 쌓기 오른쪽 열('?' 자리)의 오른쪽 끝 x: 오른쪽 아래 버튼 줄(x 850~)보다 안쪽


def opts(post):
    """목록형 릴스 선택 기능 (모두 기본 켬): hook_anim, stack, flood(dm.page.more가 있을 때만)."""
    L = post.get("list") or {}
    more = (((post.get("dm") or {}).get("page") or {}).get("more")) or []
    return {"hook_anim": L.get("hook_anim", True) is not False,
            "stack": L.get("stack", True) is not False,
            "flood": L.get("flood", True) is not False and bool(more),
            "stack_more": len(more) if (L.get("stack", True) is not False and L.get("stack_more", True) is not False) else 0}


def flood_names(post):
    more = (((post.get("dm") or {}).get("page") or {}).get("more")) or []
    return [str(m.get("en") or m.get("name") or "").upper() for m in more if (m.get("en") or m.get("name"))]


def esc(s):
    return html.escape(str(s or ""))


def hl(text, word):
    t = esc(text)
    if word:
        t = t.replace(esc(word), f'<span class="hl">{esc(word)}</span>', 1)
    return t.replace("\n", "<br>")


def rows_of(post):
    """목록 줄: [원본(list.base, 선택)] + 항목들. 각 줄 {num, name, en, src, base}."""
    L = post.get("list") or {}
    rows = []
    if L.get("base"):
        b = L["base"]
        rows.append({"num": "00", "name": b.get("name", "원본 사진"), "en": b.get("en", "ORIGINAL"), "src": b.get("src"), "base": True})
    for i, it in enumerate(L.get("items") or [], 1):
        rows.append({"num": f"{i:02d}", "name": it.get("name", ""), "en": it.get("en", ""), "src": it.get("src"), "base": False})
    return rows


def _hook_row(post, rows):
    """첫 화면에 크게 보여 줄 줄 번호 (list.hook = 항목 번호 1부터, 기본 1)."""
    h = int((post.get("list") or {}).get("hook", 1))
    idx = [i for i, r in enumerate(rows) if not r["base"]]
    if not idx:
        return 0
    return idx[min(max(h, 1), len(idx)) - 1]


def _beats(rows, k, flood=False):
    """장면마다 박 수: 첫 화면 HOOK_BEATS, 원본 줄 k+1, 항목 k, 마지막 항목 k+END_BEATS(쏟아지기가 있으면 k), (쏟아지기 FLOOD_BEATS)."""
    out = [HOOK_BEATS]
    for r, row in enumerate(rows):
        b = k + 1 if row["base"] else k
        if r == len(rows) - 1 and not flood:   # 쏟아지기가 있으면 마지막 항목 뒤 쉼 없이 바로 (운영자 2026-11-17 "실루엣 다음에 쉬는 시간 없이")
            b += END_BEATS
        out.append(b)
    if flood:
        out.append(FLOOD_BEATS)
    return out


def timeline(post):
    """장면 순서와 길이. 항목 길이는 박자 간격의 정수배, 장면이 바뀌는 시각은 박 위(프레임 단위로 맞춤).
    checks.py도 이 함수로 길이를 검사한다.
    반환: {"states", "durs", "starts"(장면 시작 초), "beat_at"(장면 시작 박 번호), "bpm", "beat", "k",
           "main", "cta", "total", "item"}"""
    from video import CTA_SECONDS
    L = post.get("list") or {}
    rows = rows_of(post)
    flood = opts(post)["flood"]
    cta = CTA_SECONDS if (post.get("dm") or {}).get("cta") else 0.0
    if L.get("bpm"):
        cands = [(float(L["bpm"]), int(L.get("beats_per_item", 2)))]
    else:
        ks = [int(L["beats_per_item"])] if L.get("beats_per_item") else [2, 3, 4]
        # 한 박이 정확히 정수 프레임(30fps)이 되는 BPM만: 1800/f (f = 한 박 프레임 수) → 전환이 박과 0ms 차이
        cands = [(1800.0 / f, k) for k in ks for f in range(14, 20) if BPM_RANGE[0] <= 1800.0 / f <= BPM_RANGE[1]]
    best = None
    for bpm, k in cands:
        beat = 60.0 / bpm
        item = k * beat
        total = sum(_beats(rows, k, flood)) * beat + cta
        bad = 0 if ITEM_RANGE[0] <= item <= ITEM_RANGE[1] else 100
        score = bad + abs(total - TARGET_TOTAL) + (k - 2) * 0.5   # 2박을 먼저
        if best is None or score < best[0]:
            best = (score, bpm, k)
    _, bpm, k = best
    beat = 60.0 / bpm
    beats = _beats(rows, k, flood)
    states = [("hook", _hook_row(post, rows))] + [("row", r) for r in range(len(rows))]
    if flood:
        states.append(("flood", len(rows) - 1))
    # 장면 경계(박 번호 누적)를 프레임으로 반올림: 쌓이는 오차 없이 각 경계가 박 시각에서 1/60초 안
    acc, bounds = 0, [0]
    for b in beats:
        acc += b
        bounds.append(acc)
    frames = [int(round(x * beat * FPS)) for x in bounds]
    durs = [(frames[i + 1] - frames[i]) / FPS for i in range(len(beats))]
    starts = [f / FPS for f in frames[:-1]]
    main = frames[-1] / FPS
    return {"states": states, "durs": durs, "starts": starts, "beat_at": bounds[:-1], "bpm": bpm, "beat": beat, "k": k,
            "main": main, "cta": cta, "total": main + cta, "item": k * beat}


def hook_plan(post, tl):
    """첫 화면 제목 줄이 박히는 시각(프레임에 맞춘 초)과 강조어 번쩍 구간. 줄 간격은 8분음표(또는 16분)."""
    lines = str(post["title"]).split("\n")
    beat = tl["beat"]
    step = beat / 2 if HOOK_STEP[0] <= beat / 2 <= HOOK_STEP[1] else beat / 4
    starts = [round(i * step * FPS) / FPS for i in range(len(lines))]
    hw = post.get("highlight")
    hl_line = next((i for i, ln in enumerate(lines) if hw and hw in ln), -1)
    fill = (starts[hl_line], round((starts[hl_line] + beat) * FPS) / FPS) if hl_line >= 0 else (0, 0)
    return {"starts": starts, "hl_line": hl_line, "fill": fill, "step": step, "drop": tl["starts"][1]}


def flood_plan(post, tl):
    """쏟아지는 이름: [{t(장면 안 초), x, y, fs, dim, green, text}], "그리고 N개 더" 박히는 시각."""
    names = flood_names(post)
    idx = [k for k, (kind, _) in enumerate(tl["states"]) if kind == "flood"]
    if not names or not idx:
        return None
    i = idx[0]
    d = tl["durs"][i]
    rnd = random.Random(17)
    drops = []
    total = len(names) * FLOOD_REPEAT
    span = d * 0.8
    for j in range(total):
        rep_ = j % FLOOD_REPEAT
        name = names[(j // FLOOD_REPEAT) % len(names)] if rep_ == 0 else names[(j * 7 + 3) % len(names)]
        t = round(j * span / total * FPS) / FPS
        fs = rnd.randint(64, 118) if rep_ == 0 else rnd.randint(34, 60)
        drops.append({"t": t, "x": rnd.randint(-120, 860), "y": rnd.randint(140, 1800), "fs": fs,
                      "dim": rep_ > 0, "green": rnd.random() < 0.22, "text": name})
    more_t = round(d * 0.4 * FPS) / FPS
    text = (post.get("list") or {}).get("flood_text") or ""
    # 오른쪽 열 "?" 자리가 차례로 번쩍 채워지는 시각 (장면 앞 60% 안, 프레임에 맞춤)
    n_items = len([r for r in rows_of(post) if not r["base"]])
    slots = [{"num": f"{n_items + 1 + j:02d}", "t": round(j * d * 0.6 / max(1, len(names)) * FPS) / FPS}
             for j in range(len(names))]
    return {"drops": drops, "more_t": more_t, "text": text, "start": tl["starts"][i], "dur": d, "slots": slots}


# ---------- 그림: 4:5 → 세로 9:16 꽉 채우기 ----------

def subject_x(img):
    """마스코트(연두 젤리)의 가로 중심 비율(0~1). 초록 기운이 있는 화소를 그림 가운데 세로 띠(20~85%)에서 찾고,
    가장 넓게 뭉친 열 구간의 가운데를 쓴다. 못 찾으면 0.5 (가운데)."""
    import numpy as np
    small = img.convert("RGB").resize((272, 340))
    a = np.asarray(small).astype(np.int16)
    a = a[int(340 * 0.2):int(340 * 0.85)]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mask = (g > 70) & (g > r + 12) & (g > b + 18)
    col = mask.sum(axis=0).astype(float)
    if col.sum() < 60:
        return 0.5
    # 열 밀도를 부드럽게 해서 가장 큰 덩어리(슬라임)를 고른다 (왼쪽 화분 같은 작은 초록은 무시)
    k = np.ones(15) / 15
    sm = np.convolve(col, k, mode="same")
    thr = sm.max() * 0.35
    best, cur, start = (0, 0, 0), 0, 0
    for i, v in enumerate(list(sm) + [0]):
        if v >= thr and cur == 0:
            start = i
        if v >= thr:
            cur += sm[i] if i < len(sm) else 0
        elif cur:
            if cur > best[0]:
                best = (cur, start, i)
            cur = 0
    _, s0, s1 = best
    xs = np.arange(s0, s1)
    w = sm[s0:s1]
    return float((xs * w).sum() / w.sum() / len(sm)) if w.sum() else 0.5


def fill_frame(src, out, x_center=None):
    """4:5 그림에서 세로 9:16 부분을 잘라 1080x1920 Lanczos 확대. 가로 기준은 마스코트 중심(x_center, 없으면 찾음).
    반환: (중심 비율, 확대 배율)."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    cw = min(w, int(round(h * 9 / 16)))
    cx = subject_x(im) if x_center is None else float(x_center)
    left = int(round(cx * w - cw / 2))
    left = max(0, min(w - cw, left))
    crop = im.crop((left, 0, left + cw, h))
    crop.resize((W, H), Image.LANCZOS).save(out, "JPEG", quality=94)
    return cx, H / h


# ---------- 대상 위치·크기 고정 (list.align, 운영자 결정 2026-11-17 "캐릭터 위치는 동일해야지") ----------
# 같은 대상에 조명·그림체·질감만 바꾼 비교 목록은 대상이 모든 장에서 같은 자리, 같은 크기여야 바뀐 것만 보인다.
# 기준 장(원본 줄이 있으면 원본, 없으면 첫 항목)에서 마스코트 영역을 찾고, 그 영역의 윤곽(밝기 변화) 무늬를
# 다른 장에서 배율 0.85~1.15로 바꿔 가며 찾아(정규화 상호상관) 장마다 위치·크기를 잰다. 조명이 바뀌어도 윤곽은 남는다.
# 그 값으로 장마다 배율과 자르는 자리를 정해 9:16 화면에서 마스코트가 정확히 같은 자리·같은 크기에 오게 한다.
REG_W = 272                      # 정렬 계산용 축소 너비
REG_SCALES = [round(0.85 + 0.01 * i, 2) for i in range(31)]
REG_MIN_SCORE = 0.30             # 이보다 낮게 맞으면 정렬을 믿지 않고 기준 자리 그대로
ALIGN_MARGIN = 1.05              # 기준 장도 조금 더 확대해 둔다 (다른 장을 옮기거나 키울 때 가장자리 빈칸이 안 생기게)
MAX_SCALE = 1.75                 # 이보다 크게 확대하면 화질 경고
DET_W, DET_H = 136, 170


def detect_subject(img):
    """마스코트 영역(연두~초록 색 덩어리 중 가장 큰 것)의 상자 (x0, y0, x1, y1 비율, 면적비) 또는 None."""
    import numpy as np
    a = np.asarray(img.convert("HSV").resize((DET_W, DET_H))).astype(float)
    h, s, v = a[..., 0] * 360 / 255, a[..., 1] / 255, a[..., 2] / 255
    m = (h >= 45) & (h <= 160) & (s >= 0.22) & (v >= 0.12)
    lab = np.zeros(m.shape, np.int32)
    best, bl, cur = 0, 0, 0
    for y0 in range(DET_H):
        for x0 in range(DET_W):
            if not m[y0, x0] or lab[y0, x0]:
                continue
            cur += 1
            lab[y0, x0] = cur
            st, n = [(y0, x0)], 0
            while st:
                y, x = st.pop()
                n += 1
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < DET_H and 0 <= nx < DET_W and m[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        st.append((ny, nx))
            if n > best:
                best, bl = n, cur
    if best < DET_W * DET_H * 0.01:
        return None
    ys, xs = np.where(lab == bl)
    return (xs.min() / DET_W, ys.min() / DET_H, (xs.max() + 1) / DET_W, (ys.max() + 1) / DET_H, best / (DET_W * DET_H))


def _edges(img, w):
    """밝기 윤곽 지도(축소). 조명 색·밝기가 달라도 모양이 남게 장마다 밝기 분포를 고르게 편다."""
    import numpy as np
    from PIL import ImageOps
    h = int(round(img.size[1] * w / img.size[0]))
    g = ImageOps.equalize(img.convert("L").resize((w, h)))
    a = np.asarray(g).astype(float)
    gy, gx = np.gradient(a)
    e = np.sqrt(gx * gx + gy * gy)
    return e / (e.std() + 1e-6)


def _ncc_map(img, tpl):
    """tpl(작은 판)이 img 어디에 가장 잘 맞는지: 정규화 상호상관 지도 (FFT)."""
    import numpy as np
    th, tw = tpl.shape
    H_, W_ = img.shape
    t = tpl - tpl.mean()
    tn = np.sqrt((t * t).sum()) + 1e-9
    fs = (H_ + th, W_ + tw)
    F = np.fft.rfft2(img, fs)
    corr = np.fft.irfft2(F * np.conj(np.fft.rfft2(t, fs)), fs)[:H_ - th + 1, :W_ - tw + 1]
    c1 = np.cumsum(np.cumsum(np.pad(img, ((1, 0), (1, 0))), 0), 1)
    c2 = np.cumsum(np.cumsum(np.pad(img * img, ((1, 0), (1, 0))), 0), 1)

    def box(c):
        return c[th:, tw:] - c[:-th, tw:] - c[th:, :-tw] + c[:-th, :-tw]
    s1, s2 = box(c1), box(c2)
    var = np.maximum(s2 - s1 * s1 / (th * tw), 1e-9)
    return corr / (np.sqrt(var) * tn)


def _peak(m):
    """최댓값 자리 (포물선 보간으로 소수점까지)."""
    import numpy as np
    y, x = np.unravel_index(int(np.argmax(m)), m.shape)

    def sub(a, b, c):
        d = a - 2 * b + c
        return 0.0 if abs(d) < 1e-12 else 0.5 * (a - c) / d
    dy = sub(m[y - 1, x], m[y, x], m[y + 1, x]) if 0 < y < m.shape[0] - 1 else 0.0
    dx = sub(m[y, x - 1], m[y, x], m[y, x + 1]) if 0 < x < m.shape[1] - 1 else 0.0
    return float(m[y, x]), x + dx, y + dy


def register(ref_img, box, img):
    """기준 그림의 마스코트 영역(box 비율)을 img에서 찾는다. 반환 (일치 점수, 중심 x, 중심 y, 높이 — 모두 img 비율)."""
    R = _edges(ref_img, REG_W)
    rh, rw = R.shape
    pad = 0.08
    bw, bh = box[2] - box[0], box[3] - box[1]
    x0 = max(0, int((box[0] - pad * bw) * rw))
    x1 = min(rw, int((box[2] + pad * bw) * rw))
    y0 = max(0, int((box[1] - pad * bh) * rh))
    y1 = min(rh, int((box[3] + pad * bh) * rh))
    tpl = R[y0:y1, x0:x1]
    best = None
    for s in REG_SCALES:
        T = _edges(img, int(round(REG_W * s)))
        if T.shape[0] < tpl.shape[0] or T.shape[1] < tpl.shape[1]:
            continue
        sc, px, py = _peak(_ncc_map(T, tpl))
        if best is None or sc > best[0]:
            best = (sc, s, px, py, T.shape)
    sc, s, px, py, (th_, tw_) = best
    # 판 왼쪽 위 → 마스코트 중심 (기준 상자 중심이 판 안에서 놓인 자리 그대로)
    cx = (px + ((box[0] + box[2]) / 2 * rw - x0)) / tw_
    cy = (py + ((box[1] + box[3]) / 2 * rh - y0)) / th_
    return sc, cx, cy, bh / s


def plan_align(paths, ref_index=0):
    """기준 장의 마스코트 상자를 찾고, 장마다 같은 마스코트가 어디에 어떤 크기로 있는지 잰다.
    반환: (기준 (cx, cy, h), [{"use": (cx, cy, h), "score", "how"}])."""
    from PIL import Image
    imgs = [Image.open(p).convert("RGB") for p in paths]
    box = detect_subject(imgs[ref_index])
    if not box:
        return None, []
    ref = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, box[3] - box[1])
    plans = []
    for i, im in enumerate(imgs):
        if i == ref_index:
            plans.append({"use": ref, "score": 1.0, "how": "기준 장"})
            continue
        sc, cx, cy, hh = register(imgs[ref_index], box, im)
        if sc < REG_MIN_SCORE:
            plans.append({"use": ref, "score": sc, "how": f"정렬 불확실(일치 {sc:.2f}) → 기준 자리"})
        else:
            plans.append({"use": (cx, cy, hh), "score": sc, "how": f"정렬(일치 {sc:.2f})"})
    return ref, plans


def fill_aligned(src, out, use, ref, base_scale):
    """대상 중심(use)을 기준 장의 화면 자리에, 높이를 기준 높이에 맞춰 1080x1920으로 자르고 확대(Lanczos).
    base_scale: 기준 장의 확대 배율. 반환: (이 장 배율, 가장자리 빈칸 여부)."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = base_scale * ref[2] / use[2]
    tx = W / 2                                       # 기준 장: 대상 가로 중심을 화면 가운데
    ty = H / 2 + (ref[1] - 0.5) * h * base_scale     # 기준 장: 원본 세로 가운데를 화면 가운데
    left = use[0] * w - tx / s
    top = use[1] * h - ty / s
    cw, ch = W / s, H / s
    blank = left < -0.5 or top < -0.5 or left + cw > w + 0.5 or top + ch > h + 0.5
    # 그림 밖으로 나가는 자리는 검정으로 채우고(빈칸 경고), 소수점 자리까지 Lanczos로 잘라 키운다
    pad = int(max(0, -left, -top, left + cw - w, top + ch - h)) + 2
    src_img = im
    if pad > 2:
        src_img = Image.new("RGB", (w + 2 * pad, h + 2 * pad), (10, 11, 10))
        src_img.paste(im, (pad, pad))
    else:
        pad = 0
    sub = src_img.resize((W, H), Image.Resampling.LANCZOS, box=(left + pad, top + pad, left + pad + cw, top + pad + ch))
    sub.save(out, "JPEG", quality=94)
    return s, blank


def prepare_images(post, folder, work):
    """줄마다 세로 꽉 찬 그림 파일과 보고용 정보.
    list.align true(조명·그림체·고급 사진처럼 같은 대상에 한 가지만 바꾼 결과 비교 목록): 대상 위치·크기를 모든 장에서 같게.
    false(카메라 용어처럼 구도 자체가 결과인 목록): 장마다 대상 가로 중심만 맞춰 자른다 (list.items[].center로 손으로 정할 수 있다).
    반환: [{"path", "cx", "scale", "how", "blank"}]."""
    L = post.get("list") or {}
    rows = rows_of(post)
    centers = ([L["base"].get("center")] if L.get("base") else []) + [it.get("center") for it in L.get("items") or []]
    paths = [Path(folder) / r["src"] for r in rows]
    out = []
    if L.get("align"):
        from PIL import Image
        ref, plans = plan_align(paths, 0)
        if ref:
            h0 = Image.open(paths[0]).size[1]
            base_scale = H / h0 * ALIGN_MARGIN
            for i, (p, pl) in enumerate(zip(paths, plans)):
                dst = work / f"img{i:02d}.jpg"
                s, blank = fill_aligned(p, dst, pl["use"], ref, base_scale)
                out.append({"path": dst, "cx": pl["use"][0], "scale": s, "how": pl["how"], "blank": blank,
                            "use": pl["use"], "ref": ref, "score": pl["score"]})
            return out
    for i, (p, c) in enumerate(zip(paths, centers)):
        dst = work / f"img{i:02d}.jpg"
        cx, scale = fill_frame(p, dst, c)
        out.append({"path": dst, "cx": cx, "scale": scale, "how": "가로 중심만", "blank": False})
    return out


def page_html(post, imgs, cfg, tl=None):
    b = cfg["brand"]
    op = opts(post)
    tl = tl or timeline(post)
    hp = hook_plan(post, tl)
    fp = flood_plan(post, tl) if op["flood"] else None
    t_lines = str(post["title"]).split("\n")
    hw = post.get("highlight")
    used = False
    spans = []
    for ln in t_lines:
        if hw and not used and hw in ln:
            spans.append(f'<span class="ln">{hl(ln, hw)}</span>')
            used = True
        else:
            spans.append(f'<span class="ln">{esc(ln)}</span>')
    title_html = "".join(spans)
    fonts = (ROOT / "assets" / "fonts").as_uri()
    L = post["list"]
    rows = rows_of(post)
    # 제목 줄 수: 기본 2줄, 운영자가 줄바꿈으로 3줄을 정했으면 3줄까지 (checks.py와 같음)
    title_lines = min(3, max(2, len(str(post["title"]).split("\n"))))
    mode = L.get("label", "en")        # "en": 영어 이름만 크게(기본), "ko": 한국어 크게 + 영어 작게, "both": 영어 크게 + 한국어 작게
    ko_big = mode == "ko"
    cls = {"ko": "big-ko", "both": ""}.get(mode, "en-only")
    js_rows = json.dumps([{"num": r["num"], "name": r["name"], "en": (r["en"] or "").upper(), "img": p.resolve().as_uri(),
                           "base": r["base"]}
                          for r, p in zip(rows, [x["path"] for x in imgs])], ensure_ascii=False)
    js_hook = json.dumps({"on": op["hook_anim"], "starts": hp["starts"], "hl": hp["hl_line"], "fill": hp["fill"],
                          "scale": HOOK_SCALE})
    js_flood = json.dumps(fp or {}, ensure_ascii=False)
    flood_html = ""
    if fp:
        flood_html = "".join(
            f'<div class="fd{" dim" if d_["dim"] else ""}{" g" if d_["green"] else ""}" '
            f'style="left:{d_["x"]}px;top:{d_["y"]}px;font-size:{d_["fs"]}px">{esc(d_["text"])}</div>' for d_ in fp["drops"])
    from banner import banner_text, banner_height
    bt = banner_text(post)
    label_top = SAFE_TOP + (banner_height(bt) + 16 if bt else 15)   # 이름 띠: '자료' 안내 띠 바로 아래
    title_top = SAFE_TOP + 15                                       # 제목 띠: 첫 화면(안내 띠는 3초부터)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Black.otf');font-weight:900}}
@font-face{{font-family:'Pretendard';src:url('{fonts}/Pretendard-Bold.otf');font-weight:700}}
*{{box-sizing:border-box}}html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:#fff;word-break:keep-all}}
#img{{position:absolute;inset:0;width:{W}px;height:{H}px;display:block}}
.hl{{color:{b['accent']}}}
/* 위쪽 띠: 단색 반투명 검정(그라데이션 금지, STYLE_GUIDE 1-1). 글은 양옆 {SIDE}px 안. 마스코트는 화면 가운데~아래라 가리지 않는다 */
#title{{top:{title_top}px}} #label{{top:{label_top}px}}
.band{{position:absolute;left:0;right:0;background:rgba(6,7,6,.62);
  padding:30px {SIDE}px 28px;text-align:center;display:none;text-shadow:0 2px 12px rgba(0,0,0,.55)}}
.inner{{will-change:transform,opacity}}
#title .t{{font-family:'Black Han Sans';font-weight:400;font-size:{TITLE_FONT}px;line-height:1.16;letter-spacing:-.01em}}
.num{{font-family:'Black Han Sans';font-size:40px;line-height:1;color:{b['accent']};letter-spacing:.18em;margin-bottom:16px}}
.en{{font-family:'Pretendard';font-weight:900;font-size:{EN_FONT}px;line-height:1.04;white-space:nowrap}}
.ko{{font-family:'Wanted';font-weight:700;font-size:46px;line-height:1.2;margin-top:14px;color:#E8EDEA}}
.big-ko .en{{font-family:'Pretendard';font-weight:700;font-size:34px;letter-spacing:.24em;margin-top:14px;color:#E8EDEA;order:3}}
.big-ko .ko{{font-family:'Black Han Sans';font-weight:400;font-size:{KO_BIG}px;line-height:1.05;margin-top:0;color:#fff;white-space:nowrap}}
.big-ko .inner{{display:flex;flex-direction:column;align-items:center}}
.en-only .ko{{display:none}}
#title .ln{{display:block;transform-origin:50% 55%;will-change:transform}}
/* 강조어 번쩍: 글자 범위에 딱 맞는 녹색 면(모서리 각짐), 글자는 검정. 자리(너비)는 그대로 */
#title .hl.fill{{background:{b['accent']};color:#000;text-shadow:none;box-shadow:0 0 0 .06em {b['accent']}}}
/* 목록 쌓기: 이름 띠 아래 왼쪽, 작은 글씨. 지난 것 흐리게, 지금 것 녹색, 다음은 '?' */
#stack{{position:absolute;left:0;right:0;display:none;font-family:'Pretendard';font-weight:700;letter-spacing:.06em;
  text-shadow:0 2px 8px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);white-space:nowrap}}
#stack .c1{{position:absolute;left:{SIDE}px;top:0}} #stack .c2{{position:absolute;right:{W - STACK_C2_RIGHT}px;top:0}}
#stack .s.ex{{color:rgba(255,255,255,.5)}} #stack .s.ex b{{color:rgba(255,255,255,.5)}}
#stack .s.ex.on, #stack .s.ex.on b{{color:{b['accent']}}}
#stack .s.ex.fl{{background:{b['accent']};color:#000;text-shadow:none;padding:0 .2em;margin:0 -.2em}} #stack .s.ex.fl b{{color:#000}}
#stack .s{{color:rgba(255,255,255,.62)}} #stack .s b{{font-family:'Black Han Sans';font-weight:400;color:rgba(0,255,102,.55);margin-right:.5em}}
#stack .s.cur{{color:{b['accent']}}} #stack .s.cur b{{color:{b['accent']}}}
#stack .s.nx{{color:rgba(255,255,255,.85)}} #stack .s.nx b{{color:rgba(255,255,255,.7)}}
/* 쏟아지기: 단색 어둡게 + 이름이 화면 가득 (가장자리 넘쳐도 됨). 가운데 "그리고 N개 더"는 안전 영역 안 */
#dim{{position:absolute;inset:0;background:#000;opacity:0;display:none}}
#flood{{position:absolute;inset:0;display:none}}
.fd{{position:absolute;font-family:'Pretendard';font-weight:900;color:#fff;white-space:nowrap;letter-spacing:.06em;line-height:1;
  text-shadow:0 3px 14px rgba(0,0,0,.7);opacity:0}}
.fd.dim{{color:rgba(255,255,255,.3)}} .fd.g{{color:rgba(0,255,102,.6)}}
#more{{position:absolute;left:0;right:0;top:820px;display:none;text-align:center;background:rgba(6,7,6,.82);padding:34px {SIDE}px}}
#more .m{{font-family:'Black Han Sans';font-size:104px;line-height:1.05;color:#fff;display:inline-block}}
</style></head><body><div id="f">
<img id="img" src="">
<div class="band" id="title"><div class="inner"><div class="t">{title_html}</div></div></div>
<div id="dim"></div><div id="flood">{flood_html}</div>
<div id="stack"></div>
<div id="more"><div class="m">{esc(fp["text"]) if fp else ""}</div></div>
<div class="band {cls}" id="label"><div class="inner">
  <div class="num" id="ln"></div><div class="en" id="le"></div><div class="ko" id="lk"></div></div></div>
</div><script>
const ROWS = {js_rows};
const HK = {js_hook};
const FL = {js_flood};
const STACK_ON = {'true' if op['stack'] else 'false'};
const STACK_MORE = {op['stack_more']};
const SAFE_BOTTOM = {SAFE_BOTTOM};
const KO_BIG = {'true' if ko_big else 'false'};
const lab = document.getElementById('label'), ttl = document.getElementById('title');
const maxW = {W - 2 * SIDE};
const fits = {{}};   // 줄마다 큰 이름 글씨 크기 (한 줄에 들어가게)
const set = (r) => {{
  const row = ROWS[r];
  document.getElementById('ln').textContent = row.num;
  document.getElementById('le').textContent = row.en;
  document.getElementById('lk').textContent = row.name;
}};
const bigEl = () => document.getElementById(KO_BIG ? 'lk' : 'le');
window.twProblems = () => {{
  const out = [];
  lab.style.display = 'block';
  ROWS.forEach((row, r) => {{
    set(r);
    const el = bigEl(); let fs = KO_BIG ? {KO_BIG} : {EN_FONT}; const min = KO_BIG ? {KO_BIG_MIN} : {EN_MIN};
    el.style.letterSpacing = KO_BIG ? '-.01em' : '.12em'; el.style.fontSize = fs + 'px';
    while (el.scrollWidth > maxW && fs > min) {{ fs -= 2; el.style.fontSize = fs + 'px'; }}
    let wrap = false;
    if (el.scrollWidth > maxW) {{
      // 가장 작게 해도 한 줄에 안 들어가는 긴 이름은 두 줄로 (글씨는 처음 크기에서 다시 줄여 맞춘다)
      wrap = true; el.style.whiteSpace = 'normal'; el.style.maxWidth = maxW + 'px'; el.style.margin = '0 auto';
      fs = KO_BIG ? {KO_BIG} : {EN_FONT}; el.style.fontSize = fs + 'px';
      const ln = () => Math.round(el.clientHeight / parseFloat(getComputedStyle(el).lineHeight));
      while ((ln() > 2 || el.scrollWidth > maxW) && fs > min) {{ fs -= 2; el.style.fontSize = fs + 'px'; }}
      if (ln() > 2) out.push('이름이 두 줄에도 안 들어감: ' + (KO_BIG ? row.name : row.en));
      el.style.whiteSpace = ''; el.style.maxWidth = ''; el.style.margin = '';
    }}
    fits[r] = [fs, wrap];
  }});
  if (lab.getBoundingClientRect().bottom > {SAFE_BOTTOM}) out.push('이름 띠가 안전 영역 밖');
  lab.style.display = 'none';
  ttl.style.display = 'block';
  const t = ttl.querySelector('.t'); let tfs = {TITLE_FONT};
  const lines = () => Math.round(t.clientHeight / parseFloat(getComputedStyle(t).lineHeight));
  while (lines() > {title_lines} && tfs > 56) {{ tfs -= 2; t.style.fontSize = tfs + 'px'; }}
  if (lines() > {title_lines}) out.push('제목이 {title_lines}줄을 넘음');
  if (ttl.getBoundingClientRect().bottom > {SAFE_BOTTOM}) out.push('제목 띠가 안전 영역 밖');
  // 박히는 시작 배율: 줄 너비 x 배율이 양옆 안전 영역({SIDE}px) 안에 들어가게
  window.hkScale = [...t.querySelectorAll('.ln')].map(el => {{
    const rg = document.createRange(); rg.selectNodeContents(el); const w = rg.getBoundingClientRect().width;
    return Math.max(1, Math.min(HK.scale, maxW / Math.max(1, w)));
  }});
  ttl.style.display = 'none';
  // 목록 쌓기 자리: 이름 띠가 가장 높을 때의 바닥 + 22px부터 안전 영역 바닥까지, 줄 수(항목 + '?')에 맞춰 글씨 크기
  let labBottom = 0;
  lab.style.display = 'block';
  ROWS.forEach((row, r) => {{ set(r); const el = bigEl(); el.style.fontSize = fits[r][0] + 'px';
    el.style.whiteSpace = fits[r][1] ? 'normal' : ''; labBottom = Math.max(labBottom, lab.getBoundingClientRect().bottom); }});
  lab.style.display = 'none';
  const nReal = ROWS.filter(x => !x.base).length;
  const nStack = Math.max(nReal, STACK_MORE);
  window.stackTop = labBottom + 22;
  window.stackLH = Math.min(48, Math.floor((SAFE_BOTTOM - 8 - window.stackTop) / nStack));
  // 두 열이 겹치면(왼쪽 열 긴 이름) 글씨를 줄인다
  if (STACK_ON) {{
    const last = ROWS.length - 1;
    for (;;) {{
      drawStack(last, 1, 'flood', 99);
      const c1 = stackEl.querySelector('.c1'), c2 = stackEl.querySelector('.c2');
      const over = c2 && c1.getBoundingClientRect().right > c2.getBoundingClientRect().left - 24;
      if (!over || window.stackLH <= 24) break;
      window.stackLH -= 1;
    }}
    stackEl.style.display = 'none';
  }}
  if (STACK_ON && window.stackLH < 26) out.push('목록 쌓기 글씨가 너무 작음 (줄 높이 ' + window.stackLH + 'px)');
  if (FL.text) {{ const mo = document.getElementById('more'); mo.style.display = 'block';
    const b2 = mo.getBoundingClientRect(); if (b2.top < {SAFE_TOP} || b2.bottom > SAFE_BOTTOM) out.push('"더" 띠가 안전 영역 밖');
    if (mo.querySelector('.m').getBoundingClientRect().width > maxW) out.push('"더" 글이 양옆 안전 영역 밖');
    mo.style.display = 'none'; }}
  return out;
}};
const stackEl = document.getElementById('stack');
// mode 'row': 지금 줄 r까지 이름, 나머지 '?'. mode 'flood': 모든 이름 + 오른쪽 열 '?' 자리가 t에 따라 번쩍 채워짐
const drawStack = (r, e, mode, t) => {{
  if (!STACK_ON || ROWS[r].base) {{ stackEl.style.display = 'none'; return; }}
  const items = ROWS.map((x, i) => [x, i]).filter(([x]) => !x.base);
  const k = mode === 'flood' ? items.length : items.findIndex(([, i]) => i === r);
  let h = '<div class="c1">';
  items.forEach(([x, i], j) => {{
    const cur = j === k;
    if (j > k) {{ h += `<div class="s nx"><b>${{x.num}}</b>?</div>`; return; }}
    h += `<div class="s${{cur ? ' cur' : ''}}" style="${{cur ? 'opacity:' + e.toFixed(3) + ';transform:translateX(' + ((1 - e) * -24).toFixed(1) + 'px)' : ''}}"><b>${{x.num}}</b>${{x.en || x.name}}</div>`;
  }});
  h += '</div>';
  if (STACK_MORE) {{
    h += '<div class="c2">';
    for (let j = 0; j < STACK_MORE; j++) {{
      const num = String(items.length + 1 + j).padStart(2, '0');
      let c = '';
      if (mode === 'flood' && FL.slots && FL.slots[j]) {{
        const u = t - FL.slots[j].t + 1e-6;
        if (u >= 0) c = u < 0.134 ? ' fl' : ' on';
      }}
      h += `<div class="s ex${{c}}"><b>${{num}}</b>?</div>`;
    }}
    h += '</div>';
  }}
  stackEl.innerHTML = h;
  stackEl.style.top = window.stackTop + 'px';
  stackEl.style.fontSize = Math.round(window.stackLH * 0.74) + 'px';
  stackEl.style.lineHeight = window.stackLH + 'px';
  stackEl.style.display = 'block';
}};
const imgEl = document.getElementById('img');
const reset = () => {{
  imgEl.style.transform = '';
  document.getElementById('dim').style.display = 'none';
  document.getElementById('flood').style.display = 'none';
  document.getElementById('more').style.display = 'none';
  ttl.querySelectorAll('.ln').forEach(el => {{ el.style.transform = ''; el.style.opacity = ''; }});
  ttl.querySelectorAll('.hl').forEach(el => el.classList.remove('fill'));
}};
// 첫 화면 후킹 (list.hook_anim): t = 장면 안 초
window.twHook = (r, t) => {{
  reset();
  imgEl.src = ROWS[r].img;
  ttl.style.display = 'block'; lab.style.display = 'none'; stackEl.style.display = 'none';
  const inner = ttl.querySelector('.inner'); inner.style.transform = ''; inner.style.opacity = '1';
  let dx = 0, dy = 0, z = 1.04 + 0.06 * Math.exp(-t / 0.35);
  ttl.querySelectorAll('.ln').forEach((el, i) => {{
    const u = t - HK.starts[i] + 1e-6;
    if (u < 0) {{ el.style.opacity = '0'; return; }}
    const S0 = window.hkScale[i];
    let s = 1;
    if (u < 0.1) s = S0 - (S0 - 0.95) * Math.pow(u / 0.1, 2);
    else if (u < 0.234) {{ const q = (u - 0.1) / 0.134; s = 0.95 + 0.05 * (1 - Math.pow(1 - q, 2)); }}
    el.style.opacity = '1';
    el.style.transform = `scale(${{s.toFixed(4)}})`;
    if (u < 0.3) {{ const a = (i === 0 ? 22 : 14) * Math.exp(-u / 0.07);
      dx += a * Math.sin(u * 95 + i * 1.7); dy += a * Math.cos(u * 83 + i * 2.3); z += 0.015 * Math.exp(-u / 0.08); }}
  }});
  imgEl.style.transform = `translate(${{dx.toFixed(1)}}px, ${{dy.toFixed(1)}}px) scale(${{z.toFixed(4)}})`;
  ttl.querySelectorAll('.hl').forEach(el => el.classList.toggle('fill', t >= HK.fill[0] - 1e-6 && t < HK.fill[1] - 1e-6));
  return Promise.all([...document.images].filter(i => i.src).map(i => i.decode().catch(() => null)));
}};
// 끝 쏟아지기 (list.flood): t = 장면 안 초
window.twFlood = (r, t) => {{
  reset();
  imgEl.src = ROWS[r].img;
  ttl.style.display = 'none'; lab.style.display = 'none';
  drawStack(r, 1, 'flood', t);
  const dim = document.getElementById('dim'); dim.style.display = 'block'; dim.style.opacity = (0.62 * Math.min(1, t / 0.3)).toFixed(3);
  const fl = document.getElementById('flood'); fl.style.display = 'block';
  fl.querySelectorAll('.fd').forEach((el, j) => {{
    const v = (t - FL.drops[j].t + 1e-6) / 0.17;
    if (v < 0) {{ el.style.opacity = '0'; return; }}
    const e = 1 - Math.pow(1 - Math.min(1, v), 3);
    el.style.opacity = String(Math.min(0.55, v * 1.5));
    el.style.transform = `translateY(${{((1 - e) * -220).toFixed(1)}}px)`;
  }});
  const mo = document.getElementById('more');
  const u = t - FL.more_t + 1e-6;
  if (FL.text && u >= 0) {{
    mo.style.display = 'block';
    let s = 1; if (u < 0.1) s = 1.3 - 0.35 * Math.pow(u / 0.1, 2); else if (u < 0.234) {{ const q = (u - 0.1) / 0.134; s = 0.95 + 0.05 * (1 - Math.pow(1 - q, 2)); }}
    mo.querySelector('.m').style.transform = `scale(${{s.toFixed(4)}})`;
  }}
  return Promise.all([...document.images].filter(i => i.src).map(i => i.decode().catch(() => null)));
}};
// p: 등장 진행(0~1). 0.27초 동안 아래에서 36px 올라오며 나타나고, 큰 영어 이름은 자간이 .3em → .12em로 좁혀진다
window.twState = (kind, r, p) => {{
  const e = 1 - Math.pow(1 - p, 3);
  reset();
  document.getElementById('img').src = ROWS[r].img;
  ttl.style.display = kind === 'hook' ? 'block' : 'none';
  lab.style.display = kind === 'row' ? 'block' : 'none';
  const band = kind === 'hook' ? ttl : lab;
  const inner = band.querySelector('.inner');
  inner.style.transform = `translateY(${{(1 - e) * 36}}px)`;
  inner.style.opacity = String(e);
  if (kind === 'row') {{
    set(r);
    const el = bigEl(); el.style.fontSize = fits[r][0] + 'px';
    el.style.whiteSpace = fits[r][1] ? 'normal' : ''; el.style.maxWidth = fits[r][1] ? maxW + 'px' : ''; el.style.margin = fits[r][1] ? '0 auto' : '';
    if (!KO_BIG) el.style.letterSpacing = (0.12 + 0.18 * (1 - e)).toFixed(3) + 'em';
    drawStack(r, e, 'row', 0);
  }} else {{
    stackEl.style.display = 'none';
  }}
  return Promise.all([...document.images].filter(i => i.src).map(i => i.decode().catch(() => null)));
}};
</script></body></html>"""


async def shoot_states(post, imgs, cfg, work):
    """장면마다 등장 모션 프레임(ANIM_FRAMES장, 1/30초씩) + 정지 화면 한 장. [(png, 초), ...], 문제 목록, timeline."""
    from playwright.async_api import async_playwright
    tl = timeline(post)
    page_file = work / "list.html"
    page_file.write_text(page_html(post, imgs, cfg, tl), encoding="utf-8")
    op = opts(post)
    shots = []
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(page_file.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(200)
        problems = await pg.evaluate("twProblems()")
        el = await pg.query_selector("#f")
        for i, ((kind, r), d) in enumerate(zip(tl["states"], tl["durs"])):
            if (kind == "hook" and op["hook_anim"]) or kind == "flood":
                # 프레임마다 그린다 (박히는 제목·흔들림·쏟아지기)
                fn = "twHook" if kind == "hook" else "twFlood"
                for k in range(int(round(d * FPS))):
                    await pg.evaluate(f"{fn}({r}, {k / FPS:.5f})")
                    png = work / f"s{i:03d}_{k:03d}.png"
                    await el.screenshot(path=str(png))
                    shots.append((png, 1 / FPS))
                continue
            n_anim = min(ANIM_FRAMES, int(round(d * FPS)) - 1)
            for k in range(n_anim):
                await pg.evaluate(f"twState('{kind}', {r}, {(k + 1) / (n_anim + 1):.4f})")
                png = work / f"s{i:03d}_{k}.png"
                await el.screenshot(path=str(png))
                shots.append((png, 1 / FPS))
            await pg.evaluate(f"twState('{kind}', {r}, 1)")
            png = work / f"s{i:03d}.png"
            await el.screenshot(path=str(png))
            shots.append((png, d - n_anim / FPS))
        await browser.close()
    return shots, problems, tl


def accents(post, tl):
    """크래시(강한 박자) 자리: 목록 시작, 그 뒤 ACCENT_EVERY 항목마다."""
    out = []
    for (kind, r), t in zip(tl["states"], tl["starts"]):
        if (kind == "row" and r % ACCENT_EVERY == 0) or kind == "flood":
            out.append(t)
    return out


def beat_check(tl):
    """장면 전환 시각과 박 시각의 차이(초). 최대값을 보고용으로."""
    return max(abs(t - b * tl["beat"]) for t, b in zip(tl["starts"], tl["beat_at"]))


PH_DIR = "_ph"


def with_placeholders(post, folder):
    """그림이 아직 없는 줄(AI 그림은 render.yml이 만든다)을 회색 자리표시(번호만)로 바꾼 사본.
    자리표시는 게시물 폴더의 _ph/에 만들고 렌더링 뒤 지운다 (img/ 자리에는 넣지 않는다: 넣으면 Actions가 그림을 안 만든다).
    반환: (사본 post, 자리표시 수)."""
    import copy
    from PIL import Image, ImageDraw, ImageFont
    folder = Path(folder)
    p = copy.deepcopy(post)
    L = p.get("list") or {}
    cells = ([("00", L["base"])] if L.get("base") else []) + [(f"{i:02d}", it) for i, it in enumerate(L.get("items") or [], 1)]
    ph = folder / PH_DIR
    made = {}
    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Pretendard-Black.otf"), 380)
    for num, it in cells:
        src = it.get("src")
        if src and (folder / src).exists():
            continue
        ph.mkdir(exist_ok=True)
        out = ph / f"{num}.jpg"
        im = Image.new("RGB", (1080, 1350), (58, 63, 60))
        dr = ImageDraw.Draw(im)
        bx = dr.textbbox((0, 0), num, font=font)
        dr.text(((1080 - bx[2] - bx[0]) / 2, (1350 - bx[3] - bx[1]) / 2), num, font=font, fill=(150, 158, 153))
        im.save(out, "JPEG", quality=85)
        made[src] = str(out.resolve())
        it["src"] = made[src]
    t = (p.get("thumb") or {}).get("image") or {}
    if t.get("src") in made:
        t["src"] = made[t["src"]]
    return p, len(made)


def clear_placeholders(folder):
    shutil.rmtree(Path(folder) / PH_DIR, ignore_errors=True)



# ---------- 소리: 음악 + 목소리(선택) ----------
SR = 44100
VOICE_DIR = "voice"
VOICE_OVER_MUSIC_DB = 17.0   # 말하는 동안 말이 음악보다 이만큼 크게 (15~20dB)
MUSIC_GAP_DB = 6.0           # 말이 없을 때 음악은 말보다 이만큼만 작게 (비트가 살게)


def _read_audio(path):
    """아무 소리 파일 → 44.1kHz 스테레오 float32 (ffmpeg)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768.0


def _write_wav(path, x):
    import wave
    import numpy as np
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _db(x):
    import numpy as np
    r = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    return 20 * np.log10(max(r, 1e-9))


def voice_files(post, folder, tl):
    """[(시작 초, 파일)]: 항목 장면마다 voice/<번호>.wav가 있으면 그 장면이 시작하는 박에."""
    rows = rows_of(post)
    out = []
    for (kind, r), t in zip(tl["states"], tl["starts"]):
        if kind != "row":
            continue
        f = Path(folder) / VOICE_DIR / f"{rows[r]['num']}.wav"
        if f.exists():
            out.append((t, f))
    return out


SFX_OVER_MUSIC_DB = 3.0      # 효과음(소리 나는 곳 RMS)을 말 없을 때 음악보다 이만큼 크게


def _add_sfx(mix, sfx, ref_db):
    """효과음을 덕킹 뒤에 더한다 (말에 묻혀 줄지 않게). 크기: 소리 나는 곳 RMS = ref_db + SFX_OVER_MUSIC_DB."""
    import numpy as np
    if sfx is None:
        return mix, None
    s = np.zeros_like(mix)
    k = min(len(s), len(sfx))
    s[:k] = sfx[:k]
    act = np.abs(s).max(axis=1) > 0.02
    g = 10 ** ((ref_db + SFX_OVER_MUSIC_DB - _db(s[act])) / 20) if act.any() else 0.0
    return mix + s * g, ref_db + SFX_OVER_MUSIC_DB


def mix_audio(music_wav, voices, total, out_wav, sfx=None):
    """음악 + 목소리 (+ 효과음). 말하는 동안 음악을 줄여(덕킹) 말이 음악보다 VOICE_OVER_MUSIC_DB 크게,
    말이 없을 때는 음악을 말보다 MUSIC_GAP_DB 작게 둔다. 효과음은 덕킹 뒤에 더한다. 반환: 측정값 dict (RMS 기준 dB)."""
    import numpy as np
    n = int(round(total * SR))
    m = _read_audio(music_wav)[:n]
    if len(m) < n:
        m = np.pad(m, ((0, n - len(m)), (0, 0)))
    if not voices:
        out, sdb = _add_sfx(m, sfx, _db(m))
        _write_wav(out_wav, out)
        return {"voices": 0, "sfx_db": sdb}
    v = np.zeros_like(m)
    for t, f in voices:
        x = _read_audio(f)
        i = int(round(t * SR))
        k = min(len(x), n - i)
        if k > 0:
            v[i:i + k] += x[:k]
    # 말소리 있는 곳 (10ms 창 RMS) → 부드러운 덕킹 곡선 (올라갈 때 20ms, 내려갈 때 250ms)
    mono = np.abs(v).mean(axis=1)
    win = int(0.01 * SR)
    pad = (-len(mono)) % win
    blocks = np.pad(mono, (0, pad)).reshape(-1, win).max(axis=1)
    on = (blocks > 0.02).astype(float)
    env = np.zeros_like(on)
    a_up, a_dn = 1 - np.exp(-1 / 2), 1 - np.exp(-1 / 25)
    e = 0.0
    for i, x in enumerate(on):
        e += (x - e) * (a_up if x > e else a_dn)
        env[i] = e
    env = np.repeat(env, win)[:n]
    speech = env > 0.9
    lv = _db(v[speech])
    lm = _db(m)
    base_db = (lv - MUSIC_GAP_DB) - lm                       # 말 없을 때 음악 크기
    duck_db = -(VOICE_OVER_MUSIC_DB - MUSIC_GAP_DB)          # 말하는 동안 더 줄이는 양
    gain = 10 ** ((base_db + duck_db * env) / 20)
    mm = m * gain[:, None]
    mix, sdb = _add_sfx(v + mm, sfx, _db(mm[~speech]))
    _write_wav(out_wav, mix)
    return {"voices": len(voices), "voice_db": lv, "music_in_speech_db": _db(mm[speech]),
            "music_between_db": _db(mm[~speech]), "diff_in_speech_db": lv - _db(mm[speech]), "sfx_db": sdb}


def make_list_reel(post, folder, cfg):
    """reel.mp4 (본편 + 안내 띠 + 끝 화면, -14 LUFS), frames/*.jpg·cover.jpg(썸네일이 덮어씀). 전체 길이(초) 반환."""
    folder = Path(folder)
    missing = [r["src"] for r in rows_of(post) if not r.get("src") or not (folder / r["src"]).exists()]
    if missing:
        raise FileNotFoundError("목록 이미지 없음: " + ", ".join(map(str, missing[:5]))
                                + " → list.items[].prompt·mascot 확인 (그림은 render.yml이 만든다)")
    work = folder / "_list"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    imgs = prepare_images(post, folder, work)
    for im, row in zip(imgs, rows_of(post)):
        warn = (" ← 확대가 커서 화질 확인" if im["scale"] > MAX_SCALE else "") + (" ← 가장자리 빈칸" if im["blank"] else "")
        print(f"  그림 {row['num']}: {im['how']}, 중심 {im['cx']:.3f}, 확대 {im['scale']:.2f}배{warn}")
    shots, problems, tl = asyncio.run(shoot_states(post, imgs, cfg, work))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    # 1) 장면 이어 붙이기 (등장 모션 프레임 + 정지 화면)
    lst = work / "list.txt"
    lines = []
    for png, d in shots:
        lines += [f"file '{png.name}'", f"duration {d:.5f}"]
    lines.append(f"file '{shots[-1][0].name}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps={FPS},scale={W}:{H},setsar=1,format=yuv420p", "-t", f"{tl['main']:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(silent)],
                   check=True, cwd=str(work))
    # 2) 음악 (소리 없는 릴스 금지, STYLE_GUIDE 6장): post.music.src → assets/music → 코드로 만든 후킹 비트
    pm = post.get("music") or {}
    files = sorted((ROOT / "assets" / "music").glob("*.mp3")) + sorted((ROOT / "assets" / "music").glob("*.m4a"))
    dur = tl["main"]
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    elif files and not pm.get("generate"):
        music = random.choice(files)
    else:
        from music_gen import make_hook_music
        music = work / "music.wav"
        acc = accents(post, tl)
        make_hook_music(music, tl["bpm"], dur, acc, seed=int(pm.get("seed", 7)),
                        drop_at=tl["starts"][1] if opts(post)["hook_anim"] else None)
        print(f"배경음악: 후킹 비트 BPM {tl['bpm']:g} (박 {tl['beat']:.4f}초, 항목 {tl['k']}박 = {tl['item']:.3f}초), "
              f"크래시 {len(acc)}곳, 장면 전환과 박의 최대 차이 {beat_check(tl) * 1000:.1f}ms")
    # 3) 목소리 (선택, voice/<번호>.wav, agent/tts.py로 이 컴퓨터에서 미리 만든다)
    sfx, sfx_info = make_sfx(post, tl, dur)
    mixed = work / "mix.wav"
    st = mix_audio(music, voice_files(post, folder, tl), dur, mixed, sfx)
    if sfx_info:
        on = sfx_info["onsets"]
        print("효과음: " + ", ".join(f"{k} {', '.join(f'{x:.3f}' for x in v)}" for k, v in on.items() if isinstance(v, list) and v)
              + f", 틱 {on['ticks']}개 (소리 나는 곳 {st.get('sfx_db') or 0:.1f} dB RMS)")
    if st.get("voices"):
        print(f"목소리 {st['voices']}개: 말하는 동안 말 {st['voice_db']:.1f} dB / 음악 {st['music_in_speech_db']:.1f} dB "
              f"(차이 {st['diff_in_speech_db']:.1f} dB), 말 없을 때 음악 {st['music_between_db']:.1f} dB (RMS)")
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    # 4) 앞쪽 '자료' 안내 띠 (dm.banner): 안전 영역 맨 위, 3초부터 본편 끝까지
    from banner import banner_text, make_banner_png, apply_banner, banner_height
    bt = banner_text(post)
    if bt:
        png = make_banner_png(bt, cfg, W - 2 * SIDE, work / "banner.png")
        apply_banner(out, png, SIDE, SAFE_TOP, dur)
        print(f"  안내 띠 자리: 안전 영역 맨 위 (세로 {SAFE_TOP}~{SAFE_TOP + banner_height(bt)}px)")
    # 5) 끝 화면 (dm.cta 2.5초, 음악은 그 앞에서 페이드아웃)
    from video import dm_cta, append_cta_card
    cta = dm_cta(post)
    if cta:
        dur = append_cta_card(out, cta, cfg, work, dur)
    from loudness import normalize
    normalize(out)
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    for k, t in enumerate(preview_times(post, tl, dur), 1):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.copy(frames / "01.jpg", folder / "cover.jpg")
    shutil.rmtree(work)
    print(f"목록 {len(rows_of(post))}줄, 항목당 {tl['item']:.2f}초, 본편 {tl['main']:.1f}초 + 끝 화면 {tl['cta']:.1f}초")
    return dur


def make_sfx(post, tl, total):
    """효과음 트랙 (hook_anim·flood가 켜졌을 때). 시각은 모두 화면이 바뀌는 프레임 시각. (배열|None, 정보|None)"""
    op = opts(post)
    if not (op["hook_anim"] or op["flood"]):
        return None, None
    from music_gen import make_hook_sfx
    kw = {}
    if op["hook_anim"]:
        hp = hook_plan(post, tl)
        kw.update(impacts=[hp["starts"][0]], hits=hp["starts"][1:], whooshes=hp["starts"][1:],
                  riser_to=hp["drop"], riser_len=max(0.4, min(1.0, hp["drop"] - hp["starts"][-1] - 0.25)), drop=hp["drop"])
    if op["flood"]:
        fp = flood_plan(post, tl)
        kw.update(flood=(fp["start"], fp["start"] + fp["dur"]),
                  ticks=[fp["start"] + sl["t"] for sl in fp["slots"]] if op["stack_more"]
                  else [fp["start"] + d["t"] for d in fp["drops"] if not d["dim"]])
        if fp["text"]:
            kw["hits"] = list(kw.get("hits", [])) + [fp["start"] + fp["more_t"]]
    return make_hook_sfx(total, **kw)


def preview_times(post, tl, total):
    """미리보기: 첫 화면 1초, 안내 띠가 들어온 뒤 항목, 중간 항목 몇 개, 마지막 항목, 끝 화면."""
    rows = [(r, t + d * 0.6) for (kind, r), t, d in zip(tl["states"], tl["starts"], tl["durs"]) if kind == "row"]
    ts = [1.0]
    after = [x for x in rows if x[1] > 3.4]
    picks = [after[0]] + [rows[len(rows) * k // 4] for k in (1, 2, 3)] + [rows[-1]]
    ts += [t for _, t in picks]
    ts += [t + d * 0.7 for (kind, _), t, d in zip(tl["states"], tl["starts"], tl["durs"]) if kind == "flood"]
    if tl["cta"]:
        ts.append(total - 1.0)
    return ts
