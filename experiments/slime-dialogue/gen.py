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
COMP = {   # 회사: [(후보, 묘사, seed)]  A·B는 같은 안의 다른 seed, C는 다른 안
    "claude": [
        ("A", "Warm terracotta orange round chubby dumpling-shaped body, a small cream knitted scarf.", 101),
        ("B", "Warm terracotta orange round chubby dumpling-shaped body, a small cream knitted scarf.", 202),
        ("C", "Warm terracotta orange body shaped like a soft round bread bun with a slightly flat top, small round wire glasses.", 303),
    ],
    "chatgpt": [
        ("A", "Monochrome character: soft white rounded cloud-shaped body with charcoal black hands and feet, a tiny black headset.", 101),
        ("B", "Monochrome character: soft white rounded cloud-shaped body with charcoal black hands and feet, a tiny black headset.", 202),
        ("C", "Monochrome character: light grey rounded pebble-shaped body, a tiny black bow tie.", 303),
    ],
    "gemini": [
        ("A", "Body shaped like a soft puffy four-pointed sparkle star with very rounded tips, two-tone: sky blue body with lavender purple tips.", 101),
        ("B", "Body shaped like a soft puffy four-pointed sparkle star with very rounded tips, two-tone: sky blue body with lavender purple tips.", 202),
        ("C", "Round chubby sky blue body with two small rounded lavender purple star-shaped hair clips on top.", 303),
    ],
    "grok": [
        ("A", "Matte black egg-shaped body, a short antenna with a small white ball on top, a tiny silver earring.", 101),
        ("B", "Matte black egg-shaped body, a short antenna with a small white ball on top, a tiny silver earring.", 202),
        ("C", "Matte black round body with small sunglasses pushed up on top of its head.", 303),
    ],
    "deepseek": [
        ("A", "Navy blue chubby baby whale-shaped body standing upright, tiny fins as arms, a small water spout on top.", 101),
        ("B", "Navy blue chubby baby whale-shaped body standing upright, tiny fins as arms, a small water spout on top.", 202),
        ("C", "Round navy blue body with small white diving goggles on its forehead.", 303),
    ],
    "meta": [
        ("A", "Cobalt blue round chubby body with a soft clay ring-shaped halo floating above its head.", 101),
        ("B", "Cobalt blue round chubby body with a soft clay ring-shaped halo floating above its head.", 202),
        ("C", "Blue-violet body shaped like a soft rounded capsule, small round goggles on its forehead.", 303),
    ],
    "copilot": [
        ("A", "Teal round chubby body wearing a tiny brown leather pilot cap and orange pilot goggles on the forehead.", 101),
        ("B", "Teal round chubby body wearing a tiny brown leather pilot cap and orange pilot goggles on the forehead.", 202),
        ("C", "Body in soft teal and orange halves, a tiny white pilot scarf around the neck.", 303),
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
