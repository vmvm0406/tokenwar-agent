# 영상 받기 작업 (회원님 컴퓨터가 켜져 있을 때)

예약 작업이 매시간(09~23시) 실행한다. 회원님 컴퓨터(Claude 데스크톱 앱)가 꺼져 있으면 그 회차는 건너뛰고 다음 시간에 다시 시도한다.
하는 일: `requests/clips/`의 요청 하나를 골라 유튜브에서 1분 언저리(원본 길이의 1/3 이하) 구간을 받고, 영상 프레임 릴스 게시물을 만든다.

유튜브는 클라우드 서버를 막기 때문에, 영상 받기만 회원님 컴퓨터(`device_bash`, 작업 폴더 `Videos/tokenwar`)에서 하고 나머지는 클라우드 작업 환경에서 한다.

## 0. 할 일이 있는지 확인 (클라우드)

1. `git pull`
2. `requests/clips/*.json`이 없으면 **아무것도 하지 않고 끝낸다** (보고도 한 줄만).
3. 게시 시각은 `python3 agent/slots.py next reel`이 주는 가장 가까운 빈 칸 (config.json `slots`, LOCAL.md 5장).
4. 요청을 `score` 높은 순으로 정렬한다. 3일 지난 요청은 `done/`으로 옮기고 건너뛴다.

## 1. 컴퓨터 준비 (device_bash)

```bash
pip install -q --user -U "yt-dlp[default,curl-cffi]"
mkdir -p $HOME/work && cd $HOME/work      # 임시 작업은 여기서 (회원님 폴더는 삭제가 막혀 있어 조각 파일이 남는다)
Y="$HOME/.local/bin/yt-dlp --js-runtimes node --no-playlist -q --no-progress"
```

완성된 클립만 `$HOME/mnt/Videos/tokenwar/cur.mp4`로 복사한다 (`cp`, 같은 이름으로 덮어쓰기).

`device_bash`가 연결되지 않으면 컴퓨터가 꺼진 것이다. 끝낸다.

## 2. 영상 정보와 자막 (device_bash)

```bash
$Y --skip-download --no-simulate --write-info-json --write-auto-subs --write-subs \
   --sub-langs "en,ko" --sub-format vtt -o "cur" "<url>"
```

자막 받기가 `429 Too Many Requests`로 자주 막힌다. 그러면 영상이 10분 이하일 때는 영상을 통째로 받아(아래 3번, `--download-sections` 없이) 클라우드로 가져와서 `analyze.py`로 받아쓴다. 정확한 자르기 지점은 faster-whisper `word_timestamps=True`로 단어 단위 시각을 본다.

- `cur.info.json`에서 `channel`, `uploader`, `upload_date`, `duration`, `view_count`, `title`을 확인한다.
- **원본 채널인지 확인한다.** 클립 모음·재업로드 채널이면 요청을 `done/`으로 옮기고("원본 아님") 다음 요청으로.
- 자막(`cur.*.vtt`)에서 `hint`의 문장을 찾고, 스타일 가이드 6-1장 "구간 고르기" 기준으로 1분 언저리(원본 길이의 1/3 이하) 구간을 정한다. 자막이 없으면 3분 구간을 오디오로만 받아(`-x --download-sections`) 클라우드에서 `analyze.py`로 받아쓴다.

## 3. 구간 받기 (device_bash)

앞뒤로 1초씩 여유를 두고 받는다. 정확한 시작·끝은 post.json의 `video.start`/`end`로 맞춘다.

```bash
$Y -S "res:1080,ext:mp4:m4a" --merge-output-format mp4 -o "full.mp4" "<url>"
ffmpeg -y -loglevel error -ss <시작-1초> -to <끝+1초> -i full.mp4 -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 160k clip.mp4
cp clip.mp4 $HOME/mnt/Videos/tokenwar/cur.mp4
```

- `-S res:1080`은 짧은 변 기준 1080이라 세로 영상도 1080x1920으로 받는다 (`height<=1080`을 쓰면 세로 영상이 608px로 작아진다).
- `--download-sections`는 이 환경에서 ffmpeg가 원격 주소를 못 읽어 실패한다. 긴 영상도 통째로 받아(1시간 1080p ≈ 500MB, 1분 안쪽) `ffmpeg -ss ... -to ... -c copy`로 자른다.

## 4. 클라우드로 가져오기

`device_stage_files`로 `C:\Users\vmmxu\Videos\tokenwar\cur.mp4`를 올리고, 게시물 폴더 `posts/queue/<날짜>-video-<슬러그>/clips/source.mp4`로 옮긴다.

## 5. 게시물 만들기 (클라우드)

`AGENT.md`의 "영상 릴스 만들기"와 같은 규칙. 정리하면:

1. `python3 agent/analyze.py <폴더>/clips/source.mp4`로 장면·말소리·받아쓰기를 확인하고, 시트 이미지를 직접 본다.
2. `post.json` (형식은 `samples/s8-huang-quote/post.json`, `TEMPLATES.md`):
   - `type: "video"`, `rights: "quote"`, `credit`(채널·발언자), `source_url`(원본 링크, 가능하면 `&t=초` 포함)
   - `video.start`/`end`: 1분 언저리(원본 길이의 1/3 이하)
   - 중간에 자르지 않는다 (`video.keep` 쓰지 않음, STYLE_GUIDE 6-1). `python3 agent/tighten.py clips/source.mp4 <start> <end>`는 단어 시각을 얻는 데만 쓰고, 그 단어 목록으로 번역 자막 시각을 맞춘다
   - 원본에 영어 자막이 박혀 있거나 이름표가 있으면 `video.crop: {"top": 0, "bottom": 0.7}`처럼 그 아래를 잘라낸다. 우리 자막과 겹치지 않게 (예시: `samples/s8-huang-quote`)
   - 제목 2줄, 영어 부제, 자막. **말이 있는 영상은 발언을 문장 단위로 빠짐없이 번역**한다 (요약 금지, 질문하는 사람은 `기자:`처럼 표시). 말이 없는 영상(AI 생성 영상, 시연)은 장면마다 우리 설명 자막. 어느 쪽이든 영상 길이의 60% 이상을 덮는다
   - `video.source_duration`: 원본 전체 길이(초). 인용 비율 확인용
   - `thumb`: 발언자 얼굴이 잘 보이는 순간을 `ffmpeg -ss <초> -i clips/source.mp4 -frames:v 1 -q:v 2 img/thumb.jpg`로 뽑아 쓰고 `person`에 이름·설명, `image.url`에는 원본 영상 주소. 얼굴 장면이 별로면 AI 상징 이미지(`prompt`)
   - 캡션: 맥락, 왜 중요한지, "영상: 채널 이름", 원본 링크
   - `publish_at`: 0-3에서 받은 칸 시각
3. `python3 agent/build.py <폴더>`로 렌더링하고 `cover.jpg`, `frames/01.jpg`를 직접 열어 확인한다. (썸네일이 AI 그림이면 임시 그림으로 확인 후 지우고 Actions에 맡긴다. AGENT.md 3장)
4. 요청 파일에 `result`(게시물 폴더, 고른 구간, 이유)를 적고 `requests/clips/done/`으로 옮긴다.

## 6. 올리기

`config.json`의 `mode`를 따른다 (AGENT.md 4장). 검토 모드면 `post/<날짜>-reel` 브랜치와 PR. PR 본문에 원본 링크(구간 시각 포함), 고른 이유, 썸네일, 캡션을 넣는다.

## 하지 말 것

- 원본 전체나 원본 영상 파일을 저장소에 올리지 않는다 (저장소는 공개다).
- 회원님 컴퓨터에서 `Videos/tokenwar` 밖의 파일을 건드리지 않는다.
- 구글 계정 로그인·쿠키를 쓰지 않는다. 막히면 요청에 "받기 실패"를 적고 다음 회차에 다시 시도한다 (3번 실패하면 `done/`).
