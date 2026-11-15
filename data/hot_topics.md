# 잘 터진 주제 (2026-11-16 00:36 기준)

주제를 고를 때 이 표의 위쪽 주제와 **같거나 비슷한 것**을 먼저 고른다 (STYLE_GUIDE 3장). PR 본문에 "참고한 잘 터진 주제: …" 한 줄을 적는다.

- 자료: `data/benchmarks/*.json`에 저장된 벤치마크 계정 최근 180일 게시물 682개 (팔로워 1천 이상, API 새로 부르지 않음). `agent/benchmarks.py`가 매일 갱신, 단독: `py -3.12 agent/benchmarks.py --hot-topics-only`.
- 배수 = 그 계정 같은 유형(릴스/카드) 중간값 대비. 릴스는 조회수, 카드는 좋아요+3×댓글.
- 순위 = 묶음 안 상위 3개 배수(30배로 자름)의 기하평균. 묶음은 캡션 키워드 규칙(`HOT_TOPICS`)이라 대략이다. 한 게시물이 두 묶음에 들 수 있다.

| 순위 | 주제 | 대표 게시물 (첫 줄) | 반응 배수 | 형식 | 묶음 크기 (2배 이상) |
|---|---|---|---|---|---|
| 1 | AI 영상·영화 만들기 (창작) | @ai.trend.kr: [눈 뭉치 던진 범인이 나라고요? ❄️](https://www.instagram.com/reel/DetX442xkFz/) | 31.7x | 릴스 | 54개 (15) |
| 2 | 돈·일자리·교육 (생활) | @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/) | 307.0x | 릴스 | 66개 (18) |
| 3 | 챗GPT·제미나이 사진·그림 변환 (창작) | @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/) | 40.6x | 카드 | 60개 (23) |
| 4 | 유명인·CEO 발언 (인용) | @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/) | 24.3x | 릴스 | 102개 (27) |
| 5 | 챗GPT 질문·대화 활용법 (따라 하기) | @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/) | 27.4x | 카드 | 17개 (8) |
| 6 | 미중 경쟁·반도체·데이터센터 (산업) | @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/) | 485.3x | 릴스 | 37개 (12) |
| 7 | MCP·스킬·클로드 코드 자동화 (연결 도구) | @ai.trend.kr: [명령어 한 줄이면 프롬프트 2,000개가 내 AI 에이전트에 통째로 들어옵니다. 🔌](https://www.instagram.com/p/DdTM6hvDw-R/) | 12.1x | 카드 | 109개 (41) |
| 8 | AI 안전·논란 (논란) | @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/) | 480.4x | 릴스 | 19개 (5) |
| 9 | 생활 앱·무료 도구 (생활) | @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/) | 15.2x | 카드 | 24개 (7) |
| 10 | AI로 광고·디자인 만들기 (창작) | @ex.treme.ai: [광고 올릴 때 제일 막히는 건 디자인이 아니라 ”무슨 말로 팔지“입니다.](https://www.instagram.com/p/DaFI7YXGOjf/) | 10.0x | 카드 | 15개 (8) |
| 11 | 대회·무료 지원 (생활) | @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/) | 6.0x | 카드 | 12개 (6) |
| 12 | 새 모델·기능 출시 (소식) | @ai.asap.kr: [오픈AI가 금융권 전용 ChatGPT를 내놨습니다. 9월 10일 발표한 ChatGPT for Financial Services입니다.](https://www.instagram.com/p/DdP7he-D9nI/) | 7.2x | 카드 | 60개 (13) |
| 13 | AI 음악·목소리 (창작) | @ai.trend.kr: [새로 쓴 가사에 AI 목소리, 닷새 만에 117만 뷰가 터졌어요 🔥](https://www.instagram.com/reel/DcvZNlPSOUL/) | 6.0x | 릴스 | 8개 (3) |
| 14 | 주간 요약 (묶음) | @ai.trend.kr: [AI가 이번 주엔 너무 사람 같았어요 🤖](https://www.instagram.com/p/DddjD_vD1Mv/) | 5.5x | 카드 | 13개 (3) |
| 15 | AI 게임 만들기 (창작) | @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/) | 12.8x | 카드 | 3개 (1) |

## 주제별 상위 3개

### AI 영상·영화 만들기 — 순위 점수 25.7, 릴스 22·카드 32, 배수 중간값 0.95x
- 31.7x 릴스 @ai.trend.kr: [눈 뭉치 던진 범인이 나라고요? ❄️](https://www.instagram.com/reel/DetX442xkFz/)
- 24.8x 릴스 @ai.trend.kr: [1편 반응이 뜨거워서 2편을 가져왔는데요, 이건 벌써 4967만 명이 봤습니다 📞](https://www.instagram.com/reel/DdKxQXWv-18/)
- 22.9x 릴스 @ai.trend.kr: [포장해 달라던 선물이 내 거였다고요? 🎁](https://www.instagram.com/reel/DeWZecova75/)

### 돈·일자리·교육 — 순위 점수 20.2, 릴스 40·카드 26, 배수 중간값 0.88x
- 307.0x 릴스 @ai.talk.kr: [“OpenAI와 Anthropic은 AI 버블을 이겨낼 수 있을까?”](https://www.instagram.com/reel/Db2MJLcR-10/)
- 21.5x 릴스 @ai.talk.kr: [“AI 시장, 결국 치킨 게임으로 가고 있는 걸까요?”](https://www.instagram.com/reel/DcDWvDKpGBj/)
- 12.9x 릴스 @ai.talk.kr: [“AI 시대, 지금 IT 직장인들은 어떤 상태일까요?”](https://www.instagram.com/reel/DbhgWt9JVbu/)

### 챗GPT·제미나이 사진·그림 변환 — 순위 점수 17.8, 릴스 5·카드 55, 배수 중간값 1.28x
- 40.6x 카드 @ai.trend.kr: [평범한 사진 한 장을 간직하고 싶은 그림으로 만들어보세요 🖼️](https://www.instagram.com/p/DckJfiMD83G/)
- 22.1x 카드 @ai.trend.kr: [핸드폰 배경화면을 바꿨더니, 하루에도 몇 번씩 꺼내 보게 됐어요.🐾](https://www.instagram.com/p/DcdMcZDjzBL/)
- 8.5x 카드 @ex.treme.ai: [브랜드 URL 하나, 제품 사진 한 장이면](https://www.instagram.com/p/DY35VLhmPJJ/)

### 유명인·CEO 발언 — 순위 점수 15.7, 릴스 92·카드 10, 배수 중간값 1.00x
- 24.3x 릴스 @bizucafe: [화폐는 의미 없다 (일론 머스크)](https://www.instagram.com/reel/De8mVBGgBJL/)
- 17.8x 릴스 @ai.talk.kr: [“일론 머스크는 왜 샘 올트먼을 믿지 않는 걸까요?”](https://www.instagram.com/reel/DbzUQ_VvaxQ/)
- 8.9x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)

### 챗GPT 질문·대화 활용법 — 순위 점수 14.4, 릴스 5·카드 12, 배수 중간값 1.96x
- 27.4x 카드 @ai.trend.kr: [GPT로 나도 몰랐던 내 정보 싹 다 지우세요. 🧹](https://www.instagram.com/p/Dc-nN8WjyWt/)
- 10.5x 카드 @ai.trend.kr: [GPT한테 내 연애 스타일을 물어봤더니, 말한 적도 없는 취향까지 나왔어요. 💘](https://www.instagram.com/p/DeOdX4okWIu/)
- 10.3x 카드 @ai.trend.kr: [이제 프롬프트 필요 없이 명령어만 붙이세요. 🎨](https://www.instagram.com/p/Dc92nT7j8PP/)

### 미중 경쟁·반도체·데이터센터 — 순위 점수 14.0, 릴스 31·카드 6, 배수 중간값 1.46x
- 485.3x 릴스 @ai.talk.kr: [“중국이 AI로 미국을 이길 수 있을까요?”](https://www.instagram.com/reel/DbwhvfvvknP/)
- 10.3x 릴스 @ai.talk.kr: [“챗GPT에 질문할 때마다 물이 사용된다는 사실, 알고 계셨나요?”](https://www.instagram.com/reel/DcCmtLip1ZU/)
- 8.9x 릴스 @bizucafe: [중국 이길 방법은 하나 (일론 머스크)](https://www.instagram.com/reel/Dfvj43QgnE_/)

### MCP·스킬·클로드 코드 자동화 — 순위 점수 10.2, 릴스 8·카드 101, 배수 중간값 1.23x
- 12.1x 카드 @ai.trend.kr: [명령어 한 줄이면 프롬프트 2,000개가 내 AI 에이전트에 통째로 들어옵니다. 🔌](https://www.instagram.com/p/DdTM6hvDw-R/)
- 10.1x 카드 @ai.asap.kr: [abtop은 터미널에서 도는 AI 코딩 에이전트를 한 화면에 모아 보는 모니터입니다.](https://www.instagram.com/p/DdId7_Lj4mH/)
- 8.7x 카드 @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/)

### AI 안전·논란 — 순위 점수 9.7, 릴스 14·카드 5, 배수 중간값 0.90x
- 480.4x 릴스 @ai.talk.kr: [“AI도 절박해지면 부정행위를 할까요?”](https://www.instagram.com/reel/DdVHAvSpdvb/)
- 6.7x 카드 @ai.asap.kr: [OpenDataLoader PDF는 PDF를 마크다운과 JSON, HTML로 바꾸는 파서입니다. 읽기 순서와 표, 제목 구조를 지키고 모든 요소](https://www.instagram.com/p/Dc5wGU0D4Un/)
- 4.5x 릴스 @ai.talk.kr: [AI가 보이는 사고과정과 실제 추론이 다를 수 있다면, 인간은 무엇으로 AI를 검증할 수 있을까요?](https://www.instagram.com/reel/Dd8BPz-BhvC/)

### 생활 앱·무료 도구 — 순위 점수 8.1, 릴스 1·카드 23, 배수 중간값 1.10x
- 15.2x 카드 @ai.asap.kr: [Filee는 Ctrl을 누른 채 파일을 끌면 커서 옆에 변환할 형식이 동그랗게 뜨고, 원하는 형식에 놓으면 바로 바꿔 주는 변환기입니다. 이미지](https://www.instagram.com/p/DeoW-TQj9F5/)
- 6.5x 카드 @ai.asap.kr: [DockDoor는 맥 독에 윈도우처럼 창 미리보기를 붙여 주는 무료 오픈소스 앱입니다. 독을 바꾸지 않고 메뉴바에서 돌아가며 기존 독에 기능을](https://www.instagram.com/p/DeIvEO_j3xU/)
- 5.3x 카드 @ai.asap.kr: [Plexo는 윈도우·맥·리눅스용 다운로드 앱입니다. 파일을 조각으로 나눠 와이파이, 유선, USB로 연결한 휴대폰, 셀룰러 같은 여러 네트워크에](https://www.instagram.com/p/Dd_Kxs4jy4j/)

### AI로 광고·디자인 만들기 — 순위 점수 7.3, 릴스 1·카드 14, 배수 중간값 2.32x
- 10.0x 카드 @ex.treme.ai: [광고 올릴 때 제일 막히는 건 디자인이 아니라 ”무슨 말로 팔지“입니다.](https://www.instagram.com/p/DaFI7YXGOjf/)
- 8.7x 카드 @ai.asap.kr: [M3E Canvas는 앱 화면을 그리는 웹 도구입니다. 화면을 잇고 테마를 정한 뒤 프롬프트를 복사해 클로드 코드나 코덱스에 넣으면 됩니다.](https://www.instagram.com/p/DdsbFjMDz5I/)
- 4.4x 카드 @ex.treme.ai: [크림 한 통 사진을 넣었더니, 광고 20장이 나왔어요.](https://www.instagram.com/p/Dbup2SXmEz2/)

### 대회·무료 지원 — 순위 점수 5.9, 릴스 2·카드 10, 배수 중간값 2.01x
- 6.0x 카드 @ai.asap.kr: [SK하이닉스 AI 해커톤 2026입니다. 반도체 현장의 과제를 AI로 푸는 대회이고 운영은 멋쟁이사자처럼이 맡았습니다. AI 파트너로는 오픈AI](https://www.instagram.com/p/DditRIQD1ub/)
- 6.0x 카드 @ai.asap.kr: [Open-Science는 연구자를 위한 AI 작업대입니다. 하고 싶은 분석을 말로 적으면 자료를 찾고 파이썬이나 R 코드를 돌려 표와 그림을 만](https://www.instagram.com/p/Dd6E7Cxj4YS/)
- 5.7x 카드 @ai.asap.kr: [AI 잘 쓰는 사람 100명을 뽑는 대회가 10월 1일 신청을 엽니다. 총 상금은 1억 2,500만 원입니다.](https://www.instagram.com/p/Dd7u5IvD9uD/)

### 새 모델·기능 출시 — 순위 점수 5.4, 릴스 4·카드 56, 배수 중간값 0.84x
- 7.2x 카드 @ai.asap.kr: [오픈AI가 금융권 전용 ChatGPT를 내놨습니다. 9월 10일 발표한 ChatGPT for Financial Services입니다.](https://www.instagram.com/p/DdP7he-D9nI/)
- 4.9x 카드 @ai.asap.kr: [앤트로픽 Applied AI 팀이 기업용 에이전트를 만들 때 서브에이전트를 메인 루프로 접어야 할 시점을 정리한 글을 공개했습니다.](https://www.instagram.com/p/De1Tvw5D-Ug/)
- 4.5x 카드 @ai.asap.kr: [오픈AI가 GPT-6.1 Terra를 공개했습니다. 화면을 읽고 앱을 다루는 컴퓨터 사용을 더 싸고 빠르게 만든 모델입니다.](https://www.instagram.com/p/De-Uua7k_rj/)

### AI 음악·목소리 — 순위 점수 4.5, 릴스 3·카드 5, 배수 중간값 1.38x
- 6.0x 릴스 @ai.trend.kr: [새로 쓴 가사에 AI 목소리, 닷새 만에 117만 뷰가 터졌어요 🔥](https://www.instagram.com/reel/DcvZNlPSOUL/)
- 4.7x 카드 @ai.asap.kr: [Lemo-Opuscar는 Claude Code에 설치해 쓰는 영상 스타일 모음입니다. 대표작 OPUSCAR 98은 아카데미 작품상 98편을 영화](https://www.instagram.com/p/DfVni0MD5Ql/)
- 3.3x 릴스 @ai.trend.kr: [힙합을 판소리로 바꾼 AI 영상, 닷새 만에 60만이 봤어요 🎶](https://www.instagram.com/reel/Dcmxdrgv3vR/)

### 주간 요약 — 순위 점수 3.2, 릴스 0·카드 13, 배수 중간값 1.00x
- 5.5x 카드 @ai.trend.kr: [AI가 이번 주엔 너무 사람 같았어요 🤖](https://www.instagram.com/p/DddjD_vD1Mv/)
- 2.4x 카드 @ai.asap.kr: [맥북 노치를 그냥 두고 있다면 Boring Notch가 그 자리를 아이폰 다이내믹 아일랜드처럼 바꿔 줍니다. 노치에 마우스를 올리면 재생 중인](https://www.instagram.com/p/DfGEROUk8_E/)
- 2.4x 카드 @ai.trend.kr: [이번 주 AI, 내 노트북부터 공부법까지 바꿨어요 🚀](https://www.instagram.com/p/DfLgRIPjxxY/)

### AI 게임 만들기 — 순위 점수 2.4, 릴스 0·카드 3, 배수 중간값 1.51x
- 12.8x 카드 @ai.trend.kr: [GPT가 이렇게까지 떠먹여 주는데, 가만히 있으실 거예요?](https://www.instagram.com/p/DdIP-eYj0q8/)
- 1.5x 카드 @ai.trend.kr: [초파리한테는 조금 미안한 한 주였어요. 🪰](https://www.instagram.com/p/DdI8UKQj6hJ/)
- 0.7x 카드 @ai.asap.kr: [universal-modder는 게임 엔진 파악부터 코드 분석, 모드 제작, 그림·3D·소리 생성, 실제 게임에서의 시험, 시연 영상 편집까지](https://www.instagram.com/p/Dejs6cyD5RQ/)

## 분류 안 된 2배 이상 게시물 (키워드 보강 대상)

- 49.0x 카드 @bizucafe: 광고(廣告). 한문으로 널리 알린다는 뜻이다.. 많은 사람들에게 무언가 정보를 알리는 것..
- 7.0x 릴스 @bizucafe: 우린 이미 너무 늦었다 (유발 하라리)
- 6.2x 릴스 @bizucafe: 갓 대학 졸업한 '경영 컨설턴트'
- 6.2x 릴스 @bizucafe: 창업 한번 해보세요 (유튜브 창업자 Steve Chen)
- 5.0x 릴스 @bizucafe: 우리 아이 첫 남친이 AI가 됩니다 (유발 하라리)
- 4.9x 릴스 @bizucafe: 대기업이 따라 하면 끝? (세콰이어 캐피탈 알프레드 린)
- 4.6x 릴스 @bizucafe: (캡션 없음)
- 4.4x 릴스 @bizucafe: 똑똑한 애들의 약점 (세콰이어 캐피탈 알프레드 린)
- 4.3x 릴스 @bizucafe: 한 세대는 희생해야 한다 (대우 김우중 회장)
- 3.9x 릴스 @bizucafe: 정부는 AI 속도 못 따라간다 (알렉산더 왕)
