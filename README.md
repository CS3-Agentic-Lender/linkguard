# LinkGuard

Phishing link warning system. Paste a suspicious link, get a risk level, the reasons it looks dangerous, and plain-language advice on what to do next.

CS3 Agile Processes project — CS Group 4: Nicholas Groenewald, Nikoloz Chilachava, Ibrahima Toure Ba, Solomon Sosanya.

## Layout

| Folder | What |
|---|---|
| `frontend/` | React web app |
| `backend/` | FastAPI service that serves the model |
| `ml/` | Data exploration, training, model comparison ([PhiUSIIL dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset)) |

## Workflow

Full rules are in [AGENTS.md](AGENTS.md), which every AI agent reads (`CLAUDE.md` imports it). The short version:

1. Pick a ticket in the [LG Jira space](https://alprojectcs3.atlassian.net) and assign it to yourself. No ticket, no work.
2. Branch from `dev`: `feature/LG-<n>-short-description`
3. Every commit starts with the key: `LG-12 add subdomain count feature`
4. Open a PR into `dev` titled `LG-12 Add URL feature extractor`. One approval from a teammate, `Secret scan` green.
5. At the end of each sprint, `dev` merges into `main` through a `Sprint <n> release` PR.

Use exactly **one** ticket key across the branch, commits, PR title and PR body. Jira links and moves whichever tickets it finds there.

## Setup

Once per clone, turn on the secret-scanning hook (needs [betterleaks](https://github.com/betterleaks/betterleaks): `brew install betterleaks` on Mac):

```bash
git config core.hooksPath .githooks
```

On Windows, enable Developer Mode and clone with `git clone -c core.symlinks=true ...` so the `.claude/skills` symlinks work.

## AI agents and skills

| You use | Skills live in |
|---|---|
| Claude Code | `.claude/skills/` (symlinks) |
| Codex or another agent | `.agents/skills/` (real files) |

Add skills with `npx skills add <repo> -s <skill> -a claude-code -a codex` so both folders stay in sync. For any UI work, load `ui-ux-pro-max` first. Jira skills (`/to-tickets`, `/triage`, `/wayfinder`) need the Atlassian MCP server, configured in `.mcp.json`.
