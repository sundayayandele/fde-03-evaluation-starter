# AGENTS.md

<!-- starter: verbatim -->

Instructions for any AI coding agent (Claude Code, Codex, Cursor, Gemini CLI, Copilot) working in an FDE series repo. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## What this repo is

One repo in the **Forward Deployed ML Engineer: Zero-to-Hired** series. Each reference repo builds one deployable system end to end and publishes a learner starter repo generated from it. The owner is Sunday Ayandele; he commits and pushes himself (GitHub Desktop), so never push or open pull requests unless asked.

## Non-negotiables

1. **Every deployment path keeps working:** local Python, Docker Desktop, Podman Desktop, Rancher Desktop, kind, Docker Desktop and Rancher Kubernetes, OpenShift, Helm, and Terraform for AWS, Azure and GCP. A change that breaks one path is not done.
2. **Measured results only.** The README results table holds numbers you produced with a stated method, dataset version and date. Never invent or estimate a metric and present it as measured.
3. **Regulated data stays sovereign.** Personal or regulated data goes only to providers with `regulated_data_allowed: true` in `config/providers.yaml` (Mistral or self-hosted). Use `contains_regulated_data=True` in `LLMClient.chat` for such calls.
4. **Secrets never enter Git.** Keys come from the environment, Kubernetes Secrets, or the cloud secret store created by Terraform.
5. **Datasets are downloaded at runtime**, never committed. Record source, licence, version and checksum in `docs/datasets/DATASETS.md`.

## Commands

```bash
make install        # dev environment
make lint           # ruff
make test           # tests (+ coverage gate in reference repos)
make e2e            # start the API, run tests/e2e/smoke.yaml, stop it
make structure      # required files present
make starter        # generate the learner starter into ../<repo>-starter
make help           # every target, including desktops, Kubernetes and clouds
```

## Reference vs starter

- Wrap each learner exercise in solution markers. Python markers must sit inside a function body:

  ```python
  def f():
      # >>> SOLUTION: week-02 description
      ...
      # <<< SOLUTION
  ```

- In Markdown (results tables, worked answers) use `<!-- >>> SOLUTION: label -->` and `<!-- <<< SOLUTION -->` on their own lines.
- Mark tests that need an exercise with `@pytest.mark.exercise`, and smoke checks with `exercise: true`.
- Never edit a starter repo by hand; regenerate it.
- Files with `starter: verbatim` in their first five lines are copied to the starter unchanged.

## Definition of done for a change

1. `make lint`, `make test` and `make e2e` pass; `make structure` passes.
2. Manifests and Terraform still render and validate (CI `manifests` and `iac`).
3. Docs updated where behaviour changed: README, the relevant `docs/` page, an ADR for any decision with alternatives.
4. `CHANGELOG.md` has an entry under `## [Unreleased]`.
5. If an exercise changed, `make starter` still succeeds and the starter's `make test` is green.

## Style

- Python 3.12, type hints, small functions, ruff clean, line length 100.
- Docs lead with the point, use short sentences, tables for comparisons, British spelling.
- ADRs: context, options considered, decision, consequences.
