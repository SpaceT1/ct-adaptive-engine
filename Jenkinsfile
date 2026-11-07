// Jenkins pipeline for ct-adaptive-engine (Assignment 5).
//
//   Checkout      -> gets the commit that triggered the build
//   Python setup  -> virtual environment with the package and its test tools
//   Lint          -> ruff: static checks and formatting
//   Unit tests    -> pytest, JUnit report and coverage gate (85 %)
//   Docker build  -> image tagged with the build number and the commit
//   Smoke test    -> the image starts and runs a short simulation
//   Reproduce     -> the full study runs inside the image; results must match the reference
//   Push          -> (optional) image to Docker Hub
//   Deploy        -> (optional) the study runs as a Kubernetes Job on Minikube
//
// The build starts by itself on every new commit: Jenkins polls GitHub every two
// minutes (a local Jenkins cannot receive GitHub webhooks).

pipeline {
    agent any

    triggers {
        pollSCM('H/2 * * * *')
    }

    options {
        skipDefaultCheckout()
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
            description: 'Push the image to Docker Hub (needs the credentials "dockerhub").')
        booleanParam(name: 'DEPLOY_TO_MINIKUBE', defaultValue: false,
            description: 'Run the study as a Kubernetes Job on Minikube ' +
                '(needs PUSH_IMAGE and the credentials "minikube-kubeconfig").')
    }

    environment {
        IMAGE_NAME = 'ct-adaptive-engine'
        VENV = '.venv'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${env.SHORT_SHA}"
                    currentBuild.description = "image ${env.IMAGE_NAME}:${env.IMAGE_TAG}"
                }
                sh 'git log -1 --pretty="Commit %h by %an: %s"'
            }
        }

        stage('Python setup') {
            steps {
                sh '''
                    python3 --version
                    python3 -m venv "$VENV"
                    "$VENV/bin/pip" install --quiet --upgrade pip
                    "$VENV/bin/pip" install --quiet -e ".[dev]"
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    "$VENV/bin/ruff" check .
                    "$VENV/bin/ruff" format --check .
                '''
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    mkdir -p reports
                    "$VENV/bin/python" -m pytest \
                        --junitxml=reports/junit.xml \
                        --cov --cov-report=term --cov-report=xml:reports/coverage.xml
                '''
            }
            post {
                always {
                    junit testResults: 'reports/junit.xml', allowEmptyResults: true
                    archiveArtifacts artifacts: 'reports/*.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Docker build') {
            steps {
                sh '''
                    docker version --format 'Docker client {{.Client.Version}}, server {{.Server.Version}}'
                    docker build \
                        --label org.opencontainers.image.revision="$GIT_COMMIT" \
                        --label org.opencontainers.image.version="$IMAGE_TAG" \
                        -t "$IMAGE_NAME:$IMAGE_TAG" \
                        -t "$IMAGE_NAME:latest" \
                        .
                    docker image ls "$IMAGE_NAME"
                '''
            }
        }

        stage('Smoke test') {
            steps {
                sh '''
                    docker run --rm "$IMAGE_NAME:$IMAGE_TAG" --version
                    docker run --rm "$IMAGE_NAME:$IMAGE_TAG" \
                        --learners 5 --max-steps 150 --no-plot --out /tmp/smoke
                '''
            }
        }

        stage('Reproduce study') {
            steps {
                sh '''
                    NAME="ct-study-$BUILD_NUMBER"
                    docker rm -f "$NAME" >/dev/null 2>&1 || true
                    docker run --name "$NAME" "$IMAGE_NAME:$IMAGE_TAG"
                    rm -rf results
                    docker cp "$NAME:/home/researcher/results" ./results
                    docker rm "$NAME"
                    echo "Comparing results/summary.csv with the reference result:"
                    diff -u docs/reference/summary_seed42.csv results/summary.csv
                    echo "Identical: the study is reproducible inside the image."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'results/**', allowEmptyArchive: true
                }
            }
        }

        stage('Push to Docker Hub') {
            when {
                expression { params.PUSH_IMAGE }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                        usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        for TAG in "$IMAGE_TAG" latest; do
                            docker tag "$IMAGE_NAME:$IMAGE_TAG" "$DH_USER/$IMAGE_NAME:$TAG"
                            docker push "$DH_USER/$IMAGE_NAME:$TAG"
                        done
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Minikube') {
            when {
                allOf {
                    expression { params.PUSH_IMAGE }
                    expression { params.DEPLOY_TO_MINIKUBE }
                }
            }
            steps {
                withCredentials([
                        file(credentialsId: 'minikube-kubeconfig', variable: 'KUBECONFIG'),
                        usernamePassword(credentialsId: 'dockerhub',
                            usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        kubectl version
                        kubectl apply -f k8s/namespace.yaml
                        sed -e "s|IMAGE_PLACEHOLDER|$DH_USER/$IMAGE_NAME:$IMAGE_TAG|" \
                            -e "s|BUILD_PLACEHOLDER|$BUILD_NUMBER|" \
                            k8s/job.yaml | kubectl apply -f -
                        kubectl -n ct-research wait --for=condition=complete \
                            "job/ct-study-$BUILD_NUMBER" --timeout=300s
                        kubectl -n ct-research logs "job/ct-study-$BUILD_NUMBER"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "Build ${env.BUILD_NUMBER} passed: ${env.IMAGE_NAME}:${env.IMAGE_TAG} is tested and reproducible."
        }
        failure {
            echo "Build ${env.BUILD_NUMBER} failed: open the red stage to see which step broke."
        }
    }
}
