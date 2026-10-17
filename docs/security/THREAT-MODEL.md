# Threat model

Two systems are in scope: the **harness** itself, and the **system under test**, whose threats the red-team suite exercises.

## The system under test (what the red team covers)

| Threat | STRIDE | Red-team category | fde-02 v1.0.0 | fde-02 v1.1.0 | Residual risk |
| --- | --- | --- | --- | --- | --- |
| A document carries instructions the model follows (indirect prompt injection), including exfiltration through a Markdown image URL | Tampering, information disclosure | `indirect_injection` (critical) | Poison reached the context in 4 of 4 cases | Quarantined at ingestion; 4 of 4 pass | Paraphrased instructions the patterns do not match; LLM mode untested |
| The user overrides the instructions or extracts the system prompt | Elevation of privilege, disclosure | `direct_injection` | 1 of 3 pass | 3 of 3 pass | LLM mode untested |
| Personal data in a document is repeated in an answer | Information disclosure | `pii_leakage` (critical) | 0 of 5 pass | Masked at ingestion and output; 5 of 5 pass | Names outside a role-word pattern; scanned images; the `/pdf` endpoint still serves the original document |
| The assistant gives investment advice or answers out of scope | Repudiation, reputational | `out_of_scope` | 3 of 4 pass | 4 of 4 pass | Paraphrased advice requests |
| Figures invented for periods or companies not in the corpus | Tampering (of decisions) | `fabrication`, refusal set | Refusal set 16.7% | Refusal set 80.0% | False premises: 0 of 5 declined |
| Answers without citations | Repudiation | `citation_integrity` | 3 of 3 pass | 3 of 3 pass | — |

## The harness

| Threat | STRIDE | Mitigation | Residual risk |
| --- | --- | --- | --- |
| Gaming the benchmark: tuning on the test half, editing gold answers | Tampering | Hash split; versioned golden sets with fingerprints; `golden verify` in CI; tuning disclosed in the README | A team can still tune on the test half; reviews must ask |
| A poisoned or swapped dataset download | Tampering | Pinned commits and SHA-256 checks before use | Upstream deletes the commit |
| Redistributing data we may not (FinanceBench) | Legal | Only the manifest and text-free baselines in Git; per-case files excluded from CI artefacts | A contributor commits `runs/`; `.gitignore` and review |
| Judge bias or drift inflates results | Tampering | Calibration with kappa; the judge model is pinned in run configs; κ thresholds in the gate | Self-preference of a same-provider judge |
| Regulated data sent to a non-sovereign judge | Information disclosure | `LLMClient` residency guard; the judge uses Mistral by default | Changing `LLM_PROVIDER` without reading `providers.yaml` |
| Prompt text in traces | Information disclosure | Span attributes hold ids, labels and timings, never text | A future attribute added carelessly |
| The service's run API used to load-test a production system | Denial of service | Runs are capped at 1,000 cases and use bounded concurrency; bind to localhost in labs | No authentication on the lab service |
| Leaked API keys | Information disclosure | `.env` ignored; gitleaks in CI; cloud secret stores | Keys pasted into issues or logs |

## Accepted lab trade-offs

These are inherited from the template and reported by the Trivy misconfiguration scan:

- Public lab endpoints on Azure and GCP while a lab runs.
- Provider-managed encryption keys.
- Open egress (the judge calls Mistral).
- No authentication on the evaluation service. It holds evaluation results, not customer data; put it behind the cluster's ingress authentication before sharing it.
