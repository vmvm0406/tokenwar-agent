"""out/sheet/<캐릭터>_<감정>.png → out/emotion_sheet.png (캐릭터 = 줄, 감정 = 칸, 아래에 감정 이름)."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
emos = list(json.loads((OUT / "emotions.json").read_text(encoding="utf-8"))["emotions"])
chars = [c for c in (sys.argv[1].split(",") if len(sys.argv) > 1 else ("claude", "gemini", "chatgpt")) if (OUT / "sheet" / f"{c}_neutral.png").exists()]
cell, lab = 320, 44
sheet = Image.new("RGB", (cell * len(emos), (cell + lab) * len(chars)), "black")
font_path = HERE.parent.parent / "assets" / "fonts"
fonts = sorted(font_path.glob("*.ttf")) + sorted(font_path.glob("*.otf"))
font = ImageFont.truetype(str(fonts[0]), 26) if fonts else ImageFont.load_default()
d = ImageDraw.Draw(sheet)
for r, c in enumerate(chars):
    for i, e in enumerate(emos):
        im = Image.open(OUT / "sheet" / f"{c}_{e}.png").convert("RGB").resize((cell, cell))
        y = r * (cell + lab)
        sheet.paste(im, (i * cell, y))
        d.text((i * cell + cell // 2, y + cell + lab // 2), e, fill="#00FF66", font=font, anchor="mm")
name = sys.argv[2] if len(sys.argv) > 2 else "emotion_sheet.png"
sheet.save(OUT / name)
print(OUT / name)
