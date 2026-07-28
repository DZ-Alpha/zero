# SealedSecret (Bitnami Sealed Secrets)

## 🟡 무엇인가

- **한 줄 정의**: 일반 Secret을 **공개키로 암호화(봉인)** 해 Git에 안전하게 커밋하게 만드는 CRD로, 클러스터 안의 컨트롤러(개인키)만 복호화해 진짜 Secret으로 되돌린다.

- **핵심 개념**:
  - **공개키 암호로 Git 커밋**: `kubeseal`이 클러스터 공개키로 암호화 → SealedSecret은 공개 저장소에 올려도 안전. GitOps의 단일 진실 소스를 시크릿까지 확장.
  - **컨트롤러만 복호화**: 개인키(sealing key)는 클러스터를 절대 벗어나지 않음. "대상 클러스터의 컨트롤러만 복호화할 수 있고 원저작자조차 못 한다." (비유 1줄: 넣기는 누구나, 꺼내는 열쇠는 주인 하나뿐인 우편함)
  - **봉인 스코프 3종**: `strict`(기본, 이름+네임스페이스 고정) / `namespace-wide` / `cluster-wide`. 느슨할수록 편하지만 격리가 무너진다 — 기본 `strict` 유지.
  - **sealing key 유실 = 영구 복호화 불가**: 백업이 생명줄. `kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > main.key` 후 클러스터 밖 안전한 곳에 보관.
  - **오프라인 복구**: 백업 키가 있으면 `kubeseal --recovery-unseal --recovery-private-key main.key`로 클러스터 없이도 복호화 가능(재해 복구 안전망).
  - **키 자동 갱신(기본 30일)**: 새 키는 신규 봉인에만 쓰이고 구 키는 보존 → 백업 대상은 "최신 하나"가 아니라 축적된 키 전체.

- **공식문서**:
  - <https://github.com/bitnami/sealed-secrets> — 프로젝트 정의: 비대칭 암호, 오직 컨트롤러만 복호화.
  - <https://github.com/bitnami/sealed-secrets/blob/main/README.md> — 스코프 3종, 키 백업/오프라인 복구, 30일 키 갱신.

- **면접 포인트**:
  - **Q. SealedSecret 쓰면 etcd 암호화는 불필요?** → A. 아니다. 컨트롤러가 풀면 결국 평범한 Secret이 etcd에 남는다. SealedSecret은 "Git 이동/저장" 보호, etcd Encryption at Rest는 "런타임 저장" 보호 — 서로 대체 불가.
  - **Q. 다른 클러스터에 그대로 복사 가능?** → A. 못 한다. 그 클러스터 공개키로 봉인돼 있어 짝 개인키가 없으면 복호화 불가. 키 이관 또는 재봉인 필요.
  - **Q. 가장 위험한 운영 실수는?** → A. sealing key 미백업. 클러스터가 날아가면 Git의 모든 SealedSecret이 복호화 불가능한 쓰레기가 된다.

## 🟡 왜 우리 서비스에서?

- 당당 시크릿은 **2계층(부트스트랩+런타임)+최후방어선** 설계 — SealedSecret이 **GitOps 부트스트랩 계층** 담당, 컨트롤러는 `dang-sealed-secrets-ns`에 배포.
- DB 초기 비밀번호·Harbor 자격증명 같은 부트스트랩 시크릿을 봉인해 Git에 커밋 → 클러스터 재구축 시 `dang-be-ns`·`dang-db-ns` 등에 표준 Secret으로 복원.
- **Vault와 분담**: SealedSecret = 정적·선언적 부트스트랩, Vault = 런타임 동적 발급. Vault 자체의 최초 자격증명("닭-달걀") 문제도 SealedSecret이 끊어준다. Vault는 물리 3호스트 부재로 replica 1 PoC라, 정적 시크릿은 SealedSecret이 실질 주력.
- **sealing key 백업이 최우선 운영 과제**: 물리 2호스트(master×3/worker×5)라 재구축 시나리오가 현실적 — 키를 클러스터 밖에 백업하고 `--recovery-unseal` 절차를 잡는다.
- 스코프는 기본 `strict` 유지(네임스페이스 격리·NetworkPolicy·PSA·RBAC과 일관), etcd 암호화는 생략하지 않고 **직렬로 겹치는 방어선**으로 유지.
