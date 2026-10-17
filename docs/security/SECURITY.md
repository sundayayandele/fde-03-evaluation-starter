# Security

## Reporting

Report vulnerabilities privately through GitHub's "Report a vulnerability" on this repository; do not open a public issue.

## What this repo does

- **Secrets:** API keys come from the environment, Kubernetes Secrets or the cloud secret store. `.env` is ignored, and gitleaks runs in CI.
- **Data:** raw datasets are downloaded at run time from pinned commits and checked against SHA-256 before use. FinanceBench may not be redistributed, so its items, per-case outputs and CI artefacts stay out of Git. Only manifests, summaries and text-free baselines are committed.
- **LLM calls:** only the LLM judge and the prompt-only baseline call a model, through `LLMClient`. Regulated data may only go to providers with `regulated_data_allowed: true` (Mistral or self-hosted).
- **Traces:** spans carry ids, labels and timings, not question or answer text.
- **Containers:** non-root user, read-only root filesystem, dropped capabilities, `no-new-privileges`, resource limits. Runs started through the API write to `/tmp/runs` only.
- **Supply chain:** pip-audit and Trivy in the `security` workflow; pinned base image and action versions.

## Red team as a release control

`config/redteam.yaml` is versioned. Its critical categories (`indirect_injection`, `pii_leakage`) must pass every case for the gate to pass (`config/gate.yaml`). The red-team corpus is fictional and uses published test values for personal data; see [THREAT-MODEL](THREAT-MODEL.md) and [DATASETS](../datasets/DATASETS.md#personal-data).
