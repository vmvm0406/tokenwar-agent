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
[GitHub Actions]
   ├ render.yml        posts/queue 바뀌면: 실물 이미지 받기·AI 그림(Cloudflare FLUX.2) → 렌더링 → 커밋
   ├ publish.yml       15분마다: 게시 시각이 된 것(렌더링 끝난 것만) → 인스타 Graph API로 게시 → posts/published
   ├ benchmarks.yml    매일 6시: 벤치마크 계정 조회수·우리 성과·시간대 → data/trends.md, 지금 관심 주제 → data/hot.md
   └ token-check.yml   매주 월: 토큰 상태 → data/token_status.json, 문제 있으면 이슈(메일)
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
| `agent/video.py` | 인용 영상 릴스: 제목·초록 테두리 영상 창·출처·자막. `keep`(예전 기능, 지금은 쓰지 않음), `punch`, `crop`, `captions_at` |
| `agent/slots.py` | 게시 칸 자동 배정 (`next`, `need`, `status`). 예약된 것을 피해 가장 가까운 빈 칸 |
| `agent/dm.py` | 따라 하기 게시물의 댓글 자동 DM 준비물: `dm.md`(Zorcha 설정 메모), `docs/p/<id>/` 안내 페이지(GitHub Pages) |
| `agent/shot.py` | 웹페이지 화면 캡처 → 카드뉴스 사진 (`shot` 필드로 자동, 또는 명령줄) |
| `agent/thumb.py` | 릴스 썸네일 cover.jpg (그림 꽉 차게 + 가운데 제목 2줄) |
| `agent/tighten.py` | 받아쓰기 단어 시각 → 말 사이 틈을 자른 keep 목록 |
| `agent/analyze.py` | 영상 분석: 장면 전환, 말소리 구간, 받아쓰기, 시트 이미지 |
| `agent/gen_images.py` | 실물 이미지 받기(`url`) → 없으면 AI 그림(`prompt`, Cloudflare) |
| `agent/build.py` | 그림 + 렌더링 + `.render_hash`(publish가 렌더링 끝난 것만 올리게) |
| `agent/publish.py` | 인스타 게시 (Graph API, graph.facebook.com, 페이지 토큰). `DRY_RUN=1`로 시험 |
| `agent/benchmarks.py` / `agent/hot.py` | 인스타 반응 분석 / 지금 관심 주제 |
| `agent/token_check.py` | 토큰 점검 |
| `posts/queue/<폴더>/post.json` | 올릴 게시물. 게시되면 `posts/published/`로 이동 |
| `samples/` | 예시 게시물 (s1~s3 카드뉴스, s8 젠슨 황 인터뷰, s10 드와케시 팟캐스트, s11 주간 요약, s12 따라 하기 카드뉴스, s13 따라 하기 릴스). 디자인을 바꾸면 이걸로 확인 |
| `data/` | 분석 결과 (봇이 갱신. 손으로 고치지 않는다) |
| `experiments/` | 아직 매일 작업에 안 들어간 시제품 (릴스 CRT 화면 등). README에 렌더링 방법 |
| `NEXT.md` | 이어서 할 일, 운영자 답을 기다리는 것 |

## 기능을 추가할 때

1. **관련 문서부터 고친다.** 규칙은 `STYLE_GUIDE.md`, 형식은 `TEMPLATES.md`, 절차는 `LOCAL.md`/`AGENT.md`/`CLIPS.md`. 매일 작업하는 Claude는 이 문서들만 보고 일한다.
2. **검사로 강제할 수 있는 규칙은 `checks.py`나 `dupes.py`에 넣는다.** 문서에만 있으면 지켜지지 않을 수 있다.
3. **post.json 형식은 예전 게시물과 호환되게.** 새 필드는 선택(없어도 동작)으로 추가한다.
4. **샘플로 확인한다:** `py -3.12 agent/render.py samples/s1-nvidia`, `samples/s8-huang-quote`, `samples/s10-dwarkesh-ai-rnd`. 결과 이미지를 직접 열어 본다. 검사만: `py -3.12 -c "import sys,json;sys.path.insert(0,'agent');from checks import check_post;print(check_post(json.load(open('samples/s1-nvidia/post.json',encoding='utf-8'))))"`
5. 게시 쪽을 바꿨으면 `DRY_RUN=1`로 `agent/publish.py`를 돌려 본다 (실제로 올리지 않음).
6. **main에 커밋·push 한다.** 매일 작업과 GitHub Actions는 main을 기준으로 돈다. 커밋 메시지는 한국어로 무엇이 바뀌었는지.
7. 윈도우(이 컴퓨터)와 리눅스(GitHub Actions) 둘 다에서 돌아야 한다. 경로는 `pathlib`, 외부 프로그램은 `shutil.which`로 찾는다.

## 꼭 지킬 것

- **비밀값:** `IG_ACCESS_TOKEN`, `IG_USER_ID`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`은 GitHub Secrets에만 있다. 코드·로그·커밋·채팅에 값을 쓰지 않는다. 저장소는 공개다(jsDelivr로 인스타에 미디어를 넘기기 때문).
- **저작권:** 인용 릴스는 1분 언저리(상한 없음, 이야기가 끝나는 곳에서), 원본의 1/3 이하, 우리 번역·설명 자막이 60% 이상, 출처(credit, source_url) 필수. 원본 전체를 저장소에 올리지 않는다. 통신사·언론사 보도사진은 쓰지 않는다. (STYLE_GUIDE 2-1, 6-1)
- **디자인:** 검정 배경 + 형광 초록 #00FF66, 제목 검은고딕(Black Han Sans), 본문 원티드 산스. AI 디자인 티(알약 태그, 둥근 카드, 이모지, 그라데이션 등) 금지 목록은 STYLE_GUIDE 1-1. 제목 앞 머리말([전황] 등) 쓰지 않는다. 캐릭터 쓰지 않는다.
- **글:** 카드는 짧게 끊되 조사·부사로 툭 끊지 않는다. 표지 제목은 "~합니다"나 명사로. 인터뷰 자막은 요약하지 말고 문장 단위로 번역. AI 글투 금지 (STYLE_GUIDE 4, 4-1).
- **영상 고르기:** 인터뷰·팟캐스트·공식 석상 위주, "처음 듣는 정보"와 "지금 관심도"를 가장 크게 본다. 다른 인스타 계정이 편집한 영상은 쓰지 않는다.
- **게시:** 인스타에 직접(브라우저 등으로) 올리지 않는다. 게시는 publish.yml만 한다.

## 운영자 취향 (지금까지 정한 것)

- 카드뉴스에는 사진을 꼭 넣는다: 표지는 사진 표지, 본문 장은 위쪽에 실제 화면 캡처(서비스 화면, 공식 발표, 보고서 그래프) + 아래 제목·설명. 다른 AI 정보 계정들의 모양. 표지 포함 2장 이상은 checks.py가 막는다.
- 캡션 끝 질문은 필수 아님: 일반 뉴스는 사실과 출처로 끝내고, 의견이 갈리는 소식에만 그 소식에 맞는 양자택일 질문. "여러분 생각은?" 같은 뻔한 질문은 checks.py가 막는다. 따라 하기는 '받기' 안내로 끝낸다.
- 해시태그는 3~5개: 주제 이름 1~2 + 한국어 분야 1~2(data/trends.md "많이 쓰는 해시태그" 참고) + #토큰전쟁. #reels #fyp #좋아요 같은 흔한 태그 금지.
- 댓글 자동 DM은 외부 도구 Zorcha(무료, 팔로우 확인)로. 따라 하기 게시물마다 `dm.md` 설정 메모 + GitHub Pages 안내 페이지를 만들고, 키워드는 '받기', 팔로우한 사람에게만. 직접 만들기는 계정이 커지면 다시 검토.
- 카드뉴스는 여러 템플릿을 섞는다 (표지 big/list/image, 본문 body/stat/steps/compare). 한 가지 모양만 반복하지 않는다.
- 썸네일은 간결하게: 상징물 하나 크게(예: 자물쇠), 색감과 배치를 매번 생각. 실물 이미지 우선, AI 그림은 주로 릴스 썸네일.
- 릴스는 1분 언저리 길이, 한 구간을 중간에 자르지 않고 그대로(점프 컷은 급해 보임). 자막은 입으로 말하듯 자연스럽게("1% 미만이었는데 말이죠"). 확대는 해도 되지만 자막이 얼굴 위에 오면 안 된다.
- 소식은 하나씩: 여러 소식을 "이번 주 AI 4가지"처럼 한 게시물에 묶지 않는다. 소식마다 따로 카드뉴스나 릴스로 만든다.
- 릴스는 인스타 화면에서 안 가려지는 자리에: 읽어야 할 것은 세로 285~1250px, 양옆 65px 안, 오른쪽 아래 버튼 줄(x 850~, y 1150~) 피하기. 화면 덩어리를 위로 몰지 않는다 (`config.json` reel_safe, STYLE_GUIDE 6).
- 릴스 화면 나누기(앞으로 모션을 넣을 때): 영상 위에는 평범한 자막만, 숫자·비교·강조 같은 모션은 영상 아래 빈칸에만. 초록 강조 블록은 글자 범위에 딱 맞게. 아래 요약 글은 신문 제목처럼 한자어·명사형으로("지금" 말고 "현재", "비슷한 글" 말고 "유사 보고서"). 영상 위 자막은 말하듯이.
- 같은 내용은 최대한 겹치지 않게. 지금 사람들이 관심 갖는 주제를 먼저.
- 반응 좋은 형식 따라가기 (ai.trend.kr 분석, STYLE_GUIDE 3-1): 소식만 전하지 말고 "바로 따라 해 볼 것"(챗GPT·제미나이 활용법, 복사해 쓰는 프롬프트)을 붙인다. 첫 줄은 얻는 것을 약속.
- 카드뉴스는 이틀에 한 번 이상 따라 하기·질문 형식(`format: howto/ask`, 프롬프트 상자 `kind: prompt`). 프롬프트는 직접 돌려 본 결과만 보여 주고, 틀린 점도 "주의할 점"에 적는다 (TEMPLATES.md "게시물 형식", LOCAL.md 1장).
- 주제는 일반인이 아는 것으로: 챗GPT·제미나이·삼성·네이버처럼 누구나 아는 이름, 생활에 닿는 이야기. 개발자만 아는 도구(Lovable, Cursor 등)는 고르지 않는다 (STYLE_GUIDE 3).
- 게시 칸(config.json `slots`): 릴스 12:43·15:43·19:10·20:43(하루 최대 4), 카드뉴스 10:13·13:13·17:13(최대 3). 새 게시물은 agent/slots.py가 가장 가까운 빈 칸에 넣고, 매일 작업은 하루 몫(daily_target: 릴스 2, 카드뉴스 1)이 차 있으면 쉰다. 원할 때 더 만들기·바로 올리기는 LOCAL.md 5장 (Code 탭 "릴스 3개 만들어 줘" 또는 make-posts.ps1). 시간대는 data/trends.md로 매달 다시 본다.

## 자주 쓰는 명령 (이 컴퓨터, PowerShell)

```powershell
cd $env:USERPROFILE\tokenwar-agent
git pull
py -3.12 agent/render.py samples/s1-nvidia           # 카드뉴스 렌더링 확인
py -3.12 agent/hot.py                                 # 지금 관심 주제 다시 모으기
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\run-local.ps1   # 하루 작업 수동 실행 (전용 저장소 tokenwar-daily에서 돈다)
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\make-posts.ps1 -Reels 3 -Cards 2   # 원할 때 더 만들기 (-Now: 바로 올리기, -Date 2026-11-17: 그날에 몰아 넣기)
py -3.12 agent/slots.py status                        # 며칠 치 게시 칸 상황
Get-ScheduledTask TokenwarAgent                       # 작업 스케줄러 상태
Get-Content (Get-ChildItem $env:USERPROFILE\tokenwar-daily\logs | Sort LastWriteTime | Select -Last 1).FullName   # 최근 기록
```
