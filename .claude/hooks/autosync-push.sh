#!/usr/bin/env bash
# 응답이 끝날 때마다 작업물을 커밋·푸시한다.
#
# 왜: 노트북에서 하던 걸 데스크탑에서 바로 이어받으려면, 변경이 원격에 올라가 있어야 한다.
#     수동 커밋에 의존하면 "푸시를 깜빡해서 반대편에 없는" 상황이 반드시 생긴다.
#
# ⚠️ 안전장치:
#   1) git add -A 를 절대 쓰지 않는다. 아래 SYNC_PATHS 에 적힌 경로만 추가한다.
#      (미추적 문서·설계도·시방서 백업이 딸려 올라가 유실처럼 보이는 사고를 막기 위함)
#   2) *.credentials.local.md 는 .gitignore 로 이미 제외되어 있다.
#   3) 변경이 없으면 아무것도 하지 않는다.

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# 동기화할 경로 — 여기 없는 것은 자동으로 올라가지 않는다.
SYNC_PATHS="docs k8s manifests scripts .claude infra/monitoring infra/loadtest"

BR="$(git branch --show-current 2>/dev/null)"
[ -z "$BR" ] && exit 0

# main 에서는 자동 커밋하지 않는다(팀 공유 브랜치 보호).
if [ "$BR" = "main" ]; then
  echo "[autosync] main 브랜치에서는 자동 커밋하지 않습니다."
  exit 0
fi

# 존재하는 경로만 add
for p in $SYNC_PATHS; do
  [ -e "$p" ] && git add -- "$p" 2>/dev/null
done

# 스테이지에 변경이 없으면 종료
if git diff --cached --quiet 2>/dev/null; then
  exit 0
fi

CHANGED="$(git diff --cached --name-only | wc -l | tr -d ' ')"
git commit -q -m "chore(sync): 자동 동기화 ($(date '+%m/%d %H:%M'), ${CHANGED}개 파일)" 2>/dev/null || exit 0

# 푸시 전에 한 번 더 당겨서 반대편 변경과 충돌을 피한다.
git pull --rebase --quiet origin "$BR" 2>/dev/null

if git push --quiet origin "$BR" 2>/dev/null; then
  echo "[autosync] ${CHANGED}개 파일 푸시 완료"
else
  echo "[autosync] 커밋됨 (푸시 실패 — 나중에 'git push' 필요)"
fi

exit 0
