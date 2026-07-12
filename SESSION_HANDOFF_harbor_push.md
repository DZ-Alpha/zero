# 세션 핸드오프 — Harbor 실연동 작업 (2026-07-09 ~ 07-12)

> 이 문서는 노트북 로컬 환경(원격 데스크탑 아님)에서 Claude Code로 작업을 이어가기 위한
> 컨텍스트 손실 방지용 요약이다. 새 세션에서 이 파일을 함께 참조해서 작업을 이어가면 된다.

## 0. 협업 규칙 (메모리 미동기화 대비 — 반드시 새 세션에 이 규칙들을 적용할 것)

- **매 명령/도구 호출 전에 한 줄로 무엇을/왜/어떻게 할 건지 설명**한 뒤 실행할 것 (사소한 명령도 예외 없음)
- 텍스트 에디터가 필요하면 **nano 대신 vi** 사용
- 공식 문서를 근거로 제시할 때는 **최신 버전 문서를 실제 확인**하고 인용할 것 (확인 안 했으면 라벨링)
- **설계 판단이 필요한 작업**(아키텍처 트레이드오프, 보안 설계 등) 시작 전, 또는 작업 성격이
  라이브 인시던트 대응처럼 바뀔 때마다 **effort/모델 상향이 필요한지 계속 재평가하고 먼저 말할 것**
  (일회성 판단 아님, 매번 체크)
- 팀원과 공유해야 할 변경(공유 설정 파일, GitHub Secrets, main 병합 등)이 생기면 **먼저 알려줄 것**
- **되돌리기 어려운 작업(권한 변경, 볼륨 삭제 등) 전엔 부작용을 충분히 따져보고, 추측성 수정보다
  공식 도구/절차(예: Harbor의 `prepare` 스크립트)를 우선할 것** — 이번 세션에서 `chown -R`을
  섣불리 제안했다가 컨테이너를 깨뜨린 실수가 있었음, 같은 패턴 반복 금지

## 1. 프로젝트 배경

- **ZeroCheck**: 건강식품 라벨 OCR+AI 검증 웹서비스, 부트캠프 하이브리드 클라우드+온프레미스 인프라 수업 프로젝트
- 사용자(김지훈): Team Alpha SecOps + CI/CD 담당
- 개인 마감 7/20, Docker Compose 배포 7/22, k8s 7/23+
- 원칙: **돈 나가는 건 AWS 단계 이후부터** (그 전엔 무료/이미 보유한 자원만 사용)
- GitHub 저장소: `https://github.com/love-1006/zero` (Collaborator 권한 있음)
- 인프라: Proxmox 호스트(`k8s`, 192.168.0.10) 위에 VM 5대, 데스크탑 한 대(32GB RAM)를 나눠 씀
  - harbor VM: VMID 100, IP `192.168.0.53`, hostname `harbor`, SSH 계정 `bruce`, 스펙 8GB RAM/4코어
  - harbor-template: VMID 101 (미사용, 팀원 배포용 템플릿)

## 2. 완료된 것 (main에 병합됨)

- Git 저장소 + GitHub Flow 브랜치 전략 (`Jhoon/ci-cd/*`, `Jhoon/secops/*`, main에서만 분기·병합)
- gitleaks pre-commit 훅 (`.pre-commit-config.yaml`, `scripts/setup-hooks.sh`)
- GitHub Actions Lint 워크플로 (`.github/workflows/lint.yml`) — shellcheck+yamllint
- `.gitattributes` (라인엔딩 정규화), `.yamllint.yml`
- Build & Test 파이프라인 스켈레톤 — 임시 FastAPI 샘플(`ci_sandbox/`)로 검증 완료

## 3. 진행 중 — `Jhoon/ci-cd/harbor-push` 브랜치 (origin에 push됨)

### 커밋된 파일
- `Dockerfile`, `.dockerignore` — `ci_sandbox` 앱 이미지 빌드용
- `ci_sandbox/requirements.txt`에 `uvicorn[standard]` 추가
- `infra/sonarqube/docker-compose.yml`, `.env.example`, `README.md` — SonarQube Community 자체 호스팅용
- `.github/workflows/build-test.yml` — Job 분리 완료:
  - `build-test`: `runs-on: ubuntu-latest` (클라우드, 내부망 불필요)
  - `code-scanning`, `image-scanning`, `image-push`: `runs-on: self-hosted` (harbor VM, 내부망 필요)

### 핵심 아키텍처 결정 (이유 포함, 재논의 불필요)

1. **self-hosted runner가 harbor VM에 필요한 이유**: Harbor가 사설 IP(192.168.0.53)에 있어서
   GitHub 호스팅 클라우드 러너가 도달 불가. 단, self-hosted runner는 **아웃바운드 HTTPS만
   필요**(공식 문서 확인함)해서 harbor VM을 인터넷에 노출시킬 필요는 없음.
2. **러너 배치 위치**: harbor VM에 직접 (별도 VM 안 만듦) — 사용자의 원래 설계도(Proxmox 박스 안에
   Harbor+Trivy+SonarQube+CI/CD 다 포함)와 일치, 실측 리소스로도 충분 확인됨.
3. **Jenkins 대신 GitHub Actions 유지**: Jenkins도 결국 내부망 접근 가능한 컴퓨트가 필요해서
   근본 문제가 안 없어지고, 웹훅 방식이면 오히려 인바운드 노출이 필요해져 더 불리함.
4. **SonarCloud 대신 SonarQube 자체 호스팅**: SonarCloud 무료 티어(5만 LoC 제한)를 넘으면
   원치 않는 시점에 유료 전환 강요당할 리스크 있음 → "AWS 전까지 무비용" 원칙과 충돌 →
   자체 호스팅(라이선스 무료, 무제한)으로 결정.
5. **Job 분리(cloud/self-hosted)**: 내부망 필요 없는 checkout/pytest는 클라우드 러너로 보내
   harbor VM 부하 최소화. docker build/Trivy scan/Harbor push만 self-hosted에서 실행.
6. **VM 스펙(8GB/4코어) 유지, 증설 안 함**: 데스크탑 32GB를 VM 5대가 나눠 쓰는 상황이라 여유
   없음. 실측 결과 Harbor 전체 스택이 1GB 미만 사용 중이라 SonarQube 추가해도 문제 없음 확인.
7. **Harbor 내장 Trivy(`--with-trivy`)와 CI의 pre-push Trivy는 별개** — 둘 다 사용(이중 방어선).

## 4. 현재 라이브 이슈 — 해결 완료 (2026-07-12)

### 타임라인
1. bruce 계정 비밀번호를 잊어버림 (기존 알려진 임시값 `test1234`도 안 먹힘)
2. **Proxmox 콘솔 → GRUB 복구모드(`init=/bin/bash`)로 비밀번호 재설정** — 이 과정에서 VM 재부팅 발생
3. 재부팅 후 **Harbor 핵심 컨테이너 전체(nginx, harbor-core, registry, registryctl, redis,
   harbor-db, jobservice, harbor-portal)가 자동으로 안 돌아옴** (`Exited (128)`, `harbor-log`만 생존)
   → **재부팅 시 자동 기동이 안 되는 근본 문제 발견, 아직 안 고침** (섹션 5-5 참고)
4. 복구 시도: `~/harbor`에서 `docker compose up -d` → `permission denied
   (/home/bruce/harbor/common/config/db/env)` 에러 (Harbor 설치 스크립트가 원래 root로
   실행되어 파일이 root 전용 권한이었음)
5. **실수**: `sudo chown -R bruce:bruce ~/harbor`로 전체 소유권 변경 → 일시적으로 compose는
   실행됐으나 **컨테이너 내부 프로세스가 기대하는 소유권 체계가 깨져서** registryctl/nginx/등이
   `permission denied` (예: `/etc/registryctl/config.yml`)로 재시작 루프에 빠짐
6. **올바른 복구**: `docker compose down` → `sudo ./prepare` (Harbor 공식 설정 재생성 스크립트,
   모든 `common/config/*` 파일을 올바른 내부 권한으로 재생성) → `sudo docker compose up -d`
   → **전체 컨테이너 healthy로 복구 완료**, 외부에서 443 포트 응답 확인함(`Test-NetConnection` 성공)
7. **admin 로그인 계정/비밀번호 문제**: `admin`/`admin`(SonarQube 계정과 착오), `admin`/`Harbor12345`
   (harbor.yml 초기값, DB 초기화 이후 43시간 지나 반영 안 됨) 둘 다 실패
8. **해결**: Harbor 공식 소스(`src/common/utils/encrypt.go`, v2.15.1) 확인 결과 admin 비밀번호는
   `PBKDF2-HMAC-SHA256, iterations=4096, dklen=16`으로 해시되어 `harbor_user.password`(32자 hex)에
   저장됨, salt는 `harbor_user.salt`. harbor-db 컨테이너에 `docker exec`로 직접 접속해 새 salt를
   생성하고 이 알고리즘으로 재계산한 해시값을 `UPDATE harbor_user SET salt=..., password=...
   WHERE username='admin'`으로 반영 → 임시값으로 로그인 성공(API `/api/v2.0/users/current` 200
   확인) → 즉시 `PUT /api/v2.0/users/1/password`로 비밀번호 변경 완료
   - (주의: pgcrypto 확장이 DB에 없어서 처음엔 반복횟수를 10000으로 잘못 가정해 실패했음.
     반드시 위 소스 링크 기준 4096회로 계산할 것 — 같은 문제 반복되면 재확인 필요)

### 부가 진행 사항
- harbor VM에 **Tailscale 설치 완료**, Tailscale IP로 접근 가능해짐 (기존 LAN IP `192.168.0.53`도 여전히 유효)
- 로컬(노트북) SSH 키(`~/.ssh/id_ed25519`, ed25519, 비밀번호 없음)를 harbor VM의
  `~/.ssh/authorized_keys`에 등록 완료 → 이후 세션은 비밀번호 없이 SSH 접속 가능
- **모든 실제 비밀번호/접속 주소는 `harbor.credentials.local.md`(gitignore됨, 커밋 금지)에 있음**
  — bruce SSH/sudo 비밀번호(섹션 5-8 "영구 비밀번호로 재변경" 항목 아직 미완료, 임시값 그대로),
  Harbor admin, SonarQube admin, Proxmox 웹 UI 주소 전부 그 파일 참고
- **보안 사고 대응**: 이전 SonarQube admin 비밀번호(`Zeropass123!`)가 이미 GitHub에 push된 커밋
  `91d23c5`에 평문으로 들어가 있던 게 발견됨 → 즉시 새 비밀번호로 재변경해 무효화 완료
  (git 히스토리 자체는 재작성하지 않기로 결정 — 팀원 pull 상태 충돌 우려 때문, 값만 무효화하면
  충분하다고 판단). **앞으로 이 문서에 실제 비밀번호를 절대 직접 적지 말 것**, 반드시
  `harbor.credentials.local.md`에만 기록.

## 5. 로그인 성공 이후 남은 작업 (순서대로)

1. ~~Harbor: `zerocheck` 프로젝트 생성 (Private)~~ **완료(2026-07-12)** — 단, 프로젝트명은
   `zerocheck`이 아니라 **`dangdang`**으로 생성함 (사용자가 이름 변경 지시). 이후 모든 단계에서
   `zerocheck` 대신 `dangdang` 사용할 것.
2. ~~Harbor: Robot Account 생성~~ **완료(2026-07-12)** — `dangdang` 프로젝트 한정, Push+Pull만,
   만료 없음. 계정명 `robot$dangdang+ci-push-pull`. 실제 시크릿은 `harbor.credentials.local.md`의
   `HARBOR_ROBOT_USER`/`HARBOR_ROBOT_TOKEN` 참고.
3. ~~SonarQube 비밀번호 변경 및 토큰 확인~~ **완료** — admin 비밀번호 변경 완료(값은
   `harbor.credentials.local.md` 참고), 토큰 발급도 완료(사용자가 보관 중, 대화에 노출 안 시킴)
4. ~~GitHub 저장소(`love-1006/zero`) Settings에 등록~~ **완료(2026-07-12)** — 로컬에 `gh` CLI
   설치+인증(`celtics-korean` 계정, WRITE 권한) 후 등록:
   - Variables: `SONAR_HOST_URL` = `http://192.168.0.53:9000` ✓
   - Secrets: `SONAR_TOKEN` ✓ (사용자가 로컬 PowerShell에서 직접 `gh secret set`으로 등록),
     `HARBOR_ROBOT_USER` ✓, `HARBOR_ROBOT_TOKEN` ✓
   - **참고**: `love-1006/zero`는 `PUBLIC` 저장소임이 이번에 확인됨 (팀원 한정이 아니라 인터넷
     공개). 앞으로 이 저장소에 커밋하는 모든 내용에 각별히 주의할 것.
5. ~~Harbor 재부팅 자동 기동 문제 근본 수정~~ **완료(2026-07-12), 실제 VM 재부팅으로 검증함**
   - **근본 원인**(공식 이슈 트래커로 확인): harbor-core 등 8개 컨테이너는 syslog 로그 드라이버로
     `harbor-log`(127.0.0.1:1514)에 의존하는데, `docker` 데몬이 재시작/재부팅되면 모든 컨테이너가
     동시에 뜨려고 시도해서 `harbor-log`가 준비되기 전에 로그 드라이버 연결(`dial tcp
     127.0.0.1:1514: connect: connection refused`)에 실패 → 컨테이너 시작 자체가 실패함.
     `restart: always`는 "시작된 뒤 죽은 경우"만 재시도하고 "애초에 시작을 못 한 경우"는
     재시도하지 않음(`RestartCount=0`으로 확인). `depends_on`은 `docker compose up`을 직접 실행할
     때만 순서를 보장하고, 데몬 자체의 재시작 시엔 적용 안 됨. 근거:
     [moby/moby#31971](https://github.com/moby/moby/issues/31971),
     [moby/moby#21966](https://github.com/moby/moby/issues/21966),
     [docker/compose#12589](https://github.com/docker/compose/issues/12589) — 셋 다 Docker/Compose
     프로젝트 자체 공식 이슈 트래커.
   - **해결**: `/etc/systemd/system/harbor.service` 등록 (`Type=oneshot`, `RemainAfterExit=yes`,
     `ExecStart=/usr/bin/docker compose up -d`, `After=docker.service`, `WantedBy=multi-user.target`,
     `systemctl enable`) — 부팅 시 명시적으로 `docker compose up -d`를 실행해 의존성 순서를
     지키게 함. 개별 컨테이너의 `restart: always`는 그대로 둠(평상시 크래시 복구용, 상충 안 함).
   - **알아둘 점**: 유닛에 `PartOf=docker.service`도 넣었으나, **`systemctl restart docker`처럼
     수동으로 docker 데몬만 재시작하는 경우엔 이 전파가 실측상 작동하지 않았음**(harbor.service가
     `inactive`로 남음). 검증된 것은 **VM 전체 재부팅** 경로(`WantedBy=multi-user.target`)뿐임.
     따라서 앞으로 `docker` 데몬만 따로 재시작할 일이 있으면 반드시 그 직후
     `sudo systemctl restart harbor`도 수동으로 실행할 것.
6. ~~bruce가 sudo 없이 안전하게 관리할 수 있는 방법~~ **결론: 안 함(2026-07-12), 의도적 보류**
   — `docker` 그룹 추가를 검토했으나 Docker 공식 문서("The docker group grants root-level
   privileges to the user")와 CIS Docker Benchmark(업계 표준 보안 벤치마크, "docker 그룹 멤버는
   사실상 root 권한을 얻는다" / "신뢰할 수 있는 사용자만 docker 그룹에 넣어라")가 동일하게
   최소 권한 원칙 위반으로 명시함. 완전한 해결책(Docker rootless mode)은 이미 떠있는 프로덕션급
   스택 재설치가 필요해 이 시점엔 과함. **원래 취지가 순수 편의였고 실무 표준에 안 맞는다는 근거를
   확인한 뒤, 사용자가 이 항목을 넘기기로 결정** — sudo(비밀번호 입력)는 그대로 유지.
7. ~~self-hosted GitHub Actions runner를 harbor VM에 설치~~ **완료(2026-07-12)** —
   `~/actions-runner`에 v2.335.1 설치, 이름 `harbor-runner`, 라벨 `self-hosted,harbor`, 등록 토큰은
   저장소 소유자(`love-1006`, Admin 권한)가 웹 UI에서 발급(러너 등록 API/UI는 Admin 권한 필요,
   Write 권한으로는 403 — GitHub 공식 문서로 확인함). 공식 `svc.sh install/start`로 systemd 서비스
   등록(`enabled`, bruce 계정으로 실행) → 재부팅 시 자동 기동됨. 워크플로에서 `runs-on: self-hosted`
   또는 `runs-on: [self-hosted, harbor]`로 사용 가능.
8. VM 쪽 별도 보안 항목(Claude Code 범위 밖, 여전히 미완료): bruce 계정 영구 비밀번호로 재변경
   (이번에 임시로 리셋한 값 말고 강한 값으로)

## 6. 아직 하나도 안 건드린 것

- Lane 2 (CD): `deploy trigger → docker pull → Docker Compose → SUCCESS/rollback`
  (`Jhoon/ci-cd/docker-deploy-pipeline` 브랜치, main과 미동기화)
- Rollback 커스텀 스크립트 (`Jhoon/ci-cd/rollback-config`)
- `.env` 템플릿 + pydantic Settings 표준 코드 (`Jhoon/secops/pydantic-settings`, `env-gitignore-template`)
