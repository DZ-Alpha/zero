#!/usr/bin/env bash
# 응답이 끝날 때마다 "개인 메모리 저장소만" 동기화한다.
#
# ── 왜 팀 저장소는 자동으로 안 올리는가 (2026-07-28 구조 변경) ──
#   원래 목적은 "노트북에서 하던 세션을 데스크탑에서 그대로 이어가기" 였다.
#   그건 개인 저장소(celtics-korean/zero-memory)만으로 충족된다.
#   그런데 처음엔 팀 공개 저장소(DZ-Alpha/zero)에도 자동 푸시를 걸었고,
#   첫 실행에서 미추적 상태였던 manifests/ 44개가 통째로 공개 저장소에 올라갔다.
#   자격증명은 없었지만 네임스페이스 구조·서비스 포트·자원 배분이 노출됐다.
#
#   교훈: 개인 편의 기능이 팀 저장소에 산출물을 밀어 넣게 만들면
#         "무엇이 올라갈지"에 대한 통제가 사라진다.
#   → 팀 저장소 커밋은 사람이 의도해서 하는 것만 남긴다(직접 커밋 또는 PR).
#   → 자동은 개인 저장소 하나로 한정한다.

MEMREPO="$HOME/Documents/zero-memory"
[ -d "$MEMREPO/.git" ] || exit 0

cd "$MEMREPO" || exit 0

# 메모리는 "틀린 것을 지우는" 일이 있어서 삭제도 반영해야 한다.
# 단 경로를 memory 로 한정하므로 다른 파일이 딸려가지 않는다.
git add -A -- memory 2>/dev/null

git diff --cached --quiet 2>/dev/null && exit 0

# ── 비밀 유출 차단 게이트 ───────────────────────────────────────
# 자동 커밋은 "사람이 안 보고 올린다"는 뜻이므로 게이트가 없으면 안 된다.
# 값은 harbor.credentials.local.md 에만 두고 메모리에는 참조만 남긴다.
LEAK="$(git diff --cached -U0 \
        | grep -E '^\+' \
        | grep -Ein 'AKIA[0-9A-Z]{16}|hooks\.slack\.com/services/|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|PVEAPIToken|[a-z]{3,12}zero#' \
        | head -5)"

if [ -n "$LEAK" ]; then
  git reset --quiet HEAD -- . 2>/dev/null
  echo "[autosync] ⛔ 메모리에 비밀로 보이는 값이 있어 커밋을 중단했습니다:"
  echo "$LEAK" | sed 's/^/           /'
  exit 0
fi

N="$(git diff --cached --name-only | wc -l | tr -d ' ')"
git commit -q -m "chore(memory): 자동 동기화 ($(date '+%m/%d %H:%M'), ${N}개)" 2>/dev/null || exit 0
git pull --rebase --quiet origin main 2>/dev/null

if git push --quiet origin main 2>/dev/null; then
  echo "[autosync] 메모리 ${N}개 푸시 완료"
else
  echo "[autosync] 메모리 커밋됨 (푸시 실패 — 나중에 'git push' 필요)"
fi

exit 0
