"""사진 질감을 게임 그림처럼 단순화 (운영자 2026-11-18 "얼굴이 너무 원본 같다").
잔주름·피부결은 뭉개고(중간값 필터), 색은 몇 단계로 묶고(양자화), 채도·대비를 조금 올림. 눈·안경·코·입 같은 큰 특징은 남음.
실행: py -3.12 experiments/lowpoly-chars/toon_texture.py <입력> <출력> [단계=18] [뭉갬=9]
"""
import sys
from PIL import Image, ImageFilter, ImageEnhance

src, dst = sys.argv[1], sys.argv[2]
levels = int(sys.argv[3]) if len(sys.argv) > 3 else 18
blur = int(sys.argv[4]) if len(sys.argv) > 4 else 9
im = Image.open(src).convert("RGB")
w, h = im.size
small = im.resize((w // 2, h // 2), Image.LANCZOS)
for _ in range(1):
    small = small.filter(ImageFilter.MedianFilter(blur))            # 잔디테일 지우기 (가장자리는 남음)
small = ImageEnhance.Color(small).enhance(1.2)
small = ImageEnhance.Contrast(small).enhance(1.08)
q = small.quantize(colors=levels, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
q = q.filter(ImageFilter.SMOOTH)
q.resize((w, h), Image.LANCZOS).save(dst)
print(dst)
