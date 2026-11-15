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

## 게시물 형식 (`format`, 선택)

`"format": "howto" | "ask" | "weekly" | "news"`. 없으면 예전처럼 동작한다. `howto`·`ask`는 `kind: prompt` 장이 1개 이상 있어야 렌더링된다 (checks.py). 근거는 STYLE_GUIDE 3-1 (ai.trend.kr 상위 게시물 분석).

### 따라 하기 (`format: "howto"`)

| 순서 | 장 | 만드는 법 |
|---|---|---|
| 1 | 표지 | `layout: image`. 그림은 **실제 결과물**(직접 돌려 본 답 화면, 공식 예시). 제목은 얻는 것을 약속 ("구글 검색에 물으면 여행 일정표가 나옵니다") |
| 2~ | 단계마다 한 장 | `body`(누를 곳) 또는 `prompt`(넣을 글). 위쪽 실제 화면, `num` 1·2·3으로 순서. 프롬프트는 장 안에 글자로 넣는다 (DM으로만 주지 않는다) |
| | 결과 | `body` + 실제 결과 화면. 무엇이 나왔는지 사실만 |
| | 주의할 점 | 결과에서 실제로 틀린 점, 켜야 할 설정, 다른 AI에서도 되는지. 직접 해 보고 확인한 것만 |
| 끝 | (자동) 마지막 장 | |

예시: `samples/s12-howto-ai-mode` (카드뉴스), `samples/s13-howto-ai-mode-reel` (같은 내용의 카드형 모션 릴스).

### 나를 알려 주는 질문 (`format: "ask"`)

따라 하기와 같은 틀. 단계 장이 `prompt` 장 3~4개(질문 1~4)이고 `prompt_label`을 "질문 1"처럼 쓴다. 장마다 위쪽에 실제 답변 화면(이름·이메일 같은 개인정보는 가린다), 아래 질문 전문. 질문은 같은 대화창에서 순서대로 보내는 것이어야 한다. 끝에서 두 번째 장은 조건(기억 기능을 켜야 잘 됨, 다른 AI에서도 되는지).

### 댓글 자동 DM (`dm`, 따라 하기·질문 게시물)

댓글 키워드 '받기' → 팔로우한 사람에게 안내 페이지 링크 DM (STYLE_GUIDE 7-1). 렌더링할 때 `agent/dm.py`가 게시물 폴더에 `dm.md`(Zorcha에 붙여 넣을 설정 메모)와 `docs/p/<id>/index.html`(GitHub Pages 안내 페이지)을 만든다. 예시 폴더에서는 `page.html`로만 만든다 (`samples/s12-howto-ai-mode`).

```json
"dm": {
  "keyword": "받기",
  "message": "DM 문구 3줄 (주소 없이)",
  "comment_reply": "(선택) 댓글 공개 답글. 기본: DM으로 보내 드렸어요. 안 보이면 메시지 요청함을 확인해 주세요.",
  "follow_text": "(선택) 팔로우 요청 문구. 기본값이 있음",
  "button": "(선택) 링크 버튼 이름. 기본: 자료 보기",
  "page": {
    "intro": "안내 페이지 첫 문단",
    "result": "직접 돌려 본 결과 (사실만)",
    "extra": [{"title": "고칠 때 이어서 보낼 문장", "prompt": "...", "note": "돌려 본 결과"}],
    "caution": ["주의할 점 (카드의 steps 장 항목은 자동으로 붙음)"]
  }
}
```

안내 페이지에는 카드의 순서 장(`num`이 있는 장과 `prompt` 장)이 단계로, 프롬프트는 복사 버튼이 달린 고정폭 상자로 들어간다. 출처와 기준 날짜는 자동. checks.py: `message` 900자 이하, 주소·AI 글투 금지, 캡션에 키워드 안내가 없으면 경고, 따라 하기·질문인데 `dm`이 없으면 경고.

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
- `rights`: `own`(직접 만든 영상), `permission`(원작자 허락), `license`(재사용 허락 라이선스). 남의 영상은 `credit`과 `rights_note`가 없으면 렌더링이 멈춘다.
- 제목 한 줄 13자, 자막 한 줄 18자, 자막 2줄 이하.

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

**자동으로 피한다 (video.py):** 우리 자막이 영상 안으로 들어갈 때, 자막마다 그 시간대 원본 프레임에서 박힌 글자 줄(이름 자막·하단 자막·영어 자막)을 찾는다. 겹치면 (1) 60px 안으로 올려 피할 수 있으면 그 자막만 올리고, (2) 안 되면 그 릴스의 자막 전체를 영상 창 위쪽(보통 원본 위쪽 빈 배경)으로 옮긴다. **원본 글자를 띠로 가리지 않는다** (운영자 결정: 자막만 보이게). (3) 그래도 겹치면 경고만 하니 손으로 정한다. 렌더링할 때 무엇을 했는지 출력하니, 미리보기로 얼굴을 덮지 않는지 본다. 끄려면 `video.avoid_burned: false`. 아래 `crop`·`captions_at`는 손으로 정할 때만 쓴다 (`captions_at`을 적으면 자동 피하기는 하지 않는다).

원본 화면에 자막이 박혀 있거나 이름표(로어서드)가 있으면 우리 자막과 겹친다. `"crop": {"top": 0, "bottom": 0.7}`처럼 원본 높이의 어느 부분만 쓸지 적으면 그 아래를 잘라낸다. 인물 얼굴이 잘리지 않는지 미리보기로 확인한다.

### 박힌 자막 피하기 (`video.captions_at`)

원본 화면에 영어 자막이 박혀 있으면 `"captions_at": 0.72`처럼 그 자막의 위쪽 끝 위치(원본 높이 비율)를 적는다. 우리 한국어 자막이 그 바로 위에 놓인다. 원본은 확대하지 않는다. (`video.crop`은 꼭 필요할 때만. 얼굴이 크게 확대돼 부자연스러워진다.)

## 모든 게시물 공통: `hashtags`

`"hashtags": ["#제미나이", "#AI활용법", "#토큰전쟁"]` — 3~5개. 주제 이름 1~2 + 한국어 분야 1~2 + #토큰전쟁. 흔한 태그(#reels #fyp #좋아요 등) 금지 (STYLE_GUIDE 7장, checks.py).

## 모든 게시물 공통: `topic`

`"topic": ["젠슨 황", "AI 안전", "엔비디아"]` — 핵심 대상 2~4개(인물·회사·제품·사건). `agent/dupes.py`가 최근 게시물과 겹치는지 검사하는 데 쓴다.
