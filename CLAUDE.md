# 토큰전쟁 인스타 자동화 — Claude Code 작업 안내

이 저장소는 인스타그램 **@tokenwar_ai (토큰전쟁 | AI 뉴스)** 를 자동으로 운영한다. AI 소식 카드뉴스(하루 1개)와 인용 영상 릴스(하루 1개)를 만들어 올린다. 계정을 키운 뒤 운영자의 SF 소설 「토큰 전쟁」을 알리는 것이 최종 목표다. 운영자와는 한국어로 대화한다.

이 파일은 기능을 추가하거나 고칠 때 먼저 읽는 안내서다. **진행 중인 일과 운영자 답을 기다리는 것은 `NEXT.md`에 있다. 대화를 시작하면 그것부터 읽는다.** 매일 게시물을 만드는 절차는 `LOCAL.md`(이 컴퓨터), `AGENT.md`, `CLIPS.md`에 있다.

## 전체 흐름

```
[윈도우 작업 스케줄러] 로그인 3분 뒤 · 9:30 · 12:30 · 15:30
   └ scripts/run-local.ps1 → %USERPROFILE%\tokenwar-daily(매일 작업 전용 저장소)에서 git pull로 최신 main
        → (오늘 할 일이 있을 때만) claude -p "LOCAL.md대로"   ※ Code 탭의 tokenwar-agent 폴더와 따로 돈다
        ├ agent/hot.py            지금 관심 주제 → data/hot.md
        ├ 리서치 → post.json 작성 → agent/render.py(검사·렌더링) → 직접 검수
        └ 검토 모드: post/<날짜>, post/<날짜>-reel 브랜치 + PR   (자동 모드: main)
[작업 스케줄러 15분마다] scripts/watch-models.ps1 → 게시 시각 지난 posts/queue가 있으면 gh workflow run publish.yml (cron 지연 대비)
        → agent/model_watch.py(공식 블로그 새 모델 감시)
        → 새 발표가 있을 때만 claude -p "LOCAL.md 6장" → 바로 올리기(--asap) PR
[GitHub Actions]
   ├ render.yml        posts/queue 바뀌면: 실물 이미지 받기·AI 그림(Cloudflare FLUX.2) → 렌더링 → 커밋
   ├ publish.yml       15분마다: 게시 시각이 된 것(렌더링 끝난 것만) → 인스타 Graph API로 게시 → posts/published
   ├ benchmarks.yml    매일 6시: 벤치마크 계정 조회수·우리 성과·시간대 → data/trends.md, 지금 관심 주제 → data/hot.md
   ├ token-check.yml   매주 월: 토큰 상태 → data/token_status.json, 문제 있으면 이슈(메일)
   └ review-page.yml   검토 PR(post/*)이 바뀔 때·렌더링 뒤·30분마다: 영상·카드 보는 검토 페이지 → docs/review (main)
```

## 파일 지도

| 경로 | 내용 |
|---|---|
| `config.json` | 모드(review/auto), 게시 시각, 브랜드 색, 글자 수 제한, 벤치마크 계정 |
| `STYLE_GUIDE.md` | 디자인·문체·주제 고르기·이미지·영상 고르기의 모든 규칙 (가장 중요) |
| `TEMPLATES.md` | post.json 형식 (카드 장 유형, 릴스 영상 프레임, 썸네일) |
| `AGENT.md` / `LOCAL.md` / `CLIPS.md` | 매일 작업 절차 (클라우드용 / 이 컴퓨터용 / 영상 받기) |
| `agent/checks.py` | post.json 규칙 검사 (글자 수, 금지어, AI 글투, 카드뉴스 사진 2장 이상, 인용 길이·비율, 썸네일) |
| `agent/dupes.py` | 같은 내용 반복 막기 (같은 영상 90일, 같은 출처 30일, 주제 겹침 14일, 같은 인물 주 2회) |
| `agent/render.py` | 카드뉴스 HTML → JPEG (Playwright). video 타입이면 `video.py`, 썸네일은 `thumb.py` |
| `agent/video.py` | 인용 영상 릴스: 제목·초록 테두리 영상 창·출처·자막. 구간 경계를 원본 소리에 맞춤(`fit_edges`: 말 끝 + 0.4초, 다음 말 페이드), 자막은 항상 영상 창 바닥(겹치면 글씨 줄이기 → 원본 글자 띠 위로 조금 → 겹침 감수, `captions_size`), `crop`. `keep`·`captions_at`은 예전 기능 |
| `agent/slots.py` | 게시 칸 자동 배정 (`next`, `need`, `status`). 예약된 것을 피해 가장 가까운 빈 칸 |
| `agent/model_watch.py` | 새 모델 감시 (AI 안 씀): OpenAI·구글·앤트로픽 공식 블로그 + data/hot.md 화제 회사 → 새 발표를 "회사, 제목, 주소"로. 본 것은 `data/model_watch.json`. `scripts/watch-models.ps1`이 15분마다 (LOCAL.md 6장) |
| `agent/dm.py` | 따라 하기 게시물의 댓글 자동 DM 준비물: `dm.md`(Zorcha 설정 메모), `docs/p/<id>/` 안내 페이지(GitHub Pages) |
| `agent/shot.py` | 웹페이지 화면 캡처 → 카드뉴스 사진 (`shot` 필드로 자동, 또는 명령줄) |
| `agent/thumb.py` | 릴스 썸네일 cover.jpg (그림 꽉 차게 + 가운데 제목 2줄) |
| `agent/tighten.py` | 받아쓰기 단어 시각 → 말 사이 틈을 자른 keep 목록 |
| `agent/analyze.py` | 영상 분석: 장면 전환, 말소리 구간, 받아쓰기, 시트 이미지 |
| `agent/gen_images.py` | 실물 이미지 받기(`url`) → 없으면 AI 그림(`prompt`, Cloudflare) |
| `agent/build.py` | 그림 + 렌더링 + `.render_hash`(publish가 렌더링 끝난 것만 올리게) |
| `agent/publish.py` | 인스타 게시 (Graph API, graph.facebook.com, 페이지 토큰). 미디어는 `docs/media/`에 복사·push해 GitHub Pages 주소로 넘기고, 게시 뒤 비운다. 게시된 폴더의 `clips/source.mp4`는 지운다. `DRY_RUN=1`로 시험 |
| `agent/benchmarks.py` / `agent/hot.py` | 인스타 반응 분석 / 지금 관심 주제 |
| `agent/token_check.py` | 토큰 점검 |
| `agent/review_page.py` | 검토 페이지: 열린 post/* PR의 릴스 영상·카드 장·캡션을 raw.githubusercontent(PR 커밋 고정)로 보여 주는 `docs/review/index.html` |
| `docs/review/` | 검토 페이지 (GitHub Pages https://vmvm0406.github.io/tokenwar-agent/review/, 봇이 갱신. 손으로 고치지 않는다) |
| `posts/queue/<폴더>/post.json` | 올릴 게시물. 게시되면 `posts/published/`로 이동 |
| `samples/` | 예시 게시물 (s1~s3 카드뉴스, s8 젠슨 황 인터뷰, s10 드와케시 팟캐스트, s11 주간 요약, s12 따라 하기 카드뉴스, s13 따라 하기 릴스). 디자인을 바꾸면 이걸로 확인 |
| `data/` | 분석 결과 (봇이 갱신. 손으로 고치지 않는다) |
| `data/hot_topics.md` | 잘 터진 주제 묶음: 벤치마크 계정 게시물을 평소 대비 반응 배수로 줄 세워 주제(AI 영상 만들기, 사진 변환, 돈·일자리 등)별로 묶은 표. `agent/benchmarks.py`가 매일(단독: `--hot-topics-only`, 저장된 데이터만) |
| `experiments/` | 아직 매일 작업에 안 들어간 시제품 (릴스 CRT 화면 등). README에 렌더링 방법 |
| `NEXT.md` | 이어서 할 일, 운영자 답을 기다리는 것 |

## Code 탭 운영: 지휘 세션(토큰전쟁 제작 총괄) + 하위 에이전트 (운영자 결정, 2026-11-15)

운영자는 Code 탭의 **지휘 세션 하나에만** 명령한다. 지휘 세션은 직접 대본을 읽거나 영상을 자르지 않고, 일을 나눠 하위 에이전트(`.claude/agents/`)에 맡긴 뒤 짧은 보고만 받아 묶는다. 컨텍스트를 아끼기 위해서다.

| 에이전트 | 맡는 일 |
|---|---|
| `make-quote-reel` | 릴스 1개 전부 (영상 찾기 → 구간 → 자르기 → 번역 자막 → 썸네일 → 렌더링 → 직접 검수) |
| `make-card-news` | 카드뉴스 1개 전부 (사실 확인 → 표지 후킹 사진 → 본문 → 렌더링 → 검수, 따라 하기면 dm) |
| `pick-video-segment` | 긴 자막(vtt) 읽고 1분 구간 후보 2개 (읽기만, sonnet) |
| `review-post` | 만든 게시물을 규칙·한국어 자연스러움으로 검수, 고칠 점만 보고 (sonnet) |

**운영자는 최상위 세션에만 말한다.** 지휘 세션의 질문이나 운영자가 할 일, 중요한 결과(5줄 안 요약)는 지휘 세션 화면에 묻지 말고 SendMessage로 최상위 세션에 보낸다. 최상위 세션이 운영자에게 전한다.

지휘 세션이 하는 일:
1. 요청을 게시물 단위로 나눈다. `py -3.12 agent/slots.py next <종류> --count N`으로 칸을 받고, 같은 날 겹치면 안 되는 인물·주제를 정한다.
2. 작업 폴더를 만든다: `git worktree add <scratchpad>/wt-<이름> -b post/<날짜>-<HHMM> origin/main` (운영자의 tokenwar-agent 브랜치는 바꾸지 않는다). 모든 하위 에이전트가 이 폴더 안의 서로 다른 게시물 폴더에서 일한다.
3. 게시물마다 `make-quote-reel`/`make-card-news`를 **한 메시지에서 병렬로** 부른다. 지시에는 칸 시각, 작업 폴더, 피할 주제, (있으면) 후보 영상만 짧게 쓴다.
4. 보고가 오면 `review-post`로 검수(병렬). 고칠 점은 같은 제작 에이전트에 SendMessage로 돌려보낸다.
5. 다 되면 지휘 세션이 커밋·push하고 PR 하나를 연다 (PR 본문 표: LOCAL.md 3장). 운영자에게는 결과만 짧게.
6. 지휘 세션은 이미지 시트 확인 정도만 직접 하고, 대본·긴 로그·영상 처리는 하지 않는다.

## 기능을 추가할 때

1. **관련 문서부터 고친다.** 규칙은 `STYLE_GUIDE.md`, 형식은 `TEMPLATES.md`, 절차는 `LOCAL.md`/`AGENT.md`/`CLIPS.md`. 매일 작업하는 Claude는 이 문서들만 보고 일한다.
2. **검사로 강제할 수 있는 규칙은 `checks.py`나 `dupes.py`에 넣는다.** 문서에만 있으면 지켜지지 않을 수 있다.
3. **post.json 형식은 예전 게시물과 호환되게.** 새 필드는 선택(없어도 동작)으로 추가한다.
4. **샘플로 확인한다:** `py -3.12 agent/render.py samples/s1-nvidia`, `samples/s8-huang-quote`, `samples/s10-dwarkesh-ai-rnd`. 결과 이미지를 직접 열어 본다. 검사만: `py -3.12 -c "import sys,json;sys.path.insert(0,'agent');from checks import check_post;print(check_post(json.load(open('samples/s1-nvidia/post.json',encoding='utf-8'))))"`
5. 게시 쪽을 바꿨으면 `DRY_RUN=1`로 `agent/publish.py`를 돌려 본다 (실제로 올리지 않음).
6. **main에 커밋·push 한다.** 매일 작업과 GitHub Actions는 main을 기준으로 돈다. 커밋 메시지는 한국어로 무엇이 바뀌었는지.
7. 윈도우(이 컴퓨터)와 리눅스(GitHub Actions) 둘 다에서 돌아야 한다. 경로는 `pathlib`, 외부 프로그램은 `shutil.which`로 찾는다.

## 꼭 지킬 것

- **비밀값:** `IG_ACCESS_TOKEN`, `IG_USER_ID`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`은 GitHub Secrets에만 있다. 코드·로그·커밋·채팅에 값을 쓰지 않는다. 저장소는 공개다(GitHub Pages `docs/media/`로 인스타에 미디어를 넘기기 때문. jsDelivr는 저장소가 50MB를 넘으면 403이 날 수 있어 쓰지 않는다). `docs/media/`는 publish가 잠깐 쓰는 자리라 손으로 넣지 않는다.
- **저작권:** 인용 릴스는 1분 언저리(상한 없음, 이야기가 끝나는 곳에서), 원본의 1/3 이하, 우리 번역·설명 자막이 60% 이상, 출처(credit, source_url) 필수. 원본 전체를 저장소에 올리지 않는다. 통신사·언론사 보도사진은 쓰지 않는다. (STYLE_GUIDE 2-1, 6-1)
- **디자인:** 검정 배경 + 형광 초록 #00FF66, 제목 검은고딕(Black Han Sans), 본문 원티드 산스. AI 디자인 티(알약 태그, 둥근 카드, 이모지, 그라데이션 등) 금지 목록은 STYLE_GUIDE 1-1. 제목 앞 머리말([전황] 등) 쓰지 않는다. 캐릭터 쓰지 않는다.
- **글:** 카드는 짧게 끊되 조사·부사로 툭 끊지 않는다. 표지 제목은 "~합니다"나 명사로. 인터뷰 자막은 요약하지 말고 문장 단위로 번역. AI 글투 금지 (STYLE_GUIDE 4, 4-1).
- **영상 고르기:** 인터뷰·팟캐스트·공식 석상 위주, "처음 듣는 정보"와 "지금 관심도"를 가장 크게 본다. 다른 인스타 계정이 편집한 영상은 쓰지 않는다.
- **게시:** 인스타에 직접(브라우저 등으로) 올리지 않는다. 게시는 publish.yml만 한다.

## 운영자 취향 (지금까지 정한 것)

- 카드뉴스에는 사진을 꼭 넣는다: 표지는 사진 표지, 본문 장은 위쪽에 실제 화면 캡처(서비스 화면, 공식 발표, 보고서 그래프) + 아래 제목·설명. 다른 AI 정보 계정들의 모양. 표지 포함 2장 이상은 checks.py가 막는다.
- 제목은 알아듣기 쉽게: 누가·무엇이 무엇을 했는지 서술어까지 ("3년 만에 밀레니엄 난제" 같은 명사 압축 금지), 어려운 말은 쉬운 말로. 릴스·썸네일 제목은 checks.py가 서술어 끝을 검사.
- 릴스 자막은 항상 영상 창 아래(바닥)에 단다. 위에 달지 않는다 (2026-11-16). 원본에 박힌 글자는 띠로 가리지 않고 글씨를 줄이거나 조금 올려 피하고, 안 되면 겹침을 감수한다. 자막만 깔끔하게 보이게.
- 캡션 끝 질문은 필수 아님: 일반 뉴스는 사실과 출처로 끝내고, 의견이 갈리는 소식에만 그 소식에 맞는 양자택일 질문. "여러분 생각은?" 같은 뻔한 질문은 checks.py가 막는다. 따라 하기는 '받기' 안내로 끝낸다.
- 해시태그는 3~5개: 주제 이름 1~2 + 한국어 분야 1~2(data/trends.md "많이 쓰는 해시태그" 참고) + #토큰전쟁. #reels #fyp #좋아요 같은 흔한 태그 금지.
- 댓글 자동 DM은 외부 도구 Zorcha(무료, 팔로우 확인)로. 따라 하기 게시물마다 `dm.md` 설정 메모 + GitHub Pages 안내 페이지를 만들고, 키워드는 '받기', 팔로우한 사람에게만. 직접 만들기는 계정이 커지면 다시 검토.
- 카드뉴스는 여러 템플릿을 섞는다 (표지 big/list/image, 본문 body/stat/steps/compare). 한 가지 모양만 반복하지 않는다.
- 썸네일은 간결하게: 상징물 하나 크게(예: 자물쇠), 색감과 배치를 매번 생각. 실물 이미지 우선, AI 그림은 주로 릴스 썸네일.
- 썸네일은 사진이 화면을 빈칸 없이 꽉 채운다. 영상 장면을 줄여 넣어 위아래 검은 띠가 생기면 안 된다 (인물 쪽을 9:16으로 잘라 1080x1920, thumb.py가 검은 띠를 막음). 글자는 안전 영역(285~1250px) 안.
- 릴스는 1분 언저리 길이, 한 구간을 중간에 자르지 않고 그대로(점프 컷은 급해 보임). 자막은 입으로 말하듯 자연스럽게("1% 미만이었는데 말이죠"). 확대는 해도 되지만 자막이 얼굴 위에 오면 안 된다.
- 소식은 하나씩: 여러 소식을 "이번 주 AI 4가지"처럼 한 게시물에 묶지 않는다. 소식마다 따로 카드뉴스나 릴스로 만든다.
- 릴스는 인스타 화면에서 안 가려지는 자리에: 읽어야 할 것은 세로 285~1250px, 양옆 65px 안, 오른쪽 아래 버튼 줄(x 850~, y 1150~) 피하기. 화면 덩어리를 위로 몰지 않는다 (`config.json` reel_safe, STYLE_GUIDE 6).
- 릴스 화면 나누기(앞으로 모션을 넣을 때): 영상 위에는 평범한 자막만, 숫자·비교·강조 같은 모션은 영상 아래 빈칸에만. 초록 강조 블록은 글자 범위에 딱 맞게. 아래 요약 글은 신문 제목처럼 한자어·명사형으로("지금" 말고 "현재", "비슷한 글" 말고 "유사 보고서"). 영상 위 자막은 말하듯이.
- 같은 내용은 최대한 겹치지 않게. 지금 사람들이 관심 갖는 주제를 먼저.
- 반응 좋은 형식 따라가기 (ai.trend.kr 분석, STYLE_GUIDE 3-1): 소식만 전하지 말고 "바로 따라 해 볼 것"(챗GPT·제미나이 활용법, 복사해 쓰는 프롬프트)을 붙인다. 첫 줄은 얻는 것을 약속.
- 가벼운 화제(`format: buzz`)를 일주일(월~일)에 카드·릴스 합쳐 1~2개 가끔 섞는다: 연예인·예능·유명인이 나오는 재밌는 AI 이야기나 지금 AI 화제에 빗댄 패러디(패러디면 앞에서 "사실은 ~"으로 풀기). 공식 채널 영상·보도자료 사진만, 출처 2곳, 조롱·의혹·사생활 금지 (STYLE_GUIDE 3-2, checks.py·dupes.py).
- 카드뉴스는 이틀에 한 번 이상 따라 하기·질문 형식(`format: howto/ask`, 프롬프트 상자 `kind: prompt`). 프롬프트는 직접 돌려 본 결과만 보여 주고, 틀린 점도 "주의할 점"에 적는다 (TEMPLATES.md "게시물 형식", LOCAL.md 1장).
- 주제는 일반인이 아는 것으로: 챗GPT·제미나이·삼성·네이버처럼 누구나 아는 이름, 생활에 닿는 이야기. 개발자만 아는 도구(Lovable, Cursor 등)는 고르지 않는다 (STYLE_GUIDE 3).
- 주제는 잘 터졌던 주제와 같거나 비슷한 것으로 (운영자 결정 2026-11-16): 릴스·카드뉴스 모두 `data/hot_topics.md` 위쪽 주제를 먼저, PR 본문에 "참고한 잘 터진 주제: …" 한 줄. 따라 하기는 결과물이 확 보이는 창작형(AI로 영상·게임 만들기, 클로드에 유니티 연결해 게임 만들기, 음악·이미지)을 이 컴퓨터에서 직접 만들어 본 결과로만, 단순 질문·검색 수준은 금지 (STYLE_GUIDE 3장, 3-1).
- 게시 칸(config.json `slots`): 릴스 12:43·15:43·19:10·20:43(하루 최대 4), 카드뉴스 10:13·13:13·17:13(최대 3). 새 게시물은 agent/slots.py가 가장 가까운 빈 칸에 넣고, 매일 작업은 하루 몫(daily_target: 릴스 4, 카드뉴스 3, 하루 칸 전부)이 차 있으면 쉰다. 운영자는 양으로 승부한다(2026-11-16 결정). 원할 때 더 만들기·바로 올리기는 LOCAL.md 5장 (Code 탭 "릴스 3개 만들어 줘" 또는 make-posts.ps1). 시간대는 data/trends.md로 매달 다시 본다.

## 자주 쓰는 명령 (이 컴퓨터, PowerShell)

```powershell
cd $env:USERPROFILE\tokenwar-agent
git pull
py -3.12 agent/render.py samples/s1-nvidia           # 카드뉴스 렌더링 확인
py -3.12 agent/hot.py                                 # 지금 관심 주제 다시 모으기
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\run-local.ps1   # 하루 작업 수동 실행 (전용 저장소 tokenwar-daily에서 돈다)
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\make-posts.ps1 -Reels 3 -Cards 2   # 원할 때 더 만들기 (-Now: 바로 올리기, -Date 2026-11-17: 그날에 몰아 넣기)
py -3.12 agent/model_watch.py --dry-run -v            # 새 모델 감시 확인 (기록 안 바꿈, 출처별 읽은 수)
py -3.12 agent/slots.py status                        # 며칠 치 게시 칸 상황
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\cleanup.ps1 -Force   # C 드라이브 정리 바로 (하루 한 번 조건 무시, -WhatIf: 지울 목록만)
Get-ScheduledTask TokenwarAgent                       # 작업 스케줄러 상태
Get-Content (Get-ChildItem $env:USERPROFILE\tokenwar-daily\logs | Sort LastWriteTime | Select -Last 1).FullName   # 최근 기록
```
