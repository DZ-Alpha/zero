# 당당 사용자 프론트엔드

이 디렉터리는 `sungA/front/main` 소유의 Next.js 사용자 프론트엔드입니다. 관리자 프론트엔드(`sungA/front/admin`), 백엔드, DB, CI/CD 소유 파일은 포함하지 않습니다.

## 로컬 실행

필수 버전은 Node.js 22.15.0, npm 10.9.2입니다. PowerShell 실행 정책으로 `npm.ps1`이 막히면 `npm.cmd`를 사용합니다.

```powershell
cd frontend
npm.cmd ci
npm.cmd run typecheck
npm.cmd run dev -- -p 3001
```

브라우저는 `http://localhost:3001`을 열면 됩니다. LAN 게이트웨이와 테스트할 때는 `.env.example`을 참고해 `.env.local`에 `BACKEND_GATEWAY_URL`을 지정합니다. `.env.local`은 커밋하지 않습니다.

## 같은 서버 Docker 배포

Docker 이미지는 백엔드 주소를 포함하지 않습니다. 동일 이미지를 환경마다 재사용하고 배포 시 아래 두 값만 주입합니다.

```dotenv
BACKEND_GATEWAY_URL=http://b-gateway:8080
PUBLIC_APP_URL=https://서비스도메인
```

브라우저는 항상 프론트와 같은 출처의 `/b/*`를 호출합니다. Next.js 서버가 같은 Docker 네트워크의 `b-gateway:8080/b/*`로 전달하므로 백엔드 서비스 포트를 외부에 공개할 필요가 없습니다.

`b-gateway`와 프론트는 동일한 사용자 정의 네트워크(기본 이름 `dangdang-edge`)에 연결돼야 합니다. 지금처럼 게이트웨이를 `--network host`로 따로 실행하는 방식은 LAN 확인용으로만 두고, 통합 배포에서는 게이트웨이도 Compose 서비스로 옮겨 서비스 이름 `b-gateway`를 사용할 것을 권장합니다.

- 로컬/LAN 예시: `compose.frontend.yaml`
- 운영 통합 예시: `compose.production.example.yaml`
- 헬스체크: `GET /api/health`
- 컨테이너 내부 포트: `3000`
- 운영 외부 공개 포트: edge proxy의 `80/443`만 사용

## CI/CD 담당자 인수 조건

프론트 소유 브랜치의 소스와 Dockerfile은 여기까지 제공합니다. 기존 CI/CD 워크플로 파일은 담당자 소유이므로 이 브랜치에서 수정하지 않습니다.

1. 작업 디렉터리를 `frontend`로 설정합니다.
2. Node.js 22.15.0과 npm 10.9.2로 `npm ci`, `npm run typecheck`, `npm run build`를 실행합니다.
3. Docker 빌드 컨텍스트는 `frontend`, Dockerfile은 `frontend/Dockerfile`입니다.
4. 이미지는 예를 들어 `harbor.hizero.local/dangdang/frontend:<git-sha>`처럼 변경 불가능한 태그로 올립니다.
5. Trivy 스캔을 통과한 이미지만 배포하고, 배포 Compose의 `FRONTEND_IMAGE`에 그 태그 또는 digest를 주입합니다.
6. 배포 후 `/api/health`와 브라우저의 `/b/search?page=1`을 확인합니다.

상세 API 연동 현황과 남은 백엔드 계약은 `docs/PRODUCTION_HANDOFF.md`를 참고합니다.
