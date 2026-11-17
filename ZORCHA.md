# Zorcha 댓글 자동 DM 설정 절차 ('Zorcha 담당' 세션이 따른다)

운영자 결정(2026-11-16): 참여형('자료') 게시물이 인스타에 올라가면, Zorcha에 그 게시물 전용 자동화를 만든다. 운영자가 로그인해 둔 Claude 앱 브라우저 창에서 직접 조작한다.

## 언제
- 명령 에이전트(또는 publish 결과)가 "Zorcha 설정 필요: <게시물>, 링크, 자료 페이지 주소, DM 문구"를 보내면 바로.
- 이미 그 게시물 자동화가 있으면 만들지 않는다(Automations 목록 확인).

## 어디서
- https://zorcha.com/app → Automations (워크스페이스 '토큰전쟁 | AI 뉴스', 인스타 tokenwar_ai 연결됨).
- 운영자 구글 계정으로 로그인돼 있다. 로그아웃돼 있으면 운영자에게 로그인을 부탁한다(직접 로그인하지 않는다).
- 브라우저 창이 좁으면 화면 크기를 1280x1000으로 키워서 조작하고, 끝나면 원래대로 돌린다.

## 만드는 순서 (DM from Comments)
1. New Automation → DM from Comments.
2. **Select a Post or Reel**: 해당 게시물 하나만 고른다(Any post or reel은 끔 — 게시물마다 자료 페이지가 다르기 때문). 고른 뒤 `input[name=instagram_content]`의 checked 값으로 확인.
3. **Setup Keywords**: Any keyword 켬 (아무 댓글에나 반응).
4. **Send a DM**: DM 문구 입력 → Add Link → 제목 `자료 보기`, 주소 = 그 게시물 자료 페이지(https://vmvm0406.github.io/tokenwar-agent/p/<id>/) → Add Link. 링크 행이 생겼는지 확인.
5. **Public reply to comments** 켬 → 기본 영어 답글 3개를 아래 한국어로 바꾼다(아래 칸부터 바꾸면 줄바꿈으로 위치가 밀리지 않는다):
   - DM으로 보내 드렸어요 📩 처음 받으시면 요청함에서 '수락'을 눌러 주세요.
   - 자료 보내 드렸어요 🙌 보이지 않으시면 메시지 요청함을 확인해 주세요.
   - 방금 DM 드렸어요 ✉️ 처음 받으시면 요청함에 있을 수 있어요.
   (말투: 친근하지만 정돈되게, 느낌표·이모지 없이 '~드려요/~해 보세요'. '~하십시오/~바랍니다' 금지, 운영자 결정 2026-11-17, STYLE_GUIDE 7-1. DM 문구는 게시물의 dm.md 그대로.)
   (운영자 결정 2026-11-16: 처음 받는 사람은 DM이 '메시지 요청함'으로 가므로 공개 답글마다 요청함 안내를 넣는다. 답글 칸은 contenteditable라 칸을 선택한 뒤 입력하고, 위쪽 Update 버튼으로 저장한다. 기존 자동화의 답글을 고칠 때도 같다.)
6. **Opening Message** 켬(팔로우 확인에 필요) → `댓글 고마워요 😊 아래 'Send me the link'를 누르면 자료를 바로 보내 드릴게요.`
7. **Ask to follow before sending DM** 켬 → `팔로우한 분께 자료를 보내 드려요 🙏 아래 'Visit Profile'에서 팔로우하신 뒤 'I'm following'을 누르면 바로 보내 드릴게요.` (버튼 이름은 무료 요금제에서 바꿀 수 없어 영어 그대로)
8. 아래 'Errors'가 0인지 확인 → **Go Live**. "Automation is now live"가 뜨면 끝. 목록에서 Live 확인.
9. 광고 팝업·WhatsApp 번호 요청·채팅 말풍선은 닫기만 한다. 전화번호 같은 개인정보는 넣지 않는다. 결제·요금제 업그레이드는 누르지 않는다.

## 끝나면
- 최상위 세션에 한 줄: "<게시물 제목> Zorcha 자동화 Live". 운영자에게 다른 계정으로 댓글 달아 시험해 보라고 권한다.

## 지금까지 만든 것
- 2026-11-16 수묵화 릴스(Dfzdhackgip) — Live
- 2026-11-16 화풍 스킬 릴스(DfzOGe_iqPS) — Live
- 2026-11-17 메타 카드 v2(Df0z8Upie5e) — Live
- 2026-11-17 조명 릴스(Df02CTVgaJb) — Live
