pipeline {
    agent any

    environment {
        // Customize these variables according to your environment
        DOCKER_REGISTRY = 'docker.io'
        DOCKER_IMAGE    = 'aurix-ai/video-assistant'
        IMAGE_TAG       = "${env.BUILD_NUMBER}"
        DOCKER_CRED_ID  = 'docker-hub-credentials'
    }

    parameters {
        choice(name: 'DEPLOY_ENV', choices: ['dev', 'staging', 'production'], description: 'Target environment for deployment')
        booleanParam(name: 'RUN_LINTER', defaultValue: true, description: 'Check to run flake8/bandit code checks')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Check to push the built image to Docker Registry')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint & Security Scan') {
            when {
                expression { return params.RUN_LINTER }
            }
            steps {
                script {
                    echo 'Starting Linting and Security Scan stages...'
                    try {
                        if (isUnix()) {
                            sh '''
                                python3 -m venv venv
                                . venv/bin/activate
                                pip install --upgrade pip
                                pip install flake8 bandit
                                echo "=== Running flake8 ==="
                                flake8 app.py server.py utils/ routes/ services/ --ignore=E501 || true
                                echo "=== Running bandit ==="
                                bandit -r app.py server.py utils/ routes/ services/ -x ./venv || true
                            '''
                        } else {
                            bat '''
                                python -m venv venv
                                call venv\\Scripts\\activate
                                python -m pip install --upgrade pip
                                pip install flake8 bandit
                                echo === Running flake8 ===
                                flake8 app.py server.py utils/ routes/ services/ --ignore=E501
                                echo === Running bandit ===
                                bandit -r app.py server.py utils/ routes/ services/ -x ./venv
                            '''
                        }
                    } catch (Exception e) {
                        echo "Linting failed or Python dependencies not found on agent: ${e.message}"
                        echo "Continuing pipeline since static analysis failures are non-blocking."
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker image: ${DOCKER_IMAGE}:${IMAGE_TAG}..."
                    if (isUnix()) {
                        sh "docker build -t ${DOCKER_IMAGE}:${IMAGE_TAG} -t ${DOCKER_IMAGE}:latest ."
                    } else {
                        bat "docker build -t ${DOCKER_IMAGE}:${IMAGE_TAG} -t ${DOCKER_IMAGE}:latest ."
                    }
                }
            }
        }

        stage('Push Docker Image') {
            when {
                expression { return params.PUSH_IMAGE }
            }
            steps {
                script {
                    echo 'Pushing Docker image to registry...'
                    withCredentials([usernamePassword(credentialsId: DOCKER_CRED_ID, usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASSWORD')]) {
                        if (isUnix()) {
                            sh '''
                                echo "$DOCKER_PASSWORD" | docker login "$DOCKER_REGISTRY" -u "$DOCKER_USER" --password-stdin
                                docker tag ${DOCKER_IMAGE}:${IMAGE_TAG} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${IMAGE_TAG}
                                docker tag ${DOCKER_IMAGE}:latest ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:latest
                                docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${IMAGE_TAG}
                                docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:latest
                            '''
                        } else {
                            bat '''
                                echo %DOCKER_PASSWORD% | docker login %DOCKER_REGISTRY% -u %DOCKER_USER% --password-stdin
                                docker tag %DOCKER_IMAGE%:%IMAGE_TAG% %DOCKER_REGISTRY%/%DOCKER_IMAGE%:%IMAGE_TAG%
                                docker tag %DOCKER_IMAGE%:latest %DOCKER_REGISTRY%/%DOCKER_IMAGE%:latest
                                docker push %DOCKER_REGISTRY%/%DOCKER_IMAGE%:%IMAGE_TAG%
                                docker push %DOCKER_REGISTRY%/%DOCKER_IMAGE%:latest
                            '''
                        }
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    echo "Deploying to target environment: ${params.DEPLOY_ENV}..."
                    if (params.DEPLOY_ENV == 'dev') {
                        if (isUnix()) {
                            sh '''
                                docker compose down || true
                                docker compose up -d --build
                            '''
                        } else {
                            bat '''
                                docker compose down
                                docker compose up -d --build
                            '''
                        }
                    } else {
                        echo "For staging or production, customize this step to deploy via SSH, Kubernetes (kubectl), or other CD pipelines."
                    }
                }
            }
        }
    }

    post {
        always {
            echo 'Pipeline completed.'
            cleanWs()
        }
        success {
            echo "Successfully built and processed version ${IMAGE_TAG}!"
        }
        failure {
            echo "Pipeline run failed. Check console output."
        }
    }
}
