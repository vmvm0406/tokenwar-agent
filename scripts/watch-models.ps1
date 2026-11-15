# 새 AI 모델 감시 → 새 발표가 있으면 게시물 1개를 바로 올리기로 만든다 (LOCAL.md 6장).
# 윈도우 작업 스케줄러(TokenwarModelWatch)가 30분마다 부른다. 등록: setup-local.ps1 -OnlyWatch
#   powershell -ExecutionPolicy Bypass -File scripts\watch-models.ps1            보통 실행
#   ... -CheckOnly                                                               감시만 (Claude를 부르지 않음, 기록도 안 바꿈)
# 매일 작업과 같은 전용 저장소 %USERPROFILE%\tokenwar-daily 에서 돈다. 같은 잠금 파일(%TEMP%\tokenwar.lock)을 쓰므로
# 매일 작업·make-posts가 도는 중이면 이번 차례는 건너뛴다 (30분 뒤 다시 본다).
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
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -gt (Get-Date).AddHours(-3))) { exit 0 }  # 다른 작업이 실행 중
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
    $prompt = "Follow LOCAL.md section 6 (새 모델 바로 올리기). Work and write in Korean. New announcements found by agent/model_watch.py (company | title | url):`n$list`n" +
              "Make at most $max post(s) (card news or reel; howto angle first: '바로 이렇게 써 보기'), only for consumer-facing new models or big features. " +
              "publish_at from 'py -3.12 agent/slots.py next <kind> --asap'. $ship " +
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
}
