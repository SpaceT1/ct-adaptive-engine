# Container image for ct-adaptive-engine.
#
# The image runs the reproducible simulation study by default:
#   docker build -t ct-adaptive-engine .
#   docker run --rm ct-adaptive-engine                     # full study, seed 42
#   docker run --rm ct-adaptive-engine --learners 5 --no-plot --out /tmp/out
#
# The Python version is pinned, so every run of the study uses exactly the same
# interpreter and libraries: a result produced on one computer can be repeated
# on any other computer that has Docker.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ct-adaptive-engine" \
      org.opencontainers.image.description="BKT learner model and rule-based adaptation engine (master's thesis prototype)" \
      org.opencontainers.image.source="https://github.com/SpaceT1/ct-adaptive-engine" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    MPLCONFIGDIR=/tmp/matplotlib

# 1) An ordinary user to run the study (not root), and the only third-party
#    library (for the figure) in its own layer. This layer is reused from the
#    cache as long as this line does not change, so a code change rebuilds the
#    image in seconds.
RUN useradd --create-home --uid 1000 researcher \
    && pip install "matplotlib>=3.7,<4"

# 2) The engine itself.
WORKDIR /opt/ct-adaptive-engine
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps .

# 3) Switch to the ordinary user.
USER researcher
WORKDIR /home/researcher

ENTRYPOINT ["ct-simulate"]
CMD ["--learners", "50", "--max-steps", "150", "--seed", "42", "--out", "results"]
