"""그린 얼굴 + 원본 사진 느낌 섞기 (운영자 2026-11-18 "원본 느낌을 좀 살리자" → 얼굴 그림에 사진 느낌).
얼굴 부분(이마~턱·목)만 손그림(ref/jensen_painted.png)과 잡티를 살짝 정리한 사진(ref/jensen_photo_bust.jpg)을 섞음.
머리카락·재킷·견본 영역은 그림 그대로. 경계는 크게 번지게.

실행: py -3.12 experiments/lowpoly-chars/blend_photo.py [사진 비율=0.5] → ref/jensen_mixed.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

HERE = Path(__file__).resolve().parent
amt = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
painted = Image.open(HERE / "ref" / "jensen_painted.png").convert("RGB")
photo = Image.open(HERE / "ref" / "jensen_photo_bust.jpg").convert("RGB").resize(painted.size)
photo = photo.filter(ImageFilter.MedianFilter(5))                 # 잡티만 살짝 정리 (주름·눈매는 남김)

mask = Image.new("L", painted.size, 0)
d = ImageDraw.Draw(mask)
d.ellipse([400, 380, 965, 1010], fill=int(255 * amt))             # 얼굴 (이마선 아래 ~ 턱)
d.ellipse([340, 580, 420, 770], fill=int(255 * amt * 0.7))        # 귀
d.ellipse([945, 580, 1035, 770], fill=int(255 * amt * 0.7))
d.rectangle([560, 960, 800, 1120], fill=int(255 * amt))           # 목
mask = mask.filter(ImageFilter.GaussianBlur(35))
# 사진 속 안경 테 자리는 사진을 빼고 그림만 (입체 안경과 이중으로 비치지 않게)
holes = Image.new("L", painted.size, 0)
hd = ImageDraw.Draw(holes)
for mir in (lambda x: x, lambda x: 1380 - x):
    hd.line([(mir(x), y) for x, y in [(400, 576), (438, 558), (550, 552), (660, 556), (676, 568)]], fill=255, width=34)
    hd.line([(mir(x), y) for x, y in [(410, 574), (420, 620), (448, 662), (500, 686), (560, 692), (620, 680), (656, 648), (670, 612), (676, 568)]], fill=255, width=22)
hd.line([(676, 568), (690, 556), (704, 568)], fill=255, width=26)          # 브리지
hd.line([(330, 572), (400, 576)], fill=255, width=26)                       # 안경다리
hd.line([(980, 576), (1050, 572)], fill=255, width=26)
holes = holes.filter(ImageFilter.GaussianBlur(6))
mask = ImageChops.subtract(mask, holes)

out = Image.composite(photo, painted, mask)
out.save(HERE / "ref" / "jensen_mixed.png")
out.crop((330, 300, 1060, 1060)).save(HERE / "out" / "mixed_face_preview.png")
print(HERE / "ref" / "jensen_mixed.png")
