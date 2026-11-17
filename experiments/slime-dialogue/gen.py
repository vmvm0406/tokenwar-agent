"""실험: 대화형 슬라임 릴스용 그림 (FLUX.2 [klein] 4B, Cloudflare).

1) 초록 슬라임(진행자) 표정 6장: 기준 이미지(assets/mascot/slime-base.jpg)를 참고 이미지로, 흰 배경.
2) AI 회사 캐릭터 후보: 회사마다 A/B/C 3장 (참고 이미지 없음, 같은 말랑 점토 3D 가족 스타일).
   로고 모양·글자 금지, 다른 계정 캐릭터를 따라 하지 않는다 (우리 디자인).
GitHub Actions(experiment-images.yml, 실험이 끝나면 지움)에서만 돈다 (CF_ACCOUNT_ID, CF_API_TOKEN).
그림 하루 상한(agent/image_quota.py)을 같이 센다. 이미 있는 파일은 건너뛴다.
    python experiments/slime-dialogue/gen.py [이름 앞부분 ...]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))
from gen_images import MASCOT_BASE, MASCOT_KEEP, MASCOT_SEED, ai_generate, ref_png, save_jpeg  # noqa: E402

OUT = Path(__file__).resolve().parent / "gen"
BG = ("Replace the whole background with a plain flat pure white seamless studio backdrop: no sofa, no furniture, "
      "no plant, no window, no floor line. The character stands alone, full body visible and centered, front view, "
      "soft even studio light, a soft contact shadow under the feet. ")
FACE = {
    "neutral": "Expression: calm friendly default face, small smile.",
    "surprised": "Expression: surprised, eyes a bit bigger round black dots, small open round O-shaped mouth, arms slightly raised.",
    "proud": "Expression: proud and pleased, eyes closed as happy upward arcs, wide smile, chest puffed, one arm raised.",
    "flustered": "Expression: flustered and embarrassed, small wavy mouth, light pink blush on cheeks, a tiny sweat drop beside the head.",
    "thinking": "Expression: thinking, eyes looking up to one side, small flat mouth, one stubby arm touching the chin.",
    "wink": "Expression: playful wink, left eye closed as a curved line, right eye a black dot, cheeky smile.",
}
STYLE = ("A cute original 3D character mascot toy in a soft matte clay / vinyl figure style, smooth rounded shapes, "
         "chubby small body, short stubby arms and tiny feet, simple face with two small round solid black dot eyes "
         "and a tiny curved smile, no nose. Full body, centered, front view, plain flat pure white seamless studio "
         "background, soft even studio lighting, soft contact shadow. No text, no letters, no logo, no symbols on the body. ")
COMP = {   # 회사: [(후보, 묘사, seed)]  로고 모양·색을 본뜬 몸 (운영자 2026-11-17). A·B는 같은 안의 다른 seed, C는 다른 안
    "claude": [
        ("A", "Body shaped like a chunky puffy starburst: a round center with many short soft rounded rays all around, warm terracotta orange, face on the round center.", 101),
        ("B", "Body shaped like a chunky puffy starburst: a round center with many short soft rounded rays all around, warm terracotta orange, face on the round center.", 202),
        ("C", "Round warm terracotta orange body with a ring of short soft rounded sun-like rays around its head.", 303),
    ],
    "chatgpt": [
        ("A", "Body shaped like a soft puffy hexagonal knot flower made of six interlocking rounded petal loops, monochrome white with charcoal black loop edges, face in the center.", 101),
        ("B", "Body shaped like a soft puffy hexagonal knot flower made of six interlocking rounded petal loops, monochrome white with charcoal black loop edges, face in the center.", 202),
        ("C", "Body shaped like a soft puffy hexagonal knot flower made of six interlocking rounded petal loops, glossy charcoal black with a round white face patch in the center.", 303),
    ],
    "gemini": [
        ("A", "Body shaped like a puffy four-pointed sparkle star with gently curved inward sides and soft rounded tips, smooth blue to purple color blend, face in the center.", 101),
        ("B", "Body shaped like a puffy four-pointed sparkle star with gently curved inward sides and soft rounded tips, smooth blue to purple color blend, face in the center.", 202),
        ("C", "Puffy four-pointed sparkle star body, smooth blue to purple color blend, with a tiny second sparkle star floating beside its head.", 303),
    ],
    "grok": [
        ("A", "Matte black body shaped like a chunky soft X made of two thick rounded diagonal bars crossing, face on the crossing center.", 101),
        ("B", "Matte black body shaped like a chunky soft X made of two thick rounded diagonal bars crossing, face on the crossing center.", 202),
        ("C", "Matte black round body with one bold diagonal white slash stripe across it, face above the stripe.", 303),
    ],
    "deepseek": [
        ("A", "Bright royal blue chubby whale-shaped body standing upright, tail curled up behind, small fins as arms, face on the front.", 101),
        ("B", "Bright royal blue chubby whale-shaped body standing upright, tail curled up behind, small fins as arms, face on the front.", 202),
        ("C", "Royal blue chubby whale-shaped body with a light blue belly, lying on its belly, tail curled up, small water spout.", 303),
    ],
    "meta": [
        ("A", "Body shaped like a puffy soft infinity loop (a rounded figure-eight ring), bright blue with a little violet, face on the center crossing.", 101),
        ("B", "Body shaped like a puffy soft infinity loop (a rounded figure-eight ring), bright blue with a little violet, face on the center crossing.", 202),
        ("C", "Round bright blue body with a big soft puffy infinity-loop ring floating around its waist.", 303),
    ],
    "copilot": [
        ("A", "Body shaped like a soft rounded pinwheel with four curved puffy blades in blue, green, yellow-orange and pink-purple, face in the center hub.", 101),
        ("B", "Body shaped like a soft rounded pinwheel with four curved puffy blades in blue, green, yellow-orange and pink-purple, face in the center hub.", 202),
        ("C", "Round body in soft swirled blue, green, orange and purple, with a small colorful pinwheel spinning on top of its head.", 303),
    ],
}


def jobs():
    for k, face in FACE.items():
        yield f"host-{k}", (MASCOT_KEEP + BG + face, MASCOT_SEED, True)
    for c, cands in COMP.items():
        for tag, desc, seed in cands:
            yield f"{c}-{tag}", (STYLE + desc, seed, False)


def main(names):
    ref = ref_png(MASCOT_BASE)
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, (prompt, seed, use_ref) in jobs():
        out = OUT / f"{name}.jpg"
        if out.exists() or (names and not any(name.startswith(n) for n in names)):
            continue
        print("make", name, flush=True)
        try:
            save_jpeg(ai_generate(prompt, 1088, 1360, seed, ref if use_ref else None), out)
            made += 1
        except Exception as e:   # 한 장 실패해도 나머지는 계속 (상한이면 멈춤)
            print("  fail", name, type(e).__name__, str(e)[:200], flush=True)
            if type(e).__name__ == "DailyLimitReached":
                break
    print("made", made)


if __name__ == "__main__":
    main(sys.argv[1:])
