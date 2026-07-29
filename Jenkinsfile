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

                    if (!prev) {
                        echo "이전 성공 빌드 없음 — 전체 빌드"
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
                                def lines = readFile('/tmp/diff.txt').trim()
                                def files = lines ? lines.split('\n') : []
                                changed = all.findAll { svc -> files.any { it.startsWith("backend/${svc}/") } }
                            }
                        }
                    }

                    env.CHANGED = changed.join(' ')
                    echo "빌드 대상: ${env.CHANGED ?: '(없음 — 서비스 변경 없음)'}"
                }
            }
        }

        stage('Build Changed Services') {
            when { expression { env.CHANGED?.trim() } }
            steps {
                script {
                    def scannerHome = tool 'sonar-scanner'
                    for (svc in env.CHANGED.split(' ')) {
                        env.SVC = svc
                        echo "========== [${svc}] 빌드 시작 =========="

                        // 1) SonarQube (서비스별 projectKey)
                        withSonarQubeEnv('sonarqube') {
                            sh '''
                                "''' + scannerHome + '''/bin/sonar-scanner" \
                                    -Dsonar.projectKey=zero-${SVC} \
                                    -Dsonar.projectName=zero-${SVC} \
                                    -Dsonar.sources=backend/${SVC}
                            '''
                        }
                        timeout(time: 5, unit: 'MINUTES') {
                            waitForQualityGate abortPipeline: true
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
                        echo "========== [${svc}] 완료 =========="
                    }
                }
            }
        }

        stage('Wait Staging & Promote to Prod') {
            when { expression { env.CHANGED?.trim() } }
            steps {
                script {
                    def SERVER = '192.168.0.68:30080'   // ArgoCD NodePort (HTTP, insecure)
                    withCredentials([string(credentialsId: 'argocd-token', variable: 'ARGOCD_TOKEN')]) {
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
                                    # 비인증 baseline. -I 없음: 0=PASS, 1=FAIL(High,차단), 2=WARN(통과)
                                    docker run --rm -v \$WORKSPACE/zap-out:/zap/wrk/:rw \
                                        ghcr.io/zaproxy/zaproxy:stable \
                                        zap-baseline.py -t http://\$TARGET_IP:${PORT} \
                                        -r zap-${svc}-report.html > \$WORKSPACE/zap-out/zap-${svc}.log 2>&1 || ZAP_RC=\$?
                                    ZAP_RC=\${ZAP_RC:-0}
                                    echo "ZAP ${svc} exit=\$ZAP_RC (0=PASS 1=FAIL/High 2=WARN)"
                                    tail -25 \$WORKSPACE/zap-out/zap-${svc}.log
                                    if [ "\$ZAP_RC" = "1" ]; then
                                        echo "DAST FAIL(High) — ${svc} prod 승격 차단"
                                        exit 1
                                    fi
                                    echo "DAST 통과 — ${svc} 승격 진행"
                                """
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
