# 템플릿 사용법

`post.json`의 `slides` 배열로 장을 만든다. 첫 장은 표지(`kind: "cover"`), 그 뒤는 본문 장이다. 마지막 장(슬로건·출처)은 자동으로 붙는다. 실제 예시는 `samples/` 폴더에 있다.

## 표지 (cover)

모든 표지는 위쪽에 큰 시각 요소, 아래쪽에 **태그 상자 → 제목 2줄 → 부제** 순서로 글이 들어간다.

| 필드 | 설명 |
|---|---|
| `layout` | `visual`, `icon`, `number`, `list`, `word` 중 하나 |
| `tag` / `tag_sub` | 태그 상자. 예: `전황` · `엔비디아`, `오픈소스` · `2.2천★` |
| `title` | 2줄 이하, 줄당 17자 이하. 줄바꿈은 `\n` |
| `highlight` | 제목 안에서 녹색으로 칠할 부분 |
| `sub` | `"이름 · 한 줄 설명"` 형식. 앞부분은 굵게 표시된다 |
| `visual` | 위쪽에 들어갈 시각 요소 (아래 표) |

| layout | 언제 쓰나 | visual 예 |
|---|---|---|
| `visual` | 기능·설정·대화를 보여줄 때 | `settings`, `chat`, `terminal`, `image` |
| `icon` | 앱·도구 하나를 소개할 때 | `monogram` (로고 이미지 또는 글자) |
| `number` | 숫자 하나가 핵심일 때 | `number` |
| `list` | TOP 5, 도구 모음 | `tiles` |
| `word` | AI 용어 시리즈 | 없음. 대신 `word`, `word_desc`, `wall`(배경 단어 목록), `label` |

## 본문 장

| kind | 용도 | 필드 |
|---|---|---|
| `body` | 일반 설명 | `heading`, `highlight`, `body`, `point`(선택), `visual`(선택, 넣으면 위쪽에 그림) |
| `stat` | 숫자 강조 | `value`, `unit`, `label`, `heading`, `body` |
| `steps` | 따라 하기, 체크리스트 | `heading`, `items`: [{`title`, `text`}] 2~4개 |
| `compare` | 비교, 전후 | `heading`, `left`/`right`: {`label`, `items`, `on`} |

## 인용 영상 장 (릴스 전용)

| kind | 필드 |
|---|---|
| `clip` | `src`(게시물 폴더 기준 영상 경로), `start`, `end`(초), `source`(예: "OpenAI 공식 YouTube"), `source_url`, `heading`, `highlight`, `caption`(우리 말 요약, 60자 이하) |

영상은 화면 가운데 가로로 꽉 차게 들어가고, 아래에 "영상 출처 · ○○"와 자막이 붙는다. 원본 소리는 그대로 나온다.

**인용 규칙 (checks.py가 검사):** 클립 하나 10초 이하, 클립 합계가 릴스의 40% 이하, 클립 말고 해설 장면이 표지 포함 3개 이상. 사람이 고른 영상만 쓴다(`inbox/clips/`).

## 시각 요소 (visual)

| type | 필드 | 예 |
|---|---|---|
| `image` | `src` (게시물 폴더 기준 경로), `fit` | 오픈소스 저장소 화면, 직접 넣은 사진 |
| `monogram` | `text` 또는 `src` | 앱 아이콘 타일 |
| `tiles` | `items`: [{`text` 또는 `src`}] 최대 6개 | TOP 5 아이콘 묶음 |
| `settings` | `title`, `label`, `options`, `selected`, `badge` | 공유 범위 설정 화면 |
| `chat` | `items`: [{`role`: user/ai, `text`, `highlight`}] | 질문과 AI 답 |
| `terminal` | `title`, `lines` (`$` 명령, `#` 주석, `✓` 완료) | 코드·명령 실행 |
| `bars` | `items`: [{`label`, `value`, `display`, `on`}], `unit` | 가격·성능 비교 |
| `timeline` | `items`: [{`date`, `text`, `on`}] | 사건 순서 |
| `number` | `value`, `unit`, `caption` | 핵심 숫자 |

`settings`, `chat`, `terminal`은 특정 회사 화면을 따라 그리지 않은 **일반적인 모양**이다. 실제 제품 화면처럼 보이게 꾸미지 않는다.
