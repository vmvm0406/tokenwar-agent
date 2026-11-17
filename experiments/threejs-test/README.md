# three.js 3D 캐릭터 대화 릴스 시제품 (2026-11-17)

운영자: "저 채널(@canwebuildthis)의 특성을 그대로 분석해서 three.js로 만들 수 있는지 판단하고 진행하자".
형식(책상 위 장난감 3D 캐릭터 + 위 라벨 띠 + 자막 상자 + 대사 연기)만 가져오고, 그 계정의 캐릭터·시리즈 이름·개그는 쓰지 않는다.
특징별 가능 여부와 비용은 [checklist.md](checklist.md).

## 들어 있는 것
| 파일 | 내용 |
|---|---|
| `scene3.js`, `index3.html` | v3: 사람 주인공 '나'(20대 여성 직장인, 비닐 피규어풍) + 클로드·챗GPT(책 위)·제미나이. 대사 Hana Lee "클로드, 제미나이, 지피티! 오늘 보고서, 누가 먼저 끝낼래?", 이름이 불린 AI가 점프·손 들기, 끝에 셋 다 '저요'. `twSheet(yaw)` = '나' 캐릭터 시트 |
| `actions-matrix.example.yml` | 예시(꺼져 있음): GitHub Actions 행렬 10개로 프레임을 나눠 그리고 합치기 |
| `scene.js` | v2 장면 전체. 캐릭터 3개(코드로 만든 절차적 모델), 책상·모니터·머그·키보드·꼬마전구, 조명·그림자, 보케, 카메라 키프레임, 2D 라벨 띠·자막. `twFrame(t)`가 t초 장면을 그려 JPEG로 돌려줌 (실시간 아님, 같은 t면 같은 그림) |
| `index.html` | importmap으로 `vendor/three` 연결 |
| `render.py` | Playwright 헤드리스 Chromium → 프레임 → ffmpeg mp4(1080x1920 30fps) + 대사 + 점프 효과음(직접 합성), -14 LUFS |
| `vendor/three/` | three.js **0.170.0** (npm `three@0.170.0`, MIT, LICENSE 포함) 중 쓰는 파일만: `three.module.min.js`, addons(RoomEnvironment, EffectComposer·RenderPass·BokehPass·OutputPass, RoundedBoxGeometry, BufferGeometryUtils). 인터넷 없이 돈다 |
| `line/line01.*` / `line/line03.*` | v2 대사(Deok) / v3 대사(Hana Lee), mp3 + 글자별 시각 json |

## 실행
사용법은 `render.py` 맨 위 설명. 예: `py -3.12 experiments/threejs-test/render.py --v3 --gpu` (7.5초 영상 약 20초), `--bench`(효과별 시간), `--range 0:90` + `--encode-only`(나눠 그리기). 결과 `out/` (커밋 안 함).

## 어떻게 움직이나
- 대사 시각: ElevenLabs `/with-timestamps` 글자 시각 → 입 벌림(글자마다 sin), 단어 구간에 표정·동작('대결' → 슬라임 ^ ^ 눈 + 점프, '클로드' → 클로드 점프·손 흔들기, '제미나이' → 제미나이 점프·반짝이 회전, 끝 물음표 → 슬라임 갸웃).
- 늘 하는 것: 숨쉬기(살짝 늘었다 줄었다), 정해 둔 시각 깜박임, 말하는 쪽으로 몸 돌리기.
- 카메라: `CAM` 표 한 줄 = [시각, 위치, 바라보는 곳, 초점 대상, 조리개]. 넓게 → 슬라임 쪽으로 밀기 → 둘을 보는 구도.
- 캐릭터는 회사 로고 모티프·브랜드 색을 본뜬 원래 디자인이다 (글자 로고 없음, 화면에 '비공식 팬 캐릭터').

## 판정과 다음 단계
**혼합안(hybrid) 권장, 렌더는 이 노트북 GPU 기본(30초 릴스 1분 안) + Actions 행렬 분할 예비(약 8분)**. 숫자는 checklist.md: 연기·카메라·자막·대사 맞춤은 three.js(코드라 대본만 바꾸면 자동), 캐릭터 모델은 다음 단계에서 블렌더로 한 덩어리 점토 모델 + 입 모양 morph 3~4개를 만들어 glTF로 넣는다.
재사용 틀(`agent/toon_reel.py` 같은 것, post.json에 대사 줄·화자·표정 표시 → 자동 연기)까지 약 2~3일:
1. 대사 여러 줄·화자별 목소리·컷 표 (0.5일)
2. 표정 세트(기쁨·놀람·시무룩·입 모양 3개)와 동작 세트(점프·갸웃·손짓·돌기) 이름으로 부르기 (0.5일)
3. 캐릭터 glTF 교체 구조 + 블렌더 모델 3개 (1일, 모델 품질에 따라 더)
4. 보케 개선·SSAO·장면 2~3개(책상/회의실/무대) (0.5~1일)
