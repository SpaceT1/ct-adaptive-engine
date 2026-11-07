# DevOps: Docker image and Jenkins pipeline

This page explains how the project is built, tested and delivered automatically.
GitHub Actions ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) checks
every push on GitHub's servers. The Jenkins pipeline ([`Jenkinsfile`](../Jenkinsfile))
does the same on a Jenkins server you run yourself, and adds the Docker image.

## 1. The Docker image

```bash
docker build -t ct-adaptive-engine .
docker run --rm ct-adaptive-engine                       # full study, seed 42
docker run --rm ct-adaptive-engine --learners 5 --no-plot --out /tmp/out
docker run --rm ct-adaptive-engine --version
```

| Decision in the [`Dockerfile`](../Dockerfile) | Why |
|---|---|
| `python:3.12-slim` base | small image with a fixed Python version |
| matplotlib installed in its own layer | a code change does not reinstall it, so rebuilds take seconds |
| [`.dockerignore`](../.dockerignore) | only `pyproject.toml`, `README.md`, `LICENSE` and `src/` enter the image |
| `researcher` user (UID 1000) | the container does not run as root |
| `ENTRYPOINT ["ct-simulate"]` | the image *is* the study: `docker run` repeats it |

To keep the results of a full run on your computer:

```bash
docker run --name study ct-adaptive-engine
docker cp study:/home/researcher/results ./results
docker rm study
```

## 2. Run Jenkins locally

Requirements: Docker Desktop (Windows/macOS) or Docker Engine (Linux).

```bash
cd jenkins
cp .env.example .env            # Windows: copy .env.example .env
# edit .env and choose a password
docker compose up -d --build    # first start takes 5-10 minutes
```

Open <http://localhost:8080> and log in as `admin` with the password from `.env`.
The job **ct-adaptive-engine** already exists: Jenkins is configured as code
([`jenkins/casc.yaml`](../jenkins/casc.yaml)), and its plugins are listed in
[`jenkins/plugins.txt`](../jenkins/plugins.txt).

Click **Build Now** once. After the first build Jenkins checks GitHub every two
minutes and starts a new build for every new commit on `main`.

## 3. The pipeline

| Stage | What happens | Fails when |
|---|---|---|
| Checkout | the new commit is fetched; the image tag is `<build>-<commit>` | – |
| Python setup | virtual environment with `pip install -e ".[dev]"` | a dependency cannot be installed |
| Lint | `ruff check` and `ruff format --check` | style or static errors |
| Unit tests | `pytest` with JUnit report and coverage | a test fails or coverage < 85 % |
| Docker build | `docker build`, tags `<build>-<commit>` and `latest` | the Dockerfile is broken |
| Smoke test | the image prints its version and runs a short simulation | the container does not start |
| Reproduce study | the full study runs inside the image; `summary.csv` is compared with [`docs/reference/summary_seed42.csv`](reference/summary_seed42.csv) | the published result is not reproduced |
| Push to Docker Hub | optional, parameter `PUSH_IMAGE` | login or push fails |
| Deploy to Minikube | optional, parameter `DEPLOY_TO_MINIKUBE`: the study runs as a Kubernetes Job | the Job does not complete |

Each build keeps the test report (**Tests** tab), `reports/coverage.xml` and the
study results (`results/`, including `completion.png`) as downloadable artifacts.

## 4. Optional: push the image to Docker Hub

1. Create an access token on Docker Hub (Account settings → Personal access tokens).
2. In Jenkins: **Manage Jenkins → Credentials → System → Global → Add credentials**,
   kind *Username with password*, ID `dockerhub`, username = Docker Hub user,
   password = the token.
3. **Build with Parameters** → tick `PUSH_IMAGE`.

## 5. Optional: deploy to Minikube (continuous deployment)

The Job pulls the image from Docker Hub, so step 4 is needed first.

```powershell
minikube start --driver=docker
docker network connect minikube jenkins      # Jenkins can now reach the cluster
$ip = minikube ip
kubectl config view --flatten --minify --context minikube |
  ForEach-Object { $_ -replace 'https://127\.0\.0\.1:\d+', "https://${ip}:8443" } |
  Set-Content -Encoding ascii minikube.kubeconfig
```

Add `minikube.kubeconfig` to Jenkins as a *Secret file* with ID
`minikube-kubeconfig`, then build with `PUSH_IMAGE` and `DEPLOY_TO_MINIKUBE`.
Jenkins applies [`k8s/namespace.yaml`](../k8s/namespace.yaml) and
[`k8s/job.yaml`](../k8s/job.yaml), waits for the Job to finish and prints its log.

```bash
kubectl -n ct-research get jobs,pods
```

`docker compose up --build` recreates the Jenkins container; run
`docker network connect minikube jenkins` again after it.

## 6. Stop

```bash
cd jenkins
docker compose down        # keeps Jenkins data (volume jenkins_home)
docker compose down -v     # removes it as well
```
