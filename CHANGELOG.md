# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and the
project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] – 2026-10-10

### Added
- Bayesian Knowledge Tracing learner model with the parameters of thesis Table 2.1.
- Decision layer with the nine adaptation rules R1.1–R3.3; every decision records the rules that produced it.
- Simulation study with three synthetic learner profiles and the `ct-simulate` command.
- Test suite (49 tests, coverage gate 85 %).
- GitHub Actions pipeline: lint, test matrix, reproducible simulation, package build, release on tag.
