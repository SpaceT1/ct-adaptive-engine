# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and the
project uses [Semantic Versioning](https://semver.org/).

## [0.2.0] – 2026-11-07

### Added
- `Dockerfile` and `.dockerignore`: the simulation study as a container image (non-root user, cached dependency layer).
- `Jenkinsfile`: lint, unit tests with JUnit and coverage reports, Docker build, smoke test, reproduction of the study inside the image, optional push to Docker Hub and optional deployment to Minikube.
- `jenkins/`: local Jenkins server with Docker Compose, plugin list and Configuration as Code.
- `k8s/`: namespace and Job manifests for the deployment.
- `docs/reference/summary_seed42.csv`: reference result that every pipeline run must reproduce.
- `docs/devops.md`: guide to the image and the pipeline.
- GitHub Actions job `docker`: builds the image and reproduces the study inside it; Dependabot also watches the Docker base images.

## [0.1.0] – 2026-10-10

### Added
- Bayesian Knowledge Tracing learner model with the parameters of thesis Table 2.1.
- Decision layer with the nine adaptation rules R1.1–R3.3; every decision records the rules that produced it.
- Simulation study with three synthetic learner profiles and the `ct-simulate` command.
- Test suite (49 tests, coverage gate 85 %).
- GitHub Actions pipeline: lint, test matrix, reproducible simulation, package build, release on tag.
