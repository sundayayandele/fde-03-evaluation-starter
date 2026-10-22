# Changelog

All notable changes. Versions follow semantic versioning; the starter repo is republished on every `v*` tag.

## [Unreleased]

### Added
- `.devcontainer/devcontainer.json` and an "Open in GitHub Codespaces" badge: a ready Python 3.12 environment that runs `make install` on creation.

### Fixed
- `.gitignore`: anchor `models/` to the repository root so it no longer matches source folders such as `src/*/models/`.
- Stop tracking the generated `src/fde_03_evaluation.egg-info/` build metadata.

## [1.1.0] - 2026-10-21

Repository and CI fixes; no change to the system's behaviour.

### Fixed
- Restored the files dropped on the first upload: GitHub Actions workflows, `.gitignore`, `.dockerignore`, `.env.example` and the starter configuration.
- Security workflow: `aquasecurity/trivy-action` pinned to the v0.36.0 commit (the `0.28.0` tag no longer resolves).

## [1.0.0] - 2026-10-16

### Added
- `rag-eval` package and CLI: pinned, checksummed sources; golden sets with fingerprints, dev/test split by hash, `verify` against a rebuild, `diff`. Sets: FinanceBench (150, manifest only in Git), PubMedQA (200), CUAD (200: spans and absent clauses) and a hand-written refusal set (30).
- Metrics: answer correctness by type, retrieval hit@5, citation precision/recall, false refusals, correct abstention, latency, cost; Wilson intervals; paired bootstrap; Cohen's kappa.
- Judges: deterministic reference judge; rubric-based LLM judge (Mistral, JSON). Calibration on a constructed set and from human labels (CSV export and import).
- Red-team suite (26 cases, 7 categories) with a fictional poisoned corpus; detectors for canaries, injected text, exfiltration links, PII (Luhn-checked cards), planted personal data, system-prompt leaks, investment advice and citations; context checks for what an LLM would read.
- Release gate (`config/gate.yaml`, profiles `ci-offline` and `release`); text-free baselines; `publish` and `report`.
- OpenTelemetry tracing (a span per case, `traceparent` to the SUT); evaluation service with runs API, background runs, judge endpoint, UI and `eval_*` Prometheus gauges; Grafana dashboard and alerts.
- `scripts/sut.py` and `config/sut.yaml`: named fde-02 configurations, warm-up, and a refusal to run when the SUT's retrieval mode differs from the requested one.
- Deployment: `TARGET_URL` on every path, Compose `sut` and Jaeger services, a Kubernetes red-team CronJob, Terraform `target_url`.
- CI: `release-gate` workflow (callable from fde-02) and `evals` workflow for LLM runs.
- Labs for weeks 16–18; ADR-004 to ADR-008; release-readiness memo; measured results for fde-02 v1.0.0, v1.1.0-rc1 and v1.1.0.

### Fixed during calibration
- Reference judge: free-text answers must contain the gold's figures (a changed "$20 billion" passed on word overlap).
- Constructed set: perturbations that round back to the gold (0.01 × 1.2) are dropped.
- PubMedQA sampling: rounding overshoot trims the largest stratum instead of truncating by id.

## [0.1.0] - 2026-10-13

Generated from fde-template 0.1.0.
