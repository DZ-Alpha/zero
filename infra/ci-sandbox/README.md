# ci-sandbox 배포 (harbor VM 내부, Harbor와 분리된 별도 스택)

Harbor(레지스트리)와 ci-sandbox(애플리케이션)는 라이프사이클과 장애 영향 범위가
다르므로 같은 compose 스택에 두지 않고 별도 디렉토리/프로젝트로 분리한다.
포트도 Harbor(80/443)와 겹치지 않게 8080을 사용한다.

## 실행

```bash
cd infra/ci-sandbox
IMAGE_TAG=<git-sha> docker compose up -d
```

기동 후 `http://harbor.hizero.local:8080/health`로 확인.

CI 파이프라인의 `deploy` job([build-test.yml](../../.github/workflows/build-test.yml))이
`image-push` 성공 후 harbor VM(self-hosted runner)에서 이미지를 pull하고, `docker compose up`으로
배포한 뒤 `/health`를 헬스체크한다. 헬스체크 실패 시 직전 정상 태그(`~/ci-sandbox-state/last-good-tag`)로
자동 롤백한다.

## 수동 롤백

자동 롤백과는 별개로, 사람이 SSH로 직접 특정 태그로 되돌리고 싶을 때는
[scripts/rollback.sh](../../scripts/rollback.sh)를 사용한다.

```bash
# 인자 없이: 마지막 정상 태그로 롤백
scripts/rollback.sh

# 특정 태그로 롤백
scripts/rollback.sh <git-sha>
```
