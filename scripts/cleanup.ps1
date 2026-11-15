# C 드라이브 자동 정리. run-local.ps1이 매번 부르지만 실제 정리는 하루 한 번만 한다
# (마지막 실행 시각 %TEMP%\tokenwar\.last_cleanup, 20시간 안이면 바로 끝).
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup.ps1            보통 실행
#   ... -Force                                                              하루 한 번 조건 무시
#   ... -WhatIf                                                             지울 목록만 출력 (아무것도 안 지움, 기록 안 남김)
# 할 일:
#   - %TEMP%\tokenwar 아래(dl, subs 등) 24시간 넘은 파일과 빈 폴더
#   - %USERPROFILE%\tokenwar-daily\logs 의 30일 넘은 기록 (cleanup.log 제외)
#   - 두 저장소(tokenwar-agent, tokenwar-daily): git worktree prune, 경로가 없거나 %TEMP% 아래이면서
#     7일 넘게 안 바뀐 worktree만 git worktree remove --force (다른 세션이 쓰는 worktree를 지우지 않게), git gc --auto
#   - tokenwar-daily의 posts/published/*/clips/source.mp4 중 git이 추적하지 않는 것 (커밋하지 않는 로컬 정리)
#   - 결과 한 줄을 tokenwar-daily\logs\cleanup.log 에
# 절대 규칙: 두 저장소 폴더와 %TEMP%\tokenwar 밖은 지우지 않는다(worktree는 %TEMP% 아래만).
# 모든 삭제는 Remove-Safe / Test-Under 로 경로가 허용 루트 아래인지 Resolve-Path로 확인한 뒤에 한다.
param([switch]$Force, [switch]$WhatIf)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$AgentRepo = Join-Path $env:USERPROFILE "tokenwar-agent"
$DailyRepo = Join-Path $env:USERPROFILE "tokenwar-daily"
$TempRoot  = Join-Path $env:TEMP "tokenwar"
$Stamp     = Join-Path $TempRoot ".last_cleanup"
$LogDir    = Join-Path $DailyRepo "logs"
$Allowed   = @($AgentRepo, $DailyRepo, $TempRoot)

# 하루 한 번
if (-not $Force -and -not $WhatIf -and (Test-Path -LiteralPath $Stamp)) {
    if ((Get-Item -LiteralPath $Stamp).LastWriteTime -gt (Get-Date).AddHours(-20)) { exit 0 }
}

function Get-FullPath([string]$p) {
    # 실제로 있는 경로만, 정규화된 전체 경로로 (없으면 $null)
    try { return (Resolve-Path -LiteralPath $p -ErrorAction Stop).ProviderPath.TrimEnd('\') } catch { return $null }
}
function Test-Under([string]$path, [string[]]$roots) {
    # $path가 $roots 중 하나의 "안쪽"이면 true (루트 자체는 false)
    $full = Get-FullPath $path
    if (-not $full) { return $false }
    foreach ($r in $roots) {
        $rf = Get-FullPath $r
        if ($rf -and $full.StartsWith($rf + '\', [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

$script:Count = 0
$script:Bytes = [int64]0
$script:Items = @()
function Get-Size([string]$p) {
    $it = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
    if (-not $it) { return [int64]0 }
    if (-not $it.PSIsContainer) { return [int64]$it.Length }
    $s = (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if ($s) { return [int64]$s } else { return [int64]0 }
}
function Remove-Safe([string]$path, [string]$kind, [string[]]$roots = $Allowed) {
    # 허용 루트 안쪽이고, 링크(재분석 지점)가 아닐 때만 지운다
    if (-not (Test-Under $path $roots)) { Write-Output "건너뜀(허용 경로 밖): $path"; return }
    $it = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if (-not $it) { return }
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Output "건너뜀(링크): $path"; return }
    $size = Get-Size $path
    if ($WhatIf) { Write-Output ("[WhatIf] {0} {1} ({2:N1} MB)" -f $kind, $it.FullName, ($size / 1MB)) }
    else {
        Remove-Item -LiteralPath $it.FullName -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $it.FullName) { Write-Output "지우기 실패: $($it.FullName)"; return }
    }
    $script:Count++; $script:Bytes += $size; $script:Items += $kind
}

# 1) %TEMP%\tokenwar 아래 24시간 넘은 파일, 그다음 빈 폴더(폴더 시각도 24시간 넘은 것만)
if (Test-Path -LiteralPath $TempRoot) {
    $cut = (Get-Date).AddHours(-24)
    $dirs = @(Get-ChildItem -LiteralPath $TempRoot -Recurse -Directory -Force -Attributes !ReparsePoint -ErrorAction SilentlyContinue |
              Where-Object { $_.LastWriteTime -lt $cut } | Sort-Object { $_.FullName.Length } -Descending)
    Get-ChildItem -LiteralPath $TempRoot -Recurse -File -Force -Attributes !ReparsePoint -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cut -and $_.FullName -ne $Stamp } |
        ForEach-Object { Remove-Safe $_.FullName "임시파일" }
    foreach ($d in $dirs) {
        if (-not (Test-Path -LiteralPath $d.FullName)) { continue }
        $left = @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue |
                  Where-Object { -not ($WhatIf -and $_.LastWriteTime -lt $cut) })
        if ($left.Count -eq 0) {
            if ($WhatIf) { Write-Output "[WhatIf] 빈폴더 $($d.FullName)" }
            elseif (Test-Under $d.FullName @($TempRoot)) { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue }
        }
    }
}

# 2) 30일 넘은 기록
if (Test-Path -LiteralPath $LogDir) {
    $cut = (Get-Date).AddDays(-30)
    Get-ChildItem -LiteralPath $LogDir -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cut -and $_.Name -ne "cleanup.log" } |
        ForEach-Object { Remove-Safe $_.FullName "기록" @($LogDir) }
}

# 3) git worktree 정리 (경로가 없거나, %TEMP% 아래이면서 7일 넘게 안 바뀐 것만)
function Get-LastChange([string]$dir, [datetime]$cut) {
    # 7일 안에 바뀐 파일이 하나라도 있으면 바로 그 시각을 돌려준다 (전부 훑지 않게)
    $newest = (Get-Item -LiteralPath $dir -Force).LastWriteTime
    if ($newest -ge $cut) { return $newest }
    foreach ($f in Get-ChildItem -LiteralPath $dir -Recurse -Force -Attributes !ReparsePoint -ErrorAction SilentlyContinue) {
        if ($f.LastWriteTime -gt $newest) { $newest = $f.LastWriteTime; if ($newest -ge $cut) { break } }
    }
    return $newest
}
foreach ($repo in @($AgentRepo, $DailyRepo)) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo ".git"))) { continue }
    if ($WhatIf) { git -C $repo worktree prune --dry-run --verbose 2>&1 | ForEach-Object { "[WhatIf] prune ($repo): $_" } }
    else { git -C $repo worktree prune 2>&1 | Out-Null }
    $cut = (Get-Date).AddDays(-7)
    $entries = @(); $cur = $null
    foreach ($line in (git -C $repo worktree list --porcelain 2>$null)) {
        if ($line -like "worktree *") { $cur = @{ path = $line.Substring(9).Replace('/', '\'); locked = $false }; $entries += $cur }
        elseif ($line -like "locked*" -and $cur) { $cur.locked = $true }
    }
    $repoFull = Get-FullPath $repo
    foreach ($e in $entries) {
        $p = $e.path
        if ($repoFull -and $p.TrimEnd('\') -ieq $repoFull) { continue }   # 저장소 자신
        if ($e.locked) { continue }
        if (-not (Test-Path -LiteralPath $p)) {
            if ($WhatIf) { Write-Output "[WhatIf] worktree(경로 없음) $p" }
            else { git -C $repo worktree remove --force $p 2>&1 | Out-Null; git -C $repo worktree prune 2>&1 | Out-Null }
            continue
        }
        if (-not (Test-Under $p @($env:TEMP))) { continue }               # %TEMP%(scratchpad 포함) 아래만
        $last = Get-LastChange $p $cut
        if ($last -ge $cut) { continue }                                    # 7일 안에 바뀜: 누가 쓰는 중일 수 있다
        $size = Get-Size $p
        if ($WhatIf) { Write-Output ("[WhatIf] worktree {0} (마지막 변경 {1:yyyy-MM-dd}, {2:N1} MB)" -f $p, $last, ($size / 1MB)) }
        else {
            git -C $repo worktree remove --force $p 2>&1 | Out-Null
            if (Test-Path -LiteralPath $p) { Write-Output "worktree 지우기 실패: $p"; continue }
        }
        $script:Count++; $script:Bytes += $size; $script:Items += "worktree"
    }
    if (-not $WhatIf) { git -C $repo gc --auto --quiet 2>&1 | Out-Null }
}

# 4) 게시된 릴스의 구간 영상 (git이 추적하지 않는 것만 지운다. 추적 중이면 publish가 main에서 지운다)
$pub = Join-Path $DailyRepo "posts\published"
if (Test-Path -LiteralPath $pub) {
    $tracked = @(git -C $DailyRepo ls-files -- "posts/published/*/clips/source.mp4" 2>$null)
    Get-ChildItem -Path (Join-Path $pub "*\clips\source.mp4") -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($DailyRepo.Length + 1).Replace('\', '/')
        if ($tracked -contains $rel) { Write-Output "건너뜀(git 추적 중): $rel" }
        else { Remove-Safe $_.FullName "source.mp4" @($pub) }
    }
}

$kinds = ($script:Items | Group-Object | ForEach-Object { "$($_.Name) $($_.Count)" }) -join ", "
if (-not $kinds) { $kinds = "없음" }
$summary = "{0:yyyy-MM-dd HH:mm} 지운 것 {1}개 ({2}), 비운 용량 {3:N1} MB" -f (Get-Date), $script:Count, $kinds, ($script:Bytes / 1MB)
if ($WhatIf) { Write-Output "[WhatIf] $summary"; exit 0 }
Write-Output $summary
if (Test-Path -LiteralPath $LogDir) { $summary | Out-File -Append -FilePath (Join-Path $LogDir "cleanup.log") -Encoding utf8 }
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
Set-Content -LiteralPath $Stamp -Value (Get-Date -Format s)
