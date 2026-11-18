"""젠슨 황 얼굴 질감을 '손으로 그린 것처럼' 직접 그림 (운영자 2026-11-18 "앞 얼굴도 직접 만든 것처럼").
사진(ref/jensen_photo_bust.jpg)은 위치 기준으로만 씀 — 같은 크기·좌표계(1459x1740)에 그려서 jensen_n64.py의 정면 투영 UV를 그대로 씀.
위치는 사진 격자로 잰 값(눈 (580,600)·(785,610), 콧볼 밑 y 760, 입선 y 845, 이마선 y 370, 턱 y 1000).

실행: py -3.12 experiments/lowpoly-chars/paint_face.py → ref/jensen_painted.png (+ out/painted_face_preview.png)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
W, H = 1459, 1740
S = 2                                   # 2배로 그리고 줄여서 가장자리 부드럽게
C = lambda x, y: (x * S, y * S)

SKIN, SKIN_D, SKIN_L = (218, 160, 124), (190, 128, 96), (236, 186, 152)
HAIR, HAIR_D, HAIR_L = (170, 170, 166), (140, 140, 137), (192, 192, 188)
EYE, BROW = (40, 28, 24), (70, 66, 62)
LIP_U, LIP_L, LIP_LINE = (176, 98, 90), (198, 118, 106), (110, 52, 50)
FRAME, WIRE = (26, 26, 28), (176, 180, 186)
JACKET, JACKET_L, TEE = (30, 30, 34), (64, 64, 70), (20, 20, 22)
CX = 682                                 # 얼굴 가운데


def ell(d, x0, y0, x1, y1, fill, **k):
    d.ellipse([*C(x0, y0), *C(x1, y1)], fill=fill, **k)


def poly(d, pts, fill, **k):
    d.polygon([C(x, y) for x, y in pts], fill=fill, **k)


def line(d, pts, fill, w):
    d.line([C(x, y) for x, y in pts], fill=fill, width=int(w * S), joint="curve")


def hair_strands(d, x0, x1, y_base, part_x=None, top=0):
    """가는 머리카락 가닥: 같은 방향으로 흐르는 부드러운 곡선, 회색 명암 차이는 작게.
    part_x = 옆 가르마 위치 (왼쪽 가닥은 왼쪽 위로, 오른쪽 가닥은 오른쪽 위·뒤로 크게 넘김)."""
    import random
    rng = random.Random(4)
    shades = [(150, 150, 146), (162, 162, 158), (184, 184, 180), (196, 196, 192), (138, 138, 135)]
    for k in range(int((x1 - x0) / 3)):
        x = x0 + rng.uniform(0, x1 - x0)
        y = y_base + rng.uniform(-25, 15)
        L = rng.uniform(0.6, 1.0)
        if part_x is not None and x < part_x:
            ctrl = [(0, 0), (-25, -90), (-70, -180)]
        else:
            ctrl = [(0, 0), (35, -110), (110, -250)]
        pts = []
        for i in range(7):                               # 2차 베지어
            t = i / 6 * L
            (ax, ay), (bx, by), (cx, cy) = ctrl
            px = (1 - t) ** 2 * ax + 2 * (1 - t) * t * bx + t * t * cx
            py = (1 - t) ** 2 * ay + 2 * (1 - t) * t * by + t * t * cy
            pts.append((x + px, max(top, y + py)))
        line(d, pts, rng.choice(shades), rng.uniform(2.2, 3.4))

def main():
    im = Image.new("RGB", (W * S, H * S), SKIN)
    d = ImageDraw.Draw(im)

    # 재킷·티셔츠 (목 아래)
    poly(d, [(0, 900), (360, 930), (470, 990), (560, 1150), (682, 1260), (800, 1150), (900, 990), (1010, 930),
             (1459, 900), (1459, 1740), (0, 1740)], JACKET)        # 어깨선까지 재킷
    poly(d, [(560, 1150), (682, 1260), (800, 1150), (760, 1740), (600, 1740)], TEE)
    for x0, x1 in ((120, 360), (1000, 1300)):          # 가죽 반사
        line(d, [(x0, 1300), (x0 + 60, 1500), (x0 + 40, 1700)], JACKET_L, 14)
    line(d, [(560, 1150), (610, 1740)], JACKET_L, 8)      # 지퍼 쪽 가장자리
    line(d, [(800, 1150), (760, 1740)], JACKET_L, 8)

    # 얼굴 음영: 따로 그려 크게 번지게 (덩어리로 보이지 않게)
    sh = Image.new("RGBA", im.size, (*SKIN_D, 0))     # 투명 바탕도 피부 그늘색 (검은 테두리 번짐 방지)
    sd = ImageDraw.Draw(sh)
    for x0, x1 in ((370, 470), (895, 995)):
        ell(sd, x0, 560, x1, 980, (*SKIN_D, 150))
    ell(sd, 540, 985, 830, 1050, (*SKIN_D, 130))          # 턱 아래
    sh = sh.filter(ImageFilter.GaussianBlur(20 * S))
    im.paste(sh, (0, 0), sh)
    d = ImageDraw.Draw(im)

    # 머리카락: 이마선 위·옆머리 (옆 가르마로 오른쪽에 볼륨)
    poly(d, [(330, 0), (1100, 0), (1100, 620), (990, 600), (985, 470), (930, 400), (820, 360), (682, 368), (560, 362),
             (470, 395), (420, 460), (410, 600), (330, 620)], HAIR)
    hair_strands(d, 400, 1060, 380, part_x=490)
    # 뒤통수·옆·정수리용 머리카락 견본 (사진 바깥 왼쪽 위, jensen_n64.py가 여기서 가져감) + 피부 견본
    poly(d, [(20, 20), (310, 20), (310, 310), (20, 310)], HAIR)
    hair_strands(d, 20, 310, 310, part_x=None, top=20)
    poly(d, [(20, 340), (310, 340), (310, 560), (20, 560)], SKIN)
    ell(d, 20, 400, 310, 560, SKIN_D)
    # 귀
    for x0, x1 in ((330, 400), (965, 1035)):
        ell(d, x0, 590, x1, 760, SKIN)
        ell(d, x0 + 18, 620, x1 - 18, 730, SKIN_D)

    # 눈썹 (짙은 회색, 짧고 반듯)
    line(d, [(505, 552), (560, 540), (628, 545)], BROW, 11)
    line(d, [(737, 548), (805, 543), (862, 556)], BROW, 11)

    # 눈: 가는 아몬드 + 위 눈꺼풀 선 + 하이라이트, 아래 눈두덩 그늘
    for ex, ey in ((580, 600), (785, 610)):
        ell(d, ex - 42, ey + 14, ex + 42, ey + 34, SKIN_D)           # 눈 밑 그늘
        ell(d, ex - 36, ey - 13, ex + 36, ey + 13, (245, 238, 230))  # 흰자
        ell(d, ex - 15, ey - 13, ex + 15, ey + 13, EYE)              # 눈동자
        ell(d, ex + 3, ey - 9, ex + 10, ey - 2, (255, 255, 255))     # 하이라이트
        line(d, [(ex - 40, ey + 2), (ex - 10, ey - 15), (ex + 25, ey - 13), (ex + 42, ey + 4)], EYE, 6)  # 윗눈꺼풀

    # 코: 콧대 하이라이트, 코끝, 콧볼, 콧구멍
    line(d, [(682, 600), (676, 690)], SKIN_L, 10)
    ell(d, 640, 690, 724, 760, SKIN_L)                    # 코끝
    ell(d, 612, 718, 660, 768, SKIN_D)                    # 콧볼
    ell(d, 704, 718, 752, 768, SKIN_D)
    ell(d, 642, 745, 670, 763, (96, 52, 44))              # 콧구멍
    ell(d, 694, 745, 722, 763, (96, 52, 44))
    line(d, [(612, 770), (585, 840)], SKIN_D, 6)          # 팔자 주름 (약하게)
    line(d, [(752, 770), (780, 840)], SKIN_D, 6)

    # 입: 다문 입, 얇은 윗입술·도톰한 아랫입술 (폭 170)
    poly(d, [(597, 845), (640, 828), (668, 822), (682, 826), (696, 822), (724, 828), (767, 845)], LIP_U)
    poly(d, [(597, 845), (767, 845), (740, 872), (682, 884), (624, 872)], LIP_L)
    line(d, [(597, 845), (682, 849), (767, 845)], LIP_LINE, 5)

    # 안경은 그리지 않음 — jensen_n64.py가 같은 위치에 입체로 올림 (운영자 2026-11-18)

    im = im.filter(ImageFilter.GaussianBlur(1.2)).resize((W, H), Image.LANCZOS)
    out = HERE / "ref" / "jensen_painted.png"
    im.save(out)
    im.crop((330, 300, 1060, 1060)).save(HERE / "out" / "painted_face_preview.png")
    print(out)


main()
