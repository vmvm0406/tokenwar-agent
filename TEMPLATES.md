# 템플릿 사용법

`post.json`의 `slides` 배열로 장을 만든다. 첫 장은 표지(`kind: "cover"`), 그 뒤는 본문 장이다. 마지막 장(녹색 면, 슬로건, 출처)은 자동으로 붙는다. 실제 예시는 `samples/` 폴더에 있다.

디자인 규칙은 STYLE_GUIDE.md 1-1장 (AI 디자인 티 금지 목록).

## 표지 (cover)

아래쪽에 `[시리즈] 제목` 2줄과 부제 1줄, 왼쪽 아래 TOKEN WAR. 위쪽은 layout에 따라 다르다.

| 필드 | 설명 |
|---|---|
| `layout` | `big`, `list`, `image` |
| `title` | 2줄 이하, 줄당 12자 이하 (첫 줄 앞에 `[시리즈]`가 붙으니 첫 줄은 짧게). 줄바꿈은 `\n` |
| `highlight` | 제목 안에서 녹색으로 칠할 부분 |
| `sub` | 한 줄 부제 (30자 이하) |

| layout | 위쪽 | 필드 |
|---|---|---|
| `big` | 화면을 꽉 채우는 녹색 큰 글자 (숫자나 단어, 가장자리에서 잘려도 됨) | `big`(7자 이하), `big_note`(그 아래 한 줄) |
| `list` | 녹색 가로선으로 나눈 번호 목록 (TOP 3~5, 체크리스트) | `items` 2~5개, 각 14자 이하 |
| `image` | 실제 이미지나 AI 이미지 (위쪽 꽉 채움, 아래로 어두워짐) | `visual: {"type": "image", "src": "img/cover.jpg"}`, AI로 만들 때는 `"prompt": "영어 장면 묘사"` 추가 |

### 표지 영상 (`motion`, 선택, 카드뉴스 첫 장을 짧은 영상으로)

카드뉴스(`type: carousel`) 표지에만. 넣으면 첫 장이 영상(`slides/01.mp4`, 1080x1350, H.264 + AAC, 30fps)이 되고 나머지 장은 사진 그대로인 영상+사진 캐러셀로 올라간다 (인스타 캐러셀 자식 `media_type=VIDEO`). 정지 화면 `slides/01.jpg`도 그대로 만들어져 스레드 이미지·검토 페이지 포스터·사진 장 수 규칙에 쓰인다. 없으면 예전과 똑같이 사진만.

```json
{"kind": "cover", "layout": "image", "visual": {...}, "title": "...",
 "motion": {"seconds": 6}}
```
```json
"motion": {"src": "clips/cover.mp4", "start": 12.0, "end": 19.0, "credit": "OpenAI 공식 YouTube", "source_url": "https://...", "mute": false}
```

| 필드 | 내용 |
|---|---|
| `seconds` | `src`가 없을 때: 표지 그대로에 모션(그림 천천히 확대, 제목·부제가 아래에서 올라옴). 3~10초, 기본 6. 인스타 미리보기 장면은 2초(글이 다 올라온 뒤) |
| `src`·`start`·`end` | 선택: 표지 그림 자리(위쪽)에 이 영상을 꽉 채워(잘라) 깐다. 제목·그늘은 그 위에 고정. 결과 길이 3~60초(15초 넘으면 경고, 3~10초 권장). 공식 시연·발표 영상만 |
| `credit`·`source_url` | `src`를 쓰면 `credit`(영상 출처) 필수. 캡션 출처 줄에도 적는다 |
| `mute` | true면 원본 소리를 버리고 음악을 깐다 |

- **무음 금지 (STYLE_GUIDE 6장 "릴스 소리"):** 원본 소리가 있으면 그대로, 없으면(모션 표지·화면 녹화) `music`(아래 "배경음악") → `assets/music` → 코드로 만든 음악을 깔고, 전부 -14 LUFS·-1.5 dBTP로 맞춘다 (`agent/loudness.py`). render.py가 크기·코덱·30fps·길이·소리를 검사한다.
- 표지는 여전히 사진 표지(`layout: image` + `visual` + `hook`)로 쓴다. 그 사진이 `01.jpg`가 된다.
- ffmpeg가 없는 곳에서 렌더링하면 `01.mp4`는 건너뛰고 render.yml이 만든다. `01.mp4`가 없으면 publish는 그 게시물을 렌더링 전으로 보고 기다린다.

## 본문 장

| kind | 용도 | 필드 |
|---|---|---|
| `body` | 일반 설명 | `heading`, `highlight`, `body`, `point`(굵은 녹색 선 아래 큰 녹색 문장), `visual`(선택), `num`·`num_note`(선택: 제목 위 큰 녹색 번호 01과 날짜·출처 한 줄. 주간 요약처럼 소식마다 한 장일 때. 예시 `samples/s11-weekly-ai`) |
| `stat` | 숫자 하나가 핵심 | `value`, `unit`, `label`(문장으로), `heading`, `body` |
| `steps` | 따라 하기, 체크리스트 | `heading`, `items`: [{`title`, `text`}] 2~4개 |
| `compare` | 비교, 전후 | `heading`, `left`/`right`: {`label`, `items`, `on`} |
| `prompt` | 복사해 쓰는 프롬프트 (따라 하기·질문 형식) | `heading`, `highlight`, `prompt`(글자 그대로, 320자 이하) 또는 `prompts`(여러 개), `prompt_label`(기본 "프롬프트", 질문 형식이면 "질문 1"), `prompt_hint`(기본 "그대로 복사해서 붙여 넣기"), `num`·`num_note`, `visual`(선택: 위쪽 실제 화면, 높이가 줄어듦), `body`(선택: 한 줄 설명) |

## 그림 (visual)

| type | 필드 | 쓰는 곳 |
|---|---|---|
| `image` | `src`(게시물 폴더 기준), `credit`(사진 아래 작은 출처 글씨), `position`(보여줄 부분, 기본 `top center`), `fit`(`cover`/`contain`), `bleed`(true면 위쪽 가장자리까지 꽉), `height`(선택: 그림 높이 px. 아래 글이 넘칠 때 줄인다), `place`(`inline`이면 예전처럼 글 사이에), 파일 구하기: `url`(내려받기) → `shot`(화면 캡처: `url`, `selector`, `scroll`, `width`, `height`, `dark`) → `prompt`(AI) | 본문 장 위쪽 절반에 실제 화면·사진, 아래에 제목·설명 (다른 AI 계정들의 기본 모양). 카드뉴스는 표지 포함 사진 장 2장 이상 (STYLE_GUIDE 2-1) |
| `bars` | `items`: [{`label`, `value`, `display`, `on`}], `unit` | 실제 숫자 비교 (가격, 점수) |
| `timeline` | `items`: [{`date`, `text`, `on`}] | 사건 순서 |

가짜 UI 화면(설정창, 대화창, 터미널), 아이콘 타일, 점 무늬 배경은 쓰지 않는다.

### 마스코트 그림 (`"mascot": true`, 선택)

`type: image` 그림 어디에나(본문 visual, thumb.image, 목록형 릴스 list.items) 붙인다. 규칙은 STYLE_GUIDE 1-1 "마스코트", 기준 이미지·묘사는 `assets/mascot/README.md`.

```json
{"type": "image", "src": "img/list/01.jpg", "mascot": true,
 "prompt": "Same grey sofa, same living room, same camera angle and framing. Change ONLY the lighting: ...",
 "ref": "img/list/scene.jpg", "seed": 424242}
```

| 필드 | 내용 |
|---|---|
| `mascot` | true면 `gen_images.py`가 참고 이미지를 FLUX.2 편집 입력(input_image_0, 긴 변 1024px)으로 붙이고, 프롬프트 앞에 "기준 캐릭터를 그대로 두라"는 영어 문장을 붙인다 |
| `prompt` | 영어. 바꿀 것만(조명, 카메라, 그림체, 장면). 캐릭터 모양을 바꾸는 말, 특정 스튜디오·작가 이름은 쓰지 않는다. 없으면 참고 이미지를 그대로 복사한다 |
| `ref` | 선택. 참고 이미지(게시물 폴더 기준). 없으면 `assets/mascot/slime-base.jpg`. 같은 게시물의 다른 그림이면 그 그림을 먼저 만든다 (장면 기준 그림 하나 → 그 장면의 변형들) |
| `seed` | 선택. 기본 424242 |

없으면 예전과 같다. 키가 GitHub Secrets에만 있어 그림은 render.yml에서만 만들어진다.

## 게시물 형식 (`format`, 선택)

`"format": "howto" | "ask" | "weekly" | "news" | "buzz"`. 없으면 예전처럼 동작한다. `howto`·`ask`는 `kind: prompt` 장이 1개 이상 있어야 렌더링된다 (checks.py). 근거는 STYLE_GUIDE 3-1 (ai.trend.kr 상위 게시물 분석).

### 속보 표시 (`"breaking": true`, 선택)

업계 속보·새 모델 바로 올리기(LOCAL.md 6장)로 만든 게시물에 붙인다. `agent/slots.py`가 이 게시물을 하루 칸 수(상한·daily_target)에 세지 않고, `slots.py bump`가 그 앞뒤의 따라 하기·질문만 다음 칸으로 옮긴다. 없으면 보통 게시물.

### 고쳐 다시 올리기 (`"replaces": "<원래 게시물 id>"`, 선택)

이미 올라간 게시물을 고쳐 새 게시물로 다시 올릴 때 붙인다. `agent/dupes.py`가 그 원본과의 출처·주제 겹침만 보지 않는다(다른 게시물과의 검사는 그대로). 원본 published 폴더는 건드리지 않는다.

### 승인 (`"approved": true`, `"approved_at"`, 운영자 승인 뒤에만)

`config.json` `require_approval`이 true면 이 표시가 있는 게시물만 올라간다 (`approval_exempt_before`보다 이른 `publish_at`은 예외). 만들 때는 넣지 않는다. 흐름: 검토 세션 → 운영자 OK → 지휘 세션이 `py -3.12 agent/approve.py posts/queue/<폴더> --edits N` → main에 push. 속보(`breaking`)도 같다. `approve.py`가 post.json 맨 위(`{` 다음 줄)에 두 줄을 넣고 `.render_hash`를 맞추며 `data/approvals.csv`에 기록한다. `approved_at`은 기록용(한국 시간 ISO, 예 `2026-11-16T21:20:54+09:00`). 두 줄은 렌더링 지문(`build.input_hash`)에서 빠져서 승인만 넣으면 다시 렌더링하지 않는다. 손으로 넣지 말고 approve.py를 쓴다 (`{` 다음이 아닌 곳에 넣으면 지문이 바뀌어 한 번 다시 렌더링될 수 있다).

### 가벼운 화제 (`format: "buzz"`)

카드뉴스(`carousel`)·릴스(`video`) 어디에나 붙인다. 틀은 평소와 같고 다른 점만: `sources` 2개 이상(없으면 오류), 패러디·밈이면 캡션 앞 3줄에 실제 사정("사실은 ~였다", 없으면 경고), 같은 주(월~일) 3개째면 dupes.py 경고. 사진·영상은 공식 채널 영상·공식 보도자료 사진만(보도사진 금지). 규칙은 STYLE_GUIDE 3-2.

### 따라 하기 (`format: "howto"`)

| 순서 | 장 | 만드는 법 |
|---|---|---|
| 1 | 표지 | `layout: image`. 그림은 **실제 결과물**(직접 돌려 본 답 화면, 공식 예시). 제목은 얻는 것을 약속 ("구글 검색에 물으면 여행 일정표가 나옵니다") |
| 2~ | 단계마다 한 장 | `body`(누를 곳) 또는 `prompt`(넣을 글). 위쪽 실제 화면, `num` 1·2·3으로 순서. 프롬프트는 장 안에 글자로 넣는다 (DM으로만 주지 않는다) |
| | 결과 | `body` + 실제 결과 화면. 무엇이 나왔는지 사실만 |
| | (주의할 점 장 없음) | 따라 하기 게시물에는 결과의 흠·주의할 점을 카드·캡션·자료 페이지 어디에도 넣지 않는다 (운영자 결정 2026-11-16, "주의할 점 같은 건 굳이 넣지 말자", "그것도 빼자"). 따라 하려면 꼭 알아야 하는 조건(필요한 프로그램, 요금제, 라이선스)만 자료 페이지 '준비물'로 남긴다. 결과가 기대에 못 미치면 흠을 적지 말고 더 나은 결과로 다시 만들거나 다른 소재를 고른다 |
| 끝 | (자동) 마지막 장 | |

예시: `samples/s12-howto-ai-mode` (카드뉴스), `samples/s13-howto-ai-mode-reel` (같은 내용의 카드형 모션 릴스).

### 나를 알려 주는 질문 (`format: "ask"`)

따라 하기와 같은 틀. 단계 장이 `prompt` 장 3~4개(질문 1~4)이고 `prompt_label`을 "질문 1"처럼 쓴다. 장마다 위쪽에 실제 답변 화면(이름·이메일 같은 개인정보는 가린다), 아래 질문 전문. 질문은 같은 대화창에서 순서대로 보내는 것이어야 한다. 끝에서 두 번째 장은 조건(기억 기능을 켜야 잘 됨, 다른 AI에서도 되는지).

### 댓글 자동 DM (`dm`, 따라 하기·질문 게시물)

화면·캡션 안내는 댓글 키워드 '자료'. Zorcha 반응 조건은 '아무 댓글'이라 다른 말을 써도 받게 된다. 팔로우한 사람에게 안내 페이지 링크 DM, 안 한 사람에게는 팔로우하고 다시 댓글 달라는 확인 DM, 댓글에는 공개 답글(3~4개 돌려 쓰기) (STYLE_GUIDE 7-1). 게시되면 publish.py가 "Zorcha 설정 필요" 이슈와 `data/zorcha_todo.md` 한 줄로 운영자에게 알린다. 렌더링할 때 `agent/dm.py`가 게시물 폴더에 `dm.md`(Zorcha에 붙여 넣을 설정 메모)와 `docs/p/<id>/index.html`(GitHub Pages 안내 페이지)을 만든다. 예시 폴더에서는 `page.html`로만 만든다 (`samples/s12-howto-ai-mode`). 안내 페이지 목록(자료실)은 만들지 않는다: 주소는 DM으로만 알린다 (noindex, robots.txt).

```json
"dm": {
  "keyword": "자료",
  "message": "DM 문구 3줄 (주소 없이)",
  "cta": "화면 안 안내 (필수): 얻는 것 + 댓글에 '자료'. 예: 화풍 스킬 적용법 받고 싶으면\n댓글에 '자료'. 릴스는 끝 화면 2.5초, 카드는 마지막 장",
  "banner": "(선택, 릴스 권장) 앞쪽 안내 띠. 두 줄까지, 한 줄 24자 안, 키워드는 따옴표로, '어디에 무엇을 쓰면 무엇을 어떻게 받는지' 완전한 문장(→ 같은 기호·줄임말 금지). 예: 댓글에 '자료'라고 남기면\n프롬프트를 DM으로 보내 드립니다. 3초부터 본편 끝까지. 영상 릴스는 영상 창 위쪽 테두리 안, 카드형 모션 릴스는 안전 영역 맨 위(본문은 띠 높이 + 20px 아래로, 위쪽 그림은 그만큼 줄어듦). 띠 높이 한 줄 64px·두 줄 104px. STYLE_GUIDE 7-1",
  "comment_reply": "(선택) 댓글 공개 답글. 문구 하나 또는 목록(각 150자 안). 기본 문구 4개로 채워 돌려 쓴다 (agent/dm.py DEFAULTS)",
  "follow_text": "(선택) 팔로우 안 한 사람에게 보낼 확인 DM. 기본: 팔로우하고 이 게시물에 다시 댓글을 남기면 보내 드린다는 문구 (키워드를 다시 쓰라고 하지 않는다)",
  "button": "(선택) 링크 버튼 이름. 기본: 자료 보기",
  "page": {
    "intro": "안내 페이지 첫 문단: 무엇을 얻는지 한두 문장 (날짜·'직접 넣어 본'·'저희는' 같은 제작 이야기 금지)",
    "prep": ["준비물: 따라 하는 데 꼭 필요한 조건만 (운영체제·요금제·프로그램·라이선스)"],
    "result": "결과 예시: 결과물이 무엇인지 한두 문장 (사실만, 테스트 일자·환경·걸린 시간 없이)",
    "extra": [{"title": "고칠 때 이어서 보낼 문장", "prompt": "...", "note": "이 문장으로 바뀌는 것"}],
    "setup": {"before": 2, "steps": [{"label": "처음이라면", "title": "터미널부터 엽니다", "text": "...",
      "groups": [{"name": "윈도우", "text": "...", "prompts": ["명령"], "src": [{"name": "공식 문서", "url": "..."}]}]}]}
  }
}
```

`page.skip`(선택, 카드 장 `num` 목록)은 그 장을 페이지 단계에서 빼고, `page.append`(선택, `[{"num", "text", "groups"}]`)는 카드 장 단계 밑에 페이지에만 글·명령을 덧붙인다(카드·영상은 그대로). `page.notice`(선택, `{"title", "text", "links": [{"name", "url", "note"}]}`)는 소개 아래 안내 상자. 섹션은 '준비물'(`page.prep`, 단계 앞)·단계·'결과 예시'(`page.result`)·'추가 명령어'(`page.extra`, casual은 '더 써 볼 문장')뿐이다. 날짜·테스트 환경·제작 과정 섹션은 없다(운영자 지적 2026-11-16, STYLE_GUIDE 7-1). 예전 필드는 오류 없이 넘긴다: `page.result` 항목 목록 `[{"k", "v"}]`은 일자·환경·미확인 범위 같은 항목을 빼고 보여 주고, `page.caution`은 '참고'로 나오며(새 게시물은 쓰지 않는다), 카드의 steps 장은 페이지에 붙지 않는다. 모든 글에서 날짜·'직접 넣어 본'·'저희' 같은 문장은 `agent/dm.py`가 문장째 뺀다(프롬프트 상자는 그대로). `page.setup`은 `{before, steps}` 묶음의 목록으로 여러 곳에 넣을 수 있다.

`page.setup`(선택)은 카드에는 없고 페이지에만 넣는 처음 하는 사람용 단계다(터미널 여는 법, 설치 등). 카드 장 `num`이 `before`인 단계 앞에 끼워 넣고 번호를 다시 매긴다. `groups`로 운영체제별 안내·명령(복사 상자)·출처를 나눈다. 명령은 공식 문서에서 확인한 것만, 출처 주소와 함께.

안내 페이지에는 카드의 순서 장(`num`이 있는 장과 `prompt` 장)이 단계로, 프롬프트는 복사 버튼이 달린 고정폭 상자로 들어간다. 출처는 자동(기준 날짜는 넣지 않는다). checks.py: `message` 900자 이하, 주소·AI 글투 금지, 캡션에 키워드 안내가 없으면 경고, 따라 하기·질문인데 `dm`이 없으면 경고.

### 배경음악 (`music`, 선택, 릴스·카드뉴스 표지 영상)

소리 없는 릴스는 렌더링에서 막힌다 (STYLE_GUIDE 6장). 카드형 모션 릴스는 음악이 없으면 코드로 만든 음악(`agent/music_gen.py`, 장면 전환에 박자)을 자동으로 깐다.

```json
"music": {
  "generate": true,
  "src": "(선택) 게시물 폴더 안 음원 파일. 상업 이용·저작자 표시 불필요 음원만",
  "credit": "출처·라이선스 (src를 쓰면 필수). 예: 유튜브 오디오 라이브러리 'OOO' (저작자 표시 필요 없음)",
  "volume": "(선택) 0~1.5",
  "seed": "(선택) 생성 음악 변주 번호"
}
```

### 따라 하기 릴스 (`type: "reel"` + `format: "howto"`)

영상 재료 없이 카드 장면에 모션을 입힌다 (`agent/motion.py`). 장 구성은 카드뉴스와 같고 1080x1920. 글은 인스타 안전 영역(세로 285~1250px) 안에 자동으로 놓인다. 프롬프트 장은 글자 수에 맞춰 더 오래 보여 준다 (초당 약 12자). 장면은 표지 포함 7개 이하가 좋다. 화면이 넘치면 `visual.height`를 줄이거나 제목을 한 줄로. 이 컴퓨터에 ffmpeg가 없으면 `frames/` 장면 이미지까지만 만들고 영상은 render.yml이 만든다.

## 인용 영상 장 (릴스 전용)

| kind | 필드 |
|---|---|
| `clip` | `src`(게시물 폴더 기준 영상 경로), `start`, `end`(초), `source`(예: "OpenAI 공식 YouTube"), `source_url`, `heading`, `highlight`, `caption`(우리 말 요약, 60자 이하) |

영상은 화면 가운데 가로로 꽉 차게 들어가고, 아래에 "영상 출처 · ○○"와 자막이 붙는다. 원본 소리는 그대로 나온다.

**인용 규칙 (checks.py가 검사):** 클립 하나 10초 이하, 클립 합계가 릴스의 40% 이하, 클립 말고 해설 장면이 표지 포함 3개 이상. 사람이 고른 영상만 쓴다(`inbox/clips/`).

## 영상 프레임 릴스 (type: "video")

릴스의 기본 형식. 위에 브랜드·제목·영어 부제, 가운데 네온 테두리 영상 창, 아래 시간에 맞춘 자막, 영상 아래 원작자 표기.

```json
{
  "type": "video", "rights": "permission", "credit": "@원작자", "rights_note": "11/15 DM으로 허락받음",
  "video": {"src": "clips/원본.mp4", "start": 0, "end": 45},
  "title": "한국어 제목\n2줄", "highlight": "강조", "title_en": "English subtitle line",
  "subtitles": [{"start": 0.3, "end": 3.5, "text": "자막 한두 줄", "highlight": "강조"}],
  "sources": [{"name": "원본 영상", "url": "https://..."}], "caption": "... 영상: @원작자 ...", "hashtags": []
}
```

- 영상 비율은 자동으로 맞춘다: 가로 영상(16:9, 21:9)은 창 높이를 비율에 맞추고 자막을 영상 아래에, 정사각형·세로 영상은 창을 최대 높이로 키우고 자막을 영상 위에 얹는다. 9:16처럼 아주 긴 세로 영상은 자르지 않고 양옆을 배경색으로 채운다.
- `rights`: `own`(직접 만든 영상), `permission`(원작자 허락), `license`(재사용 허락 라이선스). 남의 영상은 `credit`과 `rights_note`가 없으면 렌더링이 멈춘다. 쓴 소재(화풍·음악·글꼴·사진)의 라이선스도 `rights_note`나 `license`(선택, 어느 그림·영상 객체에나)에 적는다. 비상업(NC) 라이선스는 검사에서 막힌다 (STYLE_GUIDE 2-1 끝).
- 제목 한 줄 13자, 자막 한 줄 18자, 자막 2줄 이하.
- **각주 (선택, `subtitles[i].note` 또는 `video.notes: [{"start","end","text"}]`, 원본 시각):** 자막의 낯선 이름 뒤에 `*`를 달고(`데이비드 색스*가`), `note`에 `"* 데이비드 색스: 당시 백악관 AI·가상화폐 정책 총괄"`처럼 명사형 한 줄. 그 자막이 떠 있는 동안 영상 창 바로 아래 왼쪽(x 65~840, 28px)에 0.25초 페이드로 나타나고, 각주가 있으면 출처가 한 줄(50px) 내려간다. x 840을 넘으면 렌더링이 멈춘다. 직함은 대담 당시 기준(바뀌었으면 '당시'), 출처 2곳으로 확인.
- **자막 모션 (선택, `video.sub_motion: "rise"`):** 자막이 나올 때 0.3초 동안 아래에서 22px 올라오며 자리 잡는다. 화면 녹화처럼 글을 정적으로 띄우면 지루할 때 쓴다. 없으면 예전처럼 정적.
- **총소리 어택 살리기 (선택, `video.keep_transients: true`):** 마지막 소리 맞추기(`loudness.normalize`)의 1단계 압축을 건너뛰고 리미터만 쓴다. 게임 소리·음악을 미리 다듬어 섞은 `clips/source.mp4`에서 총소리 같은 짧은 소리가 뭉개지지 않게 할 때. 없으면 예전처럼 압축.
- **구간 경계 (start/end):** start는 첫 단어 '시작' 시각 - 0.2초, end는 마지막 단어 **'끝'** 시각 + 0.4초. `tighten.py` 출력 `words`의 `[단어, 시작, 끝]` 중 마지막 단어는 세 번째 값(끝)을 쓴다 (시작 시각 근처로 잡으면 마지막 말이 잘린다: 나델라 릴스 "rejected"). 다음 문장 첫소리가 들어가지 않게 한다. 렌더링할 때 video.py가 원본 소리 크기로 '첫 소리'와 '마지막 소리 끝'을 다시 찾아, end가 마지막 소리 끝 + 0.3초보다 앞이면 + 0.4초로 늘리고, 그 사이 다음 말이 들어오면 마지막 소리 끝 + 0.05초부터 0.12초 동안 소리를 줄여 무음으로 한다 (화면은 end까지). start 앞뒤에 앞 문장 꼬리가 있으면 그 소리만 무음 → 첫 소리 직전 페이드인. 문장 한가운데(말이 1.2초 넘게 끊김 없이 이어짐)면 렌더링이 멈춘다. 출력의 "끝: 마지막 소리 … → end …" / "시작: 첫 소리 …" 줄을 확인한다. 끄려면 `video.avoid_edge_check: false`. 끄고 경계를 손으로 정할 때(말이 빨라 소리 틈이 없을 때)는 `video.fade_out`(원본 시각, 보통 마지막 소리 끝 + 0.05초)·`video.fade_in`을 적으면 같은 페이드를 쓴다: end는 마지막 소리 끝 + 0.3초 이상으로 두고 다음 말은 fade_out으로 막는다.
- **자막 자리:** 우리 자막이 영상 창 안에 들어갈 때 자리는 **항상 영상 창 맨 아래(바닥)**다. 영상 창 위쪽에 자막을 다는 일은 없다 (운영자 결정 2026-11-16: "아래에 다는 게 맞다"). 자막 아래 끝이 안쪽 테두리 위 24px. 2줄 자막 높이 기준으로 고정해 1줄이어도 아래 끝선이 같다(들썩이지 않게). 원본에 박힌 글자(이름 자막·하단 자막·영어 자막)와 겹치면 순서대로: (1) 바닥에서 자막 글씨를 줄인다 50px → 44px → 40px (줄 간격도 함께, 40px 아래로는 줄이지 않음), (2) 그래도 겹치면 원본 글자 띠 바로 위로 조금 올린다. 단, 얼굴(턱·입)을 가리지 않게 올린 자막의 위 끝이 영상 창 아래쪽 1/3 안에 있을 때만 (얼굴 자동 검출이 없어 보수적으로), (3) 그래도 안 되면 바닥에 두고 겹침을 감수한다. 한 릴스 안에서는 글씨 크기·위치 하나로 통일(자막마다 바뀌지 않음). 렌더링 출력에 "자막: 영상 창 맨 아래, 50px" / "자막 크기 44px로 줄여 바닥 유지" / "자막: 영상 창 바닥에서 Npx 올림" / "겹침 감수: 12.3~15.0초 원본 글자와 겹침"(릴스 시각) 줄이 남는다. 겹침 감수가 나오면 PR 본문에 그 구간을 한 줄 적는다. 크기만 손으로 정하려면 `video.captions_size: 44`. `video.captions_pos: "top"`은 더 쓰지 않는다(적혀 있으면 경고 후 바닥). 영상 아래 빈칸이 안전 영역(1250px) 안에 들어가면 지금처럼 영상 아래에 둔다. **원본 글자를 띠로 가리지 않는다.** 박힌 글자 찾기를 끄려면 `video.avoid_burned: false`.

## 목록형 자료 릴스 (`type: "video"` + `list`, 운영자 결정 2026-11-16, 화면 수정 2026-11-17)

참고 형식 '34가지 조명 코드'. 결과 그림(4:5)이 화면을 가로 꽉 채우고, 항목마다 그림과 '번호 + 이름' 띠가 함께 바뀐다. `video` 대신 `list`를 쓰고, 나머지(`title`·`thumb`·`dm`·`caption`·`threads`)는 영상 프레임 릴스와 같다. 렌더링은 `agent/listreel.py` (render.py가 `list`를 보고 부른다). 예시 `samples/s14-list-reel` (자리표시 이미지), 실제 게시물 `posts/queue/2026-11-17-list-lighting`.

```json
{
  "type": "video", "format": "howto", "origin": "own", "length": "short", "rights": "own",
  "title": "AI 영상 만드는 사람에게\n꼭 필요한 조명 용어 20가지", "highlight": "조명 용어",
  "list": {
    "items": [{"name": "하이키", "en": "high-key", "desc": "밝고 그림자가 적은 조명입니다.",
               "type": "image", "src": "img/list/01.jpg", "mascot": true,
               "prompt": "Same grey sofa, same living room, same camera angle and framing. Change ONLY the lighting: high-key ..."}, ...],
    "hook": 10,
    "base": {"name": "원본 사진", "type": "image", "src": "img/list/00.jpg", "mascot": true},
    "scene": {"type": "image", "src": "img/list/scene.jpg", "mascot": true, "prompt": "(선택) 장면 기준 그림"}
  },
  "music": {"generate": true},
  "thumb": {"title": "...", "image": {"type": "image", "src": "img/list/10.jpg"}},
  "sources": [{"name": "FLUX.2 [klein] (Cloudflare Workers AI, 결과 이미지 제작 도구)", "url": "https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/", "kind": "tool"}],
  "dm": {"cta": "...", "banner": "...", "page": {
    "intro": "...", "list_title": "영상에 나온 조명 용어 20개", "list_intro": "...",
    "more": [{"name": "언더 라이팅", "en": "underlighting", "desc": "아래에서 위로 비추는 빛입니다.",
              "type": "image", "src": "img/more/underlighting.jpg", "mascot": true, "prompt": "..."},
             {"name": "키 라이트", "en": "key light", "desc": "장면을 비추는 가장 센 주된 빛입니다."}],
    "more_title": "추가 조명 용어 30개", "more_intro": "...",
    "usage": ["(선택) '사용법' 문장. 없으면 dm.py 종류별 기본 문구"]}}
}
```

| 필드 | 내용 |
|---|---|
| `list.items` | 화면 순서. `name`(화면 이름, 12자 이하, 영어 없이), `en`(영어 용어, DM 자료 페이지에만), `desc`(선택, 자료 페이지 한 줄 설명, 사실만), `src`(결과 그림, 4:5). 그림을 AI로 만들 때는 같은 객체에 `"type": "image"`, `"mascot": true`, `prompt`(영어, 바꿀 것만), 선택 `ref`(아래 "마스코트 그림") → render.yml이 만든다 |
| `list.hook` | 첫 화면(0~2초)에 제목 띠와 함께 보여 줄 항목 번호 (1부터, 기본 1). 가장 눈에 띄는 결과로 |
| `list.base` | 선택. 맨 앞 원본 줄(번호 00, 항목보다 1.3배 오래). "사진 한 장을 N가지로" 형식. `"mascot": true`에 prompt가 없으면 마스코트 기준 그림 그대로 |
| `list.scene` | 선택. 화면에 안 나오는 장면 기준 그림. 항목들이 `"ref": "img/list/scene.jpg"`로 이 그림을 참고해 같은 장면에서 한 가지만 바꾼다 (gen_images가 먼저 만든다) |
| `list.seconds` | 선택. 항목 하나 보여 주는 초. 없으면 전체가 29초 안팎이 되게 0.9~1.6초 사이에서 자동 |
| `list.per_page` | 선택. 음악 강한 박자를 넣는 묶음 크기 (기본 11) |
| `list.align` | 선택. `true`면 모든 장에서 마스코트 위치·크기를 기준 장(원본 줄, 없으면 첫 항목)에 맞춘다 (결과 비교 목록: 조명·그림체·고급 사진). 카메라 용어처럼 구도 자체가 결과인 목록은 `false` (가로 중심만 맞춤). 출력에 장마다 '정렬(일치 점수)', 확대 배율, 빈칸·확대 경고가 남는다. 일치 점수 0.30 미만이면 기준 자리 그대로 |
| `list.label` | 선택. 이름 띠: `"en"`(기본, 영어 이름만 크게), `"ko"`(한국어 크게 + 영어 작게, 그림체처럼 영어가 어색할 때), `"both"`(영어 크게 + 한국어 작게) |
| `list.items[].center` | 선택. 9:16으로 자를 때 가로 기준(0~1). 없으면 마스코트(연두색)를 찾아 자동 |
| `list.bpm`·`list.beats_per_item` | 선택. 박자 직접 지정. 없으면 한 박이 정수 프레임인 BPM 중 전체가 29초 안팎이 되는 값, 항목은 2박(필요하면 3·4박) |
| `list.voice` | 선택. `{"voice": "af_heart", "speed": 1.0, "say": {"07": "split lighting"}}` (agent/tts.py가 읽음). `"lang": "ko"`(선택, 기본 "en")면 MeloTTS 한국어로 항목 `name`(또는 say)을 읽는다. 목소리 파일은 `voice/<번호>.wav` |
| `list.hook_seconds` | 선택. 첫 화면 길이 (기본 2초) |
| `keywords` | 선택(모든 게시물). 캡션 첫 줄을 여는 검색어 목록 (예: `["AI 영상 프롬프트", "카메라 앵글"]`). checks.py가 첫 30자 안에 있는지 본다(없으면 해시태그, 그다음 제목 명사로 대신 본다). STYLE_GUIDE 9장 5번 |
| `list.hook_anim` | 선택, 기본 `true`. 첫 화면 후킹: 제목 줄마다 1.3배에서 쾅 박히며(0.95 넘침 → 1.0, 약 0.23초) 8분음표 간격(0.15~0.27초, 아니면 16분)으로 차례로 들어오고, `highlight` 단어는 녹색 면에 검은 글자로 한 박 번쩍, 그림은 줄이 박힐 때마다 짧게 흔들린다(확대 1.04~1.10배라 가장자리 빈칸 없음). 박히는 배율은 줄이 양옆 안전 영역을 넘지 않게 줄인다. 효과음(코드 합성, 샘플 없음): 0초 쿵, 둘째 줄부터 휙 + 타격, 목록 시작 앞 상승음 → 목록 시작 박에 드롭 붐. 음악(`make_hook_music drop_at`)은 첫 화면 동안 킥·클랩·하이햇만, 목록 시작에서 베이스·멜로디가 다 들어온다. `false`면 예전처럼 띠가 아래에서 올라오는 정지 제목 |
| `list.intro` | 선택, 기본 `false`. `true`면 예전처럼 제목만 있는 첫 화면(4박) 뒤에 목록 시작. 기본은 0초부터 1번 항목 + 맨 위 제목 띠(0초에 줄마다 쾅, `hook_anim`) + 그 아래 안내 한 줄, 3초 `dm.banner` 띠는 붙이지 않음 (운영자 결정 2026-11-17) |
| `list.cta_line` | 선택. 0초부터 제목 띠 아래 안내 한 줄. 없으면 "댓글 남기시면 전체 N개 DM으로"(N = items + `dm.page.more`, `dm.cta`가 있을 때만), `false`면 없음 |
| `list.stack` | 선택, 기본 `true`. 목록 쌓기 (이름 띠 아래, 안전 영역 바닥 1250px 안): 왼쪽 열 = 영상 항목 번호 목록(지난 것 흐리게, 지금 것 녹색, 아직 안 나온 것 `번호 ?`), 오른쪽 열(오른쪽 끝 x 840, 버튼 줄 안쪽) = 자료 페이지 추가 용어 자리 `16 ?` … `30 ?`('다음은?'·'더 있다' 궁금증, 운영자 2026-11-17 "목록에 ?로 15개 더"). 글씨 크기는 줄 수와 두 열이 안 겹치게 자동(줄 높이 26px 미만이면 렌더링이 멈춤) |
| `list.stack_more` | 선택, 기본 `true`. `false`면 오른쪽 열(추가 용어 '?' 자리)을 뺀다 |
| `list.flood` | 선택, 기본 `true` (`dm.page.more`가 있을 때만). 마지막 항목 바로 다음 박(쉼 없이, 운영자 2026-11-17 "실루엣 다음에 쉬는 시간 없이")부터 4박 동안 화면을 어둡게 하고, 추가 용어 영어 이름이 뒤에 흐리게 쏟아지며(가장자리 넘쳐도 됨), 목록 쌓기 오른쪽 열 `?` 자리가 위에서부터 빠르게 하나씩 녹색 면으로 번쩍 채워진다. 효과음: 커지는 스웰 + 자리마다 틱. 그 뒤 바로 `dm.cta` 끝 화면. 가운데 문구는 기본 없음, 꼭 필요하면 `list.flood_text`(짧게, 예: "나머지는 DM으로"). '15개 더'처럼 개수 문구는 쓰지 않는다 (운영자 2026-11-17) |

- **화면 (1080x1920):** 4:5 그림을 마스코트 중심으로 9:16만 잘라 화면 전체에 Lanczos 확대(약 1.41배, 그림 생성은 4:5 그대로). 첫 화면(4박)은 그림 + 제목 띠(2줄, 안전 영역 맨 위). 그 뒤 항목마다 그림 + 이름 띠(작은 녹색 번호 + 큰 영어 대문자, Pretendard Black 92px, 자간 넓게, '자료' 안내 띠 바로 아래). 띠는 단색 반투명 검정, 0.27초 등장 모션(아래에서 올라오며 자간이 좁혀짐). 긴 이름은 그 장만 글씨를 줄이고(최소 52px), 그래도 안 들어가면 렌더링이 멈춘다. 마지막 항목 2박 더 → `dm.cta` 끝 화면 2.5초. 그림 전환은 컷, 늘 박 위.
- **소리:** `music` 규칙 그대로(없으면 코드로 만든 후킹 비트 `make_hook_music`, 0초부터 킥·스네어·멜로디 훅, 크래시는 목록 시작·8개마다). `voice/<번호>.wav`(agent/tts.py, Kokoro-82M, 이 컴퓨터에서 미리 만들어 커밋)가 있으면 그 장면이 시작하는 박에 넣고, 말하는 동안 음악을 줄여 말이 음악보다 약 17dB 크게(RMS), 말이 없을 때 음악은 말보다 6dB 작게. 전체 -14 LUFS. 렌더링 출력에 BPM, 전환과 박의 차이, 말·음악 크기 차이가 숫자로 남는다. `voice/`가 없으면 음악만.
- **안내 띠(`dm.banner`):** 안전 영역 맨 위(285px), 3초부터 본편 끝까지, 그림 위에 얹힌다.
- **DM 자료 페이지 (`agent/dm.py`):** 소개 아래 `list_title` 묶음에 영상 항목, `more_title` 묶음에 추가 용어(`page.more`)가 번호를 이어서 들어간다. 항목마다 번호·한국어 이름·영어 용어(글자로만, 복사 상자 없음)·`desc`(뜻과 분위기 한 줄)·예시 그림(파일이 있을 때만, 안내 페이지 폴더 `docs/p/<id>/`에 가로 540px로 복사). 목록 위에는 '쓰는 법' 한 덩어리(용어를 요청 문장 어디에 넣는지): `dm.page.usage`(문장 목록, 선택, 제목은 `usage_title`)가 없으면 dm.py `LIST_USAGE`의 종류별 기본 문구(게시물 id `list-lighting`·`list-camera`·`list-art-style`·`list-luxury-photo`로 고름, `dm.page.kind`로 직접 지정 가능). `page.more`의 예시 그림도 `"type": "image"`·`"mascot": true`·`prompt`·`src`(`img/more/...`)로 적으면 render.yml이 만든다(하루 한도를 생각해 4~6장). **복붙 프롬프트는 싣지 않는다** (운영자 결정 2026-11-17, STYLE_GUIDE 7-1): 목록형이면 `page.extra`·`page.template`이 있어도 페이지에 나오지 않고, 소개 글의 "(복사 버튼)"과 '복사'가 든 문장은 페이지에서 빠진다. 페이지 제목·소개의 '만드는 사람'은 '제작자'로 바뀐다. 안내 문구(cta·banner·캡션)의 개수는 영상 + 추가 전체 수.
- **썸네일:** `thumb.image.src`에 목록 그림 하나를 그대로 써도 된다(이때는 `url`·`prompt` 없어도 됨). 4:5 그림이 9:16 화면을 꽉 채우게 잘린다. 썸네일 글씨(96px)로 2줄에 안 들어가는 운영자 제목은 `max_lines: 3`.
- **출처:** 직접 만든 결과물이라 소식 출처가 없다. 만든 도구 링크를 `"kind": "tool"`로 적는다 (dupes.py 같은 출처 검사에서 빠짐).
- **checks.py:** 항목 3개 이상, 항목마다 이름·그림, 그림 경로 겹침 금지(항목 수 = 그림 수), 제목·썸네일의 'N가지/N개' = 영상 항목 수, 길이(끝 화면 포함) 20~35초, `rights: own`, `hook` 범위, 마스코트 그림의 prompt·type, `page.more`의 name·en, `en` 없으면 경고.
- **그림 (마스코트):** 항목 그림은 마스코트 슬라임 AI 그림이다 (STYLE_GUIDE 1-1 "마스코트"). 게시물을 push하면 render.yml이 `gen_images.py`로 없는 그림만 만들고 렌더링까지 한다. 키(CF_ACCOUNT_ID, CF_API_TOKEN)가 Actions에만 있어서 이 컴퓨터에서 render.py를 돌리면 없는 그림은 회색 자리표시(번호만, `_ph/`에 잠깐 만들고 지움)로 틀만 렌더링한다. Actions에서 그림이 빠지면 렌더링이 멈춘다(자리표시 영상이 올라가지 않게). 그림을 다시 만들려면 프롬프트를 고치고 그 `src` 파일만 지운 뒤 push. AI 그림은 하루 상한(`config.json` `image_gen.daily_limit`, UTC 날짜 기준)이 있어서 넘으면 만든 데까지 두고 다음 날(한국 오전 9시 뒤) 이어서 만든다. 그동안 그 게시물은 렌더링되지 않아 게시되지 않는다.

## 순위 카운트다운 릴스 (`type: "video"` + `rank`, 운영자 요청 2026-11-17)

공개 자료의 순위를 10위 → 1위로 세는 릴스 (STYLE_GUIDE 6장 "순위 카운트다운 릴스"). `video` 대신 `rank`. 렌더링은 `agent/rankreel.py` (render.py가 `rank`를 보고 부른다). 그림이 없어 이 컴퓨터에서 바로 끝까지 렌더링된다. 실제 게시물 `posts/queue/2026-11-18-rank-ai-jobs`.

```json
{
  "type": "video", "format": "howto", "origin": "own", "length": "short", "rights": "own",
  "title": "AI에 가장 먼저
흔들릴 직업 TOP 10", "highlight": "TOP 10",
  "rank": {
    "items": [{"label": "통역사·번역가", "sub": "Interpreters and Translators", "value": 49.2,
               "desc": "(자료 페이지) 하는 일과 AI와 겹치는 일, 사실만"}, ...],
    "value_label": "AI 적용 점수", "value_max": 50, "value_decimals": 1, "value_unit": "",
    "avg": 15.9, "avg_label": "평균",
    "hook_count": 785, "hook_text": "{n}개 직업 중",
    "source_line": "출처: Microsoft Research 'Working with AI'"
  },
  "music": {"generate": true},
  "sources": [{"name": "...", "url": "https://arxiv.org/abs/..."}],
  "dm": {"cta": "...", "banner": "...", "page": {"intro": "...", "usage_title": "점수 읽는 법", "usage": ["..."],
         "list_title": "...", "list_intro": "...", "more": [{"label": "기자·뉴스 해설가", "sub": "...", "value": 38.3}],
         "more_title": "11위~30위", "more_intro": "..."}}
}
```

| 필드 | 내용 |
|---|---|
| `rank.items` | **1위부터** 차례로 (영상은 거꾸로 센다). 3~15개. `label`(화면 이름, 12자 이하), `sub`(선택, 작은 둘째 줄: 영어 원문 이름·직함), `value`(점수·비율, 숫자) 또는 `quote`(발언, 60자 이하, 화면에 글자가 차례로 찍힘) 중 하나 이상(둘 다 있으면 막대), `desc`(자료 페이지 설명), `source`(선택, `{name, url}`, 항목마다 출처가 다를 때 — 인물 발언 목록) |
| `rank.layout` | 선택. `"photo"`: 사진 화면 (순위표·뒤 숫자 없이 사진을 가운데에 밝게, 위 제목 띠 크게, 아래쪽 어두운 면 위에 순위 카드). 항목마다 `src`(사진)·`claim`(화면 한 줄 주장, 20자 이하, 예: 'AI와 겹치는 일: 번역·통역')·`credit`. 예: `posts/queue/2026-11-18-rank-ai-jobs`. `beats_per_item` 5(2.5초)가 읽기 좋음 |
| `rank.value_label` | 점수 줄 왼쪽 라벨 (예: "AI 적용 점수") |
| `rank.value_max` | 막대 끝 값 (축 오른쪽 숫자). 없으면 가장 큰 값. 값이 이보다 크면 오류 |
| `rank.value_decimals`·`value_unit` | 소수 자리(기본 1), 숫자 뒤 단위(선택, 예: "%") |
| `rank.avg`·`avg_label` | 선택. 막대 위 평균 눈금 (출처에서 계산한 값만) |
| `rank.hook_count`·`hook_text` | 선택. 첫 화면 카운터 (0부터 올라감). `hook_text`의 `{n}` 자리에 숫자 |
| `rank.intro`·`cta_line` | `list.intro`·`cta_line`과 같음 (기본: 0초에 바로 10위, 맨 위 제목 띠 + 안내 한 줄. `hook_count`는 `intro: true`일 때만 보임) |
| `rank.items[].src`·`img_x`·`credit` | 선택. 그 순위 장면 뒤 화면 전체 사진(게시물 폴더 안 jpg, 1080x1920·300KB 이하로 미리 잘라 둠), 가로 위치(%), 저작자·라이선스 (캡션 끝 '사진:' 줄에 모음) |
| `rank.source_line` | **필수.** 점수 줄 아래 작은 출처 한 줄 (40자 이하) |
| `rank.bpm`·`beats_per_item`·`hook_beats`·`reveal_beats`·`top_beats` | 선택. 기본 120 BPM, 순위 4박(2초), 첫 화면 4박, 1위 '?' 1박(0.5초), 1위 장면 5박 |
| `rank.mode: "intro"` | 선택. **발언 소개 릴스** (`agent/quotereel.py`, 운영자 2026-11-17 "예언 릴스는 지루하지 않게"): 순위·'?' 없이 첫 항목(가장 센 한마디)이 0초, 나머지는 `date`(YYYY-MM-DD) 순. 항목에 `who`(이름), `sub`(자리·행사), `date`, `quote`(기사 요약이면 따옴표 없이 '~라고 경고'), `key`(녹색으로 칠할 단어, 공백 구분), `note`(꼭 알아야 할 단서 한 줄, 원칙 10), `src`·`credit`(자유 이용 사진), `style`(사진 화풍: duo·halftone·scan·poster·pixel·ink, 직접 짠 CSS/SVG 효과. 비상업 라이선스 화풍 라이브러리는 쓰지 않음). 모션 그래픽(운영자 2026-11-17 "카드 뉴스 붙여놓은 느낌 말고 애니메이션 느낌으로, 스무스하게"): 항목이 가로로 놓인 세계를 카메라가 멈추지 않고 흘러가고(경계 앞뒤 0.35초 부드러운 패닝 + 머무는 동안 천천히 흐름, 층마다 다른 속도로 시차), 사진은 다음 사진이 확대된 채 밀려 들어오며 겹쳐 바뀌고, 큰 연도 숫자판이 주행 거리계처럼 굴러 넘어가며, 발언은 단어마다 떠오른다. 아래 연표 띠도 같이 흐른다. 효과음(음악 아래): 이동 휙, 제목 톡, 단어 뽁, 숫자판 째깍. `first_beats`(4 = 2초)·`beats_per_item`(6 = 3초)·`last_beats`(6). 음악 기본 `h5-fm-arp` |
| `thumb` | 선택. 없으면 첫 화면 끝(제목 + '?' 순위표)이 cover.jpg. 있으면 thumb.py가 덮어쓴다 |
| `dm.page.usage` | '읽는 법' 문장 목록 (점수 뜻, 단위 변환, 연구가 밝힌 해석의 선). `usage_title`로 제목 |
| `dm.page.more` | 이어지는 순위 (번호는 영상 순위 다음부터). `label`·`sub`·`value` |

- **checks.py:** 항목 수·이름 길이·이모지, value 또는 quote, 값이 1위부터 큰 순서, `value_max` 넘침, `source_line` 필수, 공개 자료 출처(url, kind tool 아님) 1개 이상, 제목·썸네일의 'TOP N' = 항목 수, 길이 20~35초, 1위 '?' 2초 안. 제목 끝 'TOP N'·'N위'는 앞에 꾸미는 말(~ㄴ/~ㄹ/~는)이 있으면 서술어가 있는 것으로 본다.
- **렌더링 출력:** BPM·드롭·1위 공개 시각, 효과음 개수, 안내 띠, 소리 크기(-14 LUFS). `frames/`는 0.3초·1초·카운트다운 중간 두 곳·1위 공개 직후·끝 화면.

## 연표 릴스 (`type: "video"` + `timeline`, 운영자 요청 2026-11-17)

실제 날짜 목록을 연표로 재생하는 릴스 (STYLE_GUIDE 6장 "연표 릴스"). `video` 대신 `timeline`. 렌더링은 `agent/timeline_reel.py` + `agent/timeline_reel.js` (render.py가 `timeline`을 보고 부른다). 그림이 없어 이 컴퓨터에서 바로 끝까지 렌더링된다. 실제 게시물 `posts/queue/2026-11-19-reel-ai-model-pace`.

| 필드 | 내용 |
|---|---|
| `timeline.events` | `[{date: "YYYY-MM-DD", lab, name, url}]` 5개 이상, 날짜 순. `lab`은 줄(OpenAI·Google·Anthropic·Meta·xAI·DeepSeek). `url`은 공식 발표 |
| `timeline.periods` | 끝 표의 기간 `[["2020~22년", 2020, 2022], ...]` (선택, 없으면 해마다) |
| `timeline.unit_note` | 연표 아래 작은 출처 줄 (예: "주요 AI 모델 55개 · 각 회사 공식 발표") |
| `timeline.metr` | 선택: 추세선 `{label, long, recent, recent_from, long_months, recent_months, source}`. 쓰면 sources에 METR 원문 |
| `timeline.thumb_src` | 렌더링이 그리는 썸네일 바탕 그림 경로 (`thumb.image.src`와 같게, url·prompt 없어도 됨) |

- **checks.py:** 날짜 형식·순서, url, rights own, METR 출처, 길이 20~35초. **렌더링:** 글자 폭·버튼 줄 겹침 검사, 기간별 평균 간격·효과음·소리 크기 출력, `frames/` 미리보기.
- DM 자료 페이지는 `dm.page.setup.steps`(해마다 한 단계, 모델마다 `groups`의 이름·날짜·공식 발표 링크)로 전체 연표를 싣는다.

## 릴스 썸네일 (`thumb`)

릴스(`type: "video"`)에는 꼭 넣는다. `cover.jpg`로 만들어져 프로필 격자와 피드에 보인다. 1080x1920, 그림이 꽉 차고 아래가 어두워지며 가운데 정렬 제목 2줄, 그 아래 작은 TOKEN WAR.

**그림은 빈칸 없이 꽉 채운다.** 영상 장면(16:9)을 그대로 넣으면 위아래가 검게 빈다. 인물 쪽을 세로 9:16으로 잘라 1080x1920으로 만든다: `ffmpeg -nostdin -ss <초> -i clips/source.mp4 -frames:v 1 -vf "crop=<w>:<h>:<x>:<y>,scale=1080:1920:flags=lanczos" img/thumb.jpg` (w = h×9/16). 위아래에 검은 띠가 있으면 thumb.py가 멈춘다. 제목·인물 표기·TOKEN WAR는 안전 영역(285~1250px) 안에 자동으로 놓인다.

```json
"thumb": {
  "title": "AI 피싱 시대,\n2중 보안은 필수다",
  "highlight": "2중 보안",
  "person": {"name": "Jensen Huang", "desc": "엔비디아 CEO"},
  "image": {"type": "image", "src": "img/thumb.jpg",
            "url": "https://nvidianews.nvidia.com/... (실물 이미지, 있으면)",
            "prompt": "a single giant glossy blue padlock floating in dark space, ... photorealistic 3D render",
            "position": "center 30%"}
}
```

| 필드 | 내용 |
|---|---|
| `title` | 2줄, 줄당 13자 이하. 머리말 없이 제목만 |
| `highlight` | 녹색으로 칠할 한 구절 (선택) |
| `person` | 실물 인물 사진일 때 이름·설명. 왼쪽, 제목 위에 작게 (선택) |
| `sub` | 제목 아래 작은 한 줄 (선택, 되도록 비움) |
| `image.url` | 1순위 실물 이미지 주소. Actions가 내려받음 |
| `image.prompt` | 2순위 AI 이미지 설명(영어). `url`이 없거나 내려받기에 실패하면 만듦 |
| `image.position` | 그림의 어느 부분을 보여줄지 (CSS object-position, 기본 `center 30%`) |

### 영상 자르기 (`video.crop`)

**자동으로 피한다:** 위 "자막 자리" 순서(바닥 → 글씨 줄이기 → 원본 글자 띠 위로 조금 → 겹침 감수). 자막은 항상 바닥. 아래 `crop`·`captions_at`는 손으로 정할 때만 쓴다.

원본 화면에 자막이 박혀 있거나 이름표(로어서드)가 있으면 우리 자막과 겹친다. `"crop": {"top": 0, "bottom": 0.7}`처럼 원본 높이의 어느 부분만 쓸지 적으면 그 아래를 잘라낸다. 인물 얼굴이 잘리지 않는지 미리보기로 확인한다.

### 박힌 자막 피하기 (`video.captions_size`, 예전 `captions_pos`·`captions_at`)

지금은 자동 자리 잡기에 맡기고, 크기만 손으로 정할 때 `captions_size`(50/44/40)를 쓴다. `captions_pos: "top"`은 더 쓰지 않는다 (자막은 항상 바닥, 적혀 있으면 경고 후 무시). 아래 `captions_at`은 예전 게시물 호환용으로만 남아 있다 (자막이 어중간하게 떠 보여 새 게시물에는 쓰지 않는다). 원본 화면에 영어 자막이 박혀 있으면 `"captions_at": 0.72`처럼 그 자막의 위쪽 끝 위치(원본 높이 비율)를 적는다. 우리 한국어 자막이 그 바로 위에 놓인다. 원본은 확대하지 않는다. (`video.crop`은 꼭 필요할 때만. 얼굴이 크게 확대돼 부자연스러워진다.)

## 모든 게시물 공통: `hashtags`

`"hashtags": ["#제미나이", "#AI활용법", "#토큰전쟁"]` — 3~5개. 주제 이름 1~2 + 한국어 분야 1~2 + #토큰전쟁. 흔한 태그(#reels #fyp #좋아요 등) 금지 (STYLE_GUIDE 7장, checks.py).

## 모든 게시물 공통: `topic`

`"topic": ["젠슨 황", "AI 안전", "엔비디아"]` — 핵심 대상 2~4개(인물·회사·제품·사건). `agent/dupes.py`가 최근 게시물과 겹치는지 검사하는 데 쓴다.

## 릴스 공통: `origin` (선택)

`"origin": "own"` (이 컴퓨터에서 직접 만든 결과물을 보여 주는 릴스: 화풍 스킬, 게임 실행, 따라 하기, 자료 묶음) 또는 `"quote"` (인터뷰·발표 인용 릴스). 주간 계정 분석이 data/reel_insights로 두 갈래의 넘김·시청 비율·공유를 비교한다. STYLE_GUIDE 9-0.

## 릴스 공통: `length` (선택)

`"length": "short"` (20~35초, 가장 강한 구간·결과 하나) 또는 `"long"` (1분 언저리). 길이별 시청 비율 비교용(data/reel_insights.md, 계정 분석 에이전트가 읽음). 없으면 길이로 짐작한다. STYLE_GUIDE 6장.

## 모든 게시물 공통: `threads` (선택, 스레드 글)

같은 소식의 스레드(Threads) 글 버전. 없으면 스레드에 올리지 않는다 (예전 게시물 그대로). 캡션을 쓸 때 같이 쓴다. 쓰는 법은 STYLE_GUIDE 7-2.

```json
"threads": {
  "text": "테슬라 사이버캡, 이제 개인도 살 수 있습니다.

차값은 2만 9,990달러인데, 움직이려면 월 299달러 구독이 따로 붙습니다.
운전대가 없어서 내가 직접 몰 수는 없습니다.

결국 '내 차'보다 개인 로보택시에 가깝습니다.",
  "images": ["cover", 2],
  "topic": "AI Threads",
  "replies": ["출처: 테슬라 로보택시 공식 X, Electrek (11월 13일)
https://electrek.co/..."]
}
```

| 필드 | 내용 |
|---|---|
| `text` | 본글. 500자 이하(이모지는 UTF-8 바이트 수로 셈, 😀 = 4자). **링크·해시태그 금지** |
| `images` | 선택. 카드뉴스는 장 번호(1부터, 렌더링된 slides 순서) 또는 `"cover"`(표지), 릴스는 `"cover"`(썸네일)만. 없으면 글만. 2장 이상이면 캐러셀, 10장 이하 |
| `topic` | 선택. 주제 태그 1개 (기본 `"AI Threads"`). 50자 안, `.`·`&`·`#` 없이 |
| `replies` | 선택. 본글 아래 내 답글로 차례로 올라간다. 출처 링크는 여기에 (답글 하나에 링크 5개 이하, 500자 이하) |

`checks.py`가 글자 수·본문 링크·주제 태그·장 번호·AI 글투·반응 구걸을 검사하고, 인스타 캡션과 똑같은 문장이 있으면 경고한다. 게시는 `agent/publish.py`가 인스타 게시 뒤 `config.json`의 `threads_delay_min`(40분)이 지나면 한다 (`agent/threads.py`). 결과는 published.json의 `threads_id`, `threads_permalink`. 실패하면 `threads_error`(3번까지 다시 시도), 인스타 게시 뒤 `threads_max_age_hours`(12시간)가 넘으면 `threads_skipped`.
