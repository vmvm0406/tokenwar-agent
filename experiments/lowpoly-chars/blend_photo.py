"""그린 얼굴 + 원본 사진 느낌 섞기 (운영자 2026-11-18 "원본 느낌 살리자" → 얼굴 그림에 사진 70%).
사진 속 안경 테는 주변 피부로 메워 지움(OpenCV 인페인팅) — 그림 피부색으로 덮으면 안경 모양 띠가 흔적으로 남았음.
얼굴·귀·목은 사진, 머리카락·재킷·견본 영역은 그림. 경계는 크게 번지게.

실행: py -3.12 experiments/lowpoly-chars/blend_photo.py [사진 비율=0.7] → ref/jensen_mixed.png (+ out/photo_noglasses.png 확인용)
"""
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
amt = float(sys.argv[1]) if len(sys.argv) > 1 else 0.7
painted = Image.open(HERE / "ref" / "jensen_painted.png").convert("RGB")
photo = Image.open(HERE / "ref" / "jensen_photo_bust.jpg").convert("RGB").resize(painted.size)

# 1) 사진에서 안경 테 지우기: 손으로 그린 테 위치(넉넉히) ∩ (어둡거나 반짝이는 픽셀) + 테 자체 띠 → 인페인팅
arr = np.array(photo)
hand = Image.new("L", painted.size, 0)
hd = ImageDraw.Draw(hand)
for mir in (lambda x: x, lambda x: 1380 - x):
    hd.line([(mir(x), y) for x, y in [(405, 578), (438, 558), (550, 552), (660, 556), (676, 568)]], fill=255, width=44)
    hd.line([(mir(x), y) for x, y in [(410, 574), (420, 620), (448, 662), (500, 686), (560, 692), (620, 680), (656, 648), (670, 612), (676, 568)]], fill=255, width=30)
hd.line([(676, 568), (690, 556), (704, 568)], fill=255, width=40)
hd.line([(660, 560), (668, 640)], fill=255, width=26)          # 코받침
hd.line([(720, 560), (712, 640)], fill=255, width=26)
hand = np.array(hand) > 0
gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
local = cv2.GaussianBlur(gray, (0, 0), 9)
odd = (np.abs(gray - local) > 14)                               # 주변과 확 다른(테·반사) 픽셀
eyes = np.zeros_like(hand)
for ex, ey in ((580, 600), (785, 610)):
    cv2.ellipse(eyes.view(np.uint8), (ex, ey), (46, 22), 0, 0, 360, 1, -1)  # 눈은 지우지 않음
rm = (hand & (odd | (gray < 70))) & ~eyes.astype(bool)
rm = cv2.dilate(rm.astype(np.uint8) * 255, np.ones((7, 7), np.uint8))
core = np.zeros_like(rm)                                         # 윗테 중심선은 무조건 지움
hand_top = Image.new("L", painted.size, 0)
ht = ImageDraw.Draw(hand_top)
for mir in (lambda x: x, lambda x: 1380 - x):
    ht.line([(mir(x), y) for x, y in [(410, 576), (438, 558), (550, 552), (660, 556), (676, 568)]], fill=255, width=20)
ht.ellipse([880, 560, 945, 610], fill=255)                        # 오른쪽 경첩 조각
ht.ellipse([435, 560, 500, 610], fill=255)
rm = np.maximum(rm, np.array(hand_top))
clean = cv2.inpaint(arr, rm, 9, cv2.INPAINT_TELEA)
photo = Image.fromarray(clean).filter(ImageFilter.MedianFilter(5))   # 잡티만 살짝 정리
photo.crop((300, 480, 1080, 760)).save(HERE / "out" / "photo_noglasses.png")

# 2) 얼굴·귀·목(턱 옆 포함)만 사진
mask = Image.new("L", painted.size, 0)
d = ImageDraw.Draw(mask)
d.ellipse([400, 380, 965, 1010], fill=int(255 * amt))
d.ellipse([335, 575, 425, 780], fill=int(255 * amt))             # 귀
d.ellipse([940, 575, 1040, 780], fill=int(255 * amt))
d.polygon([(470, 900), (895, 900), (840, 1150), (520, 1150)], fill=int(255 * amt))   # 턱 옆·목
mask = mask.filter(ImageFilter.GaussianBlur(35))
out = Image.composite(photo, painted, mask)
out.save(HERE / "ref" / "jensen_mixed.png")
out.crop((330, 300, 1060, 1060)).save(HERE / "out" / "mixed_face_preview.png")
print(HERE / "ref" / "jensen_mixed.png")
