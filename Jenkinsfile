pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'VALIDATION_ONLY',
            defaultValue: true,
            description: 'Run quality and resilience checks only; skip Docker, ACR and GitOps deployment.'
        )
    }
    environment {
        AZURE_CONFIG_DIR = "${WORKSPACE}\\.azure"
        ACR_NAME = "acrarmenlearning2026"
        APP_DIR = "python\\storage-demo"
    }

    stages {
        stage('Environment') {
            steps {
                bat 'python --version'
                bat 'git --version'
                bat 'docker --version'
                bat 'az version'
            }
        }

        stage('Skip GitOps-only Commit') {
            steps {
                script {
                    def message = bat(
                        script: '@git log -1 --pretty=%%B',
                        returnStdout: true
                    ).trim()

                    if (message.contains('[skip ci]')) {
                        currentBuild.result = 'NOT_BUILT'
                        error('GitOps-generated commit: skipping CI')
                    }
                }
            }
        }

        stage('Create Virtual Environment') {
            steps {
                dir('python/storage-demo') {
                    bat 'if exist .venv rmdir /s /q .venv'
                    bat 'python -m venv .venv'
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m pip install --upgrade pip'
                    bat '.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt'
                }
            }
        }

        stage('Verify Application') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m py_compile app.py'
                }
            }
        }

        stage('Unit Tests') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m pytest -v'
                }
            }
        }

        stage('AI Quality Gate') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m pytest tests\\test_agent_eval.py -v'
                }
            }
        }

        stage('Observability Configuration Gate') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m pytest tests\\test_http_metrics.py tests\\test_observability_operations.py -q'
                }
            }
        }

        stage('Release Readiness Gate') {
            steps {
                dir('python/storage-demo') {
                    bat '.venv\\Scripts\\python.exe -m pytest tests\\test_release_readiness.py -q'
                    bat '.venv\\Scripts\\python.exe ..\\..\\scripts\\validate_release.py'
                }
            }
        }

        stage('AKS Resilience Configuration Gate') {
            steps {
                withEnv(['PATH+HELM=C:\\Tools\\bin']) {
                    bat 'helm.exe lint helm\\storage-demo -f gitops\\environments\\dev\\values.yaml'
                    bat 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\\resilience\\Test-AksResilience.ps1'
                }
            }
        }
        stage('Build Container') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                script {
                    env.IMAGE_TAG = "${BUILD_NUMBER}-${GIT_COMMIT.take(7)}"
                    env.IMAGE = "${env.ACR_NAME}.azurecr.io/storage-demo:${env.IMAGE_TAG}"
                }

                dir('python/storage-demo') {
                    bat '''
                        docker build -t "%IMAGE%" .
                    '''
                }
            }
        }

        stage('Container Vulnerability Scan') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                bat '''
                    "C:/Tools/Trivy/trivy.exe" image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --format table --exit-code 1 --timeout 10m "%IMAGE%"
                '''
            }
        }

        stage('Generate SBOM') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                bat '''
                    "C:/Tools/Trivy/trivy.exe" image --format cyclonedx --output storage-demo-sbom.json "%IMAGE%"
                '''
                archiveArtifacts artifacts: 'storage-demo-sbom.json', fingerprint: true
            }
        }

        stage('Push to ACR') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                withCredentials([
                    string(
                        credentialsId: 'azure-client-id',
                        variable: 'AZURE_CLIENT_ID'
                    ),
                    string(
                        credentialsId: 'azure-client-secret',
                        variable: 'AZURE_CLIENT_SECRET'
                    ),
                    string(
                        credentialsId: 'azure-tenant-id',
                        variable: 'AZURE_TENANT_ID'
                    )
                ]) {
                    bat '''
                        az login --service-principal ^
                            --username "%AZURE_CLIENT_ID%" ^
                            --password "%AZURE_CLIENT_SECRET%" ^
                            --tenant "%AZURE_TENANT_ID%" ^
                            --output none
                    '''

                    bat 'az acr login --name %ACR_NAME%'

                    bat 'docker push "%IMAGE%"'
                }
            }
        }

        stage('Resolve Image Digest') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                script {
                    env.IMAGE_DIGEST = bat(
                        script: '@az acr repository show --name %ACR_NAME% --image storage-demo:%IMAGE_TAG% --query digest --output tsv',
                        returnStdout: true
                    ).trim()

                    echo "Resolved immutable digest: ${env.IMAGE_DIGEST}"
                }
            }
        }

        stage('Prepare GitOps Promotion Branch') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                script {
                    env.GITOPS_BRANCH = "gitops/promote-storage-demo-${env.BUILD_NUMBER}"
                }

                bat '''
                    git fetch origin +refs/heads/main:refs/remotes/origin/main
                    git switch -c "%GITOPS_BRANCH%" origin/main
                '''
            }
        }

        stage('Update GitOps Desired State') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                bat '''
                    python\\storage-demo\\.venv\\Scripts\\python.exe ^
                        scripts\\update_gitops_digest.py ^
                        gitops\\environments\\dev\\values-patch.yaml ^
                        "%IMAGE_DIGEST%"
                '''

                bat '''
                    git diff --exit-code --check
                    git diff -- gitops\\environments\\dev\\values-patch.yaml
                '''

                bat '''
                    git config user.name "jenkins-ci"
                    git config user.email "jenkins-ci@local"

                    git add gitops\\environments\\dev\\values-patch.yaml

                    git commit -m "chore(gitops): promote storage-demo %IMAGE_DIGEST% to dev [skip ci]"
                '''
            }
        }

        stage('Push GitOps Desired State') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {

                withCredentials([
                    gitUsernamePassword(
                        credentialsId: 'github-gitops-write',
                        gitToolName: 'Default'
                    )
                ]) {
                    bat '''
                        git push ^
                            https://github.com/armsah/Azure-AI-Platform-Engineering.git ^
                            HEAD:refs/heads/%GITOPS_BRANCH%
                    '''
                }
            }
        }

        stage('Create GitOps Promotion PR') {
            when {
                expression { !params.VALIDATION_ONLY }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'github-gitops-write',
                        usernameVariable: 'GITHUB_USER',
                        passwordVariable: 'GH_TOKEN'
                    )
                ]) {
                    bat '''
                        @echo off
                        "C:\\Program Files\\GitHub CLI\\gh.exe" pr create ^
                            --repo armsah/Azure-AI-Platform-Engineering ^
                            --base main ^
                            --head "%GITOPS_BRANCH%" ^
                            --title "chore(gitops): promote storage-demo build %BUILD_NUMBER%" ^
                            --body "Automated promotion of storage-demo image %IMAGE_DIGEST% to the dev environment."
                    '''
                }
            }
        }
    }

    post {
        always {
            bat 'az logout 2>NUL || exit /b 0'
            bat 'if exist .azure rmdir /s /q .azure'
        }
    }
}