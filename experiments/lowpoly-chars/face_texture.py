"""각진 젠슨 황 얼굴에 원본 사진을 살짝 입힐 질감 (운영자 2026-11-18 "원래 사진 원본을 저 모델에 맞게 살짝").
사진 안경을 지우고(인페인팅) → 캐릭터 피부색 위에 사진을 AMOUNT만큼 섞음(얼굴 타원 안, 가장자리 부드럽게).
위치 맞춤은 build_humans.py photo_uv (사진 눈 (580,600)·(785,610) = 캐릭터 눈, 사진 입선 845 = 캐릭터 입).
→ ref/jensen_face_tex.png
실행: py -3.12 experiments/lowpoly-chars/face_texture.py [강도=0.55]
"""
import sys
from pathlib import Path
import numpy as np
import cv2

HERE = Path(__file__).resolve().parent
AMOUNT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.55
SKIN = np.array([106, 143, 201], np.float32)          # #C98F6A (BGR)
img = cv2.imread(str(HERE / "ref" / "jensen_photo_bust.jpg"))
H, W = img.shape[:2]

# 안경 지우기 (blend_photo.py와 같은 테 위치)
m = np.zeros((H, W), np.uint8)
for mir in (lambda x: x, lambda x: 1380 - x):
    cv2.polylines(m, [np.int32([(mir(x), y) for x, y in [(405, 578), (438, 558), (550, 552), (660, 556), (676, 568)]])], False, 255, 40)
    cv2.polylines(m, [np.int32([(mir(x), y) for x, y in [(410, 574), (420, 620), (448, 662), (500, 686), (560, 692), (620, 680), (656, 648), (670, 612), (676, 568)]])], False, 255, 26)
cv2.polylines(m, [np.int32([(676, 568), (690, 556), (704, 568)])], False, 255, 36)
cv2.line(m, (330, 572), (405, 578), 255, 30)
cv2.line(m, (975, 578), (1050, 572), 255, 30)
for ex, ey in ((580, 600), (785, 610)):
    cv2.ellipse(m, (ex, ey), (44, 20), 0, 0, 360, 0, -1)   # 눈은 남김
clean = cv2.inpaint(img, m, 9, cv2.INPAINT_TELEA).astype(np.float32)

# 사진 전체 밝기를 캐릭터 피부색 톤에 맞춤 (색상은 사진, 밝기 평균만 맞춤)
face = clean[700:900, 520:840].reshape(-1, 3).mean(axis=0)
clean = clean * (SKIN / face) ** 0.5

a = np.zeros((H, W), np.float32)
cv2.ellipse(a, (682, 700), (290, 360), 0, 0, 360, 1.0, -1)
a = cv2.GaussianBlur(a, (0, 0), 40)[..., None] * AMOUNT
out = SKIN * (1 - a) + clean * a
cv2.imwrite(str(HERE / "ref" / "jensen_face_tex.png"), np.clip(out, 0, 255).astype(np.uint8))
print("ok", AMOUNT)
