# TOKEN WAR 에이전트 (@tokenwar_ai)

매일 AI 소식을 찾아 카드뉴스와 릴스를 만들고 인스타그램에 올리는 자동화.

```
매일 아침  Claude 예약 작업 ── AGENT.md 절차대로 리서치 → 글 작성 → 이미지·영상 렌더링
              │
              ▼  (검토 모드: Pull Request / 자동 모드: main에 바로)
           GitHub 저장소 posts/queue/
              │
              ▼  15분마다 확인, 게시 시각이 되면
           GitHub Actions ── 인스타 공식 API로 게시 → posts/published/로 이동
```

## 폴더

| 경로 | 내용 |
|---|---|
| `STYLE_GUIDE.md` | 문체, 주제 고르기, 시리즈, 이미지 규칙 |
| `TEMPLATES.md` | 표지·본문 유형과 post.json 형식 |
| `AGENT.md` | 매일 실행되는 에이전트의 절차 |
| `config.json` | 모드(review/auto), 게시 시각, 브랜드 색, 글자 수 제한 |
| `agent/render.py` | post.json → 이미지(JPEG)·릴스(MP4) |
| `agent/checks.py` | 글자 수, 금지어, 출처 개수 검사 |
| `agent/publish.py` | 인스타 게시 (GitHub Actions에서 실행) |
| `samples/` | 예시 게시물 |
| `assets/music/` | 릴스 배경음악 (저작권 걱정 없는 mp3를 넣으면 무작위로 사용) |
| `assets/manual/` | 직접 쓰고 싶은 이미지 |

## 처음 설정

1. **저장소를 공개(Public)로 만든다.** 인스타 서버가 이미지와 영상을 공개 주소(jsDelivr CDN)로 가져가기 때문이다. 토큰은 Secrets에 있으니 공개돼도 안전하다.
2. **인스타 토큰 넣기:** 저장소 Settings › Secrets and variables › Actions › New repository secret
   - 이름 `IG_ACCESS_TOKEN`, 값은 Meta 개발자 앱에서 받은 토큰
   - AI 표지 그림용: `CF_ACCOUNT_ID`(Cloudflare 계정 ID), `CF_API_TOKEN`(Workers AI 권한만 준 토큰). 하루 무료 한도 안에서 약 170장.
3. **토큰 자동 연장 (선택, 권장):** 토큰은 60일 뒤 만료된다. GitHub Settings › Developer settings › Fine-grained tokens에서 이 저장소만, 권한 "Secrets: Read and write"로 토큰을 만들고 `GH_PAT`라는 이름으로 Secrets에 넣는다. 매달 1일과 20일에 자동으로 연장된다.
4. **Actions 켜기:** 저장소 Actions 탭에서 워크플로 실행을 허용한다.
5. **시험 게시:** Actions › 인스타 게시 › Run workflow. 올릴 게 없으면 "올릴 시각이 된 게시물 없음"이 나오면 정상.

## 매일 쓰는 법

- **검토 모드 (`config.json`의 `"mode": "review"`)**: 매일 아침 Pull Request가 열린다. 휴대폰 GitHub 앱에서 이미지와 캡션을 보고 **Merge**를 누르면 게시 시각에 올라간다. 마음에 안 들면 PR에 댓글로 고칠 점을 남기거나 닫는다.
- **자동 모드 (`"auto"`)**: 사람 확인 없이 게시 시각에 올라간다. 2주쯤 검토 모드로 품질을 확인한 뒤 바꾸는 것을 권장.
- 게시에 실패하면 GitHub가 이메일로 알려주고, 해당 게시물 폴더에 `error.log`가 남는다. 3번 실패하면 더 시도하지 않는다. 원인을 고친 뒤 `error.log`를 지우면 다시 시도한다.

## 직접 만들어 보기

```bash
pip install playwright requests
python agent/render.py samples/s1-nvidia
```
