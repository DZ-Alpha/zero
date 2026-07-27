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

# ── 비밀 유출 차단 게이트 ───────────────────────────────────────
# 2026-07-27: 첫 실행에서 미검토 상태의 manifests/*/secrets.yaml 4개가
# 한꺼번에 커밋·푸시됐다. 이번엔 전부 REPLACE_ME 플레이스홀더라 무사했지만,
# 실제 값이었다면 그대로 유출이었다. 자동 커밋은 "사람이 안 보고 올린다"는 뜻이므로
# 게이트가 없으면 안 된다.
#
# 확실한 것만 막는다(오탐이 잦으면 게이트를 꺼버리게 되므로).
LEAK="$(git diff --cached -U0 \
        | grep -E '^\+' \
        | grep -Ein 'AKIA[0-9A-Z]{16}|hooks\.slack\.com/services/|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}' \
        | head -5)"

if [ -n "$LEAK" ]; then
  git reset --quiet HEAD -- . 2>/dev/null
  echo "[autosync] ⛔ 커밋 중단 — 비밀로 보이는 값이 감지됐습니다:"
  echo "$LEAK" | sed 's/^/           /'
  echo "           스테이지를 되돌렸습니다. 해당 값을 제거한 뒤 수동으로 커밋하세요."
  exit 0
fi

CHANGED="$(git diff --cached --name-only | wc -l | tr -d ' ')"

# 새로 추적되는 파일이 많으면 알린다 (의도치 않은 대량 편입 감지)
NEWF="$(git diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')"
if [ "$NEWF" -gt 10 ]; then
  echo "[autosync] ⚠️ 신규 파일 ${NEWF}개가 새로 추적됩니다. 의도한 것인지 확인하세요:"
  git diff --cached --name-only --diff-filter=A | head -5 | sed 's/^/           /'
  echo "           ..."
fi
git commit -q -m "chore(sync): 자동 동기화 ($(date '+%m/%d %H:%M'), ${CHANGED}개 파일)" 2>/dev/null || exit 0

# 푸시 전에 한 번 더 당겨서 반대편 변경과 충돌을 피한다.
git pull --rebase --quiet origin "$BR" 2>/dev/null

if git push --quiet origin "$BR" 2>/dev/null; then
  echo "[autosync] ${CHANGED}개 파일 푸시 완료"
else
  echo "[autosync] 커밋됨 (푸시 실패 — 나중에 'git push' 필요)"
fi

exit 0
