# 토큰전쟁 하루 작업 실행. 윈도우 작업 스케줄러가 로그인할 때와 9:30, 12:30, 15:30에 부른다.
# 오늘부터 모레까지 몫(config.json slots.daily_target, 날마다)이 미리 만든 게시물로 차 있으면 Claude를 부르지 않고 끝낸다 (사용량 절약).
# 운영자 승인(config require_approval)을 받을 시간을 벌려고 이틀 치를 미리 만든다. 새 게시물에는 approved를 넣지 않는다.
# 운영자가 Code 탭에서 쓰는 %USERPROFILE%\tokenwar-agent와 겹치지 않게, 매일 작업 전용 저장소
# %USERPROFILE%\tokenwar-daily 에서만 돈다. 시작할 때마다 최신 main을 받는다.
$ErrorActionPreference = "Continue"
# 한글 기록이 깨지지 않게 (claude 출력은 UTF-8)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
# 새로 설치한 프로그램(py, ffmpeg, yt-dlp)을 찾도록 PATH를 시스템 설정에서 다시 읽는다
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
foreach ($d in @("$env:LOCALAPPDATA\Microsoft\WinGet\Links", "$env:LOCALAPPDATA\Programs\Python\Launcher",
                 "$env:LOCALAPPDATA\Programs\Python\Python312", "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
                 "$env:ProgramFiles\Python312", "$env:ProgramFiles\Python312\Scripts", "$env:APPDATA\Python\Python312\Scripts")) {
    if ((Test-Path $d) -and ($env:Path -notlike "*$d*")) { $env:Path += ";$d" }
}
$Repo = Join-Path $env:USERPROFILE "tokenwar-daily"   # 매일 작업 전용 (tokenwar-agent는 건드리지 않는다)
$RepoUrl = "https://github.com/vmvm0406/tokenwar-agent"
$LogDir = Join-Path $Repo "logs"
$Lock = Join-Path $env:TEMP "tokenwar.lock"
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -gt (Get-Date).AddHours(-2))) { exit 0 }  # 이미 실행 중
Set-Content -Path $Lock -Value (Get-Date)
try {
    if (-not (Test-Path (Join-Path $Repo ".git"))) { git clone --quiet $RepoUrl $Repo }
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Set-Location $Repo
    # 최신 main으로. 지난 실행이 남긴 변경은 지우지 않고 stash에 치워 둔다 (git stash list로 볼 수 있음)
    $start = Join-Path $LogDir ("{0}-start.log" -f (Get-Date -Format "yyyy-MM-dd-HHmm"))
    function Git-Log { # git을 돌리고 출력은 시작 기록(UTF-8)에만 남긴다. 종료 코드를 돌려준다
        $out = & git @args 2>&1
        $code = $LASTEXITCODE
        if ($out) { ($out | ForEach-Object { "$_" }) | Out-File -Append -FilePath $start -Encoding utf8 }
        return $code
    }
    if (git status --porcelain) { [void](Git-Log stash push --include-untracked -m ("run-local " + (Get-Date -Format s))) }
    [void](Git-Log checkout --quiet main)
    if ((Git-Log pull --ff-only --quiet origin main) -ne 0) {
        # 로컬 main이 origin과 갈라졌으면 오래된 코드로 돌지 않도록 멈춘다. 기록을 보고 손으로 정리한다
        "git pull 실패: tokenwar-daily의 main이 origin/main과 갈라짐. 작업을 건너뜀" | Out-File -Append -FilePath $start -Encoding utf8
        exit 1
    }
    $today = Get-Date -Format "yyyy-MM-dd"
    # 주간 계정 분석 (ANALYSIS.md): 월요일 그날 첫 실행에서만, 이번 주 data/weekly_insights.md가 있으면 건너뜀
    $weekly = Join-Path $Repo "scripts\weekly-analysis.ps1"
    if ((Test-Path $weekly) -and (Get-Date).DayOfWeek -eq [DayOfWeek]::Monday) {
        try { & $weekly } catch { "주간 분석 실패: $_" | Out-File -Append -FilePath $start -Encoding utf8 }
        Set-Location $Repo
        [void](Git-Log checkout --quiet main)
        [void](Git-Log pull --ff-only --quiet origin main)
    }
    # 제작 멈춤 (config.json production_paused, 운영자 2026-11-17 "three.js 테스트 될 때까지 더이상 제작하지 말자"): 승인된 것 게시는 그대로
    if ((Get-Content config.json -Raw -Encoding utf8 | ConvertFrom-Json).production_paused -eq $true) {
        "제작 멈춤 (config production_paused): 새 게시물을 만들지 않음" | Out-File -Append -FilePath $start -Encoding utf8
        exit 0
    }
    # 게시 칸(config.json slots): 오늘부터 모레까지 날짜별 몫(daily_target)에서 이미 예약된 것을 뺀 만큼만 만든다
    # slots.py need 출력: 날짜별 "2026-11-18 carousel=1 reel=5" 줄들 + 마지막 줄 합계 "carousel=1 reel=5"
    $needOut = @(py -3.12 agent/slots.py need --days 2 2>$null | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    $nCard = 0; $nReel = 0; $plan = @()
    $target = (Get-Content config.json -Raw -Encoding utf8 | ConvertFrom-Json).slots.daily_target
    foreach ($line in $needOut) {
        if ($line -match "^(\d{4}-\d{2}-\d{2}) carousel=(\d+) reel=(\d+)") {
            $c = [int]$Matches[2]; $r = [int]$Matches[3]; $d = $Matches[1]
            if ($c -gt 0) { $plan += "$d carousel x$c ('py -3.12 agent/slots.py next carousel --count $c --date $d --max $($target.carousel)')" }
            if ($r -gt 0) { $plan += "$d reel x$r ('py -3.12 agent/slots.py next reel --count $r --date $d --max $($target.reel)')" }
        } elseif ($line -match "^carousel=(\d+) reel=(\d+)") { $nCard = [int]$Matches[1]; $nReel = [int]$Matches[2] }
    }
    if ($needOut.Count -eq 0) { $nCard = 1; $nReel = 1 }   # 칸 계산이 실패하면 예전처럼 하나씩
    if ($nCard -eq 0 -and $nReel -eq 0) { exit 0 }
    $log = Join-Path $LogDir ("{0}-{1}.log" -f $today, (Get-Date -Format "HHmm"))
    $slotsHow = if ($plan.Count) { "Per date (fill the earliest date first; get publish_at with the command shown): " + ($plan -join "; ") + "." }
                else { "Get each publish_at from 'py -3.12 agent/slots.py next <kind> --count N' (LOCAL.md 5장)." }
    $prompt = "Follow LOCAL.md for today. Work and write in Korean. Make $nCard carousel(s) and $nReel reel(s) in advance for today through the day after tomorrow. $slotsHow Do not put 'approved' in post.json (the operator approves after review; LOCAL.md 3장)."
    # 브라우저(Playwright MCP)를 쓰더라도 창을 띄우지 않는다 (2026-11-17: 정해진 시각 실행 때 크롬 창이 여러 번 떴다)
    $env:PLAYWRIGHT_MCP_HEADLESS = "true"
    # 나눠 맡긴 에이전트가 끝날 때까지 기다린다 (2026-11-17: 기본 600초에 걸려 에이전트 10개가 끝나기 전에 끊겼다)
    $env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = "0"
    claude -p $prompt --permission-mode auto --max-turns 300 2>&1 | Out-File -FilePath $log -Encoding utf8
}
finally {
    # C 드라이브 자동 정리 (하루 한 번 조건은 cleanup.ps1이 본다). 할 일이 없어 일찍 끝난 날에도 돌도록 finally 안에서
    $cleanup = Join-Path $Repo "scripts\cleanup.ps1"
    if (Test-Path $cleanup) {
        try { & $cleanup | Out-Null } catch { }
    }
    Remove-Item $Lock -ErrorAction SilentlyContinue
}
