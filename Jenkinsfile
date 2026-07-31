pipeline {
    agent any
    environment {
        REGISTRY = 'harbor.hizero.local'
        PROJECT  = 'dangdang-backend'
        // DAST 스캔 대상 워커 노드 IP 목록. NodePort는 모든 노드에 열리므로 살아있는 아무 노드나 OK.
        // 스페이스 구분: 게이트에서 순회하며 먼저 도달되는 노드로 스캔(노드 1개 장애 견딤).
        NODE_IPS = '192.168.0.71 192.168.0.72 192.168.0.73 192.168.0.75'
    }
    stages {
        // Checkout stage 없음 — "Pipeline script from SCM"이 zero repo를 자동 체크아웃.
        // 그 덕에 GIT_PREVIOUS_COMMIT(직전 빌드가 처리한 커밋)이 채워진다.

        stage('Detect Changes') {
            steps {
                script {
                    def all = ['admin-service','ai','community-service','diet-service',
                               'ingredients-service','login-service','main-service',
                               'product-service','recipe-service']
                    // 직전 빌드(성공/실패 무관)가 처리한 커밋 기준으로 diff.
                    // GIT_PREVIOUS_SUCCESSFUL_COMMIT(마지막 성공)을 쓰면 UNSTABLE이 누적될 때
                    // 기준점이 갱신 안 돼, 실패한 남의 서비스가 매 빌드에 계속 딸려온다.
                    // GIT_PREVIOUS_COMMIT은 매 빌드마다 갱신되므로 각 빌드가 "직전 빌드 이후
                    // 실제 바뀐 서비스"만 처리한다(여러 push가 한 빌드에 묶여도 그 범위는 다 봄).
                    def prev = env.GIT_PREVIOUS_COMMIT
                    def changed

                    if (!prev) {
                        echo "직전 빌드 커밋 없음(첫 빌드) — 전체 빌드"
                        changed = all
                    } else {
                        def prevExists = sh(script: "git cat-file -e ${prev}^{commit} 2>/dev/null && echo yes || echo no",
                                            returnStdout: true).trim()
                        if (prevExists != 'yes') {
                            echo "이전 커밋(${prev})이 히스토리에 없음 — 안전하게 전체 빌드"
                            changed = all
                        } else {
                            def status = sh(script: "git diff --name-only ${prev} HEAD > /tmp/diff.txt; echo \$?",
                                            returnStdout: true).trim()
                            if (status != '0') {
                                echo "git diff 실패(exit ${status}) — 안전하게 전체 빌드"
                                changed = all
                            } else {
                                def raw = readFile('/tmp/diff.txt').trim()
                                def rawFiles = raw ? raw.split('\n') : []
                                // 문서·비코드 파일 제외: 이런 파일만 바뀐 서비스는 빌드/스캔/승격 안 함.
                                // (파일 단위로 거름 — 코드+문서 동시 변경이면 코드가 남아 빌드는 됨)
                                def isDoc = { String f ->
                                    def lower = f.toLowerCase()
                                    // requirements.txt는 .txt지만 의존성 명세(코드/보안) — 문서 제외 안 함.
                                    // (CVE 패치가 requirements.txt만 바꾸는데 문서로 오판돼 빌드 스킵→초록불 방지)
                                    if (lower.tokenize('/').last() == 'requirements.txt') { return false }
                                    lower.endsWith('.md') || lower.endsWith('.txt') ||
                                    lower.endsWith('license') || lower.endsWith('.gitignore')
                                }
                                def files = rawFiles.findAll { !isDoc(it) }
                                def skipped = rawFiles.findAll { isDoc(it) }
                                if (skipped) { echo "문서·비코드 변경 무시: ${skipped.join(', ')}" }
                                changed = all.findAll { svc -> files.any { it.startsWith("backend/${svc}/") } }
                            }
                        }
                    }

                    env.CHANGED = changed.join(' ')
                    echo "빌드 대상: ${env.CHANGED ?: '(없음 — 서비스 변경 없음)'}"
                    // 이 job 소관(백엔드 서비스) 변경이 하나도 없으면 = 다른 커밋에 딸려 뜬 빌드.
                    // Poll SCM은 경로 필터가 없어 job은 뜨지만, 여기서 NOT_BUILT로 조용히 끝내고
                    // Slack 알림도 스킵한다(post에서 NOOP 플래그 확인). 빌드 correctness는 이미
                    // when 가드로 보장됨 — 이건 노이즈 제거용 표시일 뿐(변경감지 로직은 그대로).
                    if (!env.CHANGED?.trim()) {
                        env.PIPELINE_NOOP = 'true'
                        currentBuild.result = 'NOT_BUILT'
                        echo "백엔드 변경 없음 — NOT_BUILT로 종료(알림 스킵)"
                    }
                }
            }
        }

        stage('Build Changed Services') {
            when { expression { env.CHANGED?.trim() } }
            steps {
                script {
                    def scannerHome = tool 'sonar-scanner'
                    // 서비스별 독립 빌드: 한 서비스가 품질/취약점 게이트에 걸려도 다른 서비스는
                    // 계속 빌드·승격한다(마이크로서비스 원칙). 실패한 서비스는 push/manifest/승격을
                    // 건너뛰고, 빌드 전체는 UNSTABLE로 표시. (기존엔 abortPipeline:true라 한 서비스
                    // 실패가 전체를 중단 → 남의 서비스 배포를 볼모로 잡았음.)
                    def failedSvcs = []
                    def okSvcs = []
                    for (svc in env.CHANGED.split(' ')) {
                        env.SVC = svc
                        echo "========== [${svc}] 빌드 시작 =========="
                        // catchError: 이 서비스 블록이 실패해도 파이프라인은 계속(빌드는 UNSTABLE 표시).
                        catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE', message: "${svc} 빌드 실패") {
                            // 1) SonarQube (서비스별 projectKey)
                            withSonarQubeEnv('sonarqube') {
                                sh '''
                                    "''' + scannerHome + '''/bin/sonar-scanner" \
                                        -Dsonar.projectKey=zero-${SVC} \
                                        -Dsonar.projectName=zero-${SVC} \
                                        -Dsonar.sources=backend/${SVC}
                                '''
                            }
                            // 품질 게이트: abortPipeline:false로 결과만 받아, ERROR면 이 서비스만 실패 처리.
                            def qg
                            timeout(time: 5, unit: 'MINUTES') {
                                qg = waitForQualityGate abortPipeline: false
                            }
                            if (qg.status != 'OK') {
                                error("SonarQube 품질 게이트 실패(${qg.status}) — ${svc}")
                            }

                            // 2) Build + Trivy
                            sh '''
                                SHA=$(git rev-parse --short HEAD)
                                docker build -t backend-${SVC}:${SHA} backend/${SVC}
                                trivy image --severity CRITICAL,HIGH --exit-code 1 \
                                    --ignorefile .trivyignore --scanners vuln --quiet backend-${SVC}:${SHA}
                            '''

                            // 3) Harbor push
                            withCredentials([usernamePassword(credentialsId: 'harbor-cred',
                                    usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_TOKEN')]) {
                                sh '''
                                    SHA=$(git rev-parse --short HEAD)
                                    IMAGE=${REGISTRY}/${PROJECT}/${SVC}
                                    echo "${HARBOR_TOKEN}" | docker login ${REGISTRY} -u "${HARBOR_USER}" --password-stdin
                                    docker tag backend-${SVC}:${SHA} ${IMAGE}:${SHA}
                                    docker push ${IMAGE}:${SHA}
                                    docker logout ${REGISTRY}
                                    echo "push 완료: ${IMAGE}:${SHA}"
                                '''
                            }

                            // 4) Update Manifest
                            withCredentials([usernamePassword(credentialsId: 'manifest-git-pat',
                                    usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PAT')]) {
                                sh '''
                                    set -e
                                    SHA=$(git rev-parse --short HEAD)
                                    WORK=$(mktemp -d)
                                    git clone --depth 1 "https://${GIT_USER}:${GIT_PAT}@github.com/DZ-Alpha/zero-manifests.git" "$WORK"
                                    cd "$WORK"
                                    git config user.name  "jenkins-ci"
                                    git config user.email "ci@hizero.local"
                                    yq -i ".image.tag = \\"${SHA}\\"" charts/${SVC}/values-staging.yaml
                                    if git diff --quiet; then
                                        echo "태그 변경 없음 (${SVC} ${SHA}) — skip"
                                    else
                                        git commit -am "chore(${SVC}): update staging image tag to ${SHA} [skip ci]"
                                        git push origin main
                                        echo "manifest 갱신: ${SVC} tag=${SHA}"
                                    fi
                                    cd / && rm -rf "$WORK"
                                '''
                            }
                            okSvcs << svc   // 여기 도달 = 이 서비스 빌드·push 성공
                            echo "========== [${svc}] 완료 =========="
                        }
                        // catchError 블록 밖: 실패해도 여기 도달. ok에 없으면 실패로 기록.
                        if (!okSvcs.contains(svc)) { failedSvcs << svc }
                    }
                    // 승격 단계가 성공 서비스만 대상으로 하도록 CHANGED를 재설정.
                    env.CHANGED = okSvcs.join(' ')
                    // Slack 알림(post{})에서 쓰도록 성공/실패 서비스 목록을 env로 노출.
                    env.OK_SVCS = okSvcs.join(', ')
                    env.FAILED_SVCS = failedSvcs.join(', ')
                    echo "빌드 성공(승격 대상): ${okSvcs.join(', ') ?: '(없음)'}"
                    if (failedSvcs) { echo "빌드 실패(승격 제외): ${failedSvcs.join(', ')}" }
                }
            }
        }

        stage('Wait Staging & Promote to Prod') {
            when { expression { env.CHANGED?.trim() } }
            steps {
                script {
                    def SERVER = '192.168.0.68:30080'   // ArgoCD NodePort (HTTP, insecure)
                    // active scan은 staging JWT_SECRET으로 유저 토큰을 직접 서명(pyjwt).
                    // Jenkins는 클러스터 밖이라 kubectl exec 불가 → credential로 secret 주입.
                    // 서비스별 독립 승격: 한 서비스의 승격 실패(staging wait 타임아웃/DAST High/
                    // 매니페스트 push 실패)가 다른 서비스 승격을 막지 않게 catchError로 격리한다.
                    // (Build 스테이지와 동일 패턴. 이전엔 격리가 없어 앞 서비스의 argocd wait
                    // 타임아웃(exit20)이 for 루프를 깨고 뒤 서비스 승격을 통째로 건너뛰었음.)
                    def promotedSvcs = []
                    def failedPromoteSvcs = []
                    withCredentials([string(credentialsId: 'argocd-token', variable: 'ARGOCD_TOKEN'),
                                     string(credentialsId: 'staging-jwt-secret', variable: 'STG_JWT_SECRET')]) {
                        for (svc in env.CHANGED.split(' ')) {
                            env.SVC = svc
                            echo "========== [${svc}] staging 대기 후 prod 승격 =========="
                            // catchError: 이 서비스 승격이 실패해도 파이프라인은 계속(빌드는 UNSTABLE 표시).
                            catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE', message: "${svc} 승격 실패") {
                            // 1) staging App(login-service 등) Synced+Healthy 대기 (게이트)
                            sh """
                                argocd app wait ${svc} \
                                    --server ${SERVER} --auth-token \$ARGOCD_TOKEN --plaintext \
                                    --sync --health --timeout 300
                            """
                            // ★ DAST 게이트: staging 뜬 것에 비인증 ZAP baseline. High(exit1)면 prod 승격 차단.
                            def PORT_MAP = [
                                'login-service':31000, 'main-service':31001, 'community-service':31002,
                                'recipe-service':31003, 'product-service':31004, 'ingredients-service':31005,
                                'diet-service':31006, 'admin-service':31007, 'ai':31008,
                            ]
                            def PORT = PORT_MAP[svc]
                            if (PORT == null) {
                                echo "DAST 포트 매핑 없음(${svc}) — 스캔 스킵"
                            } else {
                                sh """
                                    # 이전 빌드 잔재 제거(zap-out은 workspace라 빌드 간 남음 → 옛 report/log가
                                    # 이번 아티팩트로 섞여 진단을 오도. 매 빌드 깨끗이 시작).
                                    rm -rf \$WORKSPACE/zap-out
                                    mkdir -p \$WORKSPACE/zap-out && chmod 777 \$WORKSPACE/zap-out
                                    # NodePort는 모든 노드에 열리므로, 살아있는(도달되는) 첫 노드를 골라 스캔.
                                    # 노드 1개 장애 시 다음 노드로 폴백. 전부 불통이면 서비스 자체 장애로 보고 실패.
                                    TARGET_IP=""
                                    for ip in ${NODE_IPS}; do
                                        code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://\$ip:${PORT}/health" || echo 000)
                                        echo "노드 후보 \$ip:${PORT}/health → \$code"
                                        if [ "\$code" != "000" ]; then TARGET_IP=\$ip; break; fi
                                    done
                                    if [ -z "\$TARGET_IP" ]; then
                                        echo "DAST 대상 도달 불가 — ${svc}가 어느 노드(${NODE_IPS})로도 안 뜸. 승격 차단"
                                        exit 1
                                    fi
                                    echo "DAST 스캔 대상 노드: \$TARGET_IP:${PORT} (${svc})"
                                    # 비인증 baseline. -I 없음: 0=PASS, 1=FAIL(High,차단), 2=WARN(통과), 124=timeout.
                                    # timeout 360 + ZAP -m 3: staging이 살아있는 백엔드를 보면서 ZAP가
                                    #   특정 요청에 물려 무한 hang되는 것 방지(프론트 2026-07-30 사례와 대칭).
                                    #   timeout 초과 시 exit 124 → High(1) 아니므로 통과. 차단은 오직 High(1)일 때만.
                                    # ★ 좀비 방지(2026-07-31): timeout은 docker CLI만 죽이고 dockerd의
                                    #   ZAP 컨테이너는 살아남아 좀비화(프론트에서 14분+ 실증). --name +
                                    #   trap EXIT으로 shell이 어떤 경로로 끝나도 반드시 kill.
                                    # ★ 진단성(2026-07-31): kill 시 docker run stdout(>) 소실로 로그 0 B가
                                    #   된 프론트 사례. kill '전에' docker logs로 컨테이너 stdout을 별도
                                    #   파일(zap-${svc}.container.log)로 건져 hang 원인을 남긴다.
                                    ZAP_NAME=zap-base-${svc}-${BUILD_NUMBER}
                                    trap 'if [ "\$(docker inspect -f "{{.State.Running}}" "\$ZAP_NAME" 2>/dev/null)" = "true" ]; then docker logs "\$ZAP_NAME" > \$WORKSPACE/zap-out/zap-${svc}.container.log 2>&1 || true; docker kill "\$ZAP_NAME" 2>/dev/null || true; fi' EXIT
                                    timeout 360 docker run --rm --name "\$ZAP_NAME" -v \$WORKSPACE/zap-out:/zap/wrk/:rw \
                                        ghcr.io/zaproxy/zaproxy:stable \
                                        zap-baseline.py -t http://\$TARGET_IP:${PORT} -m 3 \
                                        -r zap-${svc}-report.html > \$WORKSPACE/zap-out/zap-${svc}.log 2>&1 || ZAP_RC=\$?
                                    ZAP_RC=\${ZAP_RC:-0}
                                    echo "ZAP ${svc} exit=\$ZAP_RC (0=PASS 1=FAIL/High 2=WARN 124=timeout)"
                                    tail -25 \$WORKSPACE/zap-out/zap-${svc}.log
                                    if [ "\$ZAP_RC" = "124" ]; then
                                        echo "DAST TIMEOUT(6분 초과, hang 방지) — ${svc} 그때까지 High 없어 승격 진행"
                                    fi
                                    if [ "\$ZAP_RC" = "1" ]; then
                                        echo "DAST FAIL(High) — ${svc} prod 승격 차단"
                                        exit 1
                                    fi
                                    echo "DAST baseline 통과 — ${svc}"
                                """

                                // ★ 인증 active scan (zap-api-scan.py): openapi import + Bearer 주입.
                                //   baseline이 못 잡는 SQLi/XSS/주입을 인증 상태로 전 엔드포인트에 검사.
                                //   recipe-service는 staging에서 service.recipes(데이터팀 테이블) 의존으로
                                //   CrashLoop → active 대상 제외(baseline만). High(exit1)면 승격 차단.
                                //   토큰은 STG_JWT_SECRET으로 pyjwt 직접 서명(kubectl 불필요, 실증 검증됨).
                                if (svc == 'recipe-service') {
                                    echo "active scan 스킵(${svc}): 데이터팀 테이블 의존 — baseline만 적용"
                                } else {
                                    sh """
                                        set -e
                                        # 도달 노드 재선택(TARGET_IP는 baseline 블록의 shell 변수라 여기선 없음).
                                        TARGET_IP=""
                                        for ip in ${NODE_IPS}; do
                                            code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://\$ip:${PORT}/openapi.json" || echo 000)
                                            if [ "\$code" != "000" ]; then TARGET_IP=\$ip; break; fi
                                        done
                                        if [ -z "\$TARGET_IP" ]; then
                                            echo "active scan 대상 도달 불가 — ${svc} openapi 안 뜸. 승격 차단"
                                            exit 1
                                        fi
                                        # staging 유저(user_id=1) 토큰을 pyjwt로 직접 서명. exp 짧게(1h), 매 스캔 새로 발급.
                                        TOKEN=\$(python3 -c "import jwt,time,os;s=os.environ['STG_JWT_SECRET'];n=int(time.time());print(jwt.encode({'sub':'1','user_id':1,'provider':'dast-ci','nickname':'ci','role':'user','iat':n,'exp':n+3600},s,algorithm='HS256'))")
                                        # openapi import + active scan + Bearer replacer.
                                        # -I: 경고(WARN,exit2)는 통과 처리 — 보안헤더 등 Medium 이하는 승격 막지 않음.
                                        #    High(exit1)만 차단. (baseline과 동일 기준: High면 실패)
                                        # ★ 좀비 방지(2026-07-31): timeout이 죽이는 건 docker CLI뿐이라
                                        #   ZAP 컨테이너가 좀비로 생존. 이 블록은 set -e라 TARGET_IP 미도달/
                                        #   토큰 실패로 중간 exit돼도 trap EXIT이 컨테이너를 반드시 kill.
                                        # ★ 진단성(2026-07-31): kill 전 docker logs로 컨테이너 stdout을
                                        #   별도 파일(zap-api-${svc}.container.log)로 건져 hang 원인 보존.
                                        ZAP_NAME=zap-api-${svc}-${BUILD_NUMBER}
                                        trap 'if [ "\$(docker inspect -f "{{.State.Running}}" "\$ZAP_NAME" 2>/dev/null)" = "true" ]; then docker logs "\$ZAP_NAME" > \$WORKSPACE/zap-out/zap-api-${svc}.container.log 2>&1 || true; docker kill "\$ZAP_NAME" 2>/dev/null || true; fi' EXIT
                                        timeout 600 docker run --rm --name "\$ZAP_NAME" -v \$WORKSPACE/zap-out:/zap/wrk/:rw \
                                            ghcr.io/zaproxy/zaproxy:stable \
                                            zap-api-scan.py -t "http://\$TARGET_IP:${PORT}/openapi.json" -f openapi -I \
                                            -z "-config replacer.full_list(0).description=auth -config replacer.full_list(0).enabled=true -config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=Authorization -config replacer.full_list(0).replacement=Bearer\\ \$TOKEN" \
                                            -r zap-api-${svc}-report.html > \$WORKSPACE/zap-out/zap-api-${svc}.log 2>&1 || API_RC=\$?
                                        API_RC=\${API_RC:-0}
                                        echo "ZAP active ${svc} exit=\$API_RC (0=PASS 1=FAIL/High, -I라 WARN은 0)"
                                        tail -20 \$WORKSPACE/zap-out/zap-api-${svc}.log
                                        if [ "\$API_RC" = "1" ]; then
                                            echo "active scan FAIL(High) — ${svc} prod 승격 차단"
                                            exit 1
                                        fi
                                        echo "active scan 통과 — ${svc} 승격 진행"
                                    """
                                }
                            }
                            // 2) 통과 → values-production.yaml tag 승격
                            withCredentials([usernamePassword(credentialsId: 'manifest-git-pat',
                                    usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PAT')]) {
                                sh '''
                                    set -e
                                    SHA=$(git rev-parse --short HEAD)
                                    WORK=$(mktemp -d)
                                    git clone --depth 1 "https://${GIT_USER}:${GIT_PAT}@github.com/DZ-Alpha/zero-manifests.git" "$WORK"
                                    cd "$WORK"
                                    git config user.name  "jenkins-ci"
                                    git config user.email "ci@hizero.local"
                                    yq -i ".image.tag = \\"${SHA}\\"" charts/${SVC}/values-production.yaml
                                    if git diff --quiet; then
                                        echo "prod tag 변경 없음 (${SVC} ${SHA}) — skip"
                                    else
                                        git commit -am "chore(${SVC}): promote to prod tag ${SHA} [skip ci]"
                                        git push origin main
                                        echo "prod 승격: ${SVC} tag=${SHA}"
                                    fi
                                    cd / && rm -rf "$WORK"
                                '''
                            }
                            echo "========== [${svc}] prod 승격 완료 =========="
                            promotedSvcs << svc   // 여기 도달 = 이 서비스 승격 성공
                            } // catchError
                            // catchError 블록 밖: 실패해도 여기 도달. 성공목록에 없으면 실패로 기록.
                            if (!promotedSvcs.contains(svc)) { failedPromoteSvcs << svc }
                        }
                    }
                    // Slack 알림(post{})이 실제 prod 승격된 서비스만 표기하도록 갱신.
                    // 빌드는 됐으나 승격 실패한 서비스는 OK에서 빼고 FAILED에 합친다.
                    env.OK_SVCS = promotedSvcs.join(', ')
                    def allFailed = []
                    if (env.FAILED_SVCS?.trim()) { allFailed.addAll(env.FAILED_SVCS.split(', ') as List) }
                    allFailed.addAll(failedPromoteSvcs)
                    env.FAILED_SVCS = allFailed.unique().join(', ')
                    echo "prod 승격 성공: ${promotedSvcs.join(', ') ?: '(없음)'}"
                    if (failedPromoteSvcs) { echo "prod 승격 실패: ${failedPromoteSvcs.join(', ')}" }
                }
            }
        }
    }
    post {
        always {
            // ZAP DAST 리포트 보관(htmlpublisher 없어 archive. 빌드 페이지에서 다운로드해서 봄)
            // zap-out은 DAST 스텝이 돌 때만 생성됨 → 있을 때만 archive(스킵 빌드에서 경고 방지)
            // ★ try/catch(2026-07-31): 체크아웃 실패(네트워크/DNS)로 workspace 컨텍스트가
            //   없으면 fileExists가 MissingContextVariableException을 던져 post 블록이
            //   중단→아래 Slack FAILURE 알림도 안 감. 감싸서 예외를 삼키면 알림은 정상 발송.
            script {
                try {
                    if (fileExists('zap-out')) {
                        archiveArtifacts artifacts: 'zap-out/*.html,zap-out/*.log', allowEmptyArchive: true
                    } else {
                        echo 'DAST 미실행(백엔드 변경 없음) — 보관할 ZAP 리포트 없음'
                    }
                } catch (err) {
                    echo "ZAP 리포트 보관 스킵(workspace 컨텍스트 없음 추정): ${err.message}"
                }
            }
            // Slack 배포 알림. Incoming Webhook URL을 credential 'slack-webhook'(Secret text)로 주입.
            // 결과별 색: SUCCESS=초록, UNSTABLE(일부 실패)=노랑, FAILURE=빨강. curl POST(플러그인 불필요).
            // NOOP(백엔드 변경 없이 프론트 커밋에 딸려 뜬 빌드)이면 알림 스킵 — 노이즈 제거.
            script {
                if (env.PIPELINE_NOOP == 'true') {
                    echo 'Slack 알림 스킵: 백엔드 변경 없는 NOOP 빌드'
                    return
                }
                def result = currentBuild.result ?: 'SUCCESS'
                def color = (result == 'SUCCESS') ? 'good' : (result == 'UNSTABLE') ? 'warning' : 'danger'
                def emoji = (result == 'SUCCESS') ? '✅' : (result == 'UNSTABLE') ? '⚠️' : '❌'
                // 메시지 조립(성공/실패 서비스 목록 포함). null/빈값 안전 처리.
                def okLine  = env.OK_SVCS?.trim()     ? "배포 완료: ${env.OK_SVCS}"     : "배포된 서비스 없음"
                def failLine = env.FAILED_SVCS?.trim() ? "\\n실패(제외): ${env.FAILED_SVCS}" : ""
                def text = "${emoji} 백엔드 파이프라인 ${result} (#${env.BUILD_NUMBER})\\n${okLine}${failLine}\\n${env.BUILD_URL}"
                // Webhook 미설정 시 알림만 스킵(빌드 결과에 영향 없음).
                try {
                    withCredentials([string(credentialsId: 'slack-webhook', variable: 'SLACK_HOOK')]) {
                        sh """
                            curl -s -X POST -H 'Content-type: application/json' \
                              --data '{"attachments":[{"color":"${color}","text":"${text}"}]}' \
                              "\$SLACK_HOOK" || echo 'Slack 알림 전송 실패(무시)'
                        """
                    }
                } catch (err) {
                    echo "Slack 알림 스킵: credential 'slack-webhook' 없음 또는 오류(${err.message})"
                }
            }
        }
    }
}
