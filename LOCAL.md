# 회원님 컴퓨터에서 도는 하루 작업 (Claude Code)

윈도우 작업 스케줄러가 `scripts/run-local.ps1`을 실행하면, 그 안에서 Claude Code가 이 문서대로 일한다.
작업 폴더는 매일 작업 전용 저장소 `%USERPROFILE%\tokenwar-daily`다. 시작할 때 최신 main을 받는다. 운영자가 Code 탭에서 쓰는 `tokenwar-agent` 폴더는 열지도 고치지도 않는다.
실행 시점: 로그인할 때, 그리고 9:30, 12:30, 15:30 (컴퓨터가 켜져 있을 때). 같은 날 여러 번 실행돼도 이미 한 일은 다시 하지 않는다.

이 컴퓨터에서는 유튜브와 일반 사이트에 바로 접속할 수 있다 (클라우드 작업 환경과 다름). 영상은 여기서 바로 받는다.

## 0. 준비

윈도우에서 파이썬은 `py -3.12`로 부른다 (문서의 `python3`도 이것으로 바꿔 실행). ffmpeg, yt-dlp, gh, git은 PATH에 있다.


1. `git pull`, 그리고 `git fetch origin "+refs/heads/post/*:refs/remotes/origin/post/*"` (검토 중인 게시물과 겹치지 않게)
2. `py -3.12 agent/hot.py`로 지금 관심 주제를 새로 모은 뒤, `AGENT.md`, `STYLE_GUIDE.md`, `TEMPLATES.md`, `config.json`, `data/hot.md`, `data/trends.md`를 읽는다. **지금 관심도가 높은 주제부터** 고른다 (STYLE_GUIDE 6-1장 점수표).
3. 오늘 날짜(한국 시간)를 확인하고, 오늘 이미 만든 것을 확인한다:
   - `posts/queue/`, `posts/published/`에 오늘 날짜의 carousel / video 폴더가 있는지
   - 열린 PR: `gh pr list --state open --json headRefName,title` (브랜치 `post/<날짜>`, `post/<날짜>-reel`)
4. 둘 다 이미 있으면 **아무것도 하지 않고 끝낸다.**

## 1. 카드뉴스 (오늘 것이 없을 때)

`AGENT.md` 1~3장대로 만든다. 다른 점:
- **사진을 꼭 넣는다** (STYLE_GUIDE 2-1 "카드뉴스에는 사진을 꼭 넣는다"). 글을 쓰기 전에 장마다 넣을 실제 화면을 정하고 `py -3.12 agent/shot.py <주소> posts/queue/<폴더>/img/<번호>.jpg`로 찍는다. 표지는 사진 표지, 본문은 위쪽에 화면 캡처. 찍은 이미지는 Read로 열어 확인한다. 표지 포함 2장 이상이 안 되면 `render.py`가 멈춘다.
- `publish_at`: 지금이 10:13 전이면 오늘 10:13, 지났으면 **지금부터 30분 뒤**(오늘 안에 올린다. 소식은 신선할 때가 낫다). 단 22시가 넘었으면 내일 10:13.
- AI 이미지(`prompt`)와 실물 이미지(`url`)는 여기서 바로 처리해도 되지만, Cloudflare 키가 이 컴퓨터에는 없으므로 `prompt` 그림은 GitHub Actions(`render.yml`)에 맡긴다 (AGENT.md 3장).

## 2. 릴스 (오늘 것이 없을 때)

영상 고르기 → 받기 → 구간 → 번역 자막 → 썸네일 → 렌더링을 한 번에 한다. 기준은 `STYLE_GUIDE.md` 6-1장, 형식은 `TEMPLATES.md`, 세부 순서는 `CLIPS.md` 2~5장과 같다. 다른 점:
- 영상 후보는 이번 리서치에서 직접 고른다 (`requests/clips/`에 요청이 있으면 그것부터).
- 유튜브 검색: `yt-dlp --flat-playlist --print "%(id)s | %(channel)s | %(view_count)s | %(duration)s | %(title)s" "https://www.youtube.com/results?search_query=<검색어>&sp=EgQIAhAB"` (최근 1주, 동영상만). 공식 채널의 원본인지 확인한다. 완성 영상이 **1분 언저리**가 되려면 원본이 3분 이상이어야 한다(원본의 1/3 이하만 인용).
- 받기: `yt-dlp --js-runtimes node -S "res:1080,ext:mp4:m4a" --merge-output-format mp4 -o "%TEMP%\tokenwar\full.mp4" <url>` 후 ffmpeg로 앞뒤 1초 여유를 두고 잘라 게시물 폴더 `clips/source.mp4`로. 원본 전체는 저장소에 넣지 않는다.
- 받아쓰기와 단어 시각: `python agent/tighten.py clips/source.mp4 <시작> <끝>`
- `publish_at`: 오늘 19:10 (지금이 18:30 이후면 내일 19:10).
- 영상을 찾지 못하면 그날 릴스는 건너뛰고 끝에 이유를 적는다.

## 3. 올리기

`config.json`의 `mode`:
- review: 게시물마다 브랜치(`post/<날짜>`, `post/<날짜>-reel`)에 커밋 → `gh pr create`. PR 본문에 표지(또는 썸네일), 캡션 전문, 출처, 게시 예정 시각, 고른 이유.
- auto: main에 push.

## 4. 끝

마지막 출력에 한 줄 요약(만든 것, PR 링크, 게시 시각, 건너뛴 것과 이유)을 남긴다. `logs/`에 저장된다.

## 하지 말 것

- 인스타에 직접 올리지 않는다 (GitHub Actions가 한다).
- 토큰·비밀값을 출력하거나 저장소에 쓰지 않는다.
- 회원님의 다른 파일을 건드리지 않는다. 작업은 이 저장소 폴더와 `%TEMP%\tokenwar` 안에서만 한다.
- 구글 로그인이나 브라우저 쿠키로 유튜브를 받지 않는다.
