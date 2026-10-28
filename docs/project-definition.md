# Project definition and objectives

What LinkGuard is for, who it is for, what is in and out of scope, and the SMART objectives the final report checks against evidence. Restated from the [project proposal](Project%20Proposal%20CS%20Group%204.pdf).

## 1. The problem

Most scams now start with a link. A text says a parcel is held, a bank account is locked or a Revenue refund is waiting, and the link opens a fake site built to steal a login or card details. These sites are getting harder to spot: they copy real logos, use HTTPS, and pick web addresses that look almost identical to the real ones.

The question LinkGuard answers: **how can an ordinary person tell whether a link is safe before they click it and hand over their details?**

## 2. The users

Ordinary people who get suspicious links by text, email or message. Phishing hurts most those who can't spot it, such as older people and anyone not confident online. Today's advice, "check the URL carefully", asks them to act like security experts. LinkGuard checks the link for them and explains the warning signs in plain language, so it also teaches them what to look for next time.

## 3. Scope

**In scope.** A web app where a user pastes a link and gets back:

- a risk level: safe, suspicious or high risk;
- the specific reasons the link looks dangerous;
- clear advice on what to do next.

It is built from a React frontend, a Python FastAPI backend and a classification model trained on the PhiUSIIL Phishing URL Dataset (UCI, 235,795 labelled URLs: 134,850 legitimate, 100,945 phishing). It is delivered over three one-week sprints that follow the brief's stages:

| Sprint | Stage | Slice |
|---|---|---|
| 1 | Data Input | A pasted link is cleaned, checked and turned into features, on a cleaned dataset, with CI on every pull request (sprint goal in Jira) |
| 2 | Data Visualisation | Charts of the dataset, plus the result card that shows a link's risk level and reasons (direction agreed at the 27 Oct standup, confirmed at Sprint 2 planning) |
| 3 | Knowledge Extraction | <!-- TBC at Sprint 3 planning --> |

**Out of scope for this project.** To fit three one-week sprints, the team descoped these with the Product Owner. The stories stay in the backlog for later:

- **Scan history:** saving a person's checks, seeing them in a table or a chart, and keeping one person's checks apart from another's without personal details.
- **Feedback:** asking "Was this right?" on each result, and saving and exporting that feedback.
- **Outside test set:** collecting links from outside PhiUSIIL and scoring the model on them.
- **Lookalike warning:** warning when a link copies a well-known website.
- **Public deploy:** hosting the demo at a public address and documenting the deploy steps.
- **Phone and large text:** a layout built for phones and large text settings.

## 4. Limits of the first version

Our research on the dataset ([docs/research/phiusiil-features.md](research/phiusiil-features.md)) sets these limits:

- **The model only looks at the link itself.** About half of PhiUSIIL's features (28 of 54) come from the web page, such as the page title, password fields and hidden form fields. LinkGuard can only fetch a page through the backend's sandboxed fetcher, which doesn't exist yet, and phishing pages often go offline within hours. So the first version cannot give reasons based on the page title or hidden forms, even though the proposal lists them as examples.
- **Some dataset columns leak the answer.** `URLSimilarityIndex` is exactly 100 for every legitimate row, so it is dropped. URL features are recomputed from the raw link with the same code the backend runs at scan time.
- **Test-split scores flatter the model.** PhiUSIIL's legitimate links share a template, so a model can score about 99% on its own test split for the wrong reasons. The test-split result is reported with that caveat.

## 5. SMART objectives

Each objective names how it is measured and the sprint it is due by. The final report checks each one against this evidence.

| # | Objective | Measured by | Target | Sprint |
|---|---|---|---|---|
| O1 | Turn the raw PhiUSIIL download into a cleaned dataset that any teammate can rebuild exactly, with no duplicate or invalid rows and the label recoded so phishing = 1 | The ml tests pass in CI, and Nic re-runs the cleaning notebook on a fresh download | Same row count (235,370) on both runs, 0 duplicates, 0 invalid values, label tests green | 1 |
| O2 | Train a model that catches as many phishing links as possible without flagging everything, using only features we can compute from the link at scan time | Phishing recall and precision on the PhiUSIIL test split, with the leaking columns removed, reported as an upper bound (see section 4) | Recall ≥ 95%, precision ≥ 80% | 3 |
| O3 | Every warning tells the user why the link looks like a scam, using evidence from the link itself, how confident the model is, and what to do next, in plain language | API tests on suspicious and high-risk results, plus a check with 5 family members or friends who read sample results | 100% of warnings show at least one link-based reason, a confidence %, and advice. At least 4 of 5 readers can say back why the link is risky and what to do | 3 |
| O4a | A scan never opens, fetches or follows the pasted link: the link is only ever handled as text | The backend's `no_network` test, which fails if a scan attempts any outgoing connection, runs in CI on every pull request | 0 outgoing connections, test green on every PR | 1 |
| O4b | A user gets their result quickly enough not to give up waiting | A script sends 100 scans to the running backend with the real model loaded and records the time each takes | 95% of scans (p95) answer in under 2 seconds | 3 |
| O5 | Make the finished app usable by people who are less confident online or use assistive technology | An axe scan of every screen, plus a manual pass: keyboard only, 200% zoom, a screen reader (VoiceOver or NVDA) | 0 axe violations at WCAG 2.2 AA, and every manual check passes | 3 |

Each screen is also checked against the accessibility criteria as it is built, through the Definition of Done's UX check ([product-backlog.md](backlog/product-backlog.md)). O5 is the final check on the finished app.

## 6. Agreement

Dunmi agreed this page as the Sprint 1 Product Owner at the standup on 27 October 2026, with one change: O2's scores are reported as an upper bound. The rest of the team agreed in the same thread. The minutes are on the [14. Daily Scrum Meetings](https://alprojectcs3.atlassian.net/wiki/spaces/AGILE/pages/33292289/14.+Daily+Scrum+Meetings) page in Confluence.
