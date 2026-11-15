# 토큰전쟁 로컬 설정 (한 번만 실행)
# 관리자 권한 PowerShell에서:  powershell -ExecutionPolicy Bypass -File setup-local.ps1
# 하는 일: 필요한 프로그램 설치 → 저장소 받기 → 파이썬 패키지 → Claude Code 설치 → 작업 스케줄러 등록
$ErrorActionPreference = "Stop"
function Step($m) { Write-Host "`n== $m" -ForegroundColor Green }

Step "1/6 프로그램 설치 (Git, Python 3.12, FFmpeg, Node.js, GitHub CLI)"
foreach ($id in "Git.Git", "Python.Python.3.12", "Gyan.FFmpeg", "OpenJS.NodeJS.LTS", "GitHub.cli") {
    winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements
}
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

Step "2/6 Claude Code 설치"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Step "3/6 매일 작업 전용 저장소 받기 (%USERPROFILE%\tokenwar-daily)"
# 운영자가 Code 탭에서 쓰는 tokenwar-agent 폴더와 따로 둔다. 매일 작업은 이 폴더에서만 돈다.
$Repo = Join-Path $env:USERPROFILE "tokenwar-daily"
if (-not (Test-Path (Join-Path $Repo ".git"))) { git clone https://github.com/vmvm0406/tokenwar-agent $Repo }
Set-Location $Repo
git checkout --quiet main
git pull --ff-only --quiet origin main

Step "4/6 파이썬 패키지 (렌더링, 받아쓰기, 유튜브)"
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install requests pillow numpy playwright faster-whisper "yt-dlp[default,curl-cffi]"
py -3.12 -m playwright install chromium

Step "5/6 작업 스케줄러 등록 (로그인할 때, 9:30, 12:30, 15:30)"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Repo\scripts\run-local.ps1`""
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = "PT3M"
$t1 = New-ScheduledTaskTrigger -Daily -At "09:30"
$t2 = New-ScheduledTaskTrigger -Daily -At "12:30"
$t3 = New-ScheduledTaskTrigger -Daily -At "15:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName "TokenwarAgent" -Action $action -Trigger $logon, $t1, $t2, $t3 -Settings $settings -Principal $principal -Force | Out-Null

Step "6/6 남은 일 (직접)"
Write-Host @"
아래 두 가지는 로그인이 필요해서 직접 해 주세요 (각각 한 번만):
  1) claude          → 브라우저로 Claude 계정 로그인, 끝나면 /exit
  2) gh auth login   → GitHub.com / HTTPS / 브라우저로 로그인 (vmvm0406 계정)
     gh auth setup-git
끝나면 시험 실행:  powershell -ExecutionPolicy Bypass -File "$Repo\scripts\run-local.ps1"
결과는 $Repo\logs 폴더에 남습니다.
"@
