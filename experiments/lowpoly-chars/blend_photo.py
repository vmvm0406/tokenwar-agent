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
SRC_NAME = sys.argv[2] if len(sys.argv) > 2 else "jensen_photo_bust.jpg"
OUT_NAME = sys.argv[3] if len(sys.argv) > 3 else "jensen_mixed.png"
photo = Image.open(HERE / "ref" / SRC_NAME).convert("RGB").resize(painted.size)

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
# 볼 색 고르게 (운영자 2026-11-18 "볼 색깔들 피부색"): 잔결은 남기고 큰 명암(그늘·얼룩)만 얼굴 가운데 피부색으로.
# 가운데(눈·코·입)는 그대로, 가장자리로 갈수록 세게.
f = clean.astype(np.float32)
low = cv2.GaussianBlur(f, (0, 0), 40)
skin = np.median(low[700:900, 560:800].reshape(-1, 3), axis=0)
yy, xx = np.mgrid[0:f.shape[0], 0:f.shape[1]]
r = np.sqrt(((xx - 682) / 210.0) ** 2 + ((yy - 740) / 250.0) ** 2)
wmap = (np.clip((r - 0.4) / 0.45, 0, 1) ** 1.1 * 0.95)[..., None]
out_f = f + wmap * (skin - low)
# 그늘만 밝히기 (운영자 2026-11-18 "그늘진 부분 다듬기"): 얼굴 안에서 피부색보다 어두운 큰 명암을 60% 끌어올림
face = (np.clip((1.25 - r) / 0.25, 0, 1))[..., None]
low2 = cv2.GaussianBlur(out_f, (0, 0), 25)
dark = np.clip(skin - low2, 0, None)
out_f = out_f + face * 0.4 * dark
out_f = out_f * (1 - face * 0.1)          # 피부를 조금 어둡게 (운영자 2026-11-18 "밝기 조금 낮춰, 젠슨 황처럼")
clean = np.clip(out_f, 0, 255).astype(np.uint8)
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
# 앞머리 → 이마: 머리 회색이 이마 위쪽으로 부드럽게 옅어지게 (운영자 2026-11-18 "여기 자연스럽게 이어줘")
grad = Image.new("L", painted.size, 0)
gp = grad.load()
for y in range(300, 440):
    a = int(200 * max(0.0, min(1.0, (430 - y) / 110)) ** 1.5)
    for x in range(400, 965):
        gp[x, y] = a
gd = ImageDraw.Draw(grad)        # 관자놀이 모서리도 흰머리로 부드럽게 (이마 양옆 주황 조각 없앰)
for cx in (440, 925):
    gd.ellipse([cx - 70, 380, cx + 70, 600], fill=210)
grad = grad.filter(ImageFilter.GaussianBlur(25))
out = Image.composite(Image.new("RGB", painted.size, (172, 172, 168)), out, grad)
out.save(HERE / "ref" / OUT_NAME)
out.crop((330, 300, 1060, 1060)).save(HERE / "out" / "mixed_face_preview.png")
print(HERE / "ref" / OUT_NAME)
