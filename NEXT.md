# ▶ 새 대화는 여기부터 (2026-11-18 리셋)

- **상태:** 자동화 전부 꺼짐(config `automation_off`·`publish_paused`·`production_paused` true, GitHub Actions는 토큰 연장·토큰 점검·Pages만 켜짐). 대기열 비움(`experiments/archive-2026-11-18/`). 세션은 '최상위 에이전트' 하나만, 무거운 일은 하위 에이전트.
- **리뉴얼 방향(운영자 결정 대기):** 레퍼런스 8곳(agentpoly, base.learn, agentmorphy, ashutoshwithclaude, danborgia, ihc60435, platypus._.ai, withjun.b) 분석 = "사람 캐릭터 + AI 캐릭터" 3D 대화 콩트, 얼굴 출연 없음. 메모: side-session-notes/…/renewal-references.md
  - **확정 (운영자 2026-11-18):** ① 3D 직장 콩트(위기 한 줄 → AI 반응 → 팁 하나 → '자료' DM). 출연: 이름 없는 여성 직장인 '나' + 클로드·챗GPT·제미나이(로고 모양·색 본뜸). 슬라임은 뺌. 아이디 @tokenwar_ai 유지, 표시 이름·소개글만 새 형식에 맞게 바꿈(문구 안 정함). 제작: Blender로 캐릭터 → glTF → three.js 연기·카메라·자막.
  - 캐릭터 모양 (운영자 2026-11-18): 로고를 그대로 몸으로, 팔다리 없이 표정으로만 연기, 로우폴리. Blender 5.3 설치함. 1차 시안 `experiments/lowpoly-chars/` (build.py, README). 운영자 의견 대기 → 표정 세트 → '나' → three.js 틀 → 첫 콩트 시험 릴스.
- **제작 도구:** three.js 시험 통과(`experiments/threejs-test/`, a292de3). 노트북 GPU로 30초 릴스 ≈50초 렌더. 추천: 캐릭터는 Blender로 한 번 만들어 glTF → three.js로 연기·카메라·자막 자동. 틀 만들기 2~3일. 고칠 점: AI 팔 짧음, 챗GPT 매듭 울퉁불퉁, 머리 초록 테두리, 자막이 후드티와 겹침, 화면 '비공식 팬 캐릭터' 표기 뺄지 미정.
- **다시 켜는 법:** config 세 플래그 false + `gh workflow enable <id>`(인스타 게시·그림 만들기 등) + 작업 스케줄러는 그대로(스크립트가 automation_off를 봄).
- **연동 유지:** 인스타·스레드 토큰, Cloudflare Workers Paid(그림 상한 300, 사용 한도 $5), 일레븐랩스(Deok, Starter 월간, 키는 사용자 환경변수), Zorcha(Live 자동화 6개), GitHub Pages.

# 이어서 할 일 (2026-11-15 대화에서 넘어온 것)

> **목표 (운영자 결정 2026-11-16): 2026-12-16까지 인스타 팔로워 1만 명.** 주제·형식·게시 칸·자료 DM 등 모든 판단의 기준이다. 진행은 data/trends.md 맨 위 '목표 진행'(data/followers.csv, 매일 코드 계산), 게시물별 팔로우 기여는 data/benchmark_patterns.md 주간 요약, 월요일 주간 점검은 지휘 세션이 최상위 세션에 보고한다(뒤처지면 원인과 바꿀 점 3가지).

claude.ai 대화에서 하던 작업을 이 컴퓨터의 Claude Code로 옮겼다. 정해진 규칙은 이미 STYLE_GUIDE/CLAUDE.md에 들어가 있다. 아래는 **아직 안 끝난 것**이다. 하나 끝날 때마다 이 파일에서 지운다.

## 운영자가 할 일
- **새 모델 감시·게시 확인 작업 스케줄러 등록 (15분마다, 2026-11-15 만듦, LOCAL.md 6장).** 이미 등록했어도 주기가 15분으로 바뀌었으니 다시 실행. PowerShell(필요하면 관리자)에서 한 번:
  `git -C $env:USERPROFILE\tokenwar-daily pull; powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\setup-local.ps1 -OnlyWatch`
  확인: `Get-ScheduledTask TokenwarModelWatch`. 감시 기록은 `tokenwar-daily\logs\<연-월>-watch.log`, Claude가 게시물을 만들면 `logs\<시각>-model.log`. 지금은 `config.json` `model_watch.auto_publish: false`(PR + Merge). 바로 main에 올리고 싶으면 true로.
- 첫 몇 주는 감시가 너무 자주(구글 제미나이 블로그의 작은 기능 글) 또는 너무 드물게 잡는지 watch.log로 보고 `agent/model_watch.py`의 낱말 목록을 고친다.
- **업계 속보 감시 (2026-11-16 추가, 브랜치 fix/news-watch):** 젠슨 황 사임·복귀 논의(FT)를 놓친 일로 추가. `agent/news.py`가 주요 언론(FT·블룸버그·로이터·WSJ·더 버지·테크크런치·CNBC + 국내 주요 매체)을 Google News RSS로 보고, 15분 감시가 "주요 매체 3곳 이상 + 큰 사건 낱말"인 소식을 `[업계 속보: ...]` 후보로 낸다 (하루 3건, 같은 회사 12시간에 한 번, LOCAL.md 6장). 속보는 일반 제작보다 먼저: 매일 작업 중이면 그 Claude를 멈추고 속보부터 만든 뒤 매일 작업을 다시 띄운다. 기존 게시물은 밀지 않고 따라 하기·질문만 `slots.py bump`로 옮긴다. 확인할 것: 첫 주 watch.log에서 속보가 하루 몇 건 잡히는지, 주가·실적 기사 같은 잡음이 섞이는지 → `config.json` `model_watch.news`(`min_majors`, `max_per_day`, `major_outlets`, 회사 검색어)와 `agent/news.py` `BIG` 낱말로 조정. 매일 작업을 멈춘 기록은 watch.log의 "속보 → 매일 작업을 멈추고" 줄.

## 운영자 답을 기다리는 것
1. **릴스 새 화면(CRT 터미널) 채택 여부** — `experiments/reel-crt/` v7. 운영자 반응: 영상과 아래가 따로 노는 느낌 → 붙임, 상태줄 불필요 → 뺌, 영상이 너무 위 → 안전 영역으로 내림. 괜찮다고 하면 `agent/video.py`를 이 구조로 바꾸고 post.json에 아래 요약(`term` 장면들: 신문 제목체) 형식을 TEMPLATES.md에 추가, LOCAL.md/CLIPS.md 절차 수정.
2. **주간 요약 카드뉴스** — 샘플 완성: `samples/s11-weekly-ai` (11월 둘째 주, 소식 4개: 삼성 AI 안경·제미나이 카플레이·구글 검색 새 모델·챗GPT 기업 프로필, 소식마다 위쪽 공식 사진 + 번호·제목·설명). 본문 장 `num`/`num_note` 필드 추가함. 운영자가 보고 정한다. 운영자 의견(11-15): 초기 계정은 릴스가 우선, 릴스를 더 많이 찍어내야 함. — 운영자: "이번 주 AI에서 사진·영상 자료를 안 쓴 게 문제". 제안: 매주 일요일 "N월 N주 차 AI 뉴스" 카드뉴스 (ai.trend.kr 7,476 좋아요 글 구조: 강렬한 사진 표지 + 소식마다 한 장, 위쪽에 실제 사진·화면·영상, 아래 번호·제목·설명 3~4줄). 운영자가 샘플을 보고 정한다. 할 일: 오늘 소식으로 샘플 → 승인되면 STYLE_GUIDE의 "한 게시물에 소식 하나" 규칙에 주간 요약 예외 추가, dupes.py에서 주간 요약은 주제 겹침 예외, 캐러셀에 영상 장을 섞으려면 publish.py에 VIDEO 자식 추가.
3. **댓글 자동 DM — Zorcha 준비 끝, 첫 따라 하기 게시물 기다림 (2026-11-15)**
   - 끝난 것: GitHub Pages 켬(main, `/docs`, https://vmvm0406.github.io/tokenwar-agent/ 열림 확인). Zorcha 가입, @tokenwar_ai 연결. `agent/dm.py`가 따라 하기 게시물마다 `dm.md`(설정 메모)와 안내 페이지(`docs/p/<id>/`)를 만든다 (STYLE_GUIDE 7-1).
   - 아직 없는 것: Zorcha 자동화. 게시물이 없어서 하나도 만들지 않았다.
   - 운영 방식: 따라 하기 게시물이 올라갈 때마다 운영자가 **그 게시물 하나에 자동화를 따로** 만든다. 키워드 '받기', 팔로우 확인(Ask for Follow) 켬, DM 링크는 그 게시물 안내 페이지. 값은 게시물 폴더 `dm.md`에 있다. 매일 작업은 PR 본문 끝에 "게시 후 `dm.md`대로 Zorcha 자동화 만들기"를 적는다 (LOCAL.md).
   - 첫 게시물 때 운영자가 팔로우 안 한 계정으로 시험하고 결과를 여기에 적는다:
     (1) 팔로우하지 않고 '팔로우했어요'만 누르면 자료가 오는지 (실제로 확인하는지, 누른 것만 믿는지).
     (2) 무료 플랜 DM에 Zorcha 홍보 문구가 붙는지.
     (3) 안내 페이지 링크가 열리는지 (게시물이 main에 합쳐진 뒤 1~2분).
   - (1)이나 (2)가 안 되면 대안: InstantDM Legend Pro (팔로우 확인 있음, 월 12달러 또는 연 결제 월 9.99달러, 유료라 홍보 문구 없음). 무료로 팔로우 확인을 주는 다른 도구는 공식 요금표 기준으로 찾지 못했다.
4. **따라 하기 형식 샘플** — `samples/s12-howto-ai-mode`(카드뉴스 7장), `samples/s13-howto-ai-mode-reel`(카드형 모션 릴스, 장면 6개). 구글 AI 모드에 실제로 넣은 질문과 답 화면(11월 15일). 형식·검사·절차는 이미 main에 들어감(TEMPLATES "게시물 형식", checks.py `format`, LOCAL.md 1장). 운영자가 모양을 보고 고칠 점을 말하면 반영. 릴스 mp4는 이 컴퓨터에 ffmpeg가 없어 아직 안 만들어 봄 → ffmpeg 설치(`winget install Gyan.FFmpeg`) 후 `py -3.12 agent/render.py samples/s13-howto-ai-mode-reel`로 확인.

## 확인할 것
- **게시 칸 자동 배정 (2026-11-15 도입):** `config.json` `slots`, `agent/slots.py`, `scripts/make-posts.ps1`, LOCAL.md 5장. 매일 작업 하루 몫 `daily_target`은 **릴스 4, 카드뉴스 3 (하루 칸 전부)** (2026-11-16 운영자 결정 "양으로 승부", 전에는 릴스 2·카드 1). 하루 7개를 만들어 매일 작업 시간이 길어지고(한 번에 다 못 채우면 9:30·12:30·15:30 실행이 이어서 채움) Claude 사용량·영상 받기·Cloudflare 그림 사용도 그만큼 는다. 사용량 한도에 걸리거나 품질이 떨어지면 config만 되돌린다. 바꿀 때는 config만 고친다. 11월 16일 아침 첫 실행에서 `slots.py need`가 PR #2·#3을 오늘 몫으로 세어 카드뉴스는 만들지 않고 릴스 1개만 만드는지 `tokenwar-daily\logs`로 확인.
- PR #2(카드뉴스, 11/16 10:13)·#3(릴스, 11/16 19:10)은 새 규칙으로 보완함. 운영자 Merge 대기.
- PR #4: 릴스 3개(11/16 12:43 나델라 · 15:43 OpenAI 리눅스 · 20:43 딥마인드 알파지놈). 합치면 11/16 칸이 다 차서 그날 매일 작업은 쉰다. 운영자 Merge 대기.
- 릴스 자막은 원본에 박힌 글자(이름 자막 등)를 자동으로 피한다(video.py). 원본 글자를 띠로 가리는 방식은 운영자가 싫어함. 기사 화면·글자 화면이 내내 나오는 영상(드와케시 영상 에세이 등)은 자막이 겹쳐서 고르지 않는다.
- 이 컴퓨터에 ffmpeg를 다시 설치함(winget 기록만 있고 파일이 없었음). ffmpeg가 윈도우에서 인코딩 뒤 멈추던 문제는 `-nostdin`으로 고침.
- 카드뉴스 표지는 실제 사진·화면이 먼저. AI 그림이 실제 사건 사진처럼 보이면 쓰지 않는다 (PR #2에서 범행 도구처럼 보이는 AI 표지를 뺌).

## 댓글 자동 DM 직접 만들기 — 계정이 커지면 다시 검토 (2026-11-15 보류)

지금은 외부 도구(Zorcha)로 한다. 직접 만들기는 팔로워가 늘어 도구 제한·비용이 문제가 되거나, 도구가 팔로우를 제대로 확인하지 못할 때 다시 본다. 아래는 그때 쓸 설계·조사 기록이다. 걸림돌은 Meta 비즈니스 인증(사업자 서류)과 앱 심사다. 다시 시작하면 지금 만든 `dm` 필드·`dm.md`·GitHub Pages 안내 페이지는 그대로 쓴다.


운영자가 정한 흐름: 댓글 → 비공개 답장(Private Reply) 1번 → 버튼("자료 받기") → 팔로우 확인(`is_user_follow_business`) → 팔로워면 자료(프롬프트 전체 + 안내 페이지 링크), 아니면 "팔로우 후 다시 눌러 주세요". 이미 받은 사람은 기록해서 다시 보내지 않는다.

### 문서로 확인한 제약 (Meta 공식 문서, 2026-11)
- **비공개 답장:** `POST graph.facebook.com/<페이지 ID 또는 IG 계정 ID>/messages`, `recipient: {comment_id}`. 댓글 뒤 **7일 안**, 댓글 단 사람에게 **딱 1번**. 상대가 답장해야 이어서 보낼 수 있고, 그때부터 **24시간** 안에만 보낼 수 있다. 팔로워면 받은 편지함, 아니면 **메시지 요청함**으로 간다 (못 보고 지나칠 수 있음).
- **버튼:** Meta 공식 문서의 비공개 답장 예시는 글자뿐이다. 외부 API 업체 문서에 따르면 button_template(버튼 1~3개)은 되지만, **팔로우 안 한 사람에게는 인스타가 버튼을 거절하는 경우가 있고(오류 코드 2 / 1545133), 실패해도 그 댓글의 1번 기회가 사라진다.** 빠른 답장(quick reply)은 요청함에서 안 보인다.
- **팔로우 확인:** User Profile API `GET /<IGSID>?fields=is_user_follow_business,...`. **상대가 우리에게 메시지를 보냈거나 아이스브레이커·고정 메뉴를 눌러야**("user consent") 조회된다. 댓글만 단 사람은 오류. 비공개 답장 속 버튼(postback)을 누른 것이 동의로 치는지는 문서에 없다 → 시험 필요. 문서 설명이 `is_user_follow_business`/`is_business_follow_user` 방향을 헷갈리게 적었으니 실제 응답으로 방향을 확인한다.
- **속도 제한:** 게시물·릴스 댓글 비공개 답장은 계정당 시간당 750건.

### 그래서 권하는 흐름 (버튼 실패 위험 피하기)
1. 웹훅 `comments` → Worker가 받음. 이미 보낸 댓글·사람이면 무시.
2. 비공개 답장은 **글자만**: "자료를 받으려면 이 메시지에 '받기'라고 답장해 주세요." (버튼 거절로 1번 기회를 날리지 않게)
3. 상대가 답장하면(→ 동의 + 24시간 창 열림) 팔로우 확인.
   - 팔로워: 자료 전송(프롬프트 + 안내 페이지 링크), 보낸 기록 남김.
   - 아니면: "팔로우한 뒤 아래 버튼을 눌러 주세요" + postback 버튼 "팔로우했어요" → 누르면 다시 확인 (24시간 안).
4. 시험해서 버튼이 비팔로워에게도 잘 붙으면, 2번을 운영자 원래 설계(버튼 "자료 받기")로 바꾼다.

### 앱 권한 (지금 토큰: Facebook 로그인 방식 페이지 토큰)
- 지금 있는 권한: `pages_show_list`, `business_management`, `instagram_basic`, `instagram_manage_insights`, `instagram_content_publish`, `pages_read_engagement`.
- 더 필요한 것: `instagram_manage_comments`(댓글 웹훅·비공개 답장), `instagram_manage_messages`(DM 보내기·프로필 조회), `pages_manage_metadata`(웹훅 구독), 문서에 따라 `pages_messaging`도 요구됨(비공개 답장 문서). 앱 대시보드에서 정확한 목록을 다시 확인한다 (권한을 필요 이상 요청하면 심사에서 떨어진다).
- **토큰 재발급 필요:** 권한이 늘면 새로 로그인해서 페이지 토큰을 다시 받아야 한다. 받은 뒤 GitHub Secrets의 `IG_ACCESS_TOKEN`을 바꾸고, Worker 쪽 비밀값에도 넣는다. 앱 설정에서 인스타 메시지 "연결된 도구 접근 허용"(인스타 앱 › 설정 › 메시지 › 연결된 도구)을 켜야 한다.

### Meta 앱 심사 (Advanced Access) — 필요함
- 앱에 역할이 없는 일반 사용자에게 보내려면 **Advanced Access**가 필요하고, 이건 **앱 심사 + 비즈니스 인증**이 있어야 받는다. 심사 전(Standard Access)에는 앱 역할이 있는 계정끼리만 시험할 수 있다.
- **가장 큰 걸림돌: 비즈니스 인증.** 사업자 이름·주소가 나온 공식 서류(사업자등록증 등)가 필요하다. 개인 신분증·개인 통장은 안 받는다. 사업자등록이 없으면 Advanced Access를 못 받을 수 있다 → 운영자 확인 필요.
- 준비물:
  - 사용 장면 영상(스크린캐스트): 로그인해서 권한을 주는 과정 + 앱이 메시지를 보내고 인스타 받은 편지함에 도착하는 장면 (스크린샷 말고 녹화). 권한마다 쓰는 장면.
  - 권한마다 사용 목적 설명, 시험 방법.
  - 개인정보처리방침 페이지 URL(앱 공개에 필요) — GitHub Pages에 올린다. 데이터 처리 질문 답변, 매년 Data Use Checkup.
  - 심사 신청 전 30일 안에 권한마다 성공한 API 호출 1번 이상.
- 걸리는 기간: Meta 안내로 보통 1주 안(2~3일인 경우가 많음), 몰리면 더 길다. 비즈니스 인증은 별도로 며칠 더. 반려되면 고쳐서 다시 낸다.

### 구성
- **자료 만들기 (매일 작업 Claude):** 따라 하기 게시물을 만들 때 post.json에 `dm` 필드를 같이 만든다 (예: `keyword`, `reply_text`, `follow_text`, `material_text`, `prompts`, `page`(안내 페이지 내용)). 글로 답하는 프롬프트는 직접 돌려 보고 결과를 넣고, 확인 안 된 효과는 쓰지 않는다. checks.py가 DM 문구 길이(인스타 메시지 1,000자)·금지어를 검사.
- **안내 페이지:** 공개 저장소 GitHub Pages. Actions가 post.json `dm.page`로 `docs/p/<게시물 id>/index.html`을 만든다 (무료). 개인정보처리방침 페이지도 여기에.
- **웹훅 받기:** Cloudflare Workers (GitHub Actions는 웹훅을 못 받음). Meta 웹훅 확인(verify token), `X-Hub-Signature-256` 서명을 앱 시크릿으로 검사, 댓글·메시지·postback 처리, Graph API 호출.
- **보낸 기록:** Cloudflare D1(작은 SQL DB) 표 `sent(comment_id, igsid, post_id, sent_at)`. KV는 무료 쓰기가 하루 1,000건이라 D1이 낫다.
- **어떤 게시물의 자료인지:** Worker가 GitHub Pages에 올린 `dm/<미디어 id>.json`(게시 때 publish.py가 미디어 id와 연결해 만듦)을 읽는다. 비밀값이 아닌 공개 자료만 둔다.

### Cloudflare 비용과 비밀값
- 무료 플랜으로 충분: Workers 하루 10만 요청, D1 하루 읽기 500만 행·쓰기 10만 행, 저장 5GB. 넘으면 그날만 실패(요금 안 붙음).
- 비밀값은 **Cloudflare Worker 비밀값**(`wrangler secret put 이름` 또는 대시보드 › Worker › Settings › Variables and Secrets, 암호화)에만: 페이지 토큰, 앱 시크릿, 웹훅 verify token. GitHub에는 지금처럼 Secrets에만 (`IG_ACCESS_TOKEN` 등), 배포용으로 `CLOUDFLARE_API_TOKEN`(Workers 편집 권한만)을 추가. 코드·wrangler.toml·로그·채팅에는 값을 쓰지 않는다. 토큰 재발급 때 GitHub와 Cloudflare 두 곳을 같이 바꿔야 하므로 token_check.py가 Worker 쪽도 점검하게 한다.

### 운영자가 직접 할 일
1. **사업자등록 여부 확인** (비즈니스 인증 서류). 없으면 이 기능은 Advanced Access를 못 받아 일반 사용자에게 못 보낸다.
2. Meta 비즈니스 포트폴리오에서 비즈니스 인증 신청.
3. 앱 대시보드에서 권한 추가(위 목록), 웹훅 콜백 URL·verify token 등록(Worker 주소는 만든 뒤 알려 줌), 앱 설정에 개인정보처리방침 URL 입력.
4. 다시 로그인해서 새 페이지 토큰 받기 → GitHub Secrets `IG_ACCESS_TOKEN` 교체, Cloudflare Worker 비밀값 입력 (값은 채팅에 쓰지 않는다).
5. 인스타 앱 › 설정 › 메시지 › 연결된 도구 접근 허용 켜기.
6. Cloudflare에서 Workers 편집 권한만 있는 API 토큰 만들어 GitHub Secrets `CLOUDFLARE_API_TOKEN`에 넣기.
7. 시험용 인스타 계정을 앱 역할(테스터)로 추가 → Standard Access로 끝까지 시험 → 사용 장면 녹화 → 앱 심사 제출.

### 다시 시작하면 만들 것 (순서)
1. ~~post.json `dm` 필드 + checks.py 검사 + TEMPLATES/LOCAL.md 절차~~ (외부 도구용으로 이미 만듦)
2. ~~GitHub Pages 안내 페이지~~ (만듦) · 개인정보처리방침 페이지
3. `worker/` (Cloudflare Worker + D1 스키마, wrangler 설정은 비밀값 없이) + 배포 워크플로
4. publish.py: 게시 후 미디어 id ↔ dm 자료 연결
5. 시험 계정으로 Standard Access 시험 → 운영자 심사 제출

- **팔로워 1,000명 되면 카드 비중 재검토 (2026-11-16 운영자 결정):** 지금은 릴스 위주(config slots: 릴스 6칸·daily_target 5, 카드 10:13 1칸). 근거는 data/trends.md '우리 계정 성과'(카드 조회 0~1, 릴스 164~280). 1,000명을 넘으면 카드 칸(예전 10:13·13:13·17:13)과 소식 카드 복귀를 다시 정한다.

- **TTS 더빙 시험 (2026-11-17 예정, 운영자 결정 2026-11-16):** 상업 이용이 되는 한국어 TTS 3~4가지(무료·저비용 위주, 라이선스·약관 확인)로 같은 릴스 한 구간(예: 첫 팔로워 릴스 0~10초)을 더빙해 운영자에게 비교로 보여 준다. 소리 규칙(-14 LUFS, 배경음악은 말소리보다 15~20dB 낮게) 적용. 11/16 첫 팔로워 릴스는 자막과 음악만으로 올렸다.

- **첫 팔로워 릴스 보류 (2026-11-16 운영자 결정):** '현재 팔로워는 0명입니다 / 양질의 소식으로 보답하겠습니다' 계정 소개 릴스는 역효과 우려(0명 표시가 처음 보는 사람의 신뢰를 깎음, 비팔로워에게 얻을 게 적음, 좋은 칸 하나를 씀)로 올리지 않았다. 만든 판(v4, 22.3초)은 experiments/first-followers-reel/에 보관(대기열 밖이라 게시되지 않음). 팔로워 1,000명이나 1만 명이 되면 '0명에서 시작했습니다'로 다시 쓸 수 있다.
