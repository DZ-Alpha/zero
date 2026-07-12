# SonarQube (harbor VM 내부 호스팅)

Community Build를 harbor VM에 직접 컨테이너로 띄우기 위한 설정. SonarCloud(외부 SaaS)는
라인코드 제한(5만 LoC 무료)과 향후 유료 전환 리스크 때문에 채택하지 않고, 자체 호스팅으로 결정함.

## 1. 실행 전 호스트(harbor VM) 커널 설정 (필수, 최초 1회)

SonarQube는 내장 Elasticsearch를 쓰기 때문에 아래 값이 안 맞으면 기동에 실패한다.
(출처: SonarQube Community Build 공식 문서 - Linux pre-installation steps)

```bash
sudo tee /etc/sysctl.d/99-sonarqube.conf <<'EOF'
vm.max_map_count=524288
fs.file-max=131072
EOF
sudo sysctl --system
```

## 2. 실행

```bash
cd infra/sonarqube
cp .env.example .env   # SONARQUBE_DB_PASSWORD를 실제 값으로 변경
docker compose up -d
```

기동 후 `http://harbor.hizero.local:9000` (또는 `http://192.168.0.53:9000`)으로 접속 확인.
최초 로그인 계정은 `admin`/`admin`이며, 로그인 즉시 비밀번호 변경 필수.

## 3. GitHub Actions 연동에 필요한 값

- `SONAR_HOST_URL`: 위 접속 주소 (예: `http://192.168.0.53:9000`) — 저장소 Variables에 등록
- `SONAR_TOKEN`: SonarQube 관리자 페이지 > My Account > Security 에서 발급한 토큰 — 저장소 Secrets에 등록
