#!/bin/sh
# CI 트리거 검증용 임시 파일 (2026-07-31).
# 목적: dang-pipeline-ci의 2번째 빌드에서 event-pipeline이 NOT_BUILT로
#       걸러지는지 실증(첫 빌드만 무조건 빌드하는 폴백 동작 확인).
# event-pipeline/ 폴더 밖 + 문서(.md/.txt/.gitignore) 아님 → Detect가 코드로 취급하나
# event-pipeline 변경은 아니므로 NOT_BUILT여야 정상.
# 검증 후 삭제 예정.
echo "ci trigger test"
