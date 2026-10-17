# ADR-001: One template for every FDE phase repo

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

The series has 8 reference repos and 8 generated starter repos. Each must show the same evidence a forward-deployed hiring loop checks: working code, measured results, deployment on desktops and clouds, security and cost thinking, and customer-facing documents. Building that scaffolding 8 times by hand would drift.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Copy Project 01 by hand each time | Fast for the first repo | Drift; fixes never propagate |
| Monorepo with all phases | One CI, shared code | Learners need one self-contained repo per phase; heavy to clone |
| **GitHub template repo + init script** | Identical start, independent repos, fixes applied by re-syncing | Template changes must be ported to existing repos |

## Decision

Use `fde-03-evaluation` as a GitHub template repository. `scripts/init_repo.py` renames the package and identifiers; `scripts/check_structure.py` enforces the required layout in CI for every reference and starter repo.

## Consequences

- Every repo has the same Makefile targets, workflows and docs tree, so learners and reviewers know where to look.
- Template fixes are ported with a small pull request per repo; `CHANGELOG.md` records the template version each repo started from.
