# 목소리 (TTS): Kokoro-82M(영어) + ElevenLabs(한국어 내레이션)

- 영어: 목록형 자료 릴스에서 그림이 바뀔 때 그 영어 용어를 읽어 주는 목소리 (운영자 결정 2026-11-17).
- 한국어: 내레이션 릴스(애니메이션 위에 한국어로 읽어 주기)와 목록형 릴스 한국어 읽기(`list.voice.lang: "ko"`) (2026-11-17 추가).

- **한국어 내레이션은 ElevenLabs 남자 목소리 (운영자 결정 2026-11-17).** MeloTTS 한국어는 운영자가 듣고 쓰지 않기로 함("읽는법이 좀 그래서"). 아래 MeloTTS 기록은 예전 것.

만드는 코드는 `agent/tts.py`, 목록형 릴스에 섞는 코드는 `agent/listreel.py`.

## 출처와 라이선스: 영어 Kokoro (2026-11-17 확인)

| 무엇 | 출처 | 라이선스 |
|---|---|---|
| 엔진 `kokoro` 0.9.4 | PyPI https://pypi.org/project/kokoro/ (hexgrad) | Apache-2.0 (PyPI 패키지 정보) |
| 모델 가중치와 음성(voices/*.pt) | Hugging Face https://huggingface.co/hexgrad/Kokoro-82M (모델 카드 license: apache-2.0) | Apache-2.0 |
| 발음 사전 `misaki[en]` | PyPI (kokoro가 함께 설치) | Apache-2.0 |

## 출처와 라이선스: 한국어 MeloTTS (2026-11-17 확인)

| 무엇 | 출처 | 라이선스 |
|---|---|---|
| 엔진 `melotts` 0.1.2 (커밋 2091453) | GitHub https://github.com/myshell-ai/MeloTTS (LICENSE: MIT, Copyright MyShell.ai) | MIT |
| 한국어 모델 가중치 | Hugging Face https://huggingface.co/myshell-ai/MeloTTS-Korean (모델 카드 license: mit, "free for both commercial and non-commercial use") | MIT |
| 단어 분석 BERT `kykim/bert-kor-base` | Hugging Face (카드에 라이선스 표시 없음). 원 저장소 https://github.com/kiyoungkim1/LMkor README: "distributed under the terms of the Apache-2.0 License" | Apache-2.0 (아래 주의) |
| 발음 변환 `g2pkk` 0.1.2 | PyPI | Apache-2.0 |
| 형태소 분석 `python-mecab-ko` 1.3.7 / `python-mecab-ko-dic` 2.1.1 | PyPI | BSD-3-Clause / Apache-2.0 |
| `jamo` / `anyascii` / `txtsplit` / `librosa` / `nltk`(+ cmudict 데이터) | PyPI | Apache-2.0 / ISC / Apache-2.0 / ISC / Apache-2.0 |

- 원래 requirements에 있는 일본어 `unidic`·`mecab-python3`, 중국어 `jieba` 등은 설치하지 않는다 (tts.py가 그 언어 모듈을 빈 모듈로 막음). GPL 같은 강한 조건이 붙은 의존성은 없다.
- **주의 (bert-kor-base):** LMkor README는 Apache-2.0이라고 하면서 "모델의 상업적 사용의 경우 MOU를 통해 무료로 사용" 하라는 문장도 함께 적어 두었다. Apache-2.0 허락은 철회할 수 없어 상업 이용 자체는 가능하다고 보지만, 확실히 하려면 운영자가 README의 연락처로 MOU(무료)를 문의한다. 이 BERT 없이 돌리면(`disable_bert`) 억양이 평평해지고 띄어쓰기가 뭉개져 쓰지 않는다.
- 공통: 상업 이용 가능, 저작자 표시 의무 없음(MIT·Apache-2.0은 소스·가중치를 다시 배포할 때 라이선스 고지만 요구). 우리는 만든 음성 파일만 쓰고 모델을 다시 배포하지 않는다.
- 유료 API·계정 가입 없음. 모델은 처음 쓸 때 Hugging Face에서 자동으로 받아 사용자 캐시(`%USERPROFILE%\.cache\huggingface`)에 둔다 (MeloTTS-Korean 약 200MB, bert-kor-base 약 900MB: 윈도우에서는 .bin과 .safetensors가 둘 다 받아짐).

## 쓰는 목소리

- 영어 `af_heart` (미국 영어 여성, Kokoro 음성 중 품질 등급이 가장 높은 기본 음성). 차분하고 또렷해서 한 목소리로 통일한다. 게시물마다 바꾸려면 post.json `list.voice.voice`.
- 한국어: MeloTTS-Korean의 하나뿐인 여자 목소리(`KR`). 빠르기 1.0~1.1이 자연스럽다 (릴스는 1.1 권장). 44.1kHz.
- 한국어 대본: 숫자·%·날짜는 그대로 써도 된다(10% → 십 퍼센트, 8억 → 파럭). 영어는 tts.py `KO_WORDS`의 이름(챗GPT, 오픈AI, 엔비디아 등)과 약자(AI, CEO, GPT)만 한글로 바꾸고, 모르는 영어 단어는 글자 하나씩 읽으니 대본에 한글로 쓴다.

## 한국어 내레이션: ElevenLabs (2026-11-17)

| 무엇 | 내용 |
|---|---|
| 서비스 | ElevenLabs https://elevenlabs.io , 운영자 본인 계정, **Starter 월 결제** (월 약 3만 자) |
| 상업 이용 | 유료 플랜은 만든 음성을 상업적으로 쓸 수 있다 (무료 플랜은 불가, 출처 표시 필요). Starter부터 상업 이용 허락. 저작자 표시 의무 없음 |
| 모델 | `eleven_multilingual_v2` (한국어 지원), 출력 `mp3_44100_128` |
| 키 | 사용자 환경 변수 `ELEVENLABS_API_KEY` (이 컴퓨터만, 저장소·GitHub Secrets에 없음). 설정: MIGRATION.md 3-4장 |
| 요금 | 보낸 글자 수만큼 차감. tts.py가 같은 글·목소리·설정이면 `%USERPROFILE%\.cache\tokenwar-tts\elevenlabs\`의 파일을 다시 쓰고, 빠르기 조절은 다시 부르지 않고 ffmpeg atempo |

목소리 라이브러리(Voice Library)의 한국어 목소리도 Starter에서 ID로 바로 부를 수 있다(계정에 추가하지 않아도 됨, 2026-11-17 확인). 라이브러리 목소리는 만든 사람이 정한 조건이 있을 수 있어 쓰기 전 라이브러리 화면의 설명을 본다. 기본 제공(premade) 목소리(Adam, Brian 등)는 영어 원어민이라 한국어 억양이 어색해 쓰지 않는다.

### 후보 남자 목소리 (2026-11-17, 운영자가 듣고 하나를 고른다)

| 이름 (tts.py 별칭) | voice_id | 느낌 |
|---|---|---|
| Hyuk - Cold and Clear (`hyuk`, 지금 기본) | `ZJCNdZEjYwkOElxugmW2` | 차분한 중년 내레이터, 라이브러리 한국어 남자 목소리 중 가장 많이 쓰임 |
| Krys - Cheerful, Clear and Measured (`krys`) | `1W00IGEmNmwmsDeYy7ag` | 밝고 힘찬 젊은 목소리, 영상 내레이션·쇼츠용 |
| Kyle - Friendly, Natural and Guttural (`kyle`) | `RU7aSi6lT4uQBXMLgDxK` | 낮고 굵은 목소리, 강의용 |

운영자가 고르면 tts.py `ELEVEN_DEFAULT_VOICE`를 그 목소리로 바꾼다. 다른 목소리 찾기: `py -3.12 agent/tts.py --engine elevenlabs --list-voices`.

## 이 컴퓨터에서만 만든다

GitHub Actions에는 세 엔진(키 포함)이 없다. 이 컴퓨터에서 만들어 게시물 폴더에 함께 커밋한다.

- 목록형: `py -3.12 agent/tts.py posts/queue/<폴더>` → `voice/<번호>.wav`(24kHz 모노, 한 개 수십 KB). listreel.py는 그 파일을 박자에 맞춰 섞기만 하고, 파일이 없으면 목소리 없이 렌더링한다.
- 한국어 내레이션: `py -3.12 agent/tts.py --engine elevenlabs --voice hyuk --text "만약 AI에게 내 돈을 맡겨 투자시킨다면, 어떤 일이 벌어질까요?" --out <폴더>/voice/01.mp3`
- 문장 하나(예전 MeloTTS): `py -3.12 agent/tts.py --text "만약 AI에게 내 돈을 맡겨 투자시킨다면, 어떤 일이 벌어질까요?" --out <폴더>/voice/01.wav --speed 1.1`

설치 명령은 MIGRATION.md 2장 (Kokoro: `py -3.12 -m pip install "kokoro==0.9.4" soundfile`, MeloTTS: 공식 GitHub 커밋 고정 + 한국어 의존성만). 관리자 권한 필요 없음.
