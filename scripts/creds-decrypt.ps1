# 개인 private 저장소에서 받은 암호문을 복호화해 제자리에 놓는다.
#
# 사용법:  .\scripts\creds-decrypt.ps1
#          → 암호(passphrase)를 입력하면 harbor.credentials.local.md 가 복원된다.
#
# 복원 위치는 .gitignore 로 제외되는 경로이므로, 공용 저장소에 실수로 올라가지 않는다.

$ErrorActionPreference = "Stop"

$src = Join-Path $env:USERPROFILE "Documents\zero-memory\harbor.credentials.local.md.gpg"
$dst = Join-Path $env:USERPROFILE "Documents\zero\harbor.credentials.local.md"

if (-not (Test-Path $src)) {
  Write-Host "암호문이 없습니다: $src" -ForegroundColor Red
  Write-Host "먼저 zero-memory 저장소를 clone/pull 하세요." -ForegroundColor Yellow
  exit 1
}

if (Test-Path $dst) {
  Write-Host "이미 존재합니다: $dst" -ForegroundColor Yellow
  $a = Read-Host "덮어쓸까요? (y/N)"
  if ($a -ne "y") { Write-Host "취소했습니다."; exit 0 }
}

gpg --decrypt --yes --output $dst $src

if ($LASTEXITCODE -eq 0 -and (Test-Path $dst)) {
  Write-Host "복호화 완료: $dst" -ForegroundColor Green

  # 공용 저장소에서 gitignore가 걸려 있는지 확인 — 안 걸려 있으면 사고로 이어진다
  Push-Location (Join-Path $env:USERPROFILE "Documents\zero")
  $ig = git check-ignore harbor.credentials.local.md 2>$null
  Pop-Location
  if ($ig) {
    Write-Host "gitignore 확인됨 — 공용 저장소에 커밋될 위험 없음" -ForegroundColor Green
  } else {
    Write-Host "경고: gitignore가 안 걸려 있습니다. 절대 커밋하지 마세요!" -ForegroundColor Red
  }
} else {
  Write-Host "복호화 실패 (암호가 틀렸을 수 있습니다)" -ForegroundColor Red
  exit 1
}
