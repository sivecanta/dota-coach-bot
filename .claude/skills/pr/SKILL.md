---
name: pr
description: Write a short bulletpoint description for the current branch and open a pull request (merge request) with it. Use when the user asks for a PR/MR description, to open or create a PR/MR, or to push and submit the branch.
---

# Pull request

The remote is GitHub, so an "MR" is a pull request. Open it only when the user asks.

## Workflow
1. Find the base: `main`. Refuse to open a PR from `main`; tell the user to branch first.
2. Gather the changes: `git log main..HEAD --oneline`, `git diff main...HEAD --stat`, plus `git status --short`. Read key new files if the diff alone is unclear.
3. If uncommitted or untracked work exists, tell the user it will not be in the PR and offer the `commit` skill. Do not commit unprompted.
4. Draft the description (format below) and show it to the user.
5. Pushing and creating the PR are outward-facing: confirm with the user before running them, unless they already said to open it.
6. Push: `git push -u origin <branch>`.
7. Create: `gh pr create --base main --title "<title>" --body-file <file>`. Write the body to a file in the scratchpad dir. Add `--draft` if the user asks.
8. If `gh` is missing or unauthenticated, do not retry other ways. Print the title and body for pasting and tell the user to run `gh auth login` or install `gh`.
9. Report the PR URL.

## Title
Conventional Commits style, like the commit skill: `<type>(<scope>): <summary>`, imperative, lowercase, max ~72 chars. For a mixed branch use the dominant type.

## Body
Short, bulletpoints only, no prose paragraphs:
```
**Summary**
- <what changed, grouped by area; one line each, max ~6 bullets>

**Tests**
- <tests added or changed; how it was verified>
```
- Describe what and why, not file-by-file lists.
- Mention migrations, new env vars or breaking changes explicitly as their own bullet.
- Only claim tests that exist; check the diff. If none, omit the section.
- End the body with the attribution line given in the session's system reminder for pull requests, if there is one.
