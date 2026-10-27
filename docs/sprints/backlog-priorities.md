# Backlog priorities

- **Decided by**: Dunmi (Solomon Sosanya), Product Owner for Sprint 1
- **Date**: 27 October 2026
- **Agreed by the team**: [to add: standup date]

## Who sets the priorities

The lecturer confirmed by email on 26 October 2026 that she is the customer, not the Product Owner, and that a team member is Product Owner each sprint. So the Product Owner sets the backlog priorities. Her replies are attached to the Jira ticket for this decision.

## How the split was measured

Priorities use MoSCoW, mapped to Jira as Must = High, Should = Medium, Could = Low. The guideline is Musts at no more than about 60% of the effort, with some Coulds held back as contingency ([research notes](../research/backlog-inputs.md)).

The split counts the story points of every Story and Task. Epics and Subtasks carry no points. A few tickets without points are left out: set-up work finished before Sprint 1, and new tickets not yet triaged.

| | Must | Should | Could | Total | Must share |
|---|---|---|---|---|---|
| Full backlog | 118 | 43 | 9 | 170 | 69% |
| In scope, before this decision | 112 | 18 | 0 | 130 | 86% |
| **In scope, after this decision** | **107** | **23** | **0** | **130** | **82%** |

"In scope" leaves out the twelve tickets descoped with the Product Owner (see the Project Scope page in Confluence). Descoping removed almost every Should and every Could, which is why the in-scope Must share is so much higher than the full backlog's.

## Decision

Each Must was checked with the MoSCoW test: would we cancel the project without it? Two failed the test and move to Should:

| Story | Points | Was | Now | Why |
|---|---|---|---|---|
| Rank the features and choose the final list | 3 | Must | Should | The model can train on all 19 URL features from the shared extractor without a ranking step. Ranking still improves the model and the write-up. |
| Build and test the frontend on every pull request | 2 | Must | Should | The backend and ml code are already built and tested on every pull request, and the secret scan runs on every PR, so the pipeline works without it. |

The other 107 Must points stay Must. They are the minimum the brief asks for, in three one-week sprints:

| Area | Must points |
|---|---|
| Data input: import, clean, leakage check, cleaning report | 10 |
| Link input: paste a link, backend checks, clear errors | 9 |
| Features: shared extractor, template-bias decision, training feature set | 13 |
| Result card, its /scan wiring and the shared design tokens | 9 |
| Model: train and compare, training pipeline, risk level, serve in /scan | 11 |
| Evaluation: test-split results, risk-level cut-offs, evaluation report | 7 |
| Explain and advise: reasons and next-step advice | 13 |
| DevOps: backend and ml checks on every PR, test runners | 4 |
| Project: priorities, SMART objectives, interim and final reports, presentation | 31 |
| **Total** | **107** |

Moving the roughly 34 more points needed to reach 60% would mean calling core parts of the brief optional, such as the reasons and advice the proposal promises. That would make the priorities less honest, not more useful.

## What this means for the sprints

- There is no Could buffer. The 23 Should points are the contingency: if a sprint runs short, Shoulds move to a later sprint or out of scope first, agreed with the Product Owner.
- Every priority change is in Jira, with a comment on each changed ticket.
- The next sprint's Product Owner reviews the split at Sprint 2 planning.
