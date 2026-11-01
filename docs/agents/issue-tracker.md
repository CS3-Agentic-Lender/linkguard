# Issue tracker: Jira

Issues and specs for this repo live in Jira, space `ALG` on https://alprojectcs3.atlassian.net (cloudId `dac36108-4e6e-4fa6-93ce-26b9ce88b6f4`). Use the Atlassian MCP tools for all operations.

The same site also hosts space `AL`, another team project. Every JQL query includes `project = ALG`, and every create uses `projectKey: "ALG"`. Never touch `AL` tickets.

If the Atlassian tools are unavailable, stop and ask the user to connect the Atlassian Rovo MCP server (`https://mcp.atlassian.com/v2/mcp`; Claude Code picks it up from `.mcp.json`). Work lives only in Jira; GitHub Issues are not used.

## Structure

- **Epic**: a group of related user stories from the product backlog, grouped by user value. Who does the work shows in the assignee and subsystem label, not the epic.
- **Story**: one user story, parented to its epic.
- **Task**: technical or non-feature work (setup, CI, docs, retros), parented to an epic when one fits.
- **Bug**: a fault found in testing.
- **Subtask**: one person's piece of a story.

Every item carries one subsystem label (`data`, `ml`, `backend`, `frontend`, `docs`) and, once triaged, one state label from `triage-labels.md`.

## Conventions

- **Create an issue**: `createJiraIssue` with `projectKey: "ALG"`, `issueType`, `summary`, `description` (markdown), `parent` (the epic key), and `labels`.
- **Read an issue**: `getJiraIssue`.
- **List issues**: `searchJiraIssuesUsingJql`, e.g. `project = ALG AND labels = needs-triage AND statusCategory != Done ORDER BY created ASC`.
- **Comment on an issue**: `addOrEditJiraIssueComment`.
- **Apply / remove labels**: `editJiraIssue` with `labels`. This replaces the whole list, so read the current labels first and write the full updated list.
- **Close**: comment, then `transitionJiraIssue` to Done.

Branch, commit and PR titles must contain the Jira key (`ALG-12`) so GitHub for Atlassian links them to the ticket. See the key rules in `AGENTS.md`.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(PRs live in GitHub and are reviewed there; `/triage` reads this flag.)_

## When a skill says "publish to the issue tracker"

Create a Jira issue in space `ALG`.

## When a skill says "fetch the relevant ticket"

Run `getJiraIssue` on the `ALG-<n>` key.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single Jira Task with **child** Tasks as tickets.

- **Map**: a Task labelled `wayfinder-map`, holding the Notes / Decisions-so-far / Fog body in its description.
- **Child ticket**: a Task labelled `wayfinder-<type>` (`research`/`prototype`/`grilling`/`task`), linked to the map with a `Relates` link, with `Part of ALG-<map>` as the first description line. Once claimed, it is assigned to the driving dev.
- **Blocking**: a `Blocks` issue link via `createIssueLink`. For "A is blocked by B" pass `inwardIssue: B`, `outwardIssue: A`. A ticket is unblocked when every blocker is Done.
- **Frontier query**: `project = ALG AND issue in linkedIssues("ALG-<map>") AND labels != wayfinder-map AND statusCategory != Done AND assignee is EMPTY`, then drop any with an open blocker; first in map order wins.
- **Claim**: `editJiraIssue` setting `assignee` to the current user (`atlassianUserInfo` gives the account id), as the session's first write.
- **Resolve**: comment with the answer, transition to Done, then append a context pointer (gist + key) to the map's Decisions-so-far.
