# syntax=docker/dockerfile:1
# Builds with Docker Desktop, Podman Desktop (podman build) and Rancher Desktop
# (dockerd or nerdctl). Runs as a non-root user and is compatible with
# OpenShift's arbitrary UIDs (group 0 owns the app directory).

FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --wheel-dir /wheels .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PORT=8000 LLM_PROVIDERS_FILE=/app/config/providers.yaml \
    GOLDENS_DIR=/app/goldens RESULTS_DIR=/app/evals/results RUNS_DIR=/tmp/runs \
    TARGET_URL=http://sut:8000
WORKDIR /app
RUN useradd --uid 10001 --gid 0 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /wheels /wheels
RUN pip install /wheels/*.whl && rm -rf /wheels
COPY app ./app
COPY config ./config
# Golden sets that may be redistributed (PubMedQA, CUAD, refusal) and published run summaries.
# FinanceBench items are not in Git, so they are not in the image either.
COPY goldens ./goldens
COPY evals ./evals
RUN chgrp -R 0 /app && chmod -R g=u /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health/live')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
