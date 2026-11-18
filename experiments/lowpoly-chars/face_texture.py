"""각진 젠슨 황 얼굴 질감 — 사진 합성 없이 큰 특징만 옅게 그림 (운영자 2026-11-18 "얼굴 합성은 지우고, 주름 위치 같은 큰 특징만 살짝").
그림 좌표는 사진 틀(1459x1740, 눈 (580,600)·(785,610), 입선 845)과 같게 그려서 build_humans.py photo_uv로 그대로 붙음.
→ ref/jensen_face_tex.png
실행: py -3.12 experiments/lowpoly-chars/face_texture.py [진하기=1.0]
"""
import sys
from pathlib import Path
import numpy as np
import cv2

HERE = Path(__file__).resolve().parent
K = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
W, H = 1459, 1740
SKIN = np.array([106, 143, 201], np.float32)          # #C98F6A (BGR)
DARK = SKIN * 0.72
img = np.ones((H, W, 3), np.float32) * SKIN

lines = np.zeros((H, W), np.float32)


def stroke(pts, w, a):
    cv2.polylines(lines, [np.int32(pts)], False, a, w, cv2.LINE_AA)


for k, y in enumerate((415, 450, 485)):                                     # 이마 가로 주름 3줄
    stroke([(575 - k * 8, y + 8), (630, y), (682, y - 3), (735, y), (790 + k * 8, y + 8)], 6, 0.5)
for sx in (-1, 1):
    m = lambda x: 682 + sx * (x - 682) if sx > 0 else 682 - (x - 682)
    stroke([(m(612), 760), (m(592), 805), (m(584), 860)], 9, 0.55)            # 팔자 주름
    stroke([(m(540), 650), (m(580), 660), (m(620), 650)], 5, 0.35)            # 눈 밑 주름
    stroke([(m(510), 610), (m(495), 600)], 4, 0.35)                           # 눈가 잔주름
    stroke([(m(495), 625), (m(482), 625)], 4, 0.3)
    stroke([(m(600), 900), (m(612), 950)], 6, 0.3)                            # 입가 주름
lines = cv2.GaussianBlur(lines, (0, 0), 3.5)

shade = np.zeros((H, W), np.float32)                                        # 볼 아래·턱 옆 그늘 (넓고 옅게)
for cx in (500, 865):
    cv2.ellipse(shade, (cx, 900), (70, 120), 0, 0, 360, 0.35, -1)
cv2.ellipse(shade, (682, 1000), (150, 40), 0, 0, 360, 0.3, -1)
shade = cv2.GaussianBlur(shade, (0, 0), 35)

a = np.clip((lines + shade) * K, 0, 0.8)[..., None]
out = img * (1 - a) + DARK * a
cv2.imwrite(str(HERE / "ref" / "jensen_face_tex.png"), np.clip(out, 0, 255).astype(np.uint8))
print("ok", K)
