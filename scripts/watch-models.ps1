# 새 AI 모델 감시 → 새 발표가 있으면 게시물 1개를 바로 올리기로 만든다 (LOCAL.md 6장).
# 윈도우 작업 스케줄러(TokenwarModelWatch)가 15분마다 부른다. 등록: setup-local.ps1 -OnlyWatch
# 매번 먼저 게시 시각이 지난 게시물이 있으면 publish.yml을 직접 실행한다 (GitHub cron 지연 대비)
#   powershell -ExecutionPolicy Bypass -File scripts\watch-models.ps1            보통 실행
#   ... -CheckOnly                                                               감시만 (Claude를 부르지 않음, 기록도 안 바꿈)
# 매일 작업과 같은 전용 저장소 %USERPROFILE%\tokenwar-daily 에서 돈다. 같은 잠금 파일(%TEMP%\tokenwar.lock)을 쓰므로
# 매일 작업·make-posts가 도는 중이면 이번 차례 감시는 건너뛴다 (15분 뒤 다시 본다).
# 단, 매일 작업(run-local) 중에 처음 보는 속보(업계 속보·공식 블로그 새 모델)가 잡히면 매일 작업의 Claude를 멈추고
# 속보를 먼저 만든 뒤, 끝나면 매일 작업을 다시 띄운다 (LOCAL.md 6장 '속보가 먼저'). 남은 변경은 stash에 남는다.
param([switch]$CheckOnly)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
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

# 게시 확인 대신 눌러 주기: GitHub의 15분 cron(publish.yml)이 몇 시간씩 늦을 때가 있어서,
# origin/main의 posts/queue에 게시 시각이 지난 게시물이 하나라도 있으면 publish.yml을 직접 실행한다.
# 잠금 파일과 상관없이 매번 (작업 폴더는 건드리지 않고 fetch만 한다). gh 로그인이 필요하다.
if ((-not $CheckOnly) -and (Test-Path (Join-Path $Repo ".git"))) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $plog = Join-Path $LogDir ("{0}-watch.log" -f (Get-Date -Format "yyyy-MM"))
    try {
        git -C $Repo fetch --quiet origin main 2>$null
        $now = [DateTimeOffset]::Now
        $due = @()
        foreach ($f in @(git -C $Repo ls-tree -r --name-only origin/main -- posts/queue | Where-Object { $_ -like "*/post.json" })) {
            $j = (git -C $Repo show "origin/main:$f") -join "`n" | ConvertFrom-Json
            if ($j.publish_at -and [DateTimeOffset]::Parse($j.publish_at) -le $now) { $due += $f }
        }
        if ($due.Count -gt 0) {
            gh workflow run publish.yml -R vmvm0406/tokenwar-agent 2>&1 | Out-Null
            ("{0} 게시 시각 지난 것 {1}개 → publish.yml 실행 (종료 코드 {2}): {3}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $due.Count, $LASTEXITCODE, ($due -join ", ")) |
                Out-File -Append -FilePath $plog -Encoding utf8
        }
    } catch {
        ("{0} 게시 확인 실패: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $_) | Out-File -Append -FilePath $plog -Encoding utf8
    }
}

$Interrupted = $false
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -gt (Get-Date).AddHours(-3))) {
    # 다른 작업이 실행 중. 매일 작업(run-local의 claude)일 때만, 처음 보는 속보가 있으면 그 작업을 멈추고 속보를 먼저 한다
    if ($CheckOnly -or -not (Test-Path (Join-Path $Repo ".git"))) { exit 0 }
    $daily = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
               Where-Object { $_.CommandLine -like "*Follow LOCAL.md for today*" -and $_.Name -notlike "powershell*" })
    if ($daily.Count -eq 0) { exit 0 }   # make-posts 등 운영자가 시킨 작업은 끊지 않는다
    Push-Location $Repo
    $hits = @(py -3.12 agent/model_watch.py --dry-run --breaking-only 2>$null)   # 기록은 바꾸지 않음
    $hc = $LASTEXITCODE
    Pop-Location
    if ($hc -ne 10) { exit 0 }
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $ilog = Join-Path $LogDir ("{0}-watch.log" -f (Get-Date -Format "yyyy-MM"))
    ("{0} 속보 → 매일 작업을 멈추고 먼저 만든다: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), ($hits -join " / ")) |
        Out-File -Append -FilePath $ilog -Encoding utf8
    foreach ($p in $daily) { taskkill /PID $p.ProcessId /T /F 2>&1 | Out-Null }
    # run-local은 claude가 끝나면 finally에서 정리하고 잠금을 지운다. 3분까지 기다리고, 그래도 있으면 지운다
    for ($i = 0; ($i -lt 36) -and (Test-Path $Lock); $i++) { Start-Sleep -Seconds 5 }
    Remove-Item $Lock -ErrorAction SilentlyContinue
    $Interrupted = $true
}
Set-Content -Path $Lock -Value (Get-Date)
try {
    if (-not (Test-Path (Join-Path $Repo ".git"))) { git clone --quiet $RepoUrl $Repo }
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Set-Location $Repo
    $wlog = Join-Path $LogDir ("{0}-watch.log" -f (Get-Date -Format "yyyy-MM"))   # 감시 기록은 한 달에 파일 하나
    function Note($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $m) | Out-File -Append -FilePath $wlog -Encoding utf8 }
    function Git-Log { # git을 돌리고 출력은 감시 기록에만 남긴다. 종료 코드를 돌려준다
        $out = & git @args 2>&1
        $code = $LASTEXITCODE
        if ($out) { ($out | ForEach-Object { "  git: $_" }) | Out-File -Append -FilePath $wlog -Encoding utf8 }
        return $code
    }
    # 최신 main으로 (run-local.ps1과 같은 방식: 남은 변경은 stash에 치워 둔다)
    if (git status --porcelain) { [void](Git-Log stash push --include-untracked -m ("watch-models " + (Get-Date -Format s))) }
    [void](Git-Log checkout --quiet main)
    if ((Git-Log pull --ff-only --quiet origin main) -ne 0) { Note "git pull 실패: main이 origin/main과 갈라짐. 건너뜀"; exit 1 }

    if ($CheckOnly) { py -3.12 agent/model_watch.py --dry-run -v; exit $LASTEXITCODE }
    $all = @(py -3.12 agent/model_watch.py 2>&1)
    $code = $LASTEXITCODE
    $all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { Note "$_" }
    $found = @($all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] -and "$_".Trim() } | ForEach-Object { "$_" })
    if ($code -eq 2) { Note "출처를 하나도 읽지 못함 (인터넷 확인)"; exit 1 }

    # 본 것 기록(data/model_watch.json)은 Claude를 부르기 전에 main에 올린다 (다른 컴퓨터·다음 실행과 공유, 게시물 브랜치에 섞이지 않게)
    if (git status --porcelain -- data/model_watch.json) {
        [void](Git-Log add data/model_watch.json)
        [void](Git-Log commit --quiet -m "모델 감시: 본 글 기록 갱신")
        if ((Git-Log push --quiet origin main) -ne 0) {
            [void](Git-Log pull --rebase --quiet origin main)
            [void](Git-Log push --quiet origin main)
        }
    }
    if ($code -ne 10 -or $found.Count -eq 0) { exit 0 }

    # $found = 이번에 새로 찾은 것 + 지난 회차에 실패해 남은 것 (status pending). 3번 실패하면 failed로 빠진다
    $found | ForEach-Object { Note "후보: $_" }
    $auto = (py -3.12 -c "import json;print(json.load(open('config.json',encoding='utf-8')).get('model_watch',{}).get('auto_publish',False))") -eq "True"
    $max = (py -3.12 -c "import json;print(json.load(open('config.json',encoding='utf-8')).get('model_watch',{}).get('max_posts_per_run',1))")
    $ship = if ($auto) { "model_watch.auto_publish is on: push straight to main (no PR)." } else { "One PR (review mode, operator merges)." }
    $list = ($found -join "`n")
    $log = Join-Path $LogDir ("{0}-model.log" -f (Get-Date -Format "yyyy-MM-dd-HHmm"))
    $prompt = "Follow LOCAL.md section 6 (새 모델·업계 속보 바로 올리기). Work and write in Korean. New items found by agent/model_watch.py (company | title | url):`n$list`n" +
              "Lines starting with '[업계 속보' are major industry news (CEO resign/return, big acquisition, regulation/lawsuit, major model) seen in several major outlets: " +
              "make a news card (or a reel if there is an official video) after confirming with 2 sources, even though it is company news; put `"breaking`": true in post.json. " +
              "Other lines: only consumer-facing new models or big features (howto angle first: '바로 이렇게 써 보기'). " +
              "Take the first line first; make at most $max post(s). publish_at from 'py -3.12 agent/slots.py next <kind> --asap'. " +
              "Do not move existing timely posts; only howto/ask posts may be moved with 'py -3.12 agent/slots.py bump' (LOCAL.md 6장). $ship " +
              "End your output with exactly one line: 'MODEL_WATCH: done <PR url>' if you made a post, or 'MODEL_WATCH: skipped <reason>' if nothing qualifies."
    Note "Claude 실행 (기록: $log)"
    claude -p $prompt --permission-mode auto --max-turns 400 2>&1 | Out-File -FilePath $log -Encoding utf8
    $cc = $LASTEXITCODE

    # 결과 기록: 종료 코드 0 + 기록에 PR 주소 → done, 'MODEL_WATCH: skipped' → skipped, 그 밖은 다음 회차에 다시 (3번째 실패면 failed)
    # Claude가 게시물 브랜치에 남겨 둔 것은 stash로 치우고 main에서 기록만 커밋한다
    if (git status --porcelain) { [void](Git-Log stash push --include-untracked -m ("watch-models after claude " + (Get-Date -Format s))) }
    [void](Git-Log checkout --quiet main)
    [void](Git-Log pull --ff-only --quiet origin main)
    py -3.12 agent/model_watch.py --finish $log $cc 2>&1 | ForEach-Object { Note "결과: $_" }
    if (git status --porcelain -- data/model_watch.json) {
        [void](Git-Log add data/model_watch.json)
        [void](Git-Log commit --quiet -m "모델 감시: 후보 처리 결과 기록")
        if ((Git-Log push --quiet origin main) -ne 0) {
            [void](Git-Log pull --rebase --quiet origin main)
            [void](Git-Log push --quiet origin main)
        }
    }
    Note "끝 (claude 종료 코드 $cc)"
}
finally {
    Remove-Item $Lock -ErrorAction SilentlyContinue
    # 속보 때문에 멈춘 매일 작업을 다시 띄운다 (오늘 몫 중 남은 것만 만든다: slots.py need)
    if ($Interrupted) {
        $rl = Join-Path $Repo "scripts\run-local.ps1"
        if (Test-Path $rl) { Start-Process powershell -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -File `"$rl`"" }
    }
}
