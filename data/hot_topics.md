# 잘 터진 주제 (2026-11-16 15:14 기준)

주제를 고를 때 이 표의 위쪽 주제와 **같거나 비슷한 것**을 먼저 고른다 (STYLE_GUIDE 3장). PR 본문에 "참고한 잘 터진 주제: …" 한 줄을 적는다.

- 자료: `data/benchmarks/*.json`에 저장된 벤치마크 계정 최근 180일 게시물 890개 (팔로워 1천 이상, API 새로 부르지 않음). `agent/benchmarks.py`가 매일 갱신, 단독: `py -3.12 agent/benchmarks.py --hot-topics-only`.
- 배수 = 그 계정 같은 유형(릴스/카드) 중간값 대비. 릴스는 조회수, 카드는 좋아요+3×댓글.
- 순위 = 묶음 안 상위 3개 배수(30배로 자름)의 기하평균. 묶음은 캡션 키워드 규칙(`HOT_TOPICS`)이라 대략이다. 한 게시물이 두 묶음에 들 수 있다.

| 순위 | 주제 | 대표 게시물 (첫 줄) | 반응 배수 | 형식 | 묶음 크기 (2배 이상) |
|---|---|---|---|---|---|
| 1 | AI 영상·영화 만들기 (창작) | @ai.trend.kr: [눈 뭉치 던진 범인이 나라고요? ❄️](https://www.instagram.com/reel/DetX442xkFz/) | 31.7x | 릴스 | 96개 (29) |
| 2 | 돈·일자리·교육 (생활) | @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/) | 309.3x | 릴스 | 81개 (20) |
| 3 | 유명인·CEO 발언 (인용) | @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/) | 25.0x | 릴스 | 107개 (27) |
| 4 | 미중 경쟁·반도체·데이터센터 (산업) | @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/) | 488.9x | 릴스 | 39개 (12) |
| 5 | 챗GPT·제미나이 사진·그림 변환 (창작) | @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/) | 40.3x | 카드 | 115개 (33) |
| 6 | AI 안전·논란 (논란) | @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/) | 483.9x | 릴스 | 23개 (6) |
| 7 | 챗GPT 질문·대화 활용법 (따라 하기) | @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/) | 27.2x | 카드 | 17개 (8) |
| 8 | 새 모델·기능 출시 (소식) | @prompt_what: [바탕화면 정리도 이제 러그로 덮고 모른 척합니다.](https://www.instagram.com/reel/DePBnqgSztY/) | 38.7x | 릴스 | 86개 (20) |
| 9 | MCP·스킬·클로드 코드 자동화 (연결 도구) | @ai.trend.kr: [명령어 한 줄이면 프롬프트 2,000개가 내 AI 에이전트에 통째로 들어옵니다. 🔌](https://www.instagram.com/p/DdTM6hvDw-R/) | 12.0x | 카드 | 127개 (48) |
| 10 | 생활 앱·무료 도구 (생활) | @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/) | 15.5x | 카드 | 25개 (7) |
| 11 | AI로 광고·디자인 만들기 (창작) | @ex.treme.ai: [광고 올릴 때 제일 막히는 건 디자인이 아니라 ”무슨 말로 팔지“입니다.](https://www.instagram.com/p/DaFI7YXGOjf/) | 10.0x | 카드 | 19개 (11) |
| 12 | 대회·무료 지원 (생활) | @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/) | 6.1x | 카드 | 15개 (7) |
| 13 | AI 음악·목소리 (창작) | @ai.trend.kr: [새로 쓴 가사에 AI 목소리, 닷새 만에 117만 뷰가 터졌어요 🔥](https://www.instagram.com/reel/DcvZNlPSOUL/) | 6.0x | 릴스 | 12개 (3) |
| 14 | 주간 요약 (묶음) | @ai.trend.kr: [AI가 이번 주엔 너무 사람 같았어요 🤖](https://www.instagram.com/p/DddjD_vD1Mv/) | 5.5x | 카드 | 14개 (3) |
| 15 | AI 게임 만들기 (창작) | @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/) | 12.7x | 카드 | 3개 (1) |

## 주제별 상위 3개

### AI 영상·영화 만들기 — 순위 점수 25.7, 릴스 56·카드 40, 배수 중간값 1.14x
- 31.7x 릴스 @ai.trend.kr: [눈 뭉치 던진 범인이 나라고요? ❄️](https://www.instagram.com/reel/DetX442xkFz/)
- 24.8x 릴스 @ai.trend.kr: [1편 반응이 뜨거워서 2편을 가져왔는데요, 이건 벌써 4967만 명이 봤습니다 📞](https://www.instagram.com/reel/DdKxQXWv-18/)
- 22.9x 릴스 @ai.trend.kr: [포장해 달라던 선물이 내 거였다고요? 🎁](https://www.instagram.com/reel/DeWZecova75/)

### 돈·일자리·교육 — 순위 점수 20.3, 릴스 46·카드 35, 배수 중간값 0.88x
- 309.3x 릴스 @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/)
- 21.6x 릴스 @ai.talk.kr: [“AI 시장, 결국 치킨 게임으로 가고 있는 걸까요?”](https://www.instagram.com/reel/DcDWvDKpGBj/)
- 13.0x 릴스 @ai.talk.kr: [“AI 시대, 지금 IT 직장인들은 어떤 상태일까요?”](https://www.instagram.com/reel/DbhgWt9JVbu/)

### 유명인·CEO 발언 — 순위 점수 20.1, 릴스 95·카드 12, 배수 중간값 0.99x
- 25.0x 릴스 @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/)
- 18.1x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)
- 18.0x 릴스 @ai.talk.kr: [“일론 머스크는 왜 샘 올트먼을 믿지 않는 걸까요?”](https://www.instagram.com/reel/DbzUQ_VvaxQ/)

### 미중 경쟁·반도체·데이터센터 — 순위 점수 17.8, 릴스 32·카드 7, 배수 중간값 1.44x
- 488.9x 릴스 @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/)
- 18.1x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)
- 10.3x 릴스 @ai.talk.kr: [“챗GPT에 질문할 때마다 물이 사용된다는 사실, 알고 계셨나요?”](https://www.instagram.com/reel/DcCmtLip1ZU/)

### 챗GPT·제미나이 사진·그림 변환 — 순위 점수 17.8, 릴스 51·카드 64, 배수 중간값 0.98x
- 40.3x 카드 @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/)
- 22.0x 카드 @ai.trend.kr: [핸드폰 배경화면을 바꿨더니, 하루에도 몇 번씩 꺼내 보게 됐어요.🐾](https://www.instagram.com/p/DcdMcZDjzBL/)
- 8.5x 카드 @ex.treme.ai: [브랜드 URL 하나, 제품 사진 한 장이면](https://www.instagram.com/p/DY35VLhmPJJ/)

### AI 안전·논란 — 순위 점수 15.6, 릴스 17·카드 6, 배수 중간값 0.87x
- 483.9x 릴스 @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/)
- 18.6x 릴스 @prompt_what: [좋아요 8만 5천 개를 넘긴 강아지 시트콤 3화가 나왔습니다 🍣](https://www.instagram.com/reel/Dd3he1Cy2T-/)
- 6.8x 카드 @ai.asap.kr: [OpenDataLoader PDF는 PDF를 마크다운과 JSON, HTML로 바꾸는 파서입니다. 읽기 순서와 표, 제목 구조를 지키고 모든 요소](https://www.instagram.com/p/Dc5wGU0D4Un/)

### 챗GPT 질문·대화 활용법 — 순위 점수 14.3, 릴스 5·카드 12, 배수 중간값 1.99x
- 27.2x 카드 @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/)
- 10.4x 카드 @ai.trend.kr: [GPT한테 내 연애 스타일을 물어봤더니, 말한 적도 없는 취향까지 나왔어요. 💘](https://www.instagram.com/p/DeOdX4okWIu/)
- 10.3x 카드 @ai.trend.kr: [이제 프롬프트 필요 없이 명령어만 붙이세요. 🎨](https://www.instagram.com/p/Dc92nT7j8PP/)

### 새 모델·기능 출시 — 순위 점수 10.9, 릴스 13·카드 73, 배수 중간값 0.96x
- 38.7x 릴스 @prompt_what: [바탕화면 정리도 이제 러그로 덮고 모른 척합니다.](https://www.instagram.com/reel/DePBnqgSztY/)
- 7.4x 카드 @ai.asap.kr: [오픈AI가 금융권 전용 ChatGPT를 내놨습니다. 9월 10일 발표한 ChatGPT for Financial Services입니다.](https://www.instagram.com/p/DdP7he-D9nI/)
- 5.9x 릴스 @prompt_what: [Mirelo가 영상의 소리만 바꾸는 SFX 2.0을 공개했습니다 🎬](https://www.instagram.com/reel/Desk9fmyOFm/)

### MCP·스킬·클로드 코드 자동화 — 순위 점수 10.3, 릴스 16·카드 111, 배수 중간값 1.25x
- 12.0x 카드 @ai.trend.kr: [명령어 한 줄이면 프롬프트 2,000개가 내 AI 에이전트에 통째로 들어옵니다. 🔌](https://www.instagram.com/p/DdTM6hvDw-R/)
- 10.3x 카드 @ai.asap.kr: [abtop은 터미널에서 도는 AI 코딩 에이전트를 한 화면에 모아 보는 모니터입니다.](https://www.instagram.com/p/DdId7_Lj4mH/)
- 8.9x 카드 @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/)

### 생활 앱·무료 도구 — 순위 점수 8.2, 릴스 1·카드 24, 배수 중간값 1.19x
- 15.5x 카드 @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/)
- 6.7x 카드 @ai.asap.kr: [DockDoor는 맥 독에 윈도우처럼 창 미리보기를 붙여 주는 무료 오픈소스 앱입니다. 독을 바꾸지 않고 메뉴바에서 돌아가며 기존 독에 기능을](https://www.instagram.com/p/DeIvEO_j3xU/)
- 5.4x 카드 @ai.asap.kr: [Plexo는 윈도우·맥·리눅스용 다운로드 앱입니다. 파일을 조각으로 나눠 와이파이, 유선, USB로 연결한 휴대폰, 셀룰러 같은 여러 네트워크에](https://www.instagram.com/p/Dd_Kxs4jy4j/)

### AI로 광고·디자인 만들기 — 순위 점수 7.9, 릴스 5·카드 14, 배수 중간값 2.61x
- 10.0x 카드 @ex.treme.ai: [광고 올릴 때 제일 막히는 건 디자인이 아니라 ”무슨 말로 팔지“입니다.](https://www.instagram.com/p/DaFI7YXGOjf/)
- 8.9x 카드 @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/)
- 5.5x 릴스 @prompt_what: [대충 찍은 사진 한 장이 광고 이미지로 탄생합니다 📸](https://www.instagram.com/reel/De0XfxiyD4L/)

### 대회·무료 지원 — 순위 점수 6.0, 릴스 3·카드 12, 배수 중간값 1.25x
- 6.1x 카드 @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/)
- 6.1x 카드 @ai.asap.kr: [Open-Science는 연구자를 위한 AI 작업대입니다. 하고 싶은 분석을 말로 적으면 자료를 찾고 파이썬이나 R 코드를 돌려 표와 그림을 만](https://www.instagram.com/p/Dd6E7Cxj4YS/)
- 5.8x 카드 @ai.asap.kr: [AI 잘 쓰는 사람 100명을 뽑는 대회가 10월 1일 신청을 엽니다. 총 상금은 1억 2,500만 원입니다.](https://www.instagram.com/p/Dd7u5IvD9uD/)

### AI 음악·목소리 — 순위 점수 4.6, 릴스 5·카드 7, 배수 중간값 1.04x
- 6.0x 릴스 @ai.trend.kr: [새로 쓴 가사에 AI 목소리, 닷새 만에 117만 뷰가 터졌어요 🔥](https://www.instagram.com/reel/DcvZNlPSOUL/)
- 4.8x 카드 @ai.asap.kr: [Lemo-Opuscar는 Claude Code에 설치해 쓰는 영상 스타일 모음입니다. 대표작 OPUSCAR 98은 아카데미 작품상 98편을 영화](https://www.instagram.com/p/DfVni0MD5Ql/)
- 3.3x 릴스 @ai.trend.kr: [힙합을 판소리로 바꾼 AI 영상, 닷새 만에 60만이 봤어요 🎶](https://www.instagram.com/reel/Dcmxdrgv3vR/)

### 주간 요약 — 순위 점수 3.2, 릴스 0·카드 14, 배수 중간값 1.10x
- 5.5x 카드 @ai.trend.kr: [AI가 이번 주엔 너무 사람 같았어요 🤖](https://www.instagram.com/p/DddjD_vD1Mv/)
- 2.5x 카드 @ai.asap.kr: [맥북 노치를 그냥 두고 있다면 Boring Notch가 그 자리를 아이폰 다이내믹 아일랜드처럼 바꿔 줍니다. 노치에 마우스를 올리면 재생 중인](https://www.instagram.com/p/DfGEROUk8_E/)
- 2.4x 카드 @ai.trend.kr: [이번 주 AI, 내 노트북부터 공부법까지 바꿨어요 🚀](https://www.instagram.com/p/DfLgRIPjxxY/)

### AI 게임 만들기 — 순위 점수 2.4, 릴스 0·카드 3, 배수 중간값 1.50x
- 12.7x 카드 @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/)
- 1.5x 카드 @ai.trend.kr: [초파리한테는 조금 미안한 한 주였어요. 🪰](https://www.instagram.com/p/DdI8UKQj6hJ/)
- 0.7x 카드 @ai.asap.kr: [universal-modder는 게임 엔진 파악부터 코드 분석, 모드 제작, 그림·3D·소리 생성, 실제 게임에서의 시험, 시연 영상 편집까지](https://www.instagram.com/p/Dejs6cyD5RQ/)

## 분류 안 된 2배 이상 게시물 (키워드 보강 대상)

- 125.0x 릴스 @prompt_what: 황궁에서 벌어지는 맞불륜, 전개는 한국 막장 드라마입니다.
- 49.2x 카드 @bizucafe: 광고(廣告). 한문으로 널리 알린다는 뜻이다.. 많은 사람들에게 무언가 정보를 알리는 것..
- 27.6x 릴스 @prompt_what: 1화가 333만 번 재생된 K-막장 로판, 이번엔 2화입니다 🎬
- 14.9x 릴스 @prompt_what: 댓글에 ‘Elsa’ 남겨주시면 프롬프트 보내드릴게요 ❄️
- 8.9x 릴스 @prompt_what: 이제 알바 그만하고 이걸로 수익화하세요🚌
- 7.3x 릴스 @prompt_what: 칵테일 잔을 든 포메라니안이 퇴근한 집사에게 밥 투정을 합니다 🍸
- 6.9x 릴스 @bizucafe: 우린 이미 너무 늦었다 (유발 하라리)
- 6.1x 릴스 @bizucafe: 갓 대학 졸업한 '경영 컨설턴트'
- 6.0x 릴스 @bizucafe: 창업 한번 해보세요 (유튜브 창업자 Steve Chen)
- 4.9x 릴스 @bizucafe: 우리 아이 첫 남친이 AI가 됩니다 (유발 하라리)
