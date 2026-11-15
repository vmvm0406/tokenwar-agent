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
| `series_label` | 머리말을 시리즈 이름 대신 다른 말로 쓸 때 (예: "속보") |

| layout | 위쪽 | 필드 |
|---|---|---|
| `big` | 화면을 꽉 채우는 녹색 큰 글자 (숫자나 단어, 가장자리에서 잘려도 됨) | `big`(7자 이하), `big_note`(그 아래 한 줄) |
| `list` | 녹색 가로선으로 나눈 번호 목록 (TOP 3~5, 체크리스트) | `items` 2~5개, 각 14자 이하 |
| `image` | 실제 이미지나 AI 이미지 (위쪽 꽉 채움, 아래로 어두워짐) | `visual: {"type": "image", "src": "img/cover.jpg"}`, AI로 만들 때는 `"prompt": "영어 장면 묘사"` 추가 |

## 본문 장

| kind | 용도 | 필드 |
|---|---|---|
| `body` | 일반 설명 | `heading`, `highlight`, `body`, `point`(굵은 녹색 선 아래 큰 녹색 문장), `visual`(선택) |
| `stat` | 숫자 하나가 핵심 | `value`, `unit`, `label`(문장으로), `heading`, `body` |
| `steps` | 따라 하기, 체크리스트 | `heading`, `items`: [{`title`, `text`}] 2~4개 |
| `compare` | 비교, 전후 | `heading`, `left`/`right`: {`label`, `items`, `on`} |

## 그림 (visual)

| type | 필드 | 쓰는 곳 |
|---|---|---|
| `image` | `src` (게시물 폴더 기준), `fit`, `prompt`(선택) | 실제 이미지. 오픈소스 저장소 화면(라이선스 확인), 직접 넣은 사진. `prompt`가 있고 파일이 없으면 GitHub Actions가 AI로 만든다 (STYLE_GUIDE 2-1) |
| `bars` | `items`: [{`label`, `value`, `display`, `on`}], `unit` | 실제 숫자 비교 (가격, 점수) |
| `timeline` | `items`: [{`date`, `text`, `on`}] | 사건 순서 |

가짜 UI 화면(설정창, 대화창, 터미널), 아이콘 타일, 점 무늬 배경은 쓰지 않는다.

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
