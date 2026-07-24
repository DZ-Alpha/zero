# syntax=docker/dockerfile:1.7
# frontend/Dockerfile과 동일 베이스 이미지 digest 고정 — Trivy CRITICAL/HIGH 0으로
# 이미 검증된 조합이라 그대로 재사용한다(CI/CD 팀 권고, cicd/frontend-admin-pipeline).
FROM node:22.15.0-bookworm-slim@sha256:557e52a0fcb928ee113df7e1fb5d4f60c1341dbda53f55e3d815ca10807efdce AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

FROM node:22.15.0-bookworm-slim@sha256:557e52a0fcb928ee113df7e1fb5d4f60c1341dbda53f55e3d815ca10807efdce AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* 값은 런타임 env가 아니라 빌드 시점에 번들에 박힌다 — compose의
# environment로 나중에 넣어봐야 소용없다. 로그인 캡차 위젯(TurnstileWidget.tsx)이
# 이 값을 쓴다 — CI가 이미지 빌드할 때 --build-arg로 넘겨줘야 한다.
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY
ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN --mount=type=cache,target=/app/.next/cache npm run build

FROM node:22.15.0-alpine3.21 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# 컨테이너 내부 포트는 frontend와 동일하게 3000으로 고정한다 — 외부 공개 포트는
# 이 서비스가 정하지 않는다(호스트 publish는 배포 override 파일의 책임, 여기서는
# expose만 한다. compose.production.example.yaml 참고).
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN apk upgrade --no-cache \
  && rm -rf /usr/local/lib/node_modules/npm \
  && rm -f /usr/local/bin/npm /usr/local/bin/npx \
  && chown -R node:node /app

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

USER node
EXPOSE 3000
# 배포 검증 스크립트가 docker exec ... node -e ... 로 헬스체크를 겸하므로
# node 바이너리는 지우지 않는다(npm/npx만 제거, 위 참고).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]
CMD ["node", "server.js"]
