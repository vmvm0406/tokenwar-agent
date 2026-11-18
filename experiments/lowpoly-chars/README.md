# 로우폴리 로고 캐릭터 (2026-11-18)

운영자 결정: 회사 로고 모양을 **그대로** 몸으로 쓰고, 팔다리 없이 **표정(눈·입)으로만** 연기한다.
스타일은 **로우폴리**: 잘게 쪼갠 다각형으로 정교하게, 그래도 면이 보이는 다각형 조합 느낌.

- `build.py`: Blender 스크립트. SVG 윤곽 → 두께 → 복셀 리메시 → 부풀리기 → Decimate(불규칙 삼각형) → 평면 셰이딩 → 면마다 색 살짝 흔들기. 결과 `out/<이름>.glb`(three.js용, 앞이 +Z) + 미리보기 png.
- 실행: `& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background --python experiments/lowpoly-chars/build.py -- [--only claude] [--quick]` (셋 다 약 40초)
- 설정은 `build.py`의 `CHARS`(두께·부풀림·얼굴 위치·면 수)와 `GEM_STOPS`(제미나이 색).

## logos/ (커밋하지 않음)
공개 저장소라 로고 파일은 올리지 않는다. 새 컴퓨터에서는 위키미디어 커먼스에서 다시 받는다:
- `openai.svg` ← File:OpenAI logo 2025 (symbol).svg
- `claude.svg` ← File:Claude AI symbol.svg
- `gemini.svg` ← File:Google Gemini icon 2025.svg 의 첫 `<path>`(별 윤곽)만 남긴 것 (viewBox 0 0 65 65)

## 다음
1. 운영자 모양 확인 → 고칠 점 반영
2. 표정 세트: 눈(기본·감음·^^·놀람·찡그림), 입(웃음·벌림 아/이/우·시무룩·당황), 눈썹, 볼 → glb에 이름 붙은 부품으로 넣고 three.js가 켜고 끔
3. 주인공 '나' (형식 미정)
4. three.js 틀(`experiments/threejs-test`)에서 glb 불러 연기·카메라·자막

## 젠슨 황 (2026-11-18)
- 참고 사진: Wikimedia Commons "Jensen huang stanford 2026-04-30 011.jpg", Anders Eidesvik, CC BY 4.0 (게시물 크레딧에 표기).
- 사진 → Hugging Face 무료 데모 TRELLIS(운영자 무료 계정 HF_TOKEN) → `ref/jensen_trellis.glb`(커밋 안 함, 형태 참고용).
- `jensen_simple.py`: 참고 형태를 뭉개 단순화 → 큼직한 면 → 영역별 단색(피부·머리·재킷) → 매끈한 입술, 네모 눈, 하프림 안경, 머리 1.35배. 결과 `out/jensen.glb`.
- 예전 시도: `lowpoly_from_glb.py`(질감 그대로 로우폴리), `jensen_real.py`(그 위에 부품) — 원본 흔적이 남아 운영자가 단순화 재제작을 택함.
