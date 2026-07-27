#!/usr/bin/env bash
# 세션 시작 시 원격 최신 상태를 가져온다.
#
# 왜: 데스크탑/노트북 어느 쪽에 앉든, 세션을 열자마자 상대편에서 한 작업이 반영된 상태로 시작한다.
# 실패해도 세션을 막지 않는다(exit 0). 네트워크가 없거나 충돌이 나도 작업은 계속되어야 한다.

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

BR="$(git branch --show-current 2>/dev/null)"
[ -z "$BR" ] && exit 0

# --autostash: 로컬에 작업 중이던 변경이 있어도 잠시 치웠다가 되돌려 놓는다.
# --rebase   : 머지 커밋을 만들지 않아 히스토리가 깔끔하다.
if git pull --rebase --autostash --quiet origin "$BR" 2>/dev/null; then
  AHEAD="$(git rev-list --count "origin/$BR..HEAD" 2>/dev/null || echo 0)"
  echo "[autosync] $BR 최신화 완료 (미푸시 커밋 ${AHEAD}개)"
else
  echo "[autosync] pull 건너뜀 — 원격 연결 실패이거나 충돌. 'git status'로 확인하세요."
fi

# ── 개인 메모리 저장소도 함께 당긴다 ────────────────────────────
# ~/.claude/.../memory 는 junction 으로 이 저장소를 가리키므로,
# 여기서 pull 하면 반대편 PC에서 쌓인 메모리가 즉시 반영된다.
MEMREPO="$HOME/Documents/zero-memory"
if [ -d "$MEMREPO/.git" ]; then
  if (cd "$MEMREPO" && git pull --rebase --autostash --quiet origin main 2>/dev/null); then
    echo "[autosync] 메모리 저장소 최신화 완료"
  fi
fi

exit 0
