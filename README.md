# LinkGuard

Phishing link warning system. Paste a suspicious link, get a risk level, the reasons it looks dangerous, and plain-language advice on what to do next.

CS3 Agile Processes project — CS Group 4: Nicholas Groenewald, Nikoloz Chilachava, Ibrahima Toure Ba, Solomon Sosanya (Dunmi).

Marked on the [project specification](docs/spec/README.md); three sprints (Data Input, Data Visualisation, Knowledge Extraction) with a rotating Scrum Master and Product Owner. See [docs/sprints/README.md](docs/sprints/README.md) for the checklist to finish **before any real work** and the evidence each sprint needs.

## Layout

| Folder | What |
|---|---|
| `frontend/` | React web app |
| `backend/` | FastAPI service that serves the model |
| `ml/` | Data exploration, training, model comparison ([PhiUSIIL dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset)) |

## Workflow

Full rules are in [AGENTS.md](AGENTS.md), which every AI agent reads (`CLAUDE.md` imports it). The short version:

0. Sprint planning done first: roles set, stories pointed with acceptance criteria and assignees, Jira sprint started ([checklist](docs/sprints/README.md)).
1. Work only on tickets **assigned to you in the active sprint** in the [ALG Jira space](https://alprojectcs3.atlassian.net). Tickets are assigned at sprint planning. No ticket, no work. `ALG` is the Jira space key: every branch, commit and PR title starts with `ALG-<n>` so Jira can track it.
2. Branch from `dev`: `feature/ALG-<n>-short-description`
3. Every commit starts with the key: `ALG-12 add subdomain count feature`
4. Open a PR into `dev` titled `ALG-12 Add URL feature extractor`. One approval from a teammate, `Secret scan` green.
5. At the end of each sprint, `dev` merges into `main` through a `Sprint <n> release` PR.

Use exactly **one** ticket key across the branch, commits, PR title and PR body. Jira links and moves whichever tickets it finds there.

## Sprint rules

Strict, for every member and every AI agent. Full wording is in [AGENTS.md](AGENTS.md#sprint-scope-strict).

- **Only your sprint work.** Work only on the tickets assigned to you in the active sprint. Don't build ahead into later sprints, pick up unassigned tickets or other people's work, or build extras beyond the acceptance criteria.
- **Scope changes go through the Scrum Master.** They are agreed at standup and made in Jira. Finished early? Say so at standup.
- **AI agents enforce this.** Before writing code, an agent checks the ticket is in the active sprint, assigned to you, and not Done. If not, it stops.
- **Document every completed ticket in Confluence** (space *Agile LinkGuard*), in your own folder under that sprint's folder. Use one page per ticket, titled `ALG-<n> <summary>`, with what you did, how it works, diagrams or UI flows where useful, evidence and the PR link. A ticket isn't Done until its page exists.

## Setup

Once per clone, turn on the secret-scanning hook (needs [betterleaks](https://github.com/betterleaks/betterleaks): `brew install betterleaks` on Mac) and the commit message template, which pre-fills the `ALG-<n> summary` format:

```bash
git config core.hooksPath .githooks
git config commit.template .gitmessage
```

On Windows, enable Developer Mode and clone with `git clone -c core.symlinks=true ...` so the `.claude/skills` symlinks work.

## AI agents and skills

| You use | Skills live in |
|---|---|
| Claude Code | `.claude/skills/` (symlinks) |
| Codex or another agent | `.agents/skills/` (real files) |

Add skills with `npx skills add <repo> -s <skill> -a claude-code -a codex` so both folders stay in sync. For any UI work, load `ui-ux-pro-max` first. Jira skills (`/to-tickets`, `/triage`, `/wayfinder`) need the Atlassian MCP server, configured in `.mcp.json`.
