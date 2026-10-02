---
name: commit
description: Commit conventions and workflow for this repo. Use whenever the user asks to commit, create a commit, or split changes into commits (never commit unprompted).
---

# Commit

Commit only when the user asks. Never push unless asked.

## Workflow
1. `git status` and `git diff` (staged and unstaged) to see what will be committed; check recent `git log --oneline` for style.
2. Run `make lint` and `make test` (or `uv run ...`) first if code changed; do not commit a failing tree unless the user says so.
3. If a folder or top-level file was added, renamed, moved or removed, check that the "Project structure" section of `README.md` reflects it; update it in the same commit if not.
4. Group changes into logical commits (one concern each). Stage files explicitly by path, not `git add -A`.
5. Never commit: `.env`, secrets, `data/`, anything under `.plans/` (gitignored). If such a file shows up in status, stop and tell the user.
6. After committing, show `git log --oneline -n <count>`.

## Message format
Follow Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
```
<type>(<scope>): <summary>

<optional body: what and why, wrapped at ~72 cols>

<optional footers, e.g. BREAKING CHANGE: ..., Refs: #12>
```
- Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`.
- Scope (optional): the area, e.g. `bot`, `agent`, `services`, `opendota`, `storage`, `charts`, `docker`, `deps`.
- Summary: imperative, lowercase, no trailing period, max ~72 chars ("add match tracker", not "added...").
- Body only when the why is not obvious from the diff. `feat` and `fix` are the spec's core types (minor and patch bumps). Breaking change: `!` before the colon (`feat(api)!: ...`) and/or a `BREAKING CHANGE: <description>` footer. Body and footers are separated from the summary by a blank line.
- End with the attribution trailer given in the session's system reminder, if there is one.

## Branches
Work on a feature branch, not `main`: `feat/<short-name>`, `fix/<short-name>`. Create one before the first commit if on `main`.
