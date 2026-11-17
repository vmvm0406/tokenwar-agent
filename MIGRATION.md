# 새 노트북으로 옮기기 (이사 안내서)

마지막 확인: 2026-11-16 (옛 노트북: Windows 11 Pro, 사용자 폴더 `C:\Users\vmmxu`)

운영자는 2027년 1월쯤 노트북을 바꾼다. 이 문서만 보고 새 노트북에서 자동 제작을 다시 돌릴 수 있게 적었다. 명령은 모두 **PowerShell**에 그대로 붙여 넣으면 된다.

---

## 0. 요약: 따라오는 것과 새로 할 것

**GitHub에 있어서 저절로 따라오는 것 (할 일 없음)**

- 코드(`agent/`), 규칙 문서(CLAUDE.md, STYLE_GUIDE.md, LOCAL.md 등), `posts/`, `data/`, `samples/`, 글꼴(`assets/fonts/`, 검은고딕·원티드 산스가 저장소 안에 있어 따로 설치하지 않음)
- 하위 에이전트 설정 `.claude/agents/` (make-quote-reel, make-card-news, pick-video-segment, review-post)
- GitHub Secrets·Variables (토큰들)
- **GitHub Actions는 노트북과 상관없이 계속 돈다.** 렌더링(render.yml), 인스타 게시(publish.yml, 15분마다), 반응 분석, 릴스 시청 지표(reel-insights.yml, 기존 IG Secrets 사용), 토큰 점검, 검토 페이지. 노트북이 꺼져 있어도 이미 큐에 있는 게시물은 제시간에 올라간다.

**노트북에만 있어서 새로 해야 하는 것**

| 무엇 | 옛 노트북 상태 | 새 노트북에서 |
|---|---|---|
| 프로그램 | Python 3.12, Git, GitHub CLI, FFmpeg, Node.js, Claude Code, yt-dlp, Playwright 크로미움 | 2장 |
| 로그인 | Claude Code(구독 계정), GitHub CLI(vmvm0406) | 3장 (직접) |
| 저장소 두 개 | `%USERPROFILE%\tokenwar-agent`(Code 탭용), `%USERPROFILE%\tokenwar-daily`(매일 작업 전용) | 4장 |
| 작업 스케줄러 2개 | `TokenwarAgent`, `TokenwarModelWatch` | 5장 |
| Claude 기억(memory) | `C:\Users\vmmxu\.claude\projects\C--Users-vmmxu-tokenwar-agent\memory\` | 1장에서 복사, 4장에서 붙여 넣기 |

**새 노트북이 해 주던 일 (멈추면 생기는 일):** 하루 게시물 만들기(9:30·12:30·15:30, 로그인 3분 뒤), 새 모델 속보 감시와 게시 지연 대비 publish.yml 깨우기(15분마다), 월요일 주간 분석, C 드라이브 정리. 이사하는 동안 이것들이 멈춰도 이미 만든 게시물은 Actions가 올린다.

---

## 1. 옛 노트북에서 할 일 (옮기기 전)

### 1-1. 올리지 않은 것이 없는지 확인

두 저장소 모두 확인한다. 아무것도 안 나오면 된다.

```powershell
foreach ($r in "$env:USERPROFILE\tokenwar-agent", "$env:USERPROFILE\tokenwar-daily") {
    Write-Host "`n== $r" -ForegroundColor Green
    git -C $r fetch --quiet origin
    git -C $r status --short                                  # 커밋 안 한 파일
    git -C $r log --branches --not --remotes --oneline        # push 안 한 커밋
    git -C $r stash list                                      # 치워 둔 변경
    git -C $r worktree list                                   # 작업 폴더 (main 하나만 있으면 정상)
}
```

나온 것이 있으면 지휘 세션(Code 탭)에 "이것 정리해 줘"라고 맡긴다. `tokenwar-daily`의 stash는 매일 작업이 남긴 찌꺼기라 보통 버려도 된다.

### 1-2. Claude 기억(memory) 복사

Code 탭 Claude가 대화 사이에 기억하는 메모다. USB나 OneDrive로 옮긴다.

```powershell
$src = "$env:USERPROFILE\.claude\projects\C--Users-vmmxu-tokenwar-agent\memory"
$dst = "$env:USERPROFILE\OneDrive\tokenwar-memory"     # USB면 예: E:\tokenwar-memory
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item "$src\*.md" $dst
Get-ChildItem $dst
```

(선택) 같이 옮기면 좋은 것:
- `%USERPROFILE%\.claude\skills\unity-mcp-skill` — 유니티 연결 따라 하기용 스킬
- `%USERPROFILE%\tokenwar-daily\logs` — 지난 실행 기록 (저장소에 안 올라감, 없어도 됨)

**대화 기록은 옮겨지지 않는다.** 괜찮다: 지금까지 정한 것은 CLAUDE.md(운영자 취향), NEXT.md(진행 중인 일)에 다 적혀 있다. 옮기기 전에 지휘 세션에 "NEXT.md 최신으로 정리해 줘"를 한 번 시키면 좋다.

### 1-3. 옛 노트북 작업 스케줄러 끄기 (중요)

**두 노트북에서 동시에 돌면 같은 칸에 게시물을 두 번 만들거나, 같은 속보를 두 번 올릴 수 있다.** 새 노트북 5장을 하기 직전에 끈다.

```powershell
Disable-ScheduledTask -TaskName TokenwarAgent
Disable-ScheduledTask -TaskName TokenwarModelWatch
Get-ScheduledTask -TaskName Tokenwar* | Select-Object TaskName, State     # 둘 다 Disabled
```

옛 노트북을 아주 정리할 때는 지운다 (되돌릴 수 없음):

```powershell
Unregister-ScheduledTask -TaskName TokenwarAgent -Confirm:$false
Unregister-ScheduledTask -TaskName TokenwarModelWatch -Confirm:$false
```

---

## 2. 새 노트북: 프로그램 설치

저장소 안의 `scripts/setup-local.ps1`이 설치·저장소 받기·파이썬 패키지·작업 스케줄러 등록을 한 번에 한다. 그 스크립트를 받으려면 Git이 먼저 있어야 해서, Git만 먼저 깐다.

### 2-1. Git 먼저

PowerShell을 **관리자 권한**으로 연다 (시작 → PowerShell 오른쪽 클릭 → 관리자 권한으로 실행).

```powershell
winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
```

설치 뒤 PowerShell 창을 닫고 **관리자 권한으로 다시** 연다 (새 PATH를 읽도록).

### 2-2. Code 탭용 저장소 받기

```powershell
git clone https://github.com/vmvm0406/tokenwar-agent "$env:USERPROFILE\tokenwar-agent"
```

### 2-3. 나머지 한 번에 설치

**주의:** 이 스크립트는 5장의 작업 스케줄러 등록까지 한다. 옛 노트북 스케줄러를 끈 뒤(1-3) 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\tokenwar-agent\scripts\setup-local.ps1"
```

하는 일:
1. winget으로 `Git.Git`, `Python.Python.3.12`, `Gyan.FFmpeg`, `OpenJS.NodeJS.LTS`, `GitHub.cli`
2. Claude Code 설치 (`claude`가 없을 때만, `https://claude.ai/install.ps1`)
3. `%USERPROFILE%\tokenwar-daily`에 저장소를 한 번 더 받음
4. 파이썬 패키지: `requests pillow numpy playwright faster-whisper "yt-dlp[default,curl-cffi]"`, 그리고 `playwright install chromium`
5. 작업 스케줄러 `TokenwarAgent`, `TokenwarModelWatch` 등록 (5장)

### 2-4. 옛 노트북에서 쓰던 버전 (2026-11-16)

최신을 깔면 된다. 문제가 생기면 이 버전과 비교한다.

| 프로그램 | 버전 | 확인 명령 |
|---|---|---|
| Python | 3.12.10 | `py -3.12 --version` |
| Git | 2.56.0 | `git --version` |
| GitHub CLI | 2.104.0 | `gh --version` |
| Node.js | 26.13.1 | `node --version` |
| FFmpeg | 9.0.2 (gyan.dev full build, winget) | `ffmpeg -version` |
| yt-dlp | 2026.10.26 (pip) | `py -3.12 -m yt_dlp --version` |
| Claude Code | 2.1.281 | `claude --version` |
| pip 패키지 | requests 2.34.2, pillow 13.0.0, numpy 2.5.4, playwright 1.65.2, faster-whisper 1.2.1 (ctranslate2 4.9.0, av 19.0.2), curl_cffi 0.17.0 | `py -3.12 -m pip list` |
| Playwright 브라우저 | chromium-1255 | `Get-ChildItem $env:LOCALAPPDATA\ms-playwright` |

참고:
- 옛 노트북의 Claude Code는 npm으로 깔려 있었다(`%APPDATA%\npm\claude.ps1`). 새 노트북은 setup-local.ps1의 공식 설치 방법을 쓰면 된다. 어느 쪽이든 `claude`가 PATH에서 찾아지면 된다.
- 받아쓰기 모델(faster-whisper)은 처음 쓸 때 저절로 받는다 (`%USERPROFILE%\.cache\huggingface`). 따로 할 일 없음.
- 글꼴은 저장소 `assets/fonts/`에 있어서 윈도우에 설치하지 않는다 (`agent/render.py`가 그 폴더를 직접 읽음).
- (선택) 유니티 따라 하기용: 옛 노트북에 Unity Editor 6000.5.3f1이 있었다. 그 형식을 만들 때만 Unity Hub로 설치한다.

명령 하나씩 따로 설치하고 싶으면:

```powershell
foreach ($id in "Git.Git", "Python.Python.3.12", "Gyan.FFmpeg", "OpenJS.NodeJS.LTS", "GitHub.cli") {
    winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements
}
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install requests pillow numpy playwright faster-whisper "yt-dlp[default,curl-cffi]"
py -3.12 -m playwright install chromium
py -3.12 -m pip install "kokoro==0.9.4" soundfile   # 목록형 릴스 영어 용어 목소리 (agent/tts.py, Kokoro-82M Apache-2.0, 2026-11-17 설치. 모델은 처음 쓸 때 Hugging Face에서 자동으로 받음, assets/voice/README.md)
# 한국어 내레이션 목소리 (agent/tts.py --lang ko, MeloTTS 한국어 MIT, 2026-11-17 설치). melotts는 PyPI에 공식판이 없어 공식 GitHub 커밋을 고정해 의존성 없이 깔고,
# 한국어에 필요한 것만 따로 깐다 (원래 requirements는 transformers 4.27 등 옛 버전 고정이라 파이썬 3.12에서 안 깔림. 중국어·일본어 패키지는 tts.py가 빈 모듈로 막음)
py -3.12 -m pip install "librosa==1.0.1" "jamo==0.4.1" "anyascii==0.3.3" "g2pkk==0.1.2" "txtsplit==1.0.0" "python-mecab-ko==1.3.7"
py -3.12 -m pip install --no-deps "git+https://github.com/myshell-ai/MeloTTS.git@209145371cff8fc3bd60d7be902ea69cbdb7965a"
py -3.12 agent/tts.py --text "시험입니다" --out $env:TEMP\ko-test.wav   # 처음 한 번: 모델(MeloTTS-Korean 약 200MB, bert-kor-base 약 450MB)을 Hugging Face에서 받고 nltk cmudict를 %APPDATA%\nltk_data에 받음
```

---

## 3. 로그인 (직접 해야 함)

비밀번호와 인증 코드는 운영자가 직접 넣는다. PowerShell은 **보통 권한**(관리자 아님)으로 새로 연다.

### 3-1. Claude Code

매일 작업 폴더에서 로그인하고 그 폴더를 믿는다고(trust) 답한다. 이걸 안 하면 작업 스케줄러가 부르는 `claude -p`가 멈춘다.

```powershell
cd $env:USERPROFILE\tokenwar-daily
claude
```

1. 화면에서 이 폴더를 믿겠냐고 물으면 **Yes**.
2. `/login` → 브라우저에서 **구독 계정(Claude Pro/Max)** 으로 로그인.
3. 끝나면 `/exit`.

Code 탭용 폴더도 한 번 열어 trust 해 둔다:

```powershell
cd $env:USERPROFILE\tokenwar-agent
claude
```

(Claude 데스크톱 앱의 Code 탭을 쓰면 앱에서도 같은 계정으로 로그인하고 `tokenwar-agent` 폴더를 연다.)

### 3-2. GitHub CLI

```powershell
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
gh auth status
```

- 계정은 **vmvm0406**. `gh auth status`에 `repo`, `workflow` 권한이 보이면 된다 (workflow 권한이 없으면 `.github/workflows` 파일을 바꾼 커밋을 push하지 못한다).
- `gh auth setup-git`을 해야 매일 작업의 `git push`가 이 로그인을 쓴다.
- watch-models.ps1이 `gh workflow run publish.yml`로 게시를 깨우므로 이 로그인이 꼭 필요하다.

### 3-3. git 사용자 이름 (커밋에 찍히는 이름)

```powershell
git config --global user.name "vmvm0406"
git config --global user.email "vmmxu0406@gmail.com"
```

---

## 4. 저장소 받기

2장의 setup-local.ps1을 했으면 둘 다 이미 있다. 확인만 한다.

```powershell
git -C "$env:USERPROFILE\tokenwar-agent" remote -v      # https://github.com/vmvm0406/tokenwar-agent
git -C "$env:USERPROFILE\tokenwar-daily" remote -v      # 같은 주소
```

없으면 받는다:

```powershell
git clone https://github.com/vmvm0406/tokenwar-agent "$env:USERPROFILE\tokenwar-agent"
git clone https://github.com/vmvm0406/tokenwar-agent "$env:USERPROFILE\tokenwar-daily"
```

두 폴더의 쓰임:
- **tokenwar-agent**: 운영자가 Code 탭(지휘 세션)에서 쓰는 폴더. 사람이 시키는 일은 여기서.
- **tokenwar-daily**: 작업 스케줄러 전용. 스크립트가 매번 `main`으로 맞추고 `git pull` 하므로 손으로 고치지 않는다. 기록은 `tokenwar-daily\logs\`.

**폴더 위치를 바꾸지 않는다.** 스크립트들이 `%USERPROFILE%\tokenwar-daily`, `%USERPROFILE%\tokenwar-agent`를 그대로 가정한다. 사용자 이름(`vmmxu`)이 달라지는 것은 괜찮다.

### 4-1. Claude 기억(memory) 붙여 넣기

기억 폴더 이름은 저장소 경로로 정해진다. 경로의 `:`와 `\`가 `-`로 바뀐다. 예: `C:\Users\vmmxu\tokenwar-agent` → `C--Users-vmmxu-tokenwar-agent`. 새 사용자 이름이 다르면 폴더 이름도 다르다. 아래 명령이 알아서 계산한다.

```powershell
$name = (Join-Path $env:USERPROFILE "tokenwar-agent") -replace '[:\\]', '-'
$mem = "$env:USERPROFILE\.claude\projects\$name\memory"
New-Item -ItemType Directory -Force -Path $mem | Out-Null
Copy-Item "$env:USERPROFILE\OneDrive\tokenwar-memory\*.md" $mem     # 1-2에서 복사해 둔 곳
Get-ChildItem $mem
```

`MEMORY.md`가 목차이고, 나머지 `.md`가 각 기억이다. 이 폴더는 Code 탭에서 `tokenwar-agent`를 한 번 열어야 확실히 쓰인다. 옮긴 뒤 Code 탭에서 "기억 목록 보여 줘"로 확인한다.

(선택) 유니티 스킬:

```powershell
Copy-Item -Recurse "$env:USERPROFILE\OneDrive\unity-mcp-skill" "$env:USERPROFILE\.claude\skills\"
```

---

## 5. 작업 스케줄러 등록

setup-local.ps1이 이미 했다면 건너뛴다 (확인만: 5-3). 새 감시 작업만 다시 등록하려면 `setup-local.ps1 -OnlyWatch`.

### 5-1. 옛 노트북에 있던 작업 (2026-11-16 확인)

| 이름 | 언제 | 무엇을 |
|---|---|---|
| `TokenwarAgent` | 로그인 3분 뒤, 매일 9:30·12:30·15:30 | `tokenwar-daily\scripts\run-local.ps1`: 최신 main 받기 → 오늘 빈 칸만큼 `claude -p "Follow LOCAL.md for today..."` → 월요일 첫 실행이면 주간 분석(`weekly-analysis.ps1`) → C 드라이브 정리(`cleanup.ps1`, 3시간에 한 번. `TokenwarModelWatch`도 15분마다 부름) |
| `TokenwarModelWatch` | 15분마다 (끝없이 반복) | `tokenwar-daily\scripts\watch-models.ps1`: 게시 시각 지난 큐가 있으면 `gh workflow run publish.yml` → 공식 블로그 새 모델 감시 → 새 발표면 `claude -p "LOCAL.md 6장"`으로 바로 올리기 PR |

공통 설정: 로그인한 사용자로만 실행(Interactive, 보통 권한), 놓친 시각은 켜지면 바로 실행(StartWhenAvailable), 배터리에서도 실행, 최대 2시간, 이미 돌고 있으면 새로 안 띄움. **노트북이 켜져 있고 로그인돼 있어야 돈다.** 두 작업은 `%TEMP%\tokenwar.lock`으로 서로 겹치지 않는다.

### 5-2. 손으로 등록하기 (setup-local.ps1을 안 쓸 때)

보통 권한 PowerShell에서 그대로 붙여 넣는다.

```powershell
$Repo = Join-Path $env:USERPROFILE "tokenwar-daily"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

# 1) 매일 작업: 로그인 3분 뒤, 9:30, 12:30, 15:30
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Repo\scripts\run-local.ps1`""
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = "PT3M"
$t1 = New-ScheduledTaskTrigger -Daily -At "09:30"
$t2 = New-ScheduledTaskTrigger -Daily -At "12:30"
$t3 = New-ScheduledTaskTrigger -Daily -At "15:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "TokenwarAgent" -Action $action -Trigger $logon, $t1, $t2, $t3 -Settings $settings -Principal $principal -Force

# 2) 새 모델 감시·게시 깨우기: 15분마다
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Repo\scripts\watch-models.ps1`""
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 15)
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "TokenwarModelWatch" -Action $a -Trigger $t -Settings $s -Principal $principal -Force
```

### 5-3. 등록 확인

```powershell
Get-ScheduledTask -TaskName Tokenwar* | ForEach-Object {
    $i = Get-ScheduledTaskInfo -TaskName $_.TaskName
    "{0}  {1}  다음 실행: {2}" -f $_.TaskName, $_.State, $i.NextRunTime
}
```

둘 다 `Ready`이고 다음 실행 시각이 보이면 된다.

---

## 6. 확인

순서대로 해 본다. 보통 권한 PowerShell.

```powershell
cd $env:USERPROFILE\tokenwar-agent

# 1) 카드뉴스 렌더링 (Playwright·글꼴) → samples\s1-nvidia 안에 JPEG가 생기면 성공. 직접 열어 글꼴이 검은고딕인지 본다
py -3.12 agent/render.py samples/s1-nvidia

# 2) 릴스 렌더링 (FFmpeg) → mp4가 생기면 성공
py -3.12 agent/render.py samples/s8-huang-quote

# 3) 게시 칸 상황 (config.json 읽기)
py -3.12 agent/slots.py status

# 4) 새 모델 감시 (인터넷·파이썬, 기록은 안 바꿈)
py -3.12 agent/model_watch.py --dry-run -v

# 5) Claude가 스케줄러처럼 혼자 도는지 (짧은 시험, 아무것도 안 만듦)
cd $env:USERPROFILE\tokenwar-daily
claude -p "Reply with the single word OK." --permission-mode auto --max-turns 1

# 6) GitHub CLI로 Actions를 부를 수 있는지 (실행은 안 함, 목록만)
gh workflow list -R vmvm0406/tokenwar-agent
```

샘플 렌더링은 `samples/` 안의 결과 파일을 다시 쓴다. 확인이 끝나면 되돌린다:

```powershell
git -C "$env:USERPROFILE\tokenwar-agent" checkout -- samples
```

감시 작업을 한 번 직접 돌려 본다 (Claude는 부르지 않음):

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\tokenwar-daily\scripts\watch-models.ps1" -CheckOnly
```

하루 작업을 손으로 한 번 돌려 보고 싶으면 (오늘 칸이 비어 있으면 실제로 게시물을 만든다):

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\tokenwar-daily\scripts\run-local.ps1"
```

**기록 보는 곳**

| 무엇 | 위치 |
|---|---|
| 매일 작업 Claude 출력 | `%USERPROFILE%\tokenwar-daily\logs\<날짜>-<시각>.log` |
| 매일 작업 git 기록 | `...\logs\<날짜>-<시각>-start.log` |
| 감시·게시 깨우기 | `...\logs\<연-월>-watch.log` (한 달에 파일 하나) |
| 원할 때 만들기 | `...\logs\<날짜>-<시각>-make-r<N>-c<N>.log` |
| 주간 분석 | `...\logs\<날짜>-<시각>-weekly.log` |
| C 드라이브 정리 | `...\logs\cleanup.log` |
| 임시 파일(영상 받기 등) | `%TEMP%\tokenwar\` (정리 스크립트가 24시간 지난 것을 지움, 옮길 필요 없음) |

가장 최근 기록 보기:

```powershell
Get-Content (Get-ChildItem $env:USERPROFILE\tokenwar-daily\logs | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

다음 날 아침 9:30 뒤에 `logs`에 새 기록이 생기고 GitHub에 `post/<날짜>` PR이 열리면 이사가 끝난 것이다.

---

## 7. 바뀌지 않는 것 (다시 할 필요 없음)

노트북이 아니라 GitHub·Meta·외부 서비스에 있는 것들이다.

- **GitHub Secrets** (저장소 Settings › Secrets and variables › Actions). 값은 여기에만 있고 노트북에는 없다:
  - `IG_ACCESS_TOKEN`, `IG_USER_ID` — 인스타 게시·분석
  - `THREADS_ACCESS_TOKEN` — 스레드 게시
  - `CF_ACCOUNT_ID`, `CF_API_TOKEN` — Cloudflare AI 그림 (Cloudflare Workers Paid 요금제(월 5달러), 운영자 결제 2026-11-17. 하루 그림 상한은 config.json `image_gen.daily_limit`)
  - `GH_PAT` — 토큰 연장 작업(refresh-token.yml)이 Secrets를 고칠 때
  - Variables: `IG_API_HOST`
- **Meta 개발자 앱**(`tokenwar-publisher`)과 페이지·인스타 연결, 권한
- **Zorcha** (댓글 자동 DM, @tokenwar_ai 연결) — 웹 서비스라 노트북과 무관. 브라우저에서 다시 로그인만 하면 된다
- **GitHub Pages** (main `/docs`, https://vmvm0406.github.io/tokenwar-agent/), 검토 페이지
- **GitHub Actions** 일정 전부 (게시 15분마다, 벤치마크 매일, 토큰 점검 매주 월, 토큰 연장 매달 1·20일, 검토 페이지 30분마다)

---

## 8. 이 문서 갱신 규칙

- **이 컴퓨터에만 있는 설정을 추가하거나 바꾸면 같은 커밋에서 MIGRATION.md를 고친다.** 예: 새 작업 스케줄러 작업, 일정 변경, 새 프로그램이나 pip 패키지 설치, 새 로그인(새 CLI·서비스), 새 GitHub Secret·Variable, 폴더 위치 변경, Claude 설정(스킬·기억) 추가.
- 설치·등록은 가능하면 `scripts/setup-local.ps1`에도 같이 넣어, 새 노트북에서 한 번에 되게 한다.
- 고칠 때 맨 위 "마지막 확인" 날짜를 바꾼다. 2-4의 버전 표는 크게 바뀌었을 때만.
- 2027년 1월 이사 전에 지휘 세션에 "MIGRATION.md 다시 확인해 줘"를 시켜 이 컴퓨터 상태와 맞는지 본다.
