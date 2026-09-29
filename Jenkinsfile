pipeline {
    agent any

    environment {
        AZURE_CONFIG_DIR = "${WORKSPACE}\\.azure"
        ACR_NAME = "acrarmenlearning2026"
    }

    stages {
        stage('Environment') {
            steps {
                bat 'python --version'
                bat 'git --version'
            }
        }

        stage('Create Virtual Environment') {
            steps {
                bat 'if exist .venv rmdir /s /q .venv'
                bat 'python -m venv .venv'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt'
            }
        }

        stage('Verify Application') {
            steps {
                bat '.venv\\Scripts\\python.exe -m py_compile app.py'
            }
        }

        stage('Unit Tests') {
            steps {
                bat '.venv\\Scripts\\python.exe -m pytest -v'
            }
        }

        stage('AI Quality Gate') {
            steps {
                bat '.venv\\Scripts\\python.exe -m pytest tests\\test_agent_eval.py -v'
            }
        }

        stage('Build Container') {
            steps {
                script {
                    env.IMAGE_TAG = "${BUILD_NUMBER}-${GIT_COMMIT.take(7)}"
                    env.IMAGE = "${env.ACR_NAME}.azurecr.io/storage-demo:${env.IMAGE_TAG}"
                }

                bat '''
                    docker build -t "%IMAGE%" .
                '''
            }
        }

        stage('Push to ACR') {
            steps {
                withCredentials([
                    string(credentialsId: 'azure-client-id', variable: 'AZURE_CLIENT_ID'),
                    string(credentialsId: 'azure-client-secret', variable: 'AZURE_CLIENT_SECRET'),
                    string(credentialsId: 'azure-tenant-id', variable: 'AZURE_TENANT_ID')
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
            steps {
                script {
                    env.IMAGE_DIGEST = bat(
                        script: '@az acr repository show --name %ACR_NAME% --image storage-demo:%IMAGE_TAG% --query digest --output tsv',
                        returnStdout: true
                    ).trim()

                    echo "Deploying immutable digest: ${env.IMAGE_DIGEST}"
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
