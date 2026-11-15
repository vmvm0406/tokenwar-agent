# 이어서 할 일 (2026-11-15 대화에서 넘어온 것)

claude.ai 대화에서 하던 작업을 이 컴퓨터의 Claude Code로 옮겼다. 정해진 규칙은 이미 STYLE_GUIDE/CLAUDE.md에 들어가 있다. 아래는 **아직 안 끝난 것**이다. 하나 끝날 때마다 이 파일에서 지운다.

## 운영자 답을 기다리는 것
1. **릴스 새 화면(CRT 터미널) 채택 여부** — `experiments/reel-crt/` v7. 운영자 반응: 영상과 아래가 따로 노는 느낌 → 붙임, 상태줄 불필요 → 뺌, 영상이 너무 위 → 안전 영역으로 내림. 괜찮다고 하면 `agent/video.py`를 이 구조로 바꾸고 post.json에 아래 요약(`term` 장면들: 신문 제목체) 형식을 TEMPLATES.md에 추가, LOCAL.md/CLIPS.md 절차 수정.
2. **주간 요약 카드뉴스** — 샘플 완성: `samples/s11-weekly-ai` (11월 둘째 주, 소식 4개: 삼성 AI 안경·제미나이 카플레이·구글 검색 새 모델·챗GPT 기업 프로필, 소식마다 위쪽 공식 사진 + 번호·제목·설명). 본문 장 `num`/`num_note` 필드 추가함. 운영자가 보고 정한다. 운영자 의견(11-15): 초기 계정은 릴스가 우선, 릴스를 더 많이 찍어내야 함. — 운영자: "이번 주 AI에서 사진·영상 자료를 안 쓴 게 문제". 제안: 매주 일요일 "N월 N주 차 AI 뉴스" 카드뉴스 (ai.trend.kr 7,476 좋아요 글 구조: 강렬한 사진 표지 + 소식마다 한 장, 위쪽에 실제 사진·화면·영상, 아래 번호·제목·설명 3~4줄). 운영자가 샘플을 보고 정한다. 할 일: 오늘 소식으로 샘플 → 승인되면 STYLE_GUIDE의 "한 게시물에 소식 하나" 규칙에 주간 요약 예외 추가, dupes.py에서 주간 요약은 주제 겹침 예외, 캐러셀에 영상 장을 섞으려면 publish.py에 VIDEO 자식 추가.
3. **댓글 자동 DM (팔로우 확인 방식)** — 설계·조사 끝, 운영자 승인 대기. 아래 "댓글 자동 DM 설계" 절. 승인 전에는 만들지 않는다.
4. **따라 하기 형식 샘플** — `samples/s12-howto-ai-mode`(카드뉴스 7장), `samples/s13-howto-ai-mode-reel`(카드형 모션 릴스, 장면 6개). 구글 AI 모드에 실제로 넣은 질문과 답 화면(11월 15일). 형식·검사·절차는 이미 main에 들어감(TEMPLATES "게시물 형식", checks.py `format`, LOCAL.md 1장). 운영자가 모양을 보고 고칠 점을 말하면 반영. 릴스 mp4는 이 컴퓨터에 ffmpeg가 없어 아직 안 만들어 봄 → ffmpeg 설치(`winget install Gyan.FFmpeg`) 후 `py -3.12 agent/render.py samples/s13-howto-ai-mode-reel`로 확인.

## 확인할 것
- `agent/video.py` 안전 영역 반영(제목 285px부터, 자막 1250px 넘으면 영상 안으로) 후 실제 릴스를 아직 렌더링해 보지 않았다. `py -3.12 agent/render.py samples/s8-huang-quote`로 장면 미리보기 확인.
- 2026-11-15 첫 실행: 카드뉴스 PR #2(세무사 AI 부정행위) 운영자 확인 대기, 릴스 브랜치 `post/2026-11-15-reel`(머스크 칩 발언) PR 생성 여부 확인.
- 카드뉴스 화면 캡처(`agent/shot.py`)는 PR #2에서 처음 제대로 돌았다. 표지 AI 그림이 실제 사진처럼 보이지 않는지 계속 본다.

## 댓글 자동 DM 설계 (2026-11-15 조사, 아직 만들지 않음)

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

### 덧붙임 (2026-11-15 두 번째 조사)
- **웹훅 서버 없이 시작하는 방법:** 비공개 답장은 댓글 뒤 7일 안이면 되므로, Cloudflare Worker 대신 GitHub Actions가 15분마다 최근 게시물 댓글(`GET /<미디어 id>/comments`)을 읽고 아직 안 보낸 댓글에 비공개 답장을 보내는 방식도 된다 (보낸 기록은 저장소 파일). 단점: 최대 15분 늦음, 상대가 답장한 뒤의 24시간 대화(팔로우 확인·버튼)는 웹훅이 있어야 바로 응답할 수 있다. 자료를 첫 답장 한 번에 다 주는 단순한 흐름(팔로우 확인 없음)이면 이 방식으로 충분하다.
- **로그인 방식별 권한 (Meta 비공개 답장 문서):** Facebook 로그인(지금 우리 방식) = `instagram_basic`, `instagram_manage_comments`, `pages_read_engagement`(+ 비즈니스 관리자 역할이면 `ads_management`, `ads_read`). Instagram 로그인 = `instagram_business_basic`, `instagram_business_manage_comments` (호스트 graph.instagram.com). 메시지를 더 주고받으려면(팔로우 확인 등) 메시지 권한(`instagram_manage_messages` / `instagram_business_manage_messages`)이 추가로 필요하다.
- **데이터:** ai.trend.kr 릴스 중 첫 줄부터 "댓글에 'OO' 남겨 주세요"로 시작한 6개는 조회수 중앙 33,773으로 전체 중앙 90,508의 37%. 카드뉴스에서는 DM 미끼가 댓글을 2배(중앙 397 vs 200) 올렸지만 좋아요는 그대로였다 (STYLE_GUIDE 3-1). → 하게 되면 카드뉴스 캡션 끝에만 쓰고, 릴스 첫 줄에는 쓰지 않는다.

### 승인하면 만들 것 (순서)
1. post.json `dm` 필드 + checks.py 검사 + TEMPLATES/LOCAL.md 절차
2. GitHub Pages 안내 페이지·개인정보처리방침 생성 (Actions)
3. `worker/` (Cloudflare Worker + D1 스키마, wrangler 설정은 비밀값 없이) + 배포 워크플로
4. publish.py: 게시 후 미디어 id ↔ dm 자료 연결
5. 시험 계정으로 Standard Access 시험 → 운영자 심사 제출
