# 잘 터진 주제 (2026-11-17 22:52 기준)

주제를 고를 때 이 표의 위쪽 주제와 **같거나 비슷한 것**을 먼저 고른다 (STYLE_GUIDE 3장). PR 본문에 "참고한 잘 터진 주제: …" 한 줄을 적는다.

- 자료: `data/benchmarks/*.json`에 저장된 벤치마크 계정 최근 180일 게시물 1486개 (팔로워 1천 이상, API 새로 부르지 않음). `agent/benchmarks.py`가 매일 갱신, 단독: `py -3.12 agent/benchmarks.py --hot-topics-only`.
- 배수 = 그 계정 같은 유형(릴스/카드) 중간값 대비. 릴스는 조회수, 카드는 좋아요+3×댓글.
- 순위 = 묶음 안 상위 3개 배수(30배로 자름)의 기하평균. 묶음은 캡션 키워드 규칙(`HOT_TOPICS`)이라 대략이다. 한 게시물이 두 묶음에 들 수 있다.

| 순위 | 주제 | 대표 게시물 (첫 줄) | 반응 배수 | 형식 | 묶음 크기 (2배 이상) |
|---|---|---|---|---|---|
| 1 | AI 영상·영화 만들기 (창작) | @soheejeon_: [그동안 나르시시스트도 같이 요청이 많았어서](https://www.instagram.com/reel/DaFaoQnBiUV/) | 44.2x | 릴스 | 176개 (51) |
| 2 | 돈·일자리·교육 (생활) | @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/) | 304.8x | 릴스 | 112개 (28) |
| 3 | 유명인·CEO 발언 (인용) | @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/) | 25.7x | 릴스 | 119개 (31) |
| 4 | 챗GPT·제미나이 사진·그림 변환 (창작) | @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/) | 40.6x | 카드 | 154개 (36) |
| 5 | 미중 경쟁·반도체·데이터센터 (산업) | @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/) | 481.7x | 릴스 | 43개 (14) |
| 6 | 새 모델·기능 출시 (소식) | @prompt_what: [바탕화면 정리도 이제 러그로 덮고 모른 척합니다.](https://www.instagram.com/reel/DePBnqgSztY/) | 38.7x | 릴스 | 115개 (27) |
| 7 | AI 안전·논란 (논란) | @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/) | 476.8x | 릴스 | 27개 (7) |
| 8 | 챗GPT 질문·대화 활용법 (따라 하기) | @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/) | 27.4x | 카드 | 22개 (10) |
| 9 | MCP·스킬·클로드 코드 자동화 (연결 도구) | @trenddalkak.ai: [AI 잘 쓰는 디자이너라면? 개발자분들도? 잘 쓰고 싶은 모든 사람들?](https://www.instagram.com/p/DajXgOPgeAS/) | 12.7x | 카드 | 206개 (77) |
| 10 | AI 게임 만들기 (창작) | @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/) | 12.8x | 카드 | 17개 (4) |
| 11 | 생활 앱·무료 도구 (생활) | @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/) | 15.8x | 카드 | 29개 (7) |
| 12 | AI 음악·목소리 (창작) | @gojaehyun.go: [오늘은 갤럭시 폴드를 접으면 점프하는 애벌레 게임을 만들었어요. 말 그대로 뻘리 접으면 높이 점프해요. 근데 이거 엄청 재밌음 ㅋㅋㅋㅋㅋ 배경음](https://www.instagram.com/reel/DcicLdKPaaW/) | 8.9x | 릴스 | 29개 (6) |
| 13 | 대회·무료 지원 (생활) | @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/) | 6.3x | 카드 | 20개 (8) |
| 14 | 주간 요약 (묶음) | @soheejeon_: [본업때문에 한개도 못했다는 슬픈 전설이...](https://www.instagram.com/reel/De_yUKXBj0e/) | 8.0x | 릴스 | 18개 (5) |
| 15 | AI로 광고·디자인 만들기 (창작) | @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/) | 9.1x | 카드 | 9개 (5) |

## 주제별 상위 3개

### AI 영상·영화 만들기 — 순위 점수 28.1, 릴스 123·카드 53, 배수 중간값 1.17x
- 44.2x 릴스 @soheejeon_: [그동안 나르시시스트도 같이 요청이 많았어서](https://www.instagram.com/reel/DaFaoQnBiUV/)
- 31.7x 릴스 @ai.trend.kr: [눈 뭉치 던진 범인이 나라고요? ❄️](https://www.instagram.com/reel/DetX442xkFz/)
- 24.8x 릴스 @ai.trend.kr: [1편 반응이 뜨거워서 2편을 가져왔는데요, 이건 벌써 4967만 명이 봤습니다 📞](https://www.instagram.com/reel/DdKxQXWv-18/)

### 돈·일자리·교육 — 순위 점수 25.5, 릴스 63·카드 49, 배수 중간값 0.89x
- 304.8x 릴스 @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/)
- 26.0x 릴스 @gojaehyun.go: [오늘은 갤럭시 Z폴드8로 오타마톤을 만들었어요. 힌지 걱정해주시는 분들 많은데 갤럭시는 내구성이 아주 좋아서 괜찮아요. ㅎㅎ](https://www.instagram.com/reel/DdENwWivW9L/)
- 21.3x 릴스 @ai.talk.kr: [“AI 시장, 결국 치킨 게임으로 가고 있는 걸까요?”](https://www.instagram.com/reel/DcDWvDKpGBj/)

### 유명인·CEO 발언 — 순위 점수 21.9, 릴스 106·카드 13, 배수 중간값 1.02x
- 25.7x 릴스 @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/)
- 23.3x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)
- 17.7x 릴스 @ai.talk.kr: [“일론 머스크는 왜 샘 올트먼을 믿지 않는 걸까요?”](https://www.instagram.com/reel/DbzUQ_VvaxQ/)

### 챗GPT·제미나이 사진·그림 변환 — 순위 점수 19.8, 릴스 77·카드 77, 배수 중간값 0.90x
- 40.6x 카드 @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/)
- 22.1x 카드 @ai.trend.kr: [핸드폰 배경화면을 바꿨더니, 하루에도 몇 번씩 꺼내 보게 됐어요.🐾](https://www.instagram.com/p/DcdMcZDjzBL/)
- 11.8x 릴스 @ai_dori_: [클로드 Sonnet 5 모델 출시! 힉스필드 MCP ai 연결해서 손그림으로 목업포스터 만드는 법😉 ( 제작지원 higgsfield.ai )](https://www.instagram.com/reel/Dah7Vb6zCtT/)

### 미중 경쟁·반도체·데이터센터 — 순위 점수 19.2, 릴스 34·카드 9, 배수 중간값 1.24x
- 481.7x 릴스 @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/)
- 23.3x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)
- 10.2x 릴스 @ai.talk.kr: [“챗GPT에 질문할 때마다 물이 사용된다는 사실, 알고 계셨나요?”](https://www.instagram.com/reel/DcCmtLip1ZU/)

### 새 모델·기능 출시 — 순위 점수 16.0, 릴스 26·카드 89, 배수 중간값 1.03x
- 38.7x 릴스 @prompt_what: [바탕화면 정리도 이제 러그로 덮고 모른 척합니다.](https://www.instagram.com/reel/DePBnqgSztY/)
- 18.2x 릴스 @gojaehyun.go: [오늘은 갤럭시 폴드8로 아이폰 듀오를 만들어봤어요. 열고 닫는 인터랙션이 무척 멋져서 따라해봤습니다! 사실 아이폰 출시하자마자 개발을 시작했는데](https://www.instagram.com/reel/DdJSHBuvNw5/)
- 7.5x 카드 @ai.asap.kr: [오픈AI가 금융권 전용 ChatGPT를 내놨습니다. 9월 10일 발표한 ChatGPT for Financial Services입니다.](https://www.instagram.com/p/DdP7he-D9nI/)

### AI 안전·논란 — 순위 점수 15.7, 릴스 21·카드 6, 배수 중간값 0.89x
- 476.8x 릴스 @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/)
- 18.6x 릴스 @prompt_what: [좋아요 8만 5천 개를 넘긴 강아지 시트콤 3화가 나왔습니다 🍣](https://www.instagram.com/reel/Dd3he1Cy2T-/)
- 7.0x 카드 @ai.asap.kr: [OpenDataLoader PDF는 PDF를 마크다운과 JSON, HTML로 바꾸는 파서입니다. 읽기 순서와 표, 제목 구조를 지키고 모든 요소](https://www.instagram.com/p/Dc5wGU0D4Un/)

### 챗GPT 질문·대화 활용법 — 순위 점수 14.4, 릴스 7·카드 15, 배수 중간값 1.23x
- 27.4x 카드 @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/)
- 10.5x 카드 @ai.trend.kr: [GPT한테 내 연애 스타일을 물어봤더니, 말한 적도 없는 취향까지 나왔어요. 💘](https://www.instagram.com/p/DeOdX4okWIu/)
- 10.3x 카드 @ai.trend.kr: [이제 프롬프트 필요 없이 명령어만 붙이세요. 🎨](https://www.instagram.com/p/Dc92nT7j8PP/)

### MCP·스킬·클로드 코드 자동화 — 순위 점수 12.2, 릴스 71·카드 135, 배수 중간값 1.23x
- 12.7x 카드 @trenddalkak.ai: [AI 잘 쓰는 디자이너라면? 개발자분들도? 잘 쓰고 싶은 모든 사람들?](https://www.instagram.com/p/DajXgOPgeAS/)
- 12.1x 카드 @ai.trend.kr: [명령어 한 줄이면 프롬프트 2,000개가 내 AI 에이전트에 통째로 들어옵니다. 🔌](https://www.instagram.com/p/DdTM6hvDw-R/)
- 11.8x 릴스 @ai_dori_: [클로드 Sonnet 5 모델 출시! 힉스필드 MCP ai 연결해서 손그림으로 목업포스터 만드는 법😉 ( 제작지원 higgsfield.ai )](https://www.instagram.com/reel/Dah7Vb6zCtT/)

### AI 게임 만들기 — 순위 점수 9.4, 릴스 12·카드 5, 배수 중간값 0.83x
- 12.8x 카드 @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/)
- 8.9x 릴스 @gojaehyun.go: [오늘은 갤럭시 폴드를 접으면 점프하는 애벌레 게임을 만들었어요. 말 그대로 뻘리 접으면 높이 점프해요. 근데 이거 엄청 재밌음 ㅋㅋㅋㅋㅋ 배경음](https://www.instagram.com/reel/DcicLdKPaaW/)
- 7.2x 릴스 @gojaehyun.go: [오늘은 에어팟으로 마우스를 만들었어요. 에어팟의 가속도센서를 활용한 거예요! 케이스에 넣은 채로 작동하게 하는 게 어려웠어요.(방법이 되게 킹받](https://www.instagram.com/reel/DfB9L5GPJr7/)

### 생활 앱·무료 도구 — 순위 점수 8.4, 릴스 5·카드 24, 배수 중간값 1.11x
- 15.8x 카드 @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/)
- 6.8x 카드 @ai.asap.kr: [DockDoor는 맥 독에 윈도우처럼 창 미리보기를 붙여 주는 무료 오픈소스 앱입니다. 독을 바꾸지 않고 메뉴바에서 돌아가며 기존 독에 기능을](https://www.instagram.com/p/DeIvEO_j3xU/)
- 5.6x 카드 @ai.asap.kr: [Plexo는 윈도우·맥·리눅스용 다운로드 앱입니다. 파일을 조각으로 나눠 와이파이, 유선, USB로 연결한 휴대폰, 셀룰러 같은 여러 네트워크에](https://www.instagram.com/p/Dd_Kxs4jy4j/)

### AI 음악·목소리 — 순위 점수 6.5, 릴스 22·카드 7, 배수 중간값 0.89x
- 8.9x 릴스 @gojaehyun.go: [오늘은 갤럭시 폴드를 접으면 점프하는 애벌레 게임을 만들었어요. 말 그대로 뻘리 접으면 높이 점프해요. 근데 이거 엄청 재밌음 ㅋㅋㅋㅋㅋ 배경음](https://www.instagram.com/reel/DcicLdKPaaW/)
- 6.0x 릴스 @ai.trend.kr: [새로 쓴 가사에 AI 목소리, 닷새 만에 117만 뷰가 터졌어요 🔥](https://www.instagram.com/reel/DcvZNlPSOUL/)
- 5.1x 카드 @ai.asap.kr: [Lemo-Opuscar는 Claude Code에 설치해 쓰는 영상 스타일 모음입니다. 대표작 OPUSCAR 98은 아카데미 작품상 98편을 영화](https://www.instagram.com/p/DfVni0MD5Ql/)

### 대회·무료 지원 — 순위 점수 6.2, 릴스 8·카드 12, 배수 중간값 1.09x
- 6.3x 카드 @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/)
- 6.2x 카드 @ai.asap.kr: [Open-Science는 연구자를 위한 AI 작업대입니다. 하고 싶은 분석을 말로 적으면 자료를 찾고 파이썬이나 R 코드를 돌려 표와 그림을 만](https://www.instagram.com/p/Dd6E7Cxj4YS/)
- 6.0x 카드 @ai.asap.kr: [AI 잘 쓰는 사람 100명을 뽑는 대회가 10월 1일 신청을 엽니다. 총 상금은 1억 2,500만 원입니다.](https://www.instagram.com/p/Dd7u5IvD9uD/)

### 주간 요약 — 순위 점수 5.5, 릴스 1·카드 17, 배수 중간값 1.11x
- 8.0x 릴스 @soheejeon_: [본업때문에 한개도 못했다는 슬픈 전설이...](https://www.instagram.com/reel/De_yUKXBj0e/)
- 5.5x 카드 @ai.trend.kr: [AI가 이번 주엔 너무 사람 같았어요 🤖](https://www.instagram.com/p/DddjD_vD1Mv/)
- 3.9x 카드 @trenddalkak.ai: [클로드의 뇌를 훔치자](https://www.instagram.com/p/Dag_m0Dge6v/)

### AI로 광고·디자인 만들기 — 순위 점수 5.5, 릴스 6·카드 3, 배수 중간값 2.63x
- 9.1x 카드 @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/)
- 5.5x 릴스 @prompt_what: [대충 찍은 사진 한 장이 광고 이미지로 탄생합니다 📸](https://www.instagram.com/reel/De0XfxiyD4L/)
- 3.3x 릴스 @prompt_what: [대충 찍은 사진 한 장이 광고 이미지로 탄생합니다 📸](https://www.instagram.com/reel/Desq_LYyr-_/)

## 분류 안 된 2배 이상 게시물 (키워드 보강 대상)

- 146.1x 릴스 @soheejeon_: 이 입체적인 서양놈들아 좋겠다
- 125.0x 릴스 @prompt_what: 황궁에서 벌어지는 맞불륜, 전개는 한국 막장 드라마입니다.
- 82.1x 릴스 @yangyum.zip: 타이핑하면 한 코씩 채워지는 타이포 웹! 팔로우하고 직접 해보세요!
- 75.8x 릴스 @soheejeon_: 내가 공황올때 들으려고 만든 거
- 53.0x 카드 @bizucafe: 광고(廣告). 한문으로 널리 알린다는 뜻이다.. 많은 사람들에게 무언가 정보를 알리는 것..
- 42.4x 릴스 @soheejeon_: (캡션 없음)
- 35.5x 릴스 @soheejeon_: 맡은 프로젝트만 80개,
- 34.7x 카드 @gojaehyun.go: 이빨에 초밥이 끼면?
- 34.5x 릴스 @gojaehyun.go: 오늘은 세상에서 제일 빠른 투두리스트 앱을 만들었어요. 잠금화면에서 바로 할 일을 넣고 체크할 수 있어요. 완전 요긴해요! ㅎㅎ 할 일 맨날 까
- 27.6x 릴스 @prompt_what: 1화가 333만 번 재생된 K-막장 로판, 이번엔 2화입니다 🎬
