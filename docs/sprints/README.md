# Sprint process

Three sprints, matching the spec: **1 Data Input, 2 Data Visualisation, 3 Knowledge Extraction**. Every sprint delivers a thin end-to-end slice across all four subsystems (`data`, `ml`, `backend`, `frontend`), and the sprint goal is worded around its stage. Between sprints we review each other's work and write new tickets for what needs improving, then start the next sprint.

## Roles (rotate every sprint)

The Scrum Master is different each sprint (spec requirement). The PO also rotates, and the PO and SM are never the same person in a sprint.

| Sprint | Scrum Master | Product Owner |
|---|---|---|
| 1 | Nic | Dunmi (Solomon Sosanya) |
| 2 | TBC at Sprint 1 retro | TBC |
| 3 | TBC at Sprint 2 retro | TBC |

- **Scrum Master**: runs planning, standups and retro, keeps Jira accurate, chases blockers, produces the sprint doc.
- **Product Owner**: owns the order of the backlog, writes and signs off acceptance criteria, accepts or rejects finished stories.

## Before any real work (checklist)

Do these in order. Nothing is coded until all are done.

1. **Roles set**: SM and PO for this sprint written in the table above (SM has not been SM before, SM is not PO).
2. **Backlog ready**: every story has a description, acceptance criteria, **priority**, a subsystem label (`data`, `ml`, `backend`, `frontend`, `docs`) and the epic as parent.
3. **Sprint planning meeting held**: sprint goal written; stories pulled into the sprint; each story **pointed together** (1, 2, 3, 5, 8) and given one human assignee. Workload is balanced across the four members.
4. **Jira sprint started** with start and end dates (the burndown chart is empty without dates and points).
5. **Pick a ticket**: assign it to yourself and read it in Jira. The key must be `ALG-<n>`, the Jira space key. Never invent one; a key that 404s is the wrong key.
6. **Branch from up-to-date `dev`**: `git fetch origin && git switch -c feature/ALG-<n>-short-description origin/dev`.
7. **Secret scan hook and commit template on**: `git config core.hooksPath .githooks` and `git config commit.template .gitmessage`.
8. Then work, commit as `ALG-<n> summary`, open a PR into `dev` titled `ALG-<n> Summary`, with exactly one key everywhere.

## During the sprint

- Standup at least twice a week; record attendance and a few lines of minutes in the sprint doc.
- Move tickets on the board as they change; Jira automation moves them from branch, PR and merge events.
- Keep the team chat active; it is graded evidence.

## End of sprint

1. Take a **screenshot of the Kanban board** and export the **burndown chart**.
2. Hold the **retrospective** and write notes: velocity achieved (points done), what went well, issues to improve with proposed fixes.
3. **Peer review**: each member reviews another member's area and writes new tickets for improvements.
4. Open the `Sprint <n> release` PR from `dev` to `main` (no ticket key in title or body).
5. Choose the next SM and PO.
6. Complete `docs/sprints/sprint-<n>.md` (copy [sprint-template.md](sprint-template.md)).

## Evidence each sprint must have

| Item | Where |
|---|---|
| Scrum Master name, sprint goal | sprint doc |
| Burndown chart | Jira report, saved as an image in `docs/sprints/` |
| Sprint backlog: definition, points, assignee, acceptance criteria (optional: subtasks, priority, dates) | Jira, listed in sprint doc |
| Kanban screenshot at end of sprint | `docs/sprints/` |
| Retro notes: velocity, positives, issues and fixes | sprint doc |
| Deliverable description and git link | sprint doc |
| Attendance records and minutes; chat group export or screenshot | sprint doc |

## Submissions

Interim report after Sprint 2, final report after Sprint 3, then the presentation. See [docs/spec/README.md](../spec/README.md) for the rubric.
