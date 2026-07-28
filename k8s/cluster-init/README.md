# 클러스터 초기화 — 보안 설정 3종

> 김지훈(보안·모니터링) · 2026-07-27
> **`kubeadm init` 실행 전에 마스터 노드에 배치해야 하는 파일들입니다.**

---

## 왜 지금 해야 하나

이 3개는 전부 **kube-apiserver 기동 옵션**입니다. `init` 이후에 넣으려면:

| | 지금 (init 전) | 나중에 |
| --- | --- | --- |
| etcd 암호화 | 파일 배치 + init | API 서버 재시작 + **기존 Secret 전량 재작성** |
| PSA 기본값 | 동일 | API 서버 재시작 |
| 감사 로그 | 동일 | API 서버 재시작 |
| **소요** | **약 10분** | **반나절** |

etcd 암호화는 **소급 적용이 안 됩니다.** 켜기 전에 저장된 Secret은 계속 평문으로 남고, 전부 다시 써야 암호화됩니다. 아직 Secret이 하나도 없는 지금이 가장 쌉니다.

---

## 파일 3개

| 파일 | Git 추적 | 이유 |
| --- | --- | --- |
| `admission-config.yaml` | ✅ | 비밀 없음 |
| `audit-policy.yaml` | ✅ | 비밀 없음 |
| `kubeadm-config.yaml` | ✅ | 경로만 있음 |
| **`encryption-config.yaml`** | ❌ **금지** | **암호화 키가 들어갑니다.** 아래 3번에서 마스터 노드에서 직접 생성합니다 |

---

## 실행 순서 (마스터 노드에서)

### 1. 디렉터리 생성
```bash
sudo mkdir -p /etc/kubernetes/enc \
              /etc/kubernetes/admission \
              /etc/kubernetes/audit \
              /var/log/kubernetes/audit
```

### 2. 설정 파일 배치
```bash
sudo cp admission-config.yaml /etc/kubernetes/admission/
sudo cp audit-policy.yaml     /etc/kubernetes/audit/
```

### 3. 암호화 키 생성 + 설정 작성 ⚠️ 이 파일만 Git에 올리지 않습니다

```bash
# 32바이트 랜덤 키 생성 (aescbc는 정확히 32바이트를 요구 — 공식 API 문서)
KEY=$(head -c 32 /dev/urandom | base64)

sudo tee /etc/kubernetes/enc/encryption-config.yaml > /dev/null <<EOF
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      # 목록의 첫 번째 provider로 암호화한다.
      # 복호화는 목록 전체를 순회하므로, 나중에 키를 교체할 때
      # 새 키를 맨 앞에 추가하고 옛 키는 뒤에 남겨두면 무중단으로 전환된다.
      - aescbc:
          keys:
            - name: key1
              secret: ${KEY}
      # identity는 "암호화 안 함"이다. 맨 뒤에 둬야 한다.
      # 맨 앞에 두면 새 값이 평문으로 저장된다.
      - identity: {}
EOF

sudo chmod 600 /etc/kubernetes/enc/encryption-config.yaml
unset KEY
```

> **키를 백업하세요.** 이 키를 잃으면 etcd에 암호화된 Secret을 **영영 복호화할 수 없습니다.**
> `harbor.credentials.local.md`(gitignore됨)에 기록해 두세요.

**provider 선택 근거**: 공식 API 문서의 `EncryptionConfiguration` 예제가 `aescbc`를 쓰고, 키 길이를 "AES-CBC는 정확히 32바이트"로 명시합니다. 운영 환경에서는 **KMS v2**(외부 키 관리)가 권장되지만, 외부 KMS가 없는 온프레미스라 로컬 provider를 씁니다.

> ⚠️ **한계를 알고 씁니다**: 로컬 provider는 키가 **마스터 노드 파일시스템에 평문으로** 존재합니다.
> 즉 **마스터 노드가 뚫리면 암호화 의미가 크게 줄어듭니다.** etcd 스냅샷·백업 파일 유출은 막지만,
> 노드 침해는 막지 못합니다. 발표에서 이 한계를 명시할 것.

### 4. kubeadm 설정 채우기

`kubeadm-config.yaml`에 `⬅ 결정 필요` 표시가 **3곳** 있습니다.

| 칸 | 정해야 할 것 |
| --- | --- |
| `kubernetesVersion` | 설치할 버전. cert-manager·Prometheus Operator·CNI 지원 범위를 먼저 확인 |
| `controlPlaneEndpoint` | 마스터 IP. 마스터 1대여도 지금 넣어두면 나중에 늘릴 때 인증서를 다시 안 만들어도 됨 |
| `admission-config.yaml`의 `-version` 3곳 | 위 버전과 동일하게. `latest`로 두면 업그레이드 시 정책 판정이 조용히 바뀜 |

### 5. 초기화
```bash
sudo kubeadm init --config kubeadm-config.yaml
```

---

## 🔴 podSubnet 겹침 주의

`kubeadm-config.yaml`에서 **가장 위험한 칸**입니다.

우리가 이미 쓰는 대역:
```
192.168.0.0/24   관리망  (harbor .53 / monitoring .51 / DB .54)
10.10.10.0/24    App망   (production 10.10.10.30)
10.10.20.0/24    Data망  (DB 10.10.20.10)
```

> ⚠️ **Calico의 기본 `podSubnet`은 `192.168.0.0/16`이라 우리 관리망과 정면으로 겹칩니다.**
> 기본값으로 깔면 파드에서 harbor·monitoring VM으로 가는 통신이 **원인 불명으로 깨집니다.**
> 이건 나중에 고치려면 **클러스터를 다시 세워야** 합니다.

→ `10.244.0.0/16`으로 명시합니다. 위 세 대역 어디와도 겹치지 않습니다.
→ CNI를 설치할 때도 **같은 대역**을 지정해야 합니다. 두 값이 다르면 파드 네트워크가 동작하지 않습니다.

---

## 검증 (init 직후)

### ① 감사 로그가 쌓이는가
```bash
sudo ls -l /var/log/kubernetes/audit/audit.log
sudo tail -3 /var/log/kubernetes/audit/audit.log
```

### ② PSA 기본값이 먹는가
라벨 없는 네임스페이스에 privileged 파드를 만들어 봅니다. **거부되면 정상**입니다.
```bash
kubectl create ns psa-test
kubectl -n psa-test run bad --image=nginx --privileged
# 예상: Error ... violates PodSecurity "baseline:v1.__"
kubectl delete ns psa-test
```

### ③ etcd 암호화가 먹는가 — 가장 확실한 검증
```bash
kubectl -n default create secret generic enc-test --from-literal=pw=hello

sudo ETCDCTL_API=3 etcdctl \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  get /registry/secrets/default/enc-test | hexdump -C | head -5
```
- ✅ `k8s:enc:aescbc:v1:key1` 로 시작하면 **암호화됨**
- ❌ `hello`가 그대로 보이면 **암호화 안 됨** → 3번 파일 경로·볼륨 마운트 확인

```bash
kubectl -n default delete secret enc-test
```

---

## 이 다음에 할 것

| 순서 | 작업 | 담당 |
| --- | --- | --- |
| 1 | **CNI 설치** (`podSubnet` 일치 확인) | 구축 팀 |
| 2 | etcd 스냅샷 CronJob | 지훈 (보안) |
| 3 | 네임스페이스 + PSA 라벨 (명시적 restricted) | 지훈 |
| 4 | ResourceQuota / LimitRange | 지훈 |
| 5 | ServiceAccount + RBAC | 지훈 |

> **마스터 1대 구성**이라 etcd 백업이 **유일한 복구 수단**입니다.
> 공식 문서: *"컨트롤플레인 노드가 고장나면 클러스터가 데이터를 잃고 처음부터 재생성해야 할 수 있다."*
> 2번을 미루지 않습니다.
