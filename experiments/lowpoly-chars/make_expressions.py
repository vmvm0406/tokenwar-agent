"""젠슨 황 표정 = 다른 사진으로 질감 교체 (운영자 2026-11-18 "다른 사진으로 교체 방식으로 표정, 입 열고 닫고").
같은 행사 공개 사진(Wikimedia Commons, Anders Eidesvik, CC BY 4.0)에서 두 눈동자 위치를 재서
기본 사진(011, ref/jensen_photo_bust.jpg)의 눈 위치 (580,600)·(785,610)에 맞게 돌리고·키워 같은 틀로 맞춤.
→ ref/jensen_photo_<표정>.jpg. 이후 blend_photo.py(사진 70% + 안경 지우기) → jensen_n64.py --photo 로 각 표정 질감.

실행: py -3.12 experiments/lowpoly-chars/make_expressions.py <원본 사진 폴더>
"""
import sys
from pathlib import Path
import numpy as np
import cv2

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1])
BASE_EYES = np.float32([[580, 600], [785, 610]])
W, H = 1459, 1740
# 표정: (파일, 왼눈, 오른눈) — 원본 해상도(1920px 폭) 기준, 격자로 잼
EXPR = {
    "closed": ("Jensen huang stanford 2026-04-30 007.jpg", (814, 1036), (979, 1044)),   # 입 다문 평온
    # 008(입 벌림)·035(웃음)는 기괴해 보여 뺌 (운영자 2026-11-18)
}


def similarity(src, dst):
    """두 점 → 회전·확대·이동 (찌그러짐 없음)."""
    (a, b), (c, d) = src, dst
    vs, vd = b - a, d - c
    s = np.linalg.norm(vd) / np.linalg.norm(vs)
    ang = np.arctan2(vd[1], vd[0]) - np.arctan2(vs[1], vs[0])
    R = s * np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    t = c - R @ a
    return np.hstack([R, t[:, None]]).astype(np.float32)


for name, (fn, le, re) in EXPR.items():
    img = cv2.imread(str(SRC / fn))
    if img is None:
        print("없음", fn)
        continue
    M = similarity(np.float32([le, re]), BASE_EYES)
    out = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    cv2.imwrite(str(HERE / "ref" / f"jensen_photo_{name}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 93])
    print(name, "ok")
