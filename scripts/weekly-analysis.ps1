# 주간 계정 분석: 벤치마크 계정 찾기·목록 고치기·이번 주 적용할 3가지 (ANALYSIS.md).
# run-local.ps1이 월요일 그날 첫 실행에서 부른다 (이번 주 data/weekly_insights.md가 이미 있으면 건너뜀).
# 손으로: powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\tokenwar-daily\scripts\weekly-analysis.ps1 -Force
param([switch]$Force)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Repo = Join-Path $env:USERPROFILE "tokenwar-daily"
$LogDir = Join-Path $Repo "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Repo

$today = Get-Date
$marker = Join-Path $LogDir ("weekly-{0}.done" -f $today.ToString("yyyy-MM-dd"))
if (-not $Force) {
    if ($today.DayOfWeek -ne [DayOfWeek]::Monday) { exit 0 }
    if (Test-Path $marker) { exit 0 }   # 오늘 이미 한 번 시도함 (실패해도 같은 날 다시 쓰지 않는다)
    $ins = Join-Path $Repo "data\weekly_insights.md"
    if (Test-Path $ins) {
        $first = (Get-Content $ins -TotalCount 1 -Encoding utf8)
        if ($first -match "(\d{4}-\d{2}-\d{2})") {
            $monday = $today.Date.AddDays(-(([int]$today.DayOfWeek + 6) % 7))
            if ([datetime]::ParseExact($Matches[1], "yyyy-MM-dd", $null) -ge $monday) { exit 0 }  # 이번 주 것이 있음
        }
    }
}
Set-Content -Path $marker -Value (Get-Date -Format s)

# 코드 분석은 먼저 새로 (AI 없음, 몇 초)
py -3.12 agent/peer_followers.py 2>&1 | Out-Null
py -3.12 agent/patterns.py 2>&1 | Out-Null

$log = Join-Path $LogDir ("{0}-weekly.log" -f $today.ToString("yyyy-MM-dd-HHmm"))
$prompt = "Follow ANALYSIS.md exactly (weekly account analysis). Work and write in Korean. Today is $($today.ToString('yyyy-MM-dd'))."
claude -p $prompt --permission-mode auto --max-turns 80 2>&1 | Out-File -FilePath $log -Encoding utf8
