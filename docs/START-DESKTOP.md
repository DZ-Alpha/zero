# 데스크탑 시작 가이드 — AI 진행 대본

> 작성 2026-07-27 (노트북 세션에서) · 김지훈 · 보안·모니터링
> **사용법**: 데스크탑의 새 Claude Code 세션에서 `@docs/START-DESKTOP.md 대로 진행해줘.` 라고 입력.

---

# 🤖 0. AI에게 — 이 문서를 읽었으면 이렇게 진행할 것

**진행 원칙 (반드시 지킬 것)**

1. **한 번에 한 단계씩.** 전체 목록을 한꺼번에 쏟지 않는다. 명령 하나 주고 → 결과 확인 → 다음.
2. **매 단계마다 성공 판정을 명시**하고, 사용자가 결과를 붙여넣으면 판정해 준다.
3. **실패하면 "실패하면" 항목대로 대응**하고, 그래도 안 되면 원인을 좁히는 질문을 한다.
4. **도구를 직접 실행할 수 있으면 직접 실행한다.** 사용자에게 타이핑을 미루지 않는다.
   단, Tailscale 로그인·7z 압축 해제처럼 **사람만 할 수 있는 것**은 안내만 한다.
5. 세팅이 끝나면 **8장**의 마무리 멘트를 하고, `docs/세션인계_데스크탑_20260727.md` 를 읽어
   실제 업무로 넘어간다.

**첫 발화는 이렇게 시작한다 (그대로 써도 됨)**

> "데스크탑 세팅을 8단계로 진행하겠습니다. 한 번에 하나씩 확인하면서 갈게요.
> 대부분 제가 직접 확인하고, 사람이 해야 하는 것만 요청드리겠습니다.
> 먼저 어떤 도구가 깔려 있는지 보겠습니다."
>
> → 바로 **단계 1**의 명령을 실행한다.

---

# 📋 세팅 8단계

## 단계 1 — 도구 확인

**AI가 직접 실행:**
```powershell
foreach ($t in @('git','node','claude','tailscale','code')) {
  $c = Get-Command $t -ErrorAction SilentlyContinue
  if ($c) { "OK   $t -> $($c.Source)" } else { "없음 $t" }
}
```

**성공 판정**: `git`, `claude`, `tailscale` 3개가 OK.
(`node`는 claude를 npm으로 설치했을 때만 필요, `code`는 있으면 편한 정도)

**실패하면 — 없는 것만 안내:**

| 없는 것 | 설치 |
| --- | --- |
| `git` | <https://git-scm.com/download/win> — 설치 후 **PowerShell 새로 열기** |
| `node` | <https://nodejs.org> LTS |
| `claude` | `npm i -g @anthropic-ai/claude-code` 또는 데스크탑 앱 |
| `tailscale` | <https://tailscale.com/download/windows> |
| `code` | VS Code — 설치 시 "PATH에 추가" 체크 |

> 💬 **말할 것**: "설치 후에는 PowerShell을 새로 열어야 PATH가 반영됩니다. 다시 확인해 드릴게요."

---

## 단계 2 — 저장소 확인

**AI가 직접 실행:**
```powershell
cd $env:USERPROFILE\Documents\zero
git branch --show-current
git log --oneline -3
git status --short | Select-Object -First 5
```

**성공 판정**: 브랜치가 `work/k8s-security-20260727` 이고, 로그에
`feat(k8s): 네임스페이스 16개 -ns 통일...` 이 보인다.

**실패하면:**

- **폴더가 없다** → clone부터:
  ```powershell
  cd $env:USERPROFILE\Documents
  git clone https://github.com/DZ-Alpha/zero.git
  cd zero
  git checkout work/k8s-security-20260727
  ```
- **브랜치가 main이다** → `git fetch origin; git checkout work/k8s-security-20260727`
- **최신이 아니다** → `git pull origin work/k8s-security-20260727`
- **인증을 묻는다** → GitHub 계정으로 로그인. 브라우저가 뜨면 승인.

---

## 단계 3 — 메모리 폴더 배치 ★ 가장 중요

> 💬 **말할 것**: "이게 이번 세팅에서 제일 중요합니다. 여기에 지금까지 쌓인 팀 규칙·판단 기준이 들어 있어서,
> 이게 없으면 제가 처음 만난 상태로 시작하게 됩니다."

**AI가 직접 실행 — 넣어야 할 정확한 위치를 계산:**
```powershell
$repo = "$env:USERPROFILE\Documents\zero"
$projId = ($repo -replace ':','-' -replace '\\','-')
$projId = $projId.Substring(0,1).ToLower() + $projId.Substring(1)
$mem = "$env:USERPROFILE\.claude\projects\$projId\memory"
New-Item -ItemType Directory -Force $mem | Out-Null
"넣을 위치: $mem"
if (Test-Path $mem) { "현재 파일 수: " + (Get-ChildItem $mem -Filter *.md -EA SilentlyContinue).Count }
```

> **왜 계산이 필요한가**: Claude는 **작업 디렉터리 경로**로 프로젝트를 식별한다.
> 노트북은 `c--Users-skyo4-Documents-zero` 였는데, 데스크탑 사용자명이 다르면 식별자도 달라진다.
> **경로를 억지로 맞출 필요는 없고**, 메모리 폴더 이름만 이 PC 기준으로 맞추면 된다.

**사용자에게 요청할 것:**

> 💬 "카톡으로 받은 `k8s-handoff.7z` 를 풀어서, 그 안의 `memory` 폴더에 있는 `.md` 파일들을
> 위에 나온 경로에 **전부** 복사해 주세요. 압축 비밀번호는 따로 알려드린 값입니다."

**복사 후 AI가 검증:**
```powershell
Get-ChildItem $mem -Filter *.md | Select-Object Name, Length | Format-Table -AutoSize
```

**성공 판정**: `.md` 파일이 **25개 이상**, 그중 `MEMORY.md` 가 반드시 있다.

**실패하면:**
- **파일이 0개** → 압축을 다른 데 풀었을 가능성. `MEMORY.md` 를 검색해서 찾아준다:
  ```powershell
  Get-ChildItem $env:USERPROFILE -Recurse -Filter "MEMORY.md" -EA SilentlyContinue |
    Select-Object -First 5 FullName
  ```
- **파일 수가 적다** → 하위 폴더째 복사됐을 수 있다. `memory\memory\` 같은 이중 구조인지 확인.
- **7z가 안 열린다** → 7-Zip 설치(<https://www.7-zip.org>) 또는 비밀번호 재확인.

---

## 단계 4 — 자격증명 파일 배치

**사용자에게 요청:**

> 💬 "같은 압축 안에 있는 `harbor.credentials.local.md` 를 저장소 루트에 넣어주세요:
> `%USERPROFILE%\Documents\zero\harbor.credentials.local.md`"

**AI가 검증 — 존재 + gitignore 확인:**
```powershell
cd $env:USERPROFILE\Documents\zero
if (Test-Path harbor.credentials.local.md) {
  "파일 있음"
  git check-ignore -v harbor.credentials.local.md
} else { "없음" }
```

**성공 판정**: 파일이 있고, `git check-ignore` 가 `.gitignore:6:*.credentials.local.md` 를 출력.

**실패하면:**
- **gitignore가 안 걸린다** 🔴 → **절대 커밋하면 안 된다.** `.gitignore` 에 `*.credentials.local.md` 가
  있는지 확인하고, 없으면 추가한다.
- **파일이 없다** → 없어도 진행은 가능하다. VM 비밀번호가 필요할 때 다시 요청한다.

---

## 단계 5 — Tailscale 로그인

> 💬 **말할 것**: "VM들은 사내망에 있어서 Tailscale로만 닿습니다. 로그인이 필요합니다."

**사용자가 직접 (AI는 못 함):**
```powershell
tailscale up
```
→ 브라우저가 열리면 **노트북과 같은 계정(`skyo4545@gmail.com`)** 으로 로그인.

**AI가 검증:**
```powershell
tailscale status | Select-Object -First 8
```

**성공 판정**: 목록에 `harbor` (`100.96.79.73`) 와 `monitoring` (`100.110.81.51`) 이 보인다.

**실패하면:**
- **다른 계정으로 로그인됨** → `tailscale logout` 후 다시.
- **노드 승인 대기** → Tailscale 관리 콘솔(<https://login.tailscale.com>)에서 이 기기를 승인.

---

## 단계 6 — VM 도달성 확인

**AI가 직접 실행:**
```powershell
@(
  @{n='harbor VM';    ip='100.96.79.73';  p=443},
  @{n='monitoring VM';ip='100.110.81.51'; p=3000}
) | ForEach-Object {
  $r = Test-NetConnection $_.ip -Port $_.p -WarningAction SilentlyContinue -InformationLevel Quiet
  "{0,-15} {1}" -f $_.n, $(if($r){"도달 OK"}else{"실패"})
}
```

**성공 판정**: 둘 다 `도달 OK`.

**실패하면:**
- 단계 5로 돌아가 `tailscale status` 재확인.
- VM 자체가 꺼져 있을 수 있다 — 오늘 K8s 이관 작업 중이라 재부팅됐을 가능성.
  **급하지 않으면 넘어가도 된다.** 매니페스트 작성은 VM 없이도 가능하다.

---

## 단계 7 — SSH 키 (선택)

**AI가 확인:**
```powershell
Test-Path "$env:USERPROFILE\.ssh\id_ed25519"
```

**있으면** → 통과.
**없으면** → 두 가지 중 선택하게 한다:

> 💬 "SSH 키가 없습니다. 두 가지 방법이 있어요.
> ① **지금은 넘어간다** — VM 접속 시 비밀번호(`harbor.credentials.local.md` 참조)로 됩니다. 급하면 이쪽.
> ② **새로 만든다** — 담당자가 바뀔 때 키도 새로 만드는 게 원칙이라 이쪽이 더 깔끔합니다.
>   `ssh-keygen -t ed25519 -C "desktop"` 후 공개키를 VM의 `~/.ssh/authorized_keys` 에 추가합니다.
>   제가 등록까지 도와드릴 수 있습니다."

---

## 단계 8 — 시방서 파일 (선택)

> 💬 **말할 것**: "시방서 엑셀은 저장소에 없습니다. 온라인 시트가 원본이라서요.
> 시방서 작업을 하실 거면 **온라인 시트에서 최신본을 다운로드**해서
> `Downloads` 폴더에 두시면 제가 읽겠습니다."

**AI가 확인:**
```powershell
Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "*시방서*.xlsx" -EA SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name, LastWriteTime
```

> ⚠️ **읽는 방법 주의**: 이 PC에 Python이 없을 수 있다.
> xlsx는 zip이므로 **PowerShell로 직접 파싱**하는 방법이 확실하다.
> `Expand-Archive` → `xl/sharedStrings.xml` + `xl/worksheets/sheetN.xml` 을 정규식으로 파싱.
> `[xml]` 전체 DOM 파싱은 시트가 크면 매우 느리니 정규식 방식을 쓸 것.

---

# ✅ 세팅 완료 — 최종 점검

**AI가 한 번에 실행:**
```powershell
$repo = "$env:USERPROFILE\Documents\zero"
$projId = ($repo -replace ':','-' -replace '\\','-')
$projId = $projId.Substring(0,1).ToLower() + $projId.Substring(1)
$mem = "$env:USERPROFILE\.claude\projects\$projId\memory"
cd $repo
"브랜치      : " + (git branch --show-current)
"최신 커밋   : " + (git log --oneline -1)
"메모리 파일 : " + (Get-ChildItem $mem -Filter *.md -EA SilentlyContinue).Count + " 개"
"자격증명    : " + $(if(Test-Path "$repo\harbor.credentials.local.md"){"있음"}else{"없음"})
"Tailscale   : " + $(if((tailscale status 2>$null) -match 'harbor'){"연결됨"}else{"확인필요"})
```

**전부 정상이면 이렇게 말한다:**

> 💬 "세팅 끝났습니다. 노트북에서 하던 것과 동일한 상태입니다.
> 이제 `docs/세션인계_데스크탑_20260727.md` 를 읽고 지금 상황을 파악한 다음,
> 남은 작업을 안내드리겠습니다."

→ **`docs/세션인계_데스크탑_20260727.md` 를 읽는다.**

---

# 🎯 세팅 후 — 바로 이어갈 작업

세션인계 문서를 읽었으면 아래를 **요약해서** 사용자에게 브리핑한다. 길게 늘어놓지 않는다.

**브리핑 형식 (3줄로):**
> 💬 "지금 상황은 이렇습니다.
> ① 성애님이 VM 6대를 만들었고 `kubeadm init`은 아직 안 돌렸습니다. K8s 1.36 / Cilium / 마스터1+워커5 확정입니다.
> ② 클러스터 초기화용 보안 설정 3종과 네임스페이스 16개는 이미 작성돼 있습니다.
> ③ 최우선은 시방서 PodSecurity 탭 오류입니다 — 관측 DaemonSet 2종이 baseline이라 배포하면 조용히 안 뜹니다."

**그 다음 선택지를 준다 (VM 없이도 되는 것 위주):**

| # | 작업 | 선행조건 |
| --- | --- | --- |
| 1 | 시방서 PodSecurity 탭 수정 (최우선 오류) | 시방서 파일 |
| 2 | **ServiceAccount + RBAC 매니페스트** | 없음 ✅ |
| 3 | **NetworkPolicy 매니페스트** | 없음 ✅ |
| 4 | ★ **etcd 스냅샷 CronJob** — 마스터 1대라 백업이 유일한 복구 수단 | 없음 ✅ |
| 5 | ResourceQuota / LimitRange | ⚠️ 워커 사양 확정 후 |

> ⚠️ **2번을 시작하면 학습 모드 규칙을 지킨다.** 완성본을 먼저 주지 말고 이 질문부터:
> *"각 워크로드가 API 서버에 무엇을 요청해야 하나요? `prometheus` / `cicd-deployer` /
> `cert-manager` / `kyverno` / `vault-injector` 중 **네임스페이스를 넘어야만 하는 것**은 무엇일까요?"*

---

# 📌 AI가 계속 지켜야 할 것 (노트북 세션과 동일)

1. **완성본을 먼저 주지 않는다.** 뼈대(`___`)와 힌트 → 사용자가 채움 → 리뷰.
2. **맞는 부분은 설명하지 않는다.** 틀린 것과 빠진 것만 짚는다.
3. **매일 마감에 회상 테스트 3문항을 먼저 낸다.** 요청을 기다리지 않는다.
4. **모든 기술 주장에 공식 문서 근거를 단다.** 기억으로 단정하지 않는다.
5. **제안에는 항상 리스크 평가를 붙인다.**
6. **live 시스템 변경은 리스크 제시 → 승인 → 실행** 순서. 실행하며 설명하지 않는다.
7. **한국어로, 매 단계 무엇을/왜/어떻게.** 디버깅 과정도 숨기지 않는다.
8. `git add -A` / `git add .` **금지.** 경로 명시.
9. **추적 파일에 평문 비밀번호 금지.**
10. **작업이 끝나면 알림을 보낸다.**

> 긴급해서 완성본을 줘야 할 때는 **"지금은 예외입니다, 워크스루는 X시에 하겠습니다"** 라고 명시한다.

---

# 🆘 자주 막히는 곳

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| Claude가 팀 규칙을 모른다 | 메모리 폴더 위치가 틀림 | 단계 3 재실행. 폴더명이 이 PC 경로와 맞는지 확인 |
| `git pull`이 인증 실패 | GitHub 로그인 안 됨 | `git config --global credential.helper manager` 후 재시도 |
| VM에 SSH가 안 된다 | Tailscale 미로그인 | `tailscale status` 확인 |
| `sudo`가 비밀번호를 묻고 멈춘다 | 비대화형 셸 | `sshpass` 사용하거나, 사용자가 직접 터미널에서 실행 |
| xlsx 읽기가 2분 넘게 걸린다 | `[xml]` DOM 파싱 | 정규식 방식으로 전환 (단계 8 주의사항) |
| Python이 안 된다 | Microsoft Store 스텁 | Python 대신 PowerShell 사용 |
