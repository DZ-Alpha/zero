#!/usr/bin/env bash
# 팀원 PC에 gitleaks pre-commit hook을 설치하는 스크립트.
# 실행: bash scripts/setup-hooks.sh (Windows는 Git Bash에서 실행)
set -e

if ! command -v pre-commit >/dev/null 2>&1; then
  echo "pre-commit이 설치되어 있지 않습니다. 설치를 진행합니다..."
  pip install pre-commit
fi

pre-commit install
echo "pre-commit hook 설치 완료. 검증을 위해 전체 파일 스캔을 실행합니다..."
pre-commit run gitleaks --all-files
