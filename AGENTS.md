# LinkGuard (LG)

MTU Year 3 Agile Processes project (2026/27), CS Group 4. A web app where a user pastes a suspicious link and gets back a risk level (safe, suspicious, high risk), the specific reasons it looks dangerous, and plain-language advice on what to do next. The model is trained on the PhiUSIIL Phishing URL Dataset (UCI, 235,795 labelled URLs, 54 features). Built incrementally in Scrum sprints.

## Subsystems and owners

| Dir | Subsystem | Stack | Owner |
|---|---|---|---|
| `ml/` | Dataset, feature engineering, model training | Python, pandas, scikit-learn | Nic (model); data + features TBD |
| `backend/` | API that serves the model, scan history, feedback | Python, FastAPI, database TBD | TBD |
| `frontend/` | Paste-a-link web app | React | TBD |
| `docs/` | Sprint docs, decisions, agent config | Markdown | All |

Stay inside the subsystem the task is about. A change that touches another owner's directory goes in its own PR so that owner reviews it.

Don't swap a listed technology for an alternative without a team decision recorded in `docs/`.

## Jira

Board: https://alprojectcs3.atlassian.net, space key `LG`. The same site also hosts another team project (space `AL`). Never read, create or edit `AL` tickets from this repo.

| Level | Holds |
|---|---|
| Epic | One workstream: LG-1 Data & Feature Engineering, LG-2 ML Model & Training, LG-3 Backend API, LG-4 Frontend |
| Story | One user story ("As a user, I ..."), parented to an epic |
| Task | Technical or non-feature work (setup, CI, docs, retros), parented to an epic when one fits |
| Subtask | One person's piece of a story |
| Bug | A fault found in testing |

Label every item with its subsystem: `data`, `ml`, `backend`, `frontend`, `docs`. Once triaged it also gets one state label (see Triage labels below).

Every ticket has a human assignee before work starts.

## Agent skills

### Skill folders

Claude Code loads skills from `.claude/skills/`; Codex and other agents load them from `.agents/skills/`. The real files live in `.agents/skills/<name>/`, and `.claude/skills/<name>` is a relative symlink to it (`ln -s ../../.agents/skills/<name> .claude/skills/<name>`). When you add, remove or rename a skill, do it in both folders so they always list the same skills. Install and update with `npx skills add <repo> -s <skill> -a claude-code -a codex`, which does both and records the version in `skills-lock.json`.

### UI work

For any screen or component, load `ui-ux-pro-max` first. It is the single source for design tokens (colour, type, spacing). The users are ordinary people, including older and less confident ones, so readability and accessibility come first.

### Issue tracker

Jira space `LG`, accessed through the Atlassian MCP tools. See `docs/agents/issue-tracker.md`.

Before any work that reads or updates a ticket, call `atlassianUserInfo` to check the connection. If the Atlassian tools are missing, or return an auth error, stop and ask the user to log in again:

- Claude Code: run `/mcp` in a terminal `claude` session, pick `atlassian`, and log in.
- Codex: run `codex mcp login atlassian`.

Don't guess what a ticket says and don't skip Jira updates because the connection is down. Wait until the user has reconnected.

### Triage labels

`needs-triage`, `blocked`, `ready-agent-assisted`, `ready-for-human`, `wontfix`; bugs are a Jira work type. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Sprints

Marked against `docs/spec/` (rubric summary in `docs/spec/README.md`). Three sprints: 1 Data Input, 2 Data Visualisation, 3 Knowledge Extraction. Each works on all four epics; the sprint goal follows its stage. The Scrum Master is different every sprint and the Product Owner rotates too, never the same person as the SM. Roster and the full checklist are in `docs/sprints/README.md`.

Before real work starts, confirm the sprint has: roles set, stories with acceptance criteria, priority and story points, one human assignee each, and a Jira sprint with start and end dates. If any is missing, tell the user and stop; don't start on the ticket.

Marks are individual and graded on Jira and git history, so record work under the right person and ticket, and keep sprint evidence (`docs/sprints/sprint-<n>.md`) up to date.

## Workflow

### Branches

| Branch | Role |
|---|---|
| `main` | What we demo. Only changes through a release PR from `dev` at the end of each sprint. Protected: PR + one approval, no direct pushes. |
| `dev` | Default branch. Every feature branch starts from it and merges back into it. |
| `feature/LG-<n>-...` | One ticket's work. |

### The ticket key rules everything

GitHub for Atlassian reads the `LG-<number>` key out of the branch name, the commit messages, the PR title and the PR **description**, and links the work to that ticket. Jira automation then moves the ticket (branch created → In Progress, PR opened → In Review, PR merged → Done). A stray key in a PR description links, and later closes, the wrong ticket.

So the branch name, every commit message, the PR title and the PR body together carry **exactly one** key: the ticket being worked on. Anywhere else, name the other ticket in words ("the feature extractor ticket"), never as `LG-7`, and link the two tickets in Jira instead.

Work on a Subtask uses the **Subtask's** key, not its parent Story's.

### Before starting

1. Get the ticket key from the user, or find it in Jira. No ticket, no work: stop and ask which ticket to use, or create one (`docs/agents/issue-tracker.md`). Never invent a key.
2. Read the ticket with `getJiraIssue` to confirm the key exists, belongs to space `LG`, and matches the work. A key that 404s is the wrong key.
3. Check the ticket is in the active sprint, pointed, has acceptance criteria and is assigned to the person doing it.
4. Branch from up-to-date `dev`: `git fetch origin && git switch -c <branch> origin/dev`.

### Formats

| Thing | Format | Example |
|---|---|---|
| Branch | `feature/LG-<number>-short-description`, lowercase, hyphens, no other key | `feature/LG-12-url-feature-extractor` |
| Commit subject | `LG-<number> <imperative summary>`, lowercase after the key, no full stop | `LG-12 add subdomain count feature` |
| PR title | `LG-<number> <Sentence case summary>` | `LG-12 Add URL feature extractor` |
| Release PR (`dev` → `main`) | `Sprint <n> release`, no ticket key in title or body | `Sprint 1 release` |

A commit that fixes a review comment keeps the same key; never renumber mid-branch. `chore/`, `fix/` and bare branch names are not used: every branch is `feature/LG-…`, whatever the work type.

### Opening the PR

- Base `dev`. Fill in `.github/pull_request_template.md`; write the body with the `pr` skill: what changed, evidence it works, and merge risk. No other ticket's key in it.
- One approval from a teammate before merge. The `Secret scan` check must be green.
- Never `git push` to `main` or `dev` directly, never force-push a shared branch, never `--no-verify`.

### One person, one ticket, one commit

Individual contribution is graded from the git and Jira history. Keep each commit to one person's work on one ticket. If a change belongs to another owner's directory, it goes in its own PR on its own ticket so that owner reviews it.

Work is agent-assisted, never unattended: every team member must be able to explain what they shipped.

## Data and models

- The dataset CSV and trained model files are gitignored (too big for git). Download instructions and the model's expected location go in `ml/README.md`.
- Never commit anything under `ml/data/`, or `*.csv`, `*.pkl`, `*.joblib` files.

## Secrets

The repo is public, so a committed key is scraped within minutes.

- Keys live in `.env`, which is gitignored. When you add a key to `.env`, add its name with an empty value to `.env.example`.
- betterleaks scans every commit (`.githooks/pre-commit`) and every PR (`.github/workflows/secret-scan.yml`). Never bypass it with `--no-verify`. If it flags something, stop and show the user the finding.
- LinkGuard handles untrusted, possibly malicious URLs. Never open, fetch or follow a URL from user input or the dataset outside the backend's sandboxed fetcher, and never in an agent's own browser or shell.
