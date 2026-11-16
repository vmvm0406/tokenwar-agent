# 목소리 (TTS): Kokoro-82M

목록형 자료 릴스에서 그림이 바뀔 때 그 영어 용어를 읽어 주는 목소리 (운영자 결정 2026-11-17). 만드는 코드는 `agent/tts.py`, 섞는 코드는 `agent/listreel.py`.

## 출처와 라이선스 (2026-11-17 확인)

| 무엇 | 출처 | 라이선스 |
|---|---|---|
| 엔진 `kokoro` 0.9.4 | PyPI https://pypi.org/project/kokoro/ (hexgrad) | Apache-2.0 (PyPI 패키지 정보) |
| 모델 가중치와 음성(voices/*.pt) | Hugging Face https://huggingface.co/hexgrad/Kokoro-82M (모델 카드 license: apache-2.0) | Apache-2.0 |
| 발음 사전 `misaki[en]` | PyPI (kokoro가 함께 설치) | Apache-2.0 |

- 상업 이용 가능, 저작자 표시 의무 없음(Apache-2.0은 소스·가중치를 다시 배포할 때 라이선스 고지만 요구). 우리는 만든 음성 파일만 쓰고 모델을 다시 배포하지 않는다.
- 유료 API·계정 가입 없음. 모델은 처음 쓸 때 Hugging Face에서 자동으로 받아 사용자 캐시(`%USERPROFILE%\.cache\huggingface`)에 둔다.

## 쓰는 목소리

- `af_heart` (미국 영어 여성, Kokoro 음성 중 품질 등급이 가장 높은 기본 음성). 차분하고 또렷해서 한 목소리로 통일한다.
- 게시물마다 바꾸려면 post.json `list.voice.voice`.

## 이 컴퓨터에서만 만든다

GitHub Actions에는 Kokoro가 없다. `py -3.12 agent/tts.py posts/queue/<폴더>`로 게시물 폴더에 `voice/<번호>.wav`(24kHz 모노, 한 개 수십 KB)를 만들어 함께 커밋한다. listreel.py는 그 파일을 박자에 맞춰 섞기만 하고, 파일이 없으면 목소리 없이 렌더링한다.

설치: `py -3.12 -m pip install "kokoro==0.9.4" soundfile` (torch CPU판이 함께 설치됨, 관리자 권한 필요 없음). MIGRATION.md 참고.
