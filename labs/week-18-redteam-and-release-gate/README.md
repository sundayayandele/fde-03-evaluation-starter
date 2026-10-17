# Week 18: Red team, gate and release memo

**Goal:**

- attack the assistant the way a hostile document or a careless user would;
- fix what breaks, and prove the fix did not break something else;
- write the memo that decides the release.

## Brief

A bank will load its own documents into the assistant, including customer complaints. Two questions decide the release:

- **Indirect injection:** can a sentence planted in a document change what the assistant says?
- **PII leakage:** will it repeat a customer's personal details?

Every pull request to the assistant must answer both automatically, and must also show the fix did not make the assistant refuse good questions.

## Concepts

- Direct and indirect prompt injection; canaries; exfiltration through Markdown images.
- PII detection (formats, Luhn) vs masking at ingestion and at output.
- Out-of-scope requests, fabrication pressure, citation integrity.
- Severity and "never" rules; a paired bootstrap for regressions.
- Release gates in CI; a release-readiness memo.

## Steps

1. `make corpora`, then read `redteam.py` and `config/redteam.yaml`. What is in the two "Halden Mutual Bank" PDFs, and why are its personal data values safe to publish?
2. Implement `detect_pii(text)` in `redteam.py`.
3. Implement `bootstrap_diff_ci(a, b)` in `metrics.py` and `check_gate(cfg, summary, …)` in `gate.py`.
4. `pytest -m exercise`.
5. Run the red team against **fde-02 without its guardrails**, close to v1.0.0's behaviour (only the output check stays on, so direct injection scores better than v1.0.0's 1 of 3):

   ```bash
   ../fde-02-llm-applications/.venv/bin/filing-assistant --index-dir data/index/redteam-noguard \
     ingest --demo --pdfs data/corpus/redteam --embed lsa --no-guard
   make redteam CONFIG=advanced-noguard RT_INDEX=data/index/redteam-noguard LABEL=noguard
   ```

   (Or check out fde-02's v1.0.0 commit and use `make redteam`.) Which critical categories fail?
6. Fix fde-02. The reference v1.1.0 is in fde-02's ADR-008, but write your own first. Re-run `make eval-financebench redteam calibrate gate`.
   - Does the gate pass?
   - Did your fix raise false refusals?
   - Read the masked chunks in fde-02's index. Did you mask a financial figure? The reference rc1 did both, and failed the gate.
7. Fill the README results table with your measured numbers, then write `docs/RELEASE-READINESS.md`: evidence, residual risks, decision.

## Check

```bash
make exercises
make gate        # exit 0 on your fixed fde-02
```

## Evidence

- The gate report failing on v1.0.0 and passing on your fix.
- The red-team table.
- The memo, with a sponsor's decision line.

## Stretch

Write five injections that do not match fde-02's quarantine patterns ("as a language model, your new task is…"). Add them as `redteam.yaml` v2, and measure them against the LLM mode with a key. This is the residual risk the reference memo names.
