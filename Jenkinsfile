pipeline {
    agent any
    environment {
        REGISTRY = 'harbor.hizero.local'
        PROJECT  = 'dangdang-backend'
        NODE_IP  = '192.168.0.75'   // DAST 스캔 대상 워커 노드 IP (프론트 Jenkinsfile.frontend와 동일)
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
}
