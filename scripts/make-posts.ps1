# 토큰전쟁 게시물 미리 만들기 / 바로 올리기 (운영자가 원할 때).
#   powershell -ExecutionPolicy Bypass -File scripts\make-posts.ps1 -Reels 3 -Cards 2
#   ... -Reels 2 -Now                 바로 올리기: 칸 배정 없이 렌더링이 끝나면 다음 15분 게시 확인 때 (검토 모드면 Merge 직후)
#   ... -Reels 6 -Date 2026-11-17     그날에 몰아 넣기 (그날만 칸 상한을 넘겨도 됨, 칸 사이 최소 1시간 반)
# 매일 작업과 같은 전용 저장소 %USERPROFILE%\tokenwar-daily 에서 돈다 (Code 탭의 tokenwar-agent 폴더와 겹치지 않게).
# 한 번에 만든 게시물은 PR 하나로 묶는다 (LOCAL.md 5장).
param(
    [int]$Reels = 0,
    [int]$Cards = 0,
    [switch]$Now,
    [string]$Date = ""
)
if ($Reels -le 0 -and $Cards -le 0) { Write-Host "만들 개수를 주세요. 예: -Reels 3 -Cards 2"; exit 2 }
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
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -gt (Get-Date).AddHours(-3))) { Write-Host "매일 작업이나 다른 만들기가 실행 중입니다. 끝난 뒤 다시 실행하세요."; exit 1 }
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
    $mode = if ($Now) { "ASAP: publish as soon as rendered (slots.py next <kind> --asap)" }
            elseif ($Date) { "Put them on $Date (slots.py next <kind> --count N --date $Date --max <that day's total>)" }
            else { "Assign nearest empty slots (slots.py next <kind> --count N)" }
    $log = Join-Path $LogDir ("{0}-make-r{1}-c{2}.log" -f (Get-Date -Format "yyyy-MM-dd-HHmm"), $Reels, $Cards)
    $prompt = "Follow LOCAL.md section 5 (미리 만들기·바로 올리기). Work and write in Korean. Make $Reels reel(s) and $Cards carousel(s). $mode. One PR for the whole batch."
    Write-Host "만드는 중: 릴스 $Reels, 카드뉴스 $Cards (기록: $log)"
    if ((Get-Content config.json -Raw -Encoding utf8 | ConvertFrom-Json).production_paused -eq $true) { Write-Host "제작 멈춤 (config production_paused): 만들지 않음"; exit 0 }
    claude -p $prompt --permission-mode auto --max-turns 600 2>&1 | Out-File -FilePath $log -Encoding utf8
    Write-Host "끝. 기록: $log"
}
finally {
    Remove-Item $Lock -ErrorAction SilentlyContinue
}
