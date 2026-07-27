# 데스크탑 환경 자동 세팅
#
# 사용법 (PowerShell에서):
#   irm https://raw.githubusercontent.com/DZ-Alpha/zero/work/k8s-security-20260727/scripts/setup-desktop.ps1 | iex
# 또는 파일을 받아서:
#   .\setup-desktop.ps1
#
# 이 스크립트가 하는 일:
#   1. 필수 도구 확인 (git / claude / tailscale)
#   2. 저장소 clone 또는 최신화 + 작업 브랜치 체크아웃
#   3. Claude 메모리 폴더의 "정확한 위치"를 계산해서 알려줌
#   4. 자격증명 파일 배치 여부 확인
#   5. VM 도달성 점검
#   6. 새 Claude 세션에 붙여넣을 첫 프롬프트 출력

$ErrorActionPreference = "Continue"
$BRANCH = "work/k8s-security-20260727"
$REPO   = "https://github.com/DZ-Alpha/zero.git"

function Head($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function OK($t)   { Write-Host "  [OK]   $t" -ForegroundColor Green }
function WARN($t) { Write-Host "  [확인] $t" -ForegroundColor Yellow }
function ERR($t)  { Write-Host "  [필요] $t" -ForegroundColor Red }

# ─────────────────────────────────────────────────────────────
Head "1. 필수 도구"

$tools = @{
  "git"       = "https://git-scm.com/download/win"
  "claude"    = "npm i -g @anthropic-ai/claude-code  (또는 데스크탑 앱)"
  "tailscale" = "https://tailscale.com/download/windows"
}
$missing = @()
foreach ($t in $tools.Keys) {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  if ($c) { OK "$t" } else { ERR "$t 없음 → $($tools[$t])"; $missing += $t }
}

# ─────────────────────────────────────────────────────────────
Head "2. 저장소"

# 노트북과 경로를 똑같이 맞출 필요는 없다.
# Claude는 "현재 경로"로 프로젝트를 식별하므로,
# 메모리 폴더 이름만 이 데스크탑의 경로에 맞추면 된다 (3번에서 계산).
$REPO_DIR = Join-Path $env:USERPROFILE "Documents\zero"

if (Test-Path (Join-Path $REPO_DIR ".git")) {
  OK "이미 있음: $REPO_DIR"
  Push-Location $REPO_DIR
  git fetch origin
  git checkout $BRANCH
  git pull origin $BRANCH
  Pop-Location
} else {
  if ($missing -contains "git") {
    ERR "git이 없어 clone을 건너뜁니다"
  } else {
    New-Item -ItemType Directory -Force (Split-Path $REPO_DIR) | Out-Null
    git clone $REPO $REPO_DIR
    Push-Location $REPO_DIR
    git checkout $BRANCH
    Pop-Location
    OK "clone 완료: $REPO_DIR"
  }
}

# ─────────────────────────────────────────────────────────────
Head "3. Claude 메모리 폴더 위치 ★ 가장 중요"

# Claude Code는 작업 디렉터리 경로를 변환해서 프로젝트를 식별한다.
#   C:\Users\skyo4\Documents\zero  ->  c--Users-skyo4-Documents-zero
# 즉 ':' 와 '\' 를 '-' 로 바꾼 것. 사용자명이 다르면 식별자도 달라진다.
$projId = ($REPO_DIR -replace ':', '-' -replace '\\', '-')
$projId = $projId.Substring(0,1).ToLower() + $projId.Substring(1)

$claudeProjects = Join-Path $env:USERPROFILE ".claude\projects"
$memDir = Join-Path $claudeProjects "$projId\memory"

Write-Host "  이 PC의 프로젝트 식별자 : " -NoNewline; Write-Host $projId -ForegroundColor White
Write-Host "  메모리를 넣을 위치      : " -NoNewline; Write-Host $memDir -ForegroundColor White
Write-Host ""

if (Test-Path $memDir) {
  $n = (Get-ChildItem $memDir -Filter *.md -ErrorAction SilentlyContinue).Count
  OK "메모리 폴더 존재 (파일 $n 개)"
  if ($n -lt 5) { WARN "파일이 적습니다. 노트북에서 받은 memory 폴더 내용을 전부 복사했는지 확인하세요" }
} else {
  New-Item -ItemType Directory -Force $memDir | Out-Null
  WARN "메모리 폴더를 만들었습니다. 노트북에서 받은 memory 폴더의 *.md 를 여기에 전부 복사하세요:"
  Write-Host "         $memDir" -ForegroundColor Yellow
  Write-Host "         (노트북 원본: C:\Users\skyo4\.claude\projects\c--Users-skyo4-Documents-zero\memory\)" -ForegroundColor DarkGray
}

# 참고: 다른 이름의 프로젝트 폴더가 이미 있으면 알려준다
if (Test-Path $claudeProjects) {
  $others = Get-ChildItem $claudeProjects -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*zero*" -and $_.Name -ne $projId }
  if ($others) {
    WARN "비슷한 이름의 다른 프로젝트 폴더가 있습니다 (경로가 달라서 생긴 것):"
    $others | ForEach-Object { Write-Host "         $($_.Name)" -ForegroundColor DarkGray }
  }
}

# ─────────────────────────────────────────────────────────────
Head "4. 자격증명 파일"

$cred = Join-Path $REPO_DIR "harbor.credentials.local.md"
if (Test-Path $cred) {
  OK "harbor.credentials.local.md 배치됨"
  Push-Location $REPO_DIR
  $ignored = git check-ignore harbor.credentials.local.md 2>$null
  Pop-Location
  if ($ignored) { OK "gitignore 적용 확인 (커밋될 위험 없음)" }
  else { ERR "gitignore가 안 걸려 있습니다! 절대 커밋하지 마세요" }
} else {
  WARN "harbor.credentials.local.md 없음 → 암호화 압축에서 풀어 여기에 두세요:"
  Write-Host "         $cred" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────
Head "5. VM 도달성 (Tailscale)"

if ($missing -contains "tailscale") {
  WARN "Tailscale 미설치 → VM 접속 불가. 설치 후 'tailscale up' 으로 로그인하세요"
} else {
  $targets = @(
    @{ n="harbor VM";     ip="100.96.79.73";  p=443  },
    @{ n="monitoring VM"; ip="100.110.81.51"; p=3000 }
  )
  foreach ($t in $targets) {
    $r = Test-NetConnection -ComputerName $t.ip -Port $t.p -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($r) { OK "$($t.n) ($($t.ip):$($t.p)) 도달" }
    else    { WARN "$($t.n) 도달 실패 → 'tailscale status' 로 로그인 상태를 확인하세요" }
  }
}

# SSH 키
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
if (Test-Path $key) { OK "SSH 키 있음" }
else { WARN "SSH 키 없음 → 비밀번호로 접속하거나, ssh-keygen 후 VM에 공개키 등록" }

# ─────────────────────────────────────────────────────────────
Head "6. 다음 단계"

Write-Host @"
  1) VS Code 로 저장소를 엽니다:
       code "$REPO_DIR"

  2) Claude Code 를 시작하고, 아래 프롬프트를 그대로 붙여넣습니다:
"@ -ForegroundColor White

Write-Host ""
Write-Host "  ────────────────── 복붙 시작 ──────────────────" -ForegroundColor DarkGray
Write-Host @"
@docs/세션인계_데스크탑_20260727.md 읽고 이어서 작업하자.
"@ -ForegroundColor Green
Write-Host "  ────────────────── 복붙 끝 ────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  세팅 완료." -ForegroundColor Cyan
