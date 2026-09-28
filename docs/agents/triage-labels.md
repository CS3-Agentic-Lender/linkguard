# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the Jira labels used in the `LG` space.

| Label in mattpocock/skills | Label in our tracker   | Meaning                                              |
| -------------------------- | ---------------------- | ---------------------------------------------------- |
| `needs-triage`             | `needs-triage`         | Team needs to evaluate this item                     |
| `needs-info`               | `blocked`              | Waiting on a team decision or missing information    |
| `ready-for-agent`          | `ready-agent-assisted` | Fully specified; the owner builds it with an agent and reviews every change |
| `ready-for-human`          | `ready-for-human`      | Needs a person: external accounts, design or judgment calls, manual checks (e.g. model results, UI on a real browser) |
| `wontfix`                  | `wontfix`              | Will not be actioned                                 |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Every ticket has a human assignee. Work is agent-assisted, never unattended: each team member must be able to explain what they shipped.

Category roles map to Jira work types, not labels: `bug` is a **Bug** work item, `enhancement` is a **Story** or **Task**.

State labels sit alongside the subsystem labels (`data`, `ml`, `backend`, `frontend`, `docs`); set both.
