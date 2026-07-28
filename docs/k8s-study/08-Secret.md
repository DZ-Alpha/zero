# Secret

## 🟡 무엇인가
- **한 줄 정의**: Secret은 비밀번호·API 키·토큰·TLS 인증서 같은 민감한 소량 데이터를 파드와 분리해 저장·주입하는 쿠버네티스 오브젝트다.
- **핵심 개념**:
  - **base64는 암호화가 아니다**: `data` 값은 인코딩일 뿐 누구나 디코드 가능 — 기밀성 제공 X. 평문 입력은 `stringData`(API 서버가 인코딩).
  - **기본값으로 etcd에 비암호화 저장**: 진짜 보호는 **Encryption at Rest**(AES 또는 KMS 프로바이더)를 명시적으로 켜야 한다.
  - **타입(type)**: `Opaque`(기본), `kubernetes.io/dockerconfigjson`(imagePullSecrets), `kubernetes.io/tls`(tls.crt/tls.key) 등 — 어떤 키가 들어야 하는지의 약속.
  - **소비 방식 2가지**: 환경변수(재시작 전까지 고정) vs 볼륨 파일 마운트(갱신 반영 가능, tmpfs 메모리에 올라감).
  - **크기 제한 1MiB**, 실질 보안은 **RBAC 최소권한 + 네임스페이스 격리 + etcd 암호화**의 조합.
- **공식문서**:
  - <https://kubernetes.io/docs/concepts/configuration/secret/> — 타입 목록, data/stringData, "기본적으로 etcd에 암호화되지 않음", 소비 방식.
  - <https://kubernetes.io/docs/concepts/security/secrets-good-practices/> — base64 ≠ 암호화, RBAC 최소권한·저장 시 암호화 권고.
- **면접 포인트**:
  - Q. Secret에 넣으면 암호화되나? → 아니다. base64 인코딩일 뿐이고 etcd에도 평문 저장. 암호화는 관리자가 Encryption at Rest를 켜야 적용. "자동 암호화된다"고 답하면 감점.
  - Q. ConfigMap과의 진짜 차이는? → API 구조는 거의 같고 의미(민감/비민감)와 취급이 다르다. 필요한 노드에만 전달, tmpfs 마운트 등 노출 표면을 줄이지만 "자동으로 안전"은 아니다.
  - Q. `data` vs `stringData`? → data는 base64로 넣고, stringData는 평문으로 넣으면 서버가 인코딩해 data로 합쳐진다. 편의 차이일 뿐 보안 차이 없음. (오해: imagePullSecret은 Opaque가 아니라 dockerconfigjson 타입이어야 kubelet이 인식.)

## 🟡 왜 우리 서비스에서?
- 우리 시크릿 설계는 **2계층 + 최후방어선**: Git 부트스트랩은 Sealed Secrets(문서 14), 런타임 동적 발급은 Vault(PoC), 최종 저장은 **etcd Encryption at Rest**. 어떤 계층이든 파드에 넘겨지는 최종 형태는 표준 K8s Secret이라 etcd 평문 저장을 막아야 한다.
- 타입별 용도: `dockerconfigjson`은 앱 네임스페이스(`dang-be-ns`, `dang-fe-ns`, `dang-ai-ns`)의 Harbor 레지스트리 imagePullSecrets, `tls`는 cert-manager(`dang-cert-manager-ns`)가 자동갱신하는 인증서 그릇, DB 비밀번호·API 키는 `Opaque`(`dang-db-ns` 등).
- RBAC 최소권한으로 "각 SA는 자기 네임스페이스 Secret만" 읽게 제한 + NetworkPolicy default-deny 3계층(fe→be→db)으로 유출 경로 차단.
- `dang-db-ns`는 PSA `baseline`으로 완화한 곳이라 DB 계정 Secret의 RBAC·etcd 암호화가 더 중요.
- 결론: Secret은 모든 시크릿 계층의 종착지 — Sealed Secrets는 봉인, Vault는 발급소, etcd 암호화는 자물쇠.
