# 자격증명 파일을 암호화해서 개인 private 저장소에 올릴 수 있게 만든다.
#
# 왜 암호화하는가:
#   private 저장소라도 git 히스토리는 영구적이다. 비밀번호를 나중에 바꿔도
#   옛 값은 히스토리에 남는다(2026-07-12 SonarQube 사고에서 실증됨).
#   암호문으로 올리면 저장소가 어디에 있든, 나중에 public이 되더라도 안전하다.
#
# 방식: gpg 대칭키 암호화(AES-256). Git for Windows에 gpg가 포함돼 있어 추가 설치가 필요 없다.
#
# 사용법:  .\scripts\creds-encrypt.ps1
#          → 암호(passphrase)를 두 번 입력하면 .gpg 파일이 만들어진다.

$ErrorActionPreference = "Stop"

$src = Join-Path $env:USERPROFILE "Documents\zero\harbor.credentials.local.md"
$dstDir = Join-Path $env:USERPROFILE "Documents\zero-memory"
$dst = Join-Path $dstDir "harbor.credentials.local.md.gpg"

if (-not (Test-Path $src)) {
  Write-Host "원본이 없습니다: $src" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path $dstDir)) {
  Write-Host "zero-memory 저장소가 없습니다: $dstDir" -ForegroundColor Red
  Write-Host "먼저 clone 하세요: git clone git@github.com:celtics-korean/zero-memory.git" -ForegroundColor Yellow
  exit 1
}

# --yes: 기존 파일 덮어쓰기
# --cipher-algo AES256: 명시적으로 강한 알고리즘 지정
# --symmetric: 공개키 없이 암호(passphrase)만으로 암호화
Write-Host "암호(passphrase)를 입력하세요. 잊으면 복호화할 수 없습니다." -ForegroundColor Yellow
gpg --symmetric --cipher-algo AES256 --yes --output $dst $src

if ($LASTEXITCODE -eq 0 -and (Test-Path $dst)) {
  $sz = (Get-Item $dst).Length
  Write-Host "암호화 완료: $dst ($sz bytes)" -ForegroundColor Green
  Write-Host ""
  Write-Host "다음:" -ForegroundColor Cyan
  Write-Host "  cd `"$dstDir`""
  Write-Host "  git add harbor.credentials.local.md.gpg"
  Write-Host "  git commit -m `"chore: 자격증명 갱신`""
  Write-Host "  git push"
} else {
  Write-Host "암호화 실패" -ForegroundColor Red
  exit 1
}
