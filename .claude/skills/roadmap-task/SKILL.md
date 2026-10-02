---
name: roadmap-task
description: Implement the next task from the phased roadmap in .plans/roadmap/ and verify its acceptance criteria. Use when the user says to do the next task, continue the roadmap, work on a phase, or names a roadmap task file.
---

# Roadmap task

The roadmap lives in `.plans/roadmap/` (gitignored, never commit it): `README.md` plus `phase_N/K_feature_name.md`. Tasks are done in order: phase by phase, then by K.

## Finding the task
- A finished task has a `**Status:** done (YYYY-MM-DD)` line directly under its title. The next task is the first file in order without it.
- If the user names a task, use that one, but check its "Depends on" tasks are done; if not, stop and say which are missing.
- No status line does not prove the work is missing. Check the code against the Acceptance section before starting; if it is already met, tell the user and ask before marking it.

## Workflow
1. Read the task file, `.plans/roadmap/README.md` and `.project/ARCHITECTURE.md`. Read the code the task touches.
2. State a short plan: each step with its verify check, taken from the task's Tasks and Acceptance sections. Ask about anything ambiguous before writing code (CLAUDE.md guideline 1).
3. Implement only what the task lists. Ideas beyond it: mention them, do not build them.
4. Verify every Acceptance bullet and say how each was checked. If one cannot be checked here (for example Docker is unavailable in WSL), say so explicitly; do not count it as passed.
5. Run the `check` skill.
6. If folders or top-level files changed, update the "Project structure" section of `README.md`.
7. When every acceptance bullet is met, add the `**Status:** done (YYYY-MM-DD)` line to the task file. Otherwise leave it unmarked and list what is open.
8. Update the "Roadmap progress" table in `.plans/plans.md` to match (status, notes, date).
9. Do not commit; the user asks for that separately (`commit` skill).

One task per run unless the user asks for more.
