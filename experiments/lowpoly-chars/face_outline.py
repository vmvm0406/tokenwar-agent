"""사진에서 높이별 얼굴 피부 윤곽(왼쪽·오른쪽 끝)을 잼 → ref/jensen_face_outline.json (운영자 2026-11-18 "얼굴 사진에 맞게 입체 모형도 모양이 따라가자").
피부색(색상 0~40°, 채도 0.15~0.75, 밝기 0.25 이상) 마스크 → 정리 → 행마다 얼굴 가운데(x 682)에서 이어진 피부 구간의 양 끝.
실행: py -3.12 experiments/lowpoly-chars/face_outline.py  (결과 확인용 out/face_outline_check.png)
"""
import json, colorsys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
im = Image.open(HERE / "ref" / "jensen_photo_bust.jpg").convert("RGB")
W, H = im.size
small = im.resize((W // 2, H // 2))
px = small.load()
mask = Image.new("L", small.size, 0)
mp = mask.load()
for y in range(small.size[1]):
    for x in range(small.size[0]):
        r, g, b = [v / 255 for v in px[x, y]]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if (h < 40 / 360 or h > 345 / 360) and 0.15 < s < 0.75 and v > 0.25:
            mp[x, y] = 255
mask = mask.filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
mp = mask.load()
rows = {}
CX = 682 // 2
for y in range(360 // 2, 1040 // 2):
    if not mp[CX, y]:
        continue
    l = CX
    while l > 0 and (mp[l - 1, y] or mp[max(l - 3, 0), y]):
        l -= 1
    r = CX
    while r < small.size[0] - 1 and (mp[r + 1, y] or mp[min(r + 3, small.size[0] - 1), y]):
        r += 1
    rows[y * 2] = (l * 2, r * 2)
(HERE / "ref" / "jensen_face_outline.json").write_text(json.dumps(rows), encoding="utf-8")
chk = im.copy()
d = ImageDraw.Draw(chk)
for y, (l, r) in rows.items():
    d.point([(l, y), (r, y)], fill=(0, 255, 102))
    d.point([(l + 1, y), (r - 1, y)], fill=(0, 255, 102))
chk.crop((300, 300, 1100, 1100)).save(HERE / "out" / "face_outline_check.png")
print(len(rows), "rows", min(rows), max(rows))
