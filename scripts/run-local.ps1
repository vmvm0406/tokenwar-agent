# 토큰전쟁 하루 작업 실행. 윈도우 작업 스케줄러가 로그인할 때와 9:30, 12:30, 15:30에 부른다.
# 오늘 카드뉴스와 릴스가 이미 있으면 Claude를 부르지 않고 바로 끝낸다 (사용량 절약).
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
$Repo = Join-Path $env:USERPROFILE "tokenwar-agent"
$LogDir = Join-Path $Repo "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Lock = Join-Path $env:TEMP "tokenwar.lock"
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -gt (Get-Date).AddHours(-2))) { exit 0 }  # 이미 실행 중
Set-Content -Path $Lock -Value (Get-Date)
try {
    Set-Location $Repo
    git pull --rebase --quiet 2>$null
    $today = Get-Date -Format "yyyy-MM-dd"
    $have = @(Get-ChildItem -Directory posts\queue, posts\published -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "$today-*" } | ForEach-Object { $_.Name })
    $prs = ""
    try { $prs = (gh pr list --state open --json headRefName -q ".[].headRefName" 2>$null) -join " " } catch {}
    $carousel = ($have -match "carousel").Count -gt 0 -or $prs -match "post/$today( |$)"
    $reel = ($have -match "video|reel").Count -gt 0 -or $prs -match "post/$today-reel"
    if ($carousel -and $reel) { exit 0 }
    $log = Join-Path $LogDir ("{0}-{1}.log" -f $today, (Get-Date -Format "HHmm"))
    $prompt = "Follow LOCAL.md for today. Work and write in Korean. Today carousel exists: $carousel, today reel exists: $reel."
    claude -p $prompt --permission-mode auto --max-turns 300 2>&1 | Out-File -FilePath $log -Encoding utf8
}
finally {
    Remove-Item $Lock -ErrorAction SilentlyContinue
}
