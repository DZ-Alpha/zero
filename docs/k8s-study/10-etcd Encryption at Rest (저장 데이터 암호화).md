# etcd Encryption at Rest (저장 데이터 암호화)

## 🟡 무엇인가

- **한 줄 정의**: kube-apiserver가 Secret 등을 **etcd에 쓰기 전에 암호화**하도록 하는 컨트롤플레인 설정(`EncryptionConfiguration`)으로, 없으면 etcd 스냅샷 하나가 곧 전체 시크릿 유출이다.

- **핵심 개념**:
  - **base64 ≠ 암호화**: 공식 문서 그대로 "apiserver는 기본적으로 리소스의 평문 표현을 etcd에 저장하며, at-rest 암호화가 없다." etcd 파일/백업을 얻은 사람은 모든 Secret을 그대로 읽는다.
  - **구조**: `resources`(무엇을: `secrets`, `configmaps`, 1.27+ 와일드카드) + `providers`(어떻게) 목록. `--encryption-provider-config`로 apiserver에 전달.
  - **프로바이더**: `identity`(평문) / `aescbc` / `aesgcm` / `secretbox` / `kms`(외부 KMS v1/v2, DEK 봉투암호화로 키를 클러스터 밖에 분리).
  - **순서가 핵심**: 목록의 **첫 프로바이더만 새 쓰기를 암호화**, 복호화는 순서대로 전부 시도. `identity`가 맨 앞이면 암호화 꺼진 것. 키 회전 = 새 키 맨 앞 추가 → 재시작 → 전체 재암호화 → 옛 키 제거.
  - **로컬 키의 한계**: `aescbc` 등은 키가 설정 파일째 마스터 노드에 있음 → 노드 root 탈취엔 무력. 진짜 분리는 KMS(v2 권장).
  - **소급 적용 안 됨 + 검증**: 켜도 기존 Secret은 그대로 — `kubectl get secrets -A -o yaml | kubectl replace -f -`로 재기록 후 `etcdctl ... | hexdump`로 `k8s:enc:aescbc:v1:` 접두어 실측 검증.

- **공식문서**:
  - https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/ — 기본은 평문 저장, 프로바이더 순서 규칙, `identity`=암호화 없음.
  - https://kubernetes.io/docs/concepts/configuration/secret/ — Secret은 base64일 뿐이니 etcd 암호화를 반드시 활성화하라.

- **면접 포인트**:
  - **Q. Secret은 암호화되어 저장되나?** → A. 아니다. base64 인코딩일 뿐 etcd에 평문으로 들어간다. `EncryptionConfiguration`을 명시적으로 켜야 한다.
  - **Q. 설정만 켜면 기존 시크릿도 안전한가?** → A. 아니다. 소급 적용이 안 되므로 전부 재기록(rewrite)해야 실제 암호화된다.
  - **Q. etcd 암호화가 있으면 RBAC은 불필요?** → A. 다른 층이다. etcd 암호화는 at-rest(디스크/백업) 유출 방어, RBAC은 API 접근 방어 — API로 조회하면 apiserver가 복호화해 주므로 RBAC 없으면 여전히 샌다.

## 🟡 왜 우리 서비스에서?

- 당당 시크릿 **3계층 방어**의 최후 방어선: ① Sealed Secrets(GitOps 부트스트랩) ② Vault PoC(런타임 주입) ③ **etcd Encryption at Rest**. 앞 두 층을 통과한 값도 결국 etcd에 평문 Secret으로 남는다(언실링된 DB 크리덴셜, cert-manager TLS Secret, 레거시 SA 토큰 등).
- 안 켜면 `dang-db-ns` DB 자격증명·Grafana admin·Slack webhook이 담긴 **etcd 스냅샷 하나 = 전체 유출**. 백업 정책과 직결 — 켜면 백업 파일 자체가 암호문.
- **master×3 HA 주의점**: 세 마스터의 `EncryptionConfiguration`이 완전히 동일해야 한다. 키 불일치로 못 읽는 리소스는 etcd에서 직접 지우는 것 외 복구 수단이 없다(공식 경고).
- 외부 KMS 없는 PoC 환경이라 우선 로컬 프로바이더로 "백업·디스크 유출"까지 방어 — 단 공식 문서상 `aescbc`는 padding oracle 취약성으로 비권장이므로 `secretbox`(또는 `aesgcm`) 우선. 키가 마스터 노드에 있다는 한계는 문서에 명시하고 프로덕션 승격 시 KMS 전환을 다음 과제로.
- 리스크 지점은 켜기가 아니라 **검증·키 관리**: (1) 마스터 간 설정 불일치→읽기 장애 (2) 키 유실→복구 불가 (3) 기존 Secret 미재기록 착각. live 컨트롤플레인 작업이므로 리스크 제시→승인→재기록→`etcdctl` 실측 검증을 한 세트로 진행.
