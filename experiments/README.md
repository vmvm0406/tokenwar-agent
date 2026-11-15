# 실험 (아직 매일 작업에 안 들어간 것)

운영자와 함께 고르는 중인 릴스 디자인 시제품. 매일 작업(LOCAL.md)은 아직 이걸 쓰지 않는다.

| 폴더 | 내용 | 상태 |
|---|---|---|
| `reel-crt/` | 인용 릴스 새 화면: 영상 위 평범한 자막 + 영상 바로 밑 초록 선 + 아래 빈칸 초록 CRT 터미널 모션 (타자 효과, 반전 강조, █ 막대). 인스타 안전 영역(세로 285~1250px) 안 | 운영자 확인 중 (v7). 괜찮다고 하면 `agent/video.py`를 이 방식으로 바꾼다 |
| `weekly-np/` | 주간 요약 영상(News Package 화풍) | 접음. 사진·영상 자료 없이 글자뿐이라 별로였음. 주간 요약은 카드뉴스로 다시 (NEXT.md) |

## 렌더링 방법 (이 컴퓨터)

**주의 (운영자 결정 2026-11-16): 게시물에는 비상업(NC) 소재를 쓰지 않는다. Lemo-Opuscar 화풍 설명서는 CC BY-NC라 실제 게시물에 쓰지 않는다.** 아래는 시제품용 기록이다.

화풍 라이브러리 Lemo-Opuscar의 렌더러(코드 MIT)를 쓴다. 라이브러리는 **저장소 밖**에 둔다 (화풍 설명서는 CC BY-NC라 공개 저장소에 올리지 않는다).

```powershell
cd $env:USERPROFILE
git clone --depth 1 https://github.com/lemomo-ai/lemo-opuscar
cd lemo-opuscar; npm install            # 또는 plugin/skills/lemo-opuscar/scripts/setup.sh deps
# 글꼴 복사 (fonts/는 git에 안 올림)
$R="$env:USERPROFILE\tokenwar-agent"; $E="$R\experiments\reel-crt"
Copy-Item -Recurse "$R\assets\fonts\black-han-sans" "$E\fonts\"; Copy-Item "$R\assets\fonts\WantedSans-*.otf","$R\assets\fonts\jetbrains-mono-latin-*.woff2" "$E\fonts\"
py -3.12 "$E\prep.py"; py -3.12 "$E\mix.py"     # 프레임·소리 (ffmpeg 7 이상)
node core/render/still.mjs "$E" 1.8 14.5 --size 1080x1920        # 미리보기 → $E\stills
node core/render/video.mjs "$E" --fps 30 --size 1080x1920 --out "$E\out\video.mp4"
sh core/render/mux.sh "$E\out\video.mp4" "$E\mix.wav" "$E\out\final.mp4" 30 1   # 윈도우는 Git Bash에서
```
