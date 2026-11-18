"""젠슨 황 사진에서 '피부 명암만' 뽑기 (운영자 2026-11-18 "각진 버전에 원본 사진 느낌 살짝").
눈·코·입·안경 자리는 크게 흐린 피부로 메워서, 만화 얼굴 부품과 겹쳐 보이지 않게 함. 이마 주름·볼 음영·팔자 주름은 남음.
→ ref/jensen_skin_detail.png (build_humans.py photo_tint가 면 색에 섞음)
"""
from pathlib import Path
import numpy as np
import cv2

HERE = Path(__file__).resolve().parent
img = cv2.imread(str(HERE / "ref" / "jensen_photo_bust.jpg")).astype(np.float32)
blur = cv2.GaussianBlur(img, (0, 0), 30)
mask = np.zeros(img.shape[:2], np.uint8)
cv2.rectangle(mask, (380, 535), (990, 705), 255, -1)          # 눈·안경 띠 (안경다리 포함)
cv2.ellipse(mask, (682, 715), (95, 75), 0, 0, 360, 255, -1)    # 코
cv2.ellipse(mask, (682, 850), (120, 55), 0, 0, 360, 255, -1)   # 입
m = cv2.GaussianBlur(mask, (0, 0), 18).astype(np.float32)[..., None] / 255.0
out = img * (1 - m) + blur * m
cv2.imwrite(str(HERE / "ref" / "jensen_skin_detail.png"), out.astype(np.uint8))
print("ok")
