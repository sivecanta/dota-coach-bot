---
name: plans
description: Create, list, continue and update numbered feature plans in the personal, gitignored .plans/ folder. Use when the user wants to plan a feature, asks what is planned or in progress, wants to continue or resume a plan, or to change a plan's status (start, done, blocked, drop).
---

# Plans

Personal feature plans live in `.plans/` (gitignored). Never commit them.

```
.plans/
  plans.md            index: one row per plan with status
  N_feature_name.md   one file per plan, N = incremental number
  roadmap/            phased roadmap of the whole project (reference, not numbered plans)
```

## Numbering
Read `.plans/plans.md`, take the highest number and add 1 (first plan is `1_`, then `2_` ... `13_`). Never reuse a number, even for dropped plans. File name: `N_snake_case_feature.md`.

## Statuses
`near` (planned soon), `in progress`, `far` (later), `completed`, `blocked` (always give the reason in Notes), `dropped`.

## Modes

**new `<feature>`**: 
1. Analyze first: read the relevant code, `.project/ARCHITECTURE.md`, and any matching `.plans/roadmap/` task. Do not plan from assumptions.
2. Ask the user about anything ambiguous before writing (see CLAUDE.md guideline 1).
3. Write `N_feature_name.md` from the template below.
4. Add a row to `plans.md` with status `near` (or what the user says) and today's date.

**list**: show `plans.md`, grouped by status in this order: in progress, near, blocked, far, completed.

**start N**: set `in progress` in the index and update the date. Only one plan should normally be in progress; mention it if another is.

**continue N**: read the plan file, summarize where it stands from the Progress log, check the code for steps already done, then resume at the first unfinished step. Update checkboxes and the log as you go.

**done N / block N `<reason>` / drop N / move N `<status>`**: update the index row and date, and append a line to the plan's Progress log.

Keep `plans.md` and the plan file in sync on every change, including the Updated date (absolute dates, `YYYY-MM-DD`).

`plans.md` also has a "Roadmap progress" section. Whenever a roadmap task is finished, started or found already done, update that table and its date in the same change (the `roadmap-task` skill does this after marking a task).

## Plan template

```markdown
# N. Feature name

**Status:** near | **Created:** YYYY-MM-DD | **Roadmap:** roadmap/phase_X/K_name.md (if any)

## Goal
One or two sentences. What is true when this is done.

## Analysis
- What exists today (files, modules involved).
- Layers affected (bot / agent / services / clients / storage).
- Risks and unknowns.

## Assumptions and open questions
- ...

## Steps
- [ ] 1. Step -> verify: how to check it
- [ ] 2. Step -> verify: ...

## Out of scope
- ...

## Progress log
- YYYY-MM-DD: created
```

Rules: steps small and each with a verify check; no speculative extras; keep it as short as the feature allows.
