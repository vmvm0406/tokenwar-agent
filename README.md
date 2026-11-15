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

1. **저장소를 공개(Public)로 만든다.** 인스타 서버가 이미지와 영상을 공개 주소(GitHub Pages, `docs/media/`)로 가져가기 때문이다. 게시 작업이 그때그때 미디어를 `docs/media/`에 올리고, 게시가 끝나면 지운다. Settings › Pages에서 `main` 브랜치 `/docs` 폴더로 켜 둔다. 토큰은 Secrets에 있으니 공개돼도 안전하다.
2. **인스타 연결 (Facebook 로그인 방식):** 경쟁 계정 조회수 분석(Business Discovery)이 이 방식에서만 되므로 이쪽으로 한다.
   - 인스타 @tokenwar_ai를 Facebook 페이지에 연결한다 (인스타 설정 › 계정 센터, 또는 페이지 설정 › 연결된 계정).
   - Meta 개발자 앱(비즈니스 유형)에서 Facebook 로그인을 추가하고 권한 `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `business_management`을 받는다.
   - 그래프 API 탐색기에서 사용자 토큰 → 장기 토큰으로 바꾼 뒤 `me/accounts`로 **페이지 토큰**을 받는다 (장기 사용자 토큰에서 받은 페이지 토큰은 만료되지 않는다).
   - `me/accounts?fields=instagram_business_account`로 인스타 비즈니스 계정 ID를 확인한다.
   - Secrets에 `IG_ACCESS_TOKEN`(페이지 토큰), `IG_USER_ID`(인스타 비즈니스 계정 ID)를 넣는다.
   - AI 표지 그림용: `CF_ACCOUNT_ID`, `CF_API_TOKEN` (넣어 둠).
3. **(인스타 로그인 방식을 쓸 때만)** 저장소 Variables에 `IG_API_HOST=graph.instagram.com`을 넣고, 60일 만료 토큰 연장을 위해 `GH_PAT`(이 저장소 Secrets 읽기·쓰기 권한 토큰)를 Secrets에 넣는다. 이 방식에서는 경쟁 계정 분석이 안 된다.
4. **Actions 켜기:** 저장소 Actions 탭에서 워크플로 실행을 허용한다.
5. **시험 게시:** Actions › 인스타 게시 › Run workflow. 올릴 게 없으면 "올릴 시각이 된 게시물 없음"이 나오면 정상.

## 회원님 컴퓨터에서 돌리기 (Claude Code)

매일 작업은 윈도우 컴퓨터의 Claude Code가 한다 (`LOCAL.md`). 컴퓨터를 켜서 로그인하면 3분 뒤, 그리고 9:30·12:30·15:30에 자동으로 확인하고, 오늘 카드뉴스와 릴스가 없으면 만든다.

처음 한 번: 관리자 권한 PowerShell에서 `scripts/setup-local.ps1`을 실행하고, 안내대로 `claude`와 `gh auth login`으로 로그인한다.

매일 작업은 전용 저장소 `%USERPROFILE%\tokenwar-daily`에서만 돈다 (없으면 처음 실행할 때 받는다). 시작할 때마다 최신 main을 받고, 지난 실행이 남긴 변경은 `git stash`에 치워 둔다. Code 탭에서 쓰는 `tokenwar-agent` 폴더와는 겹치지 않는다. 그래서 `inbox/clips/`에 넣은 영상이나 고친 규칙은 **main에 push해야** 매일 작업이 본다.

## 매일 쓰는 법

- **검토 모드 (`config.json`의 `"mode": "review"`)**: 매일 아침 Pull Request가 열린다. 휴대폰 GitHub 앱에서 이미지와 캡션을 보고 **Merge**를 누르면 게시 시각에 올라간다. 마음에 안 들면 PR에 댓글로 고칠 점을 남기거나 닫는다.
- **검토 페이지**: https://vmvm0406.github.io/tokenwar-agent/review/ — 열린 검토 PR의 릴스 영상을 바로 재생하고 카드 장을 옆으로 넘겨 본다 (GitHub PR 화면에서는 영상·카드가 안 보임). 캡션·해시태그·출처도 함께. 괜찮으면 '승인(Merge)하러 가기'로 PR에 가서 Merge, 아니면 '고칠 점 남기기'. PR이 바뀌면 몇 분 안에, 아니면 30분마다 새로 만든다.
- **자동 모드 (`"auto"`)**: 사람 확인 없이 게시 시각에 올라간다. 2주쯤 검토 모드로 품질을 확인한 뒤 바꾸는 것을 권장.
- 게시에 실패하면 GitHub가 이메일로 알려주고, 해당 게시물 폴더에 `error.log`가 남는다. 3번 실패하면 더 시도하지 않는다. 원인을 고친 뒤 `error.log`를 지우면 다시 시도한다.

## 직접 만들어 보기

```bash
pip install playwright requests
python agent/render.py samples/s1-nvidia
```

## 토큰 갱신 (점검 이슈가 열렸을 때, 3분)

1. https://developers.facebook.com/tools/explorer/ 에서 앱 `tokenwar-publisher` 선택, 권한 6개(instagram_basic, instagram_content_publish, instagram_manage_insights, pages_show_list, pages_read_engagement, business_management) 확인 → **Generate Access Token** → 토큰전쟁 AI뉴스 페이지와 tokenwar_ai만 선택.
2. 토큰 칸 왼쪽 (i) → **액세스 토큰 도구에서 열기** → **액세스 토큰 확장** → 나온 장기 토큰 복사.
3. 탐색기로 돌아와 토큰 칸에 장기 토큰을 붙여넣고 `me/accounts?fields=name,access_token` 제출 → 토큰전쟁 AI뉴스의 `access_token`(페이지 토큰, 만료 없음) 복사.
4. 저장소 Secrets의 `IG_ACCESS_TOKEN`을 새 값으로 바꾸고, Actions › 인스타 토큰 점검 › Run workflow로 확인.

Facebook 비밀번호를 바꾸면 페이지 토큰도 무효가 되니 그날 같이 갱신한다.
