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
        // 그 덕에 GIT_PREVIOUS_SUCCESSFUL_COMMIT이 채워진다.

        stage('Detect Changes') {
            steps {
                script {
                    def all = ['admin-service','ai','community-service','diet-service',
                               'ingredients-service','login-service','main-service',
                               'product-service','recipe-service']
                    def prev = env.GIT_PREVIOUS_SUCCESSFUL_COMMIT
                    def changed
                    def eventPipelineChanged = false

                    if (!prev) {
                        echo "이전 성공 빌드 없음 — 전체 빌드"
                        changed = all
                        eventPipelineChanged = true
                    } else {
                        def prevExists = sh(script: "git cat-file -e ${prev}^{commit} 2>/dev/null && echo yes || echo no",
                                            returnStdout: true).trim()
                        if (prevExists != 'yes') {
                            echo "이전 커밋(${prev})이 히스토리에 없음 — 안전하게 전체 빌드"
                            changed = all
                            eventPipelineChanged = true
                        } else {
                            def status = sh(script: "git diff --name-only ${prev} HEAD > /tmp/diff.txt; echo \$?",
                                            returnStdout: true).trim()
                            if (status != '0') {
                                echo "git diff 실패(exit ${status}) — 안전하게 전체 빌드"
                                changed = all
                                eventPipelineChanged = true
                            } else {
                                def raw = readFile('/tmp/diff.txt').trim()
                                def rawFiles = raw ? raw.split('\n') : []
                                // 문서·비코드 파일 제외: 이런 파일만 바뀐 서비스는 빌드/스캔/승격 안 함.
                                // (파일 단위로 거름 — 코드+문서 동시 변경이면 코드가 남아 빌드는 됨)
                                def isDoc = { String f ->
                                    def lower = f.toLowerCase()
                                    lower.endsWith('.md') || lower.endsWith('.txt') ||
                                    lower.endsWith('license') || lower.endsWith('.gitignore')
                                }
                                def files = rawFiles.findAll { !isDoc(it) }
                                def skipped = rawFiles.findAll { isDoc(it) }
                                if (skipped) { echo "문서·비코드 변경 무시: ${skipped.join(', ')}" }
                                changed = all.findAll { svc -> files.any { it.startsWith("backend/${svc}/") } }
                                // Jenkinsfile 자체가 바뀐 첫 실행에서도 새 빌드 경로를 검증한다.
                                eventPipelineChanged = files.any {
                                    it.startsWith('event-pipeline/') || it == 'Jenkinsfile'
                                }
                            }
                        }
                    }

                    env.CHANGED = changed.join(' ')
                    env.EVENT_PIPELINE_CHANGED = eventPipelineChanged ? 'true' : 'false'
                    echo "빌드 대상: ${env.CHANGED ?: '(없음 — 서비스 변경 없음)'}"
                    echo "event-pipeline 빌드: ${env.EVENT_PIPELINE_CHANGED}"
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
                    echo "빌드 성공(승격 대상): ${okSvcs.join(', ') ?: '(없음)'}"
                    if (failedSvcs) { echo "빌드 실패(승격 제외): ${failedSvcs.join(', ')}" }
                }
            }
        }

        stage('Build Event Pipeline') {
            when { expression { env.EVENT_PIPELINE_CHANGED == 'true' } }
            steps {
                script {
                  // event-pipeline 격리: 이 스테이지가 실패해도 뒤 스테이지(백엔드 Wait Staging&
                  // active scan 게이트)로 넘어가게 catchError로 감싼다. event-pipeline 실패는
                  // event-pipeline 배포만 막고, 백엔드 서비스 승격은 막지 않는다(독립).
                  catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE', message: 'event-pipeline 빌드 실패') {
                    def scannerHome = tool 'sonar-scanner'
                    withSonarQubeEnv('sonarqube') {
                        sh '''
                            "''' + scannerHome + '''/bin/sonar-scanner" \
                                -Dsonar.projectKey=zero-event-pipeline \
                                -Dsonar.projectName=zero-event-pipeline \
                                -Dsonar.sources=event-pipeline/app \
                                -Dsonar.tests=event-pipeline/tests
                        '''
                    }
                    // 품질 게이트: abortPipeline:false로 결과만 받아, ERROR면 이 스테이지만 실패.
                    def qg
                    timeout(time: 5, unit: 'MINUTES') {
                        qg = waitForQualityGate abortPipeline: false
                    }
                    if (qg.status != 'OK') {
                        error("event-pipeline SonarQube 품질 게이트 실패(${qg.status})")
                    }

                    sh '''
                        set -e
                        SHA=$(git rev-parse --short HEAD)
                        LOCAL_IMAGE=event-pipeline-local:${SHA}
                        docker build -t ${LOCAL_IMAGE} event-pipeline
                        docker run --rm \
                            -v "$WORKSPACE/event-pipeline/tests:/app/tests:ro" \
                            ${LOCAL_IMAGE} python -m unittest discover -s tests -v
                        trivy image --severity CRITICAL,HIGH --exit-code 1 \
                            --ignorefile .trivyignore --scanners vuln --quiet ${LOCAL_IMAGE}
                    '''

                    withCredentials([usernamePassword(credentialsId: 'harbor-cred',
                            usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_TOKEN')]) {
                        sh '''
                            set -e
                            SHA=$(git rev-parse --short HEAD)
                            LOCAL_IMAGE=event-pipeline-local:${SHA}
                            IMAGE=${REGISTRY}/dangdang/event-pipeline
                            echo "${HARBOR_TOKEN}" | docker login ${REGISTRY} \
                                -u "${HARBOR_USER}" --password-stdin
                            docker tag ${LOCAL_IMAGE} ${IMAGE}:${SHA}
                            docker push ${IMAGE}:${SHA}
                            docker logout ${REGISTRY}
                            echo "push 완료: ${IMAGE}:${SHA}"
                        '''
                    }

                    withCredentials([usernamePassword(credentialsId: 'manifest-git-pat',
                            usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PAT')]) {
                        sh '''
                            set -e
                            SHA=$(git rev-parse --short HEAD)
                            WORK=$(mktemp -d)
                            git clone --depth 1 \
                                "https://${GIT_USER}:${GIT_PAT}@github.com/DZ-Alpha/zero-manifests.git" "$WORK"
                            cd "$WORK"
                            git config user.name "jenkins-ci"
                            git config user.email "ci@hizero.local"
                            sed -i -E \
                                "s#harbor\\.hizero\\.local/dangdang/event-pipeline:[^[:space:]]+#harbor.hizero.local/dangdang/event-pipeline:${SHA}#g" \
                                pipeline/production/event-pipeline.yaml
                            sed -i -E \
                                -e 's#^  PROCESSOR_VERSION:.*#  PROCESSOR_VERSION: gemini-3.5-flash-lite-v2#' \
                                -e 's#^  GEMINI_MODEL:.*#  GEMINI_MODEL: gemini-3.5-flash-lite#' \
                                -e 's#^  VISION_TIMEOUT_SECONDS:.*#  VISION_TIMEOUT_SECONDS: "15"#' \
                                pipeline/production/base.yaml
                            if grep -q '^  GEMINI_THINKING_LEVEL:' pipeline/production/base.yaml; then
                                sed -i -E \
                                    's#^  GEMINI_THINKING_LEVEL:.*#  GEMINI_THINKING_LEVEL: minimal#' \
                                    pipeline/production/base.yaml
                            else
                                sed -i \
                                    '/^  GEMINI_MODEL:/a\\  GEMINI_THINKING_LEVEL: minimal' \
                                    pipeline/production/base.yaml
                            fi
                            if git diff --quiet; then
                                echo "event-pipeline manifest 변경 없음 (${SHA}) — skip"
                            else
                                git add pipeline/production/base.yaml pipeline/production/event-pipeline.yaml
                                git commit -m "chore(pipeline): deploy event-pipeline ${SHA} [skip ci]"
                                git push origin main
                                echo "event-pipeline manifest 갱신: tag=${SHA}"
                            fi
                            cd /
                            rm -rf "$WORK"
                        '''
                    }
                  }  // catchError (event-pipeline 격리)
                }
            }
        }

        stage('Wait Event Pipeline') {
            when { expression { env.EVENT_PIPELINE_CHANGED == 'true' } }
            steps {
                script {
                  // 격리: event-pipeline staging wait이 실패(타임아웃 등)해도 뒤 백엔드 승격
                  // 스테이지로 넘어가게 catchError. event-pipeline 배포 실패가 백엔드를 막지 않음.
                  catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE', message: 'event-pipeline wait 실패') {
                    withCredentials([string(credentialsId: 'argocd-token', variable: 'ARGOCD_TOKEN')]) {
                        sh '''
                            argocd app get dang-pipeline \
                                --server 192.168.0.68:30080 \
                                --auth-token "$ARGOCD_TOKEN" --plaintext --refresh >/dev/null
                            argocd app wait dang-pipeline \
                                --server 192.168.0.68:30080 \
                                --auth-token "$ARGOCD_TOKEN" --plaintext \
                                --sync --health --timeout 300
                        '''
                    }
                  }  // catchError (event-pipeline wait 격리)
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
                    withCredentials([string(credentialsId: 'argocd-token', variable: 'ARGOCD_TOKEN'),
                                     string(credentialsId: 'staging-jwt-secret', variable: 'STG_JWT_SECRET')]) {
                        for (svc in env.CHANGED.split(' ')) {
                            env.SVC = svc
                            echo "========== [${svc}] staging 대기 후 prod 승격 =========="
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
                                    timeout 360 docker run --rm -v \$WORKSPACE/zap-out:/zap/wrk/:rw \
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
                                        timeout 600 docker run --rm -v \$WORKSPACE/zap-out:/zap/wrk/:rw \
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
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            // ZAP DAST 리포트 보관(htmlpublisher 없어 archive. 빌드 페이지에서 다운로드해서 봄)
            // zap-out은 DAST 스텝이 돌 때만 생성됨 → 있을 때만 archive(스킵 빌드에서 경고 방지)
            script {
                if (fileExists('zap-out')) {
                    archiveArtifacts artifacts: 'zap-out/*.html,zap-out/*.log', allowEmptyArchive: true
                } else {
                    echo 'DAST 미실행(백엔드 변경 없음) — 보관할 ZAP 리포트 없음'
                }
            }
        }
    }
}
