# 마스코트: 고양이 귀 연두 슬라임

운영자 결정 2026-11-16. 규칙은 STYLE_GUIDE.md 1-1 "마스코트", post.json 쓰는 법은 TEMPLATES.md "마스코트 그림".

## 기준 이미지

`slime-base.jpg` (864x1080, 4:5). 모양은 이 그림으로 고정한다. 다시 만들거나 고치지 않는다.

묘사 (그림을 보고 맞춘 것):
- 고양이 귀가 두 개 달린 반투명 연두색(형광 초록에 가까운 라임색) 젤리 슬라임
- 둥근 몸통, 위가 조금 좁은 젤리 곰 같은 모양. 짧고 뭉툭한 팔 두 개와 발 두 개
- 검은 점 눈 두 개, 작게 웃는 입. 코 없음
- 매끈하고 젖은 듯한 광택, 안에 작은 공기 방울이 떠 있음, 아래쪽이 은은하게 빛남
- 모자·옷·소품 없음
- 기준 장면: 밝은 회색 3인용 패브릭 소파 가운데, 흰 벽, 왼쪽에 작은 화분, 왼쪽 창문의 부드러운 자연광, 눈높이 정면

영어 묘사 (gen_images.py `MASCOT_KEEP`, 프롬프트 앞에 자동으로 붙음):

> Keep exactly the same character from the reference image: the small translucent lime green jelly slime with two cat ears, two small round black dot eyes, a tiny curved smile, short stubby arms and feet, tiny air bubbles inside, glossy wet surface. Same shape, same proportions, same face, same color.

## 만드는 법

- 모델: Cloudflare Workers AI `@cf/black-forest-labs/flux-2-klein-4b` (FLUX.2 [klein] 4B)
- seed: **424242** (기준 이미지를 만든 값, 새 그림도 기본으로 이 값)
- 크기: 1088x1360 (4:5)
- **참고 이미지 방식:** 기준 이미지를 긴 변 1024px PNG로 줄여 `input_image_0`으로 함께 보내고, 프롬프트는 "같은 캐릭터·같은 장면을 그대로 두고 ○○만 바꿔라"로 쓴다. 참고 이미지 없이 묘사 + seed만으로 만들면 모습이 매번 달라진다 (experiments/slime-test의 seedonly-* 비교).
- post.json에서는 그림 항목에 `"mascot": true`와 영어 `prompt`(바꿀 것만)를 적으면 `agent/gen_images.py`가 위 방식으로 만든다. 키(CF_ACCOUNT_ID, CF_API_TOKEN)가 GitHub Secrets에만 있어 render.yml(Actions)에서만 만들어진다.

## 기록

`experiments/slime-test/` (gen.py, log.json, 조명 3장과 비교용 seedonly 3장, sheet.jpg). 기준 이미지는 거기서 만든 `0-base.jpg`를 옮긴 것이다.
