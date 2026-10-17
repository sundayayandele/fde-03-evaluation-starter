# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Read the phase's build spec (in the repo's `docs/` or linked from the README) before writing code; work tests first.
- Use plan mode for anything touching more than three files or any deployment path.
- After a change, run `make lint test e2e` yourself and paste the summary lines into your reply.
- When you produce measured numbers, write the command, dataset version and date next to them in the results table.
- Finish with a short summary and a suggested commit message. Do not commit or push unless asked.
