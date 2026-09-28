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

- Work is tracked in Jira (space `LG`).
- Branch off `dev` named after the ticket: `LG-12-url-feature-extraction`.
- Put the ticket key in commit messages and PR titles so they link to Jira.
- PR into `dev`. `dev` → `main` via PR at the end of each sprint.
