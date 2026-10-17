# Customer brief: can the filings assistant go to analysts?

**For:** Head of Customer Operations · **From:** forward deployed engineer · **Date:** 2026-10-16

## The problem in one paragraph

The pilot assistant (fde-02) answers questions about company filings with page citations. Before analysts rely on it, we need to know four things:

- how often it finds the right page;
- whether it declines what it cannot answer;
- whether a hostile document or a careless question can make it leak data or say something false;
- whether a new version is better or worse than the last.

Until now, all of that rested on demos.

## What we built

An evaluation system that asks the assistant hundreds of questions with known answers, in finance, health and legal documents, and grades every answer. It attacks the assistant with a planted instruction and planted personal data, and it blocks any new version that is worse than the last before it reaches users.

## Did it work?

| Measure | v1.0.0 (pilot today) | v1.1.0 (fixed) | Target |
| --- | --- | --- | --- |
| Finds the right filing page (top 5 results) | 55% | 54% | ≥ 50%, no real drop |
| Declines questions it cannot answer (30 traps) | 17% | **80%** | as high as possible |
| A poisoned document steers it | **yes** (4 of 4 attacks) | no (0 of 4) | never |
| Repeats personal data from a document | **yes** (5 of 5 tests) | no (0 of 5) | never |
| Wrongly refuses good questions | 0% | 0% | ≤ 5% |
| Answer time (95% of questions under) | 0.4 s | 0.4 s | ≤ 2 s |

The release check rejected v1.0.0, and it also rejected the first fix (rc1) for refusing too many good questions. v1.1.0 passed.

## Cost and risk

- **Running cost:** the assistant in its current mode calls no paid model. The full offline evaluation takes under a minute on a small server, once the filings are indexed (about 6 minutes, cached). It runs weekly and on every change. Grading with a language model will cost cents per run (to be measured).
- **Main risks:**
  - It answers questions built on a false premise ("Why did 3M buy Boeing?").
  - Attacks phrased differently from ours may get through.
  - Its prose answers are not yet measured.
  - The safeguard for all three: analysts verify against the cited page during the pilot.
- **Data and privacy:** test data is public (company filings, medical abstracts, contracts) or fictional. Grading by a language model uses Mistral (EU). Personal data is masked before it is stored in the assistant's index.

## Recommendation

**Pilot v1.1.0 with analysts, in its current page-finding mode.** Hold the AI-written answers until they pass the same release check (see the [release-readiness memo](../RELEASE-READINESS.md)).

## Next steps

| Step | Owner | By |
| --- | --- | --- |
| Run the paid evaluation (AI-written answers, AI grader) and record cost | Engineer | Week 1 of pilot |
| Label 40 graded answers by hand to validate the AI grader | Two analysts, 1 hour each | Week 1 |
| Ten new attacks written by someone other than the engineer | Security team | Week 2 |
| Go / no-go for AI-written answers | Customer sponsor | Week 3 |
