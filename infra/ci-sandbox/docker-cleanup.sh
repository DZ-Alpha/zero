#!/bin/sh
# harbor VM의 self-hosted 러너가 매 CI 실행마다 로컬 docker 이미지를 쌓기만 하고
# 지우는 절차가 없어서 실제로 8GB 넘게 정리 안 된 채 방치됐던 걸 2026-07-17에
# 발견하고 만든 정기 정리 스크립트. cron으로 매일 실행한다.
#
# 안전 범위: dangling 이미지(태그 없는 것)와 빌드 캐시만 지운다. 실제 태그가 붙은
# 이미지(backend-*, ci-sandbox 등)는 이 스크립트가 절대 건드리지 않는다 - 특히
# backend-* 는 재헌님 백엔드 서비스 빌드 산출물이라 신중해야 한다는 판단(2026-07-17,
# 김지훈 지시)에 따라 자동 정리 대상에서 의도적으로 제외한다.
docker image prune -f
docker builder prune -f --filter until=72h
