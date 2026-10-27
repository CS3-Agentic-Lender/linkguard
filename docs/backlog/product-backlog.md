# LinkGuard product backlog

The product backlog, loaded into Jira space `ALG`. Stories are pulled into sprints at sprint planning, not before. Follows the format the lecturer showed: epics with a short description and colour, user stories with a role, at least three acceptance criteria, subtasks, and attachments where useful. Where the brief is silent, it follows standard Scrum practice (see [docs/research/backlog-inputs.md](../research/backlog-inputs.md)).

## Rules for every item

- **Story format**: *As a [role], I want [goal], so that [reason].* Roles: **data analyst**, **ML engineer**, **developer**, **user** (a member of the public checking a link).
- **Acceptance criteria**: at least 3 per story, each one testable.
- **Subtasks**: each is one person's piece of work, small enough for a few days.
- **Priority**: MoSCoW (Must, Should, Could).
- **Points**: the numbers below are **suggestions only**. The team confirms them together with planning poker (1, 2, 3, 5, 8, 13) at sprint planning. Anything at 13 or more gets split. How hours suggest a number is in section 5 of [docs/agents/jira-standard.md](../agents/jira-standard.md).
- **Product Owner**: each sprint one team member acts as Product Owner (Dunmi for Sprint 1, see [docs/sprints/README.md](../sprints/README.md)), owns the backlog order and accepts finished work. The lecturer is the customer and gives feedback; she confirmed in writing that she is not the PO.
- **Labels**: one subsystem label per story: `data`, `ml`, `backend`, `frontend`, `docs`.

**Definition of Ready** (before a story enters a sprint): description, 3+ acceptance criteria, priority, points, subtasks, assignee.

**Definition of Done** (before a story moves to Done). The same list is on the Confluence stories page; each item says how we meet it.

1. **Tested against the acceptance criteria**: each criterion is checked, with the evidence in the PR.
2. **Approved by the UX designer** (stories that show something on screen): the PO checks the screen against the shared design tokens and the accessibility criteria. In Sprint 1 the PO holds this role, because the PO is also doing the design tokens.
3. **Approved by the Product Owner**: the sprint's PO accepts it on the board.
4. **QA performed**: a teammate reviews the PR and the tests pass in CI.
5. **Documentation and release notes updated**: docs change with the code, and the work is written up in the assignee's sprint summary in Confluence, which serves as the release notes.
6. **Merged into `dev` through a PR.**

## Epics

| # | Epic | Description | Colour |
|---|---|---|---|
| E1 | **Data Processing** | Import the PhiUSIIL phishing dataset, clean it, check it for leakage and normalise it, ready for modelling. | Blue |
| E2 | **Link Input** | Let a user paste a link into the web app, clean what they typed, and save the check. | Green |
| E3 | **Feature Extraction** | Turn any link into the features the model needs, and choose the features that best predict phishing. | Purple |
| E4 | **Data Visualisation** | Show the dataset, each result and each user's past checks in clear tables and charts. | Orange |
| E5 | **Build Models** | Train, compare and tune classifiers, and serve the best one through the API. | Teal |
| E6 | **Model Evaluation** | Measure how well the model really works, including on links from outside the dataset, and set the risk levels. | Yellow |
| E7 | **Explain and Advise** | Tell the user why a link looks risky and what to do next, in plain words. | Red |
| E8 | **DevOps and Quality** | Build, test and scan every change automatically, and optionally deploy a demo. | Grey |

---

## E1 Data Processing

### 1.1 Import the dataset · Must · 2 pts · `data`
*As a data analyst, I want the PhiUSIIL dataset imported into the project, so that the whole team works from one agreed copy.*

Acceptance criteria:
1. The dataset loads with 235,795 rows and 56 columns, and the counts are printed in the notebook.
2. Each column's type is checked against the UCI data description.
3. `ml/README.md` explains how to download the dataset and where to put it. The CSV itself is never committed.
4. The source and licence (UCI, CC BY 4.0) are recorded.

Subtasks: write the download steps · load the CSV in a notebook · check the column types · record the source and licence.
Attachments: data dictionary (column list with types); the first 20 rows as a sample.

### 1.2 Clean the data · Must · 3 pts · `data`
*As a data analyst, I want all the data cleaned, so that the models train only on valid, non-duplicated records.*

Acceptance criteria:
1. Duplicate URLs are found, counted and removed.
2. Missing, empty and out-of-range values are found and fixed or removed, and every step is counted.
3. The label is recoded so 1 = phishing and 0 = legitimate. The dataset uses the opposite, so this is noted clearly.
4. Identifier columns (`FILENAME`, `URL`, `Domain`, `TLD`, `Title`) are kept aside and not used as features.

Subtasks: find duplicates · check for missing and invalid values · recode the label · write a before-and-after cleaning report.
Attachments: cleaning report (row counts before and after each step).

### 1.3 Check the data for leakage · Must · 3 pts · `data`
*As a data analyst, I want to find columns that give the answer away, so that our model learns real warning signs instead of shortcuts.*

Acceptance criteria:
1. The share of legitimate URLs that are only a bare homepage (`https://www.<domain>` with no path) is measured.
2. Each feature that alone predicts the label with over 95% accuracy is listed.
3. Every excluded feature is written down with the reason for excluding it.

Subtasks: measure the bare-homepage pattern · test single-feature accuracy · write the excluded-features list.
Attachments: leakage findings (table and chart).

### 1.4 Normalise the data · Should · 2 pts · `data`
*As a data analyst, I want the numeric features on a common scale, so that models that are sensitive to scale train properly.*

Acceptance criteria:
1. The data is split into training and test sets (stratified by label) before any scaling.
2. The scaler is fitted on the training set only and saved to a file.
3. The same saved scaler is used at prediction time.

Subtasks: stratified train/test split · fit and save the scaler · plot distributions before and after scaling.
Attachments: before/after distribution chart.

## E2 Link Input

### 2.1 Paste a link to check it · Must · 3 pts · `frontend`
*As a user, I want to paste a link into a box and check it, so that I find out if it's safe without clicking it.*

Acceptance criteria:
1. The page has a box labelled "Paste the link here" and a Check button at least 24×24 px.
2. It works with the keyboard alone: Tab to the box, Enter to check.
3. While checking, the page shows "Checking…", and screen readers announce the result.
4. The app never opens or fetches the pasted link.

Subtasks: build the page and form (frontend) · create the `/scan` endpoint (backend) · connect the form to the endpoint.
Attachments: wireframe of the page.

### 2.2 Clear errors for things that aren't links · Must · 3 pts · `backend`
*As a user, I want to be told what's wrong when I paste something that isn't a web address, so that I can fix it.*

Acceptance criteria:
1. Given the box is empty, when I press Check, then I see "Paste a link first".
2. Given I paste "hello there", when I press Check, then I see "That doesn't look like a web address. It usually starts with www. or https://".
3. Spaces, line breaks and trailing punctuation copied from a text are removed, and a missing `https://` is added.
4. Links over 2,000 characters are rejected with a message saying so.

Subtasks: write the validation and cleaning rules (backend) · show the error messages (frontend) · unit tests for 10 sample inputs.
Attachments: table of example inputs with the expected message for each.

### 2.3 Save my checks · Should · 3 pts · `backend`
*As a user, I want my checks saved, so that I can look back at them later.*

Acceptance criteria:
1. Each check is stored with the cleaned link, the date and time, and the result.
2. No name, email or other personal detail is stored.
3. The page says in one line what is saved and why.

Subtasks: choose the database · design the checks table · save each check from the `/scan` endpoint.
Attachments: database table design.

## E3 Feature Extraction

### 3.1 Build the URL feature extractor · Must · 5 pts · `ml`
*As an ML engineer, I want one function that turns any link into features, so that training and live checks use exactly the same inputs.*

Acceptance criteria:
1. One function computes the URL-only features from a raw link, and both training and the API use it.
2. The three reference-data features (`URLSimilarityIndex`, `TLDLegitimateProb`, `URLCharProb`) and all page-content features are left out.
3. Features recomputed from the dataset's raw `URL` column match the dataset's own values for the same features, or the differences are explained.
4. Unit tests cover at least 10 links, including ones with paths, query strings, IP addresses and unusual characters.

Subtasks: write the extractor · recompute features for the whole dataset · compare with the original columns · write the tests.
Attachments: list of features used and how each is calculated.

### 3.2 Choose the best features · Must · 3 pts · `ml`
*As an ML engineer, I want the features ranked by how much they help, so that the model uses the strongest features that don't leak the answer.*

Acceptance criteria:
1. Features are ranked with at least two methods (for example mutual information and random forest importance).
2. The top 10 are shown in a chart.
3. The final feature list is written down, with a reason for each feature dropped.

Subtasks: compute mutual information · compute random forest importance · pick and document the final list.
Attachments: feature ranking chart.

## E4 Data Visualisation

### 4.1 See my result at a glance · Must · 3 pts · `frontend`
*As a user, I want to see my result as a clear risk level, so that I understand it straight away.*

Acceptance criteria:
1. The three levels are Safe, Suspicious and High risk, each shown with a word, an icon and a colour, never colour alone.
2. Text contrast is at least 4.5:1.
3. "Safe" always carries the caveat "No warning signs found. Still don't enter passwords or bank details from a message you weren't expecting."

Subtasks: design the result card (using `ui-ux-pro-max` tokens) · build the component · connect it to the `/scan` response (a placeholder result until the model is served).
Attachments: mock-up of all three levels.

### 4.2 See my past checks in a table · Should · 3 pts · `frontend`
*As a user, I want a table of my past checks, so that I can find a link I checked before.*

Acceptance criteria:
1. The table shows date, link and result, newest first.
2. Links in the table are plain text and can never be clicked.
3. With no checks yet, it says "You haven't checked any links yet".

Subtasks: history endpoint (backend) · table component (frontend) · empty state.
Attachments: mock-up of the table.

### 4.3 Learn what phishing links look like · Should · 3 pts · `data`
*As a user, I want to see charts comparing phishing and safe links, so that I learn the warning signs myself.*

Acceptance criteria:
1. A page shows at least three charts from the cleaned dataset, for example link length, number of dots or hyphens, and use of HTTPS.
2. Each chart compares phishing with legitimate links.
3. Each chart has a one-line, plain-language takeaway and a text alternative for screen readers.

Subtasks: prepare chart data from the cleaned dataset · build the charts page · write the takeaways.
Attachments: chart images.

### 4.4 Chart of my checks · Could · 2 pts · `frontend`
*As a user, I want a simple chart of how many of my checks were safe, suspicious or high risk, so that I see my overall picture.*

Acceptance criteria:
1. A bar or pie chart with a label and a number on each part.
2. The chart updates after each new check.
3. A text summary is available for screen readers.

Subtasks: count endpoint (backend) · chart component (frontend).

### 4.5 Readable on a phone and with large text · Should · 2 pts · `frontend`
*As a user, I want LinkGuard to be easy to read on my phone and with large text, so that I can use it comfortably.*

Acceptance criteria:
1. Pages work at 320 px wide with no sideways scrolling.
2. At 200% text size nothing is cut off or overlaps.
3. Keyboard focus is always visible.

Subtasks: responsive layout · test at 320 px and at 200% zoom · fix any issues found.
Attachments: screenshots at 320 px and at 200%.

## E5 Build Models

### 5.1 Train and compare models · Must · 5 pts · `ml`
*As an ML engineer, I want to train and compare several classifiers, so that we pick the best one on evidence.*

Acceptance criteria:
1. At least three classifiers are trained on the chosen features, for example logistic regression, random forest and gradient boosting.
2. All use the same train/test split and 5-fold cross-validation.
3. The results are compared in one table.

Subtasks: training pipeline · train each model · comparison table.
Attachments: model comparison table.

### 5.2 Tune the best model · Should · 3 pts · `ml`
*As an ML engineer, I want to tune the best model's settings, so that it performs as well as it can.*

Acceptance criteria:
1. A hyperparameter search (for example grid or randomised search) is run on the training set only.
2. The before and after scores are recorded.
3. The final model is saved as one file the backend can load.

Subtasks: define the search space · run the search · save the final model.

### 5.3 Get a risk level from the model · Must · 3 pts · `backend`
*As a user, I want my link scored by the trained model, so that I get a reliable result.*

Acceptance criteria:
1. The API loads the saved model and scaler once at start-up.
2. `/scan` returns Safe, Suspicious or High risk using the agreed cut-offs.
3. A result comes back in under 2 seconds.

Subtasks: load the model in the API · connect the feature extractor · map the score to a risk level · API tests.

## E6 Model Evaluation

### 6.1 Evaluate with the right measures · Must · 3 pts · `ml`
*As an ML engineer, I want the model measured properly, so that we know how often it misses phishing.*

Acceptance criteria:
1. Recall on phishing, precision, F1 and ROC-AUC are reported on the test set.
2. A confusion matrix is shown.
3. Recall on phishing is treated as the main measure, since a missed phishing link is the costly mistake.

Subtasks: evaluation script · confusion matrix and ROC charts · write-up.
Attachments: evaluation report with charts.

### 6.2 Test on links from outside the dataset · Must · 5 pts · `data`
*As a data analyst, I want the model tested on links it has never seen from other sources, so that we know it works in the real world.*

Acceptance criteria:
1. A test set of at least 200 legitimate links with paths and query strings, plus recent phishing links from a public feed, is gathered without opening any of them.
2. The model's scores on this set are reported next to its PhiUSIIL scores.
3. Any big drop is explained, with a proposed fix.

Subtasks: collect legitimate links · collect phishing links from a public feed · run the evaluation · write up the results.
Attachments: outside test set (as a CSV) and results.

### 6.3 Set the risk-level cut-offs · Must · 2 pts · `ml`
*As an ML engineer, I want clear cut-offs between Safe, Suspicious and High risk, so that the levels mean something consistent.*

Acceptance criteria:
1. Two probability cut-offs are chosen using the precision/recall trade-off.
2. The reason for each cut-off is written down.
3. The share of test links in each level is reported.

Subtasks: plot the precision/recall curve · choose the cut-offs · document them.

## E7 Explain and Advise

### 7.1 See why a link looks dangerous · Must · 5 pts · `ml`
*As a user, I want the main reasons a link looks dangerous in plain words, so that I understand the warning and learn from it.*

Acceptance criteria:
1. Up to three reasons are shown, from the features that pushed this link's score up the most (for example using SHAP).
2. Each reason is a plain sentence about this link, for example "The web address is unusually long".
3. No technical words such as "feature", "SHAP" or "probability" appear on screen.

Subtasks: compute per-link explanations (ml) · write a plain sentence for each feature · show the reasons (frontend).

### 7.2 Know what to do next · Must · 2 pts · `frontend`
*As a user, I want clear advice for my result, so that I know what to do now.*

Acceptance criteria:
1. Each risk level shows its own short advice, for example: don't click; contact the company using details you find yourself; delete the message.
2. An "If you already clicked" section says: ring your bank using the number on your card, change the password, report it to your local Garda station.
3. A "Where to get help" link sits in the same place on every page.

Subtasks: write the advice text from official sources · build the advice panel · add the help link.
Attachments: advice text with its sources.

### 7.3 Warning for lookalike websites · Should · 3 pts · `backend`
*As a user, I want to be warned when a link imitates a well-known site, such as "paypa1.com", so that I don't fall for a copycat.*

Acceptance criteria:
1. The domain is compared against a published list of popular sites (for example Tranco).
2. A close match that isn't the real site adds the reason "This looks like paypal.com but isn't".
3. The real site itself is never flagged.

Subtasks: load the top-sites list · similarity check · add the reason to the result · tests.

### 7.4 Tell LinkGuard if a result was wrong · Should · 2 pts · `backend`
*As a user, I want to say whether a result was right, so that LinkGuard can improve.*

Acceptance criteria:
1. Each result shows "Was this right? Yes / No".
2. The answer is saved against that check.
3. The team can export all feedback as a CSV.

Subtasks: feedback endpoint and table (backend) · feedback buttons (frontend) · CSV export.

## E8 DevOps and Quality

### 8.1 CI pipeline on every pull request · Must · 3 pts · `docs`
*As a developer, I want every pull request built and tested automatically, so that broken code never reaches `dev`.*

Acceptance criteria:
1. GitHub Actions installs, builds and runs the tests for `frontend`, `backend` and `ml` on every PR.
2. A failing step prints a clear message saying what failed and where.
3. The pipeline is documented in the README.

Subtasks: backend job · frontend job · ml job · README section.

### 8.2 Automated tests for each part · Must · 3 pts · `backend`, `frontend`, `ml`
*As a developer, I want automated tests for each part, so that we catch mistakes before merging.*

Acceptance criteria:
1. Each story's main behaviour has at least one automated test.
2. All tests run in CI.
3. Test coverage is reported for the backend and ml code.

Subtasks: one per story, added as each story is built.

### 8.3 Deploy a demo version · Could · 3 pts · `backend`
*As a developer, I want the app running at a public address, so that we can demo it at the presentation.*

Acceptance criteria:
1. The app runs at a public address.
2. The setup steps are documented.
3. Only the demo data is used, and no secrets are committed.

Subtasks: choose hosting · deploy backend and frontend · document the steps.

---

## Totals

| Epic | Stories | Suggested points |
|---|---|---|
| E1 Data Processing | 4 | 10 |
| E2 Link Input | 3 | 9 |
| E3 Feature Extraction | 2 | 8 |
| E4 Data Visualisation | 5 | 13 |
| E5 Build Models | 3 | 11 |
| E6 Model Evaluation | 3 | 10 |
| E7 Explain and Advise | 4 | 12 |
| E8 DevOps and Quality | 3 | 9 |
| **Total** | **27** | **82** |

Priorities: 17 Must, 8 Should, 2 Could. If a sprint runs short, the Shoulds and Coulds go first. Which stories go into which sprint is decided at each sprint planning.
