# Jira standard

How we write, check and run tickets in space `ALG`. Read this before creating or refining any ticket. The hierarchy, the refinement rule, sprint discipline and the branch and key rules live in `AGENTS.md`; this file covers what a ticket must contain and how it moves.

Jira is the source of truth for tickets. [`docs/backlog/product-backlog.md`](../backlog/product-backlog.md) is the backlog as it was first loaded.

## 1. Fields every ticket needs

| Field | Epic | Story | Subtask | Task | Bug |
|---|---|---|---|---|---|
| Summary: short, plain, starts with a verb (epics: a noun phrase) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Description in the section 2 layout | ✓ | ✓ | ✓ | ✓ | ✓ |
| Parent | | epic | story | epic, when one fits | epic, when one fits |
| One subsystem label: `data`, `ml`, `backend`, `frontend`, `docs` | ✓ | ✓ | ✓ | ✓ | ✓ |
| One state label, once triaged ([triage-labels.md](triage-labels.md)) | | ✓ | ✓ | ✓ | ✓ |
| Priority: Must = High, Should = Medium, Could = Low | | ✓ | | ✓ | ✓ |
| At least one Subtask | | ✓ | | | |
| Story points (1, 2, 3, 5, 8, 13) | | set at planning | none | | |
| Assignee | | set at planning | set at planning | set at planning | set at planning |
| Links to related tickets (Jira issue links, never a key in the text) | when related | when related | | when related | when related |

A ticket touching two subsystems takes the label of where most of its work sits. Each Subtask carries the label of its own piece.

## 2. Description layout

Plain, simple words that a teammate new to the area can follow. Numbered criteria a reviewer can check by looking or running something; "the code runs" is never a criterion. No other ticket's key anywhere in the text.

**Epic**
```
## Goal
What users get once every story in this epic is done, in one or two sentences.

## Use case
Actor: <who>
1. <step the actor takes>
2. <what LinkGuard does>
What can go wrong: <alternative paths>
```

**Story**
```
## User story
As a <data analyst | ML engineer | developer | user>, I want <goal>, so that <reason>.

## Spec            (only when fields, rules or values need pinning down)
...

## Acceptance criteria
1. At least three, each checkable.
2. Given / when / then is welcome for behaviour.

## Deliverables
- Wireframe (any story with a screen)
- Test case for each acceptance criterion
- <data reports, charts or tables the criteria call for>
```

**Subtask**
```
## What to build
One or two sentences: one person's piece of the parent story.

## Done when
1. A checkable outcome.
```

**Task**
```
## What and why
...

## Acceptance criteria
1. ...
```

**Bug**
```
## What happened
## Steps to reproduce
1. ...
## Expected
## Acceptance criteria
1. The steps above give the expected result.
2. A test covers it.
```

## 3. Creating a ticket

1. Interview the person raising it: the user story or problem, the criteria, the parent, the label and the priority. Ask; don't fill the gaps yourself.
2. Draft it in the section 2 layout, in their words.
3. Create it once they confirm. New work goes to the backlog with `needs-triage`.
4. It enters a sprint only when the team pulls it in at planning (see Sprint discipline in `AGENTS.md`).

Work found mid-ticket becomes a new ticket this way. It is never built inside the current one.

## 4. The alignment check

Run on every ticket when refining the backlog, and on any new ticket before it leaves `needs-triage`. A ticket passes when all of these hold:

1. **Traceable.** It serves the brief ([docs/spec/README.md](../spec/README.md): data input, visualisation, knowledge extraction, DevOps) or the proposal ([Project Proposal CS Group 4.pdf](../Project%20Proposal%20CS%20Group%204.pdf)).
2. **Right home.** Its parent epic matches the user value it delivers, and its type matches the section 1 table.
3. **Consistent with what we know.** Nothing contradicts [docs/research/](../research/), for example the PhiUSIIL label being inverted and its leakage findings.
4. **Unique.** No other ticket covers the same work. Overlaps are merged or split, with a link between them.
5. **Complete.** Every section 1 field for its type is filled, apart from points and assignee, which wait for planning.
6. **Sized.** A story fits one sprint and splits into Subtasks of a few days each. Anything that would take 13 points or more is split now.
7. **Plain.** Section 2 wording rules hold.

A refinement only changes how a ticket is described, never what work it is. Draft each change, get the Product Owner's agreement, then post it with a comment saying what changed and why (see Refining a ticket in `AGENTS.md`).

## 5. Story points

- Scale: 1, 2, 3, 5, 8, 13. Points size stories against each other; they are not hours.
- Anyone may suggest a number. The team agrees it at planning poker.
- A story at 13 or more is split before it enters a sprint.
- Subtasks, Tasks and Bugs carry no points.

## 6. Sprint cycle

1. **Plan:** set the sprint goal, pull in stories that fit (from Sprint 2, sized by last sprint's velocity), point them, and give every Subtask an assignee.
2. **Start:** start the sprint in Jira with dates. This starts the burndown.
3. **Run:** standups; status moves To Do, In Progress, In Review, Done, driven by the branch, PR and merge automation.
4. **Review:** demo what is Done. Unfinished stories go back to the backlog.
5. **Retro:** what went well, what went wrong, what changes. Each action becomes a ticket for the next sprint.

The full checklist and the evidence each sprint needs are in [docs/sprints/README.md](../sprints/README.md).

The burndown stays honest only while:
- every story in the sprint has points before it starts;
- a story added mid-sprint has team agreement and a comment saying why;
- Jira status matches reality.
