---
name: check
description: Run the repo quality gate (format, lint, types, tests) and fix what fails. Use when the user asks to check, verify or validate the code, before reporting a task as done, and before committing.
---

# Check

## Workflow
1. `make fmt` - ruff auto-fix and format.
2. `make lint` - ruff check, format check, mypy strict.
3. `make test` - pytest.
4. On failure: read the error, fix the cause, rerun the failing step, then rerun all three from the top.
5. Report what ran and the result. If something still fails, show the output; never report a pass that was not observed.

## Rules
- Fix the code, not the check. No `# noqa`, `# type: ignore`, skipped or deleted tests, or loosened config unless the user agrees; if one is truly needed, give the reason in the same line.
- Only fix failures caused by the current work. Pre-existing failures elsewhere: report them, do not fix unasked.
- Tests that need Postgres or Docker may not run inside WSL. Say which tests were skipped and why instead of calling the run green.
