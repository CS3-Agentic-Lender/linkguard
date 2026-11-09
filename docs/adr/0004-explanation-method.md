---
status: accepted
---

# Explain each link by how much each feature pushed its score

When a link is Suspicious or High risk, the result shows up to three plain reasons: the features that raised that link's score most. We measure **how much each feature pushed this link's score towards phishing, compared with an average training link**. The final model is gradient boosting, so this comes from SHAP's tree explainer. The code that picks the reasons only sees these numbers, so it does not depend on the model. Two features marked "watch" in the final feature list, `TLDLength` and `NoOfSubDomain`, are never shown as reasons.

Proposed by Ibrahima on 9 November 2026 (Sprint 3), and accepted the same day once two things were settled:

- **Which model is final.** The model comparison chose logistic regression (balanced) by phishing recall, and the first tuning work used it. On 9 November 2026 Nic, the Product Owner, confirmed **gradient boosting, picked by ROC-AUC**, as agreed at sprint planning, and the tuning and saving work moves to it.
- **The "never shown" rule** for the two watched features (see below). Dunmi proposed it, and Ibrahima, Nikoloz and Nic agreed on 9 November 2026.

## Why we need it

The reasons story asks for reasons that are about _this_ link, ordered by how much each raised its score, and checked by hand on five sample links against the full explanation. So we need a per-link measure that:

- gives every feature a signed amount: above zero means it pushed the score towards phishing, below zero means away;
- is exact and repeatable, so the hand check on five links can agree with it, and the same link always gets the same reasons;
- runs in well under the 2 seconds a scan is allowed;
- works on the 8 final features the model uses, after the saved scaler.

## Decision

### The measure

For each of the 8 model features, work out its **contribution**: how much it moved this link's phishing log-odds (the model's score before it is turned into a probability) away from an average training link's. The contributions add up to the difference between this link's log-odds and the average link's, so they split the score between the features with nothing left over.

The final model is gradient boosting (scikit-learn's `HistGradientBoostingClassifier`). It has no single coefficient per feature, so we use **SHAP's tree explainer** on the fitted model, in log-odds. It is exact for tree models: for each link it gives one contribution per feature, and they add up to the link's log-odds minus the explainer's expected log-odds over the training links. This adds the `shap` library to `ml/` and `backend/`, pinned to the same version in both.

If the model were ever logistic regression again, the same numbers would come straight from the model: each feature's coefficient times its scaled value, because the scaler puts an average training link at 0. That needs no SHAP.

The contributions are worked out on the scaled values the model actually saw, in the backend's scan, for the one link being checked. Nothing is fetched or opened.

### Picking the reasons

Reasons are only worked out for Suspicious and High risk results. A Safe result has an empty reasons list.

1. Work out the contribution of each of the 8 model features.
2. Drop the features that are never shown (below). They still count towards the score. They are just not named.
3. Keep a feature only if its contribution is **above zero** _and_ the link is on the side its sentence describes, compared with an average training link. For example, "The website name in this link is unusually long" is only shown when the website name is longer than average. This stops a sentence appearing that is untrue for the link.

   | Feature | Shown only when, compared with an average training link |
   |---|---|
   | `HostnameLength` | longer |
   | `IsDomainIP` | the link uses an IP address |
   | `LetterRatioInHostname` | a smaller share of letters |
   | `NoOfDigitsInHostname` | more digits |
   | `DigitRatioInHostname` | a larger share of digits |
   | `NoOfSpecialCharsInHostname` | more dots or hyphens |

4. Of the three **number features** (`NoOfDigitsInHostname`, `DigitRatioInHostname` and `LetterRatioInHostname`), keep only the one that pushed most. On a tie, keep the first in that order. Their sentences all say the website name is mostly numbers ("a lot of numbers", "numbers make up a large part", "numbers or symbols, not letters"), so showing two would use up two of the three reasons on one sign. The hand check on five made-up links (`ml/reports/explanation_check.md`) first used this step for the two digit features only, and an IP-address link then got both "numbers or symbols, not letters" and "a lot of numbers". Dunmi and Nikoloz agreed on 9 November 2026 to widen it to all three.
5. Sort what is left by contribution, largest first, and keep at most three.

### Features that are never shown

The plain sentence for each feature, and every never-shown feature with its reason, are listed in `docs/reason-sentences.md` and kept in `ml/features/reasons.py`.

- **`TLDLength` and `NoOfSubDomain`.** The final feature list keeps both but marks them to watch. The dataset's legitimate links are mostly front pages of big sites, so a short common ending like `.com`, or few subdomains, may look safe only because of how the dataset was built (the template problem in `0002-hostname-features-for-template-bias.md`). The model still uses them, but we don't tell a user "this link looks dangerous because of its ending" when that may not be a real warning sign.
- **`NoOfLettersInHostname` and `SpecialCharRatioInHostname`.** The model does not use them, because they copy other features. They can never have a contribution.

`0002-hostname-features-for-template-bias.md` set the ten features but did not say which ones may be shown as reasons. This record is where that rule lives.

## Considered options

- **Per-feature contributions in log-odds from SHAP's tree explainer** (chosen): exact for the gradient boosting model, repeatable, per link and fast. It adds the `shap` library.
- **Coefficient times scaled value** (only for logistic regression): exact and needs no library, but the final model has no coefficients.
- **Contributions in probability instead of log-odds** (turned down): easier to read, but they do not add up neatly, and the model's own sum is in log-odds. Users never see the numbers, only the order.
- **One feature importance for the whole model** (permutation importance, or the forest's importances; turned down): every link would get the same reasons, which breaks "about this link".
- **LIME** (turned down): it fits a small model on random samples around each link, so the same link can get different reasons on different runs. It is also slower, and the hand check needs a stable answer.
- **Fixed rules, such as "website name longer than 30 characters"** (turned down): simple, but not tied to what the model did. A reason could appear for a feature that did not raise this link's score.

## Consequences

- Reasons explain **what the model did**, not whether the link is truly dangerous. They are hostname-based signals only, as `0002-hostname-features-for-template-bias.md` says.
- A hidden feature can be the biggest push on a link's score. The user then sees the next largest shown features instead, or none.
- **A risky link can get no reasons**, when only hidden features raised its score, or none passes step 3. The reasons story asks for one to three reasons on a Suspicious or High risk result, so this case needs a decision before the result page is built (see Open questions).
- Correlated features (website name length, digit count and digit share) share the push between them, so each one's contribution can look smaller than the sign it stands for. Step 4 stops near-duplicate number sentences.
- The reasons are picked in one place, `ml/features/explain.py`. The scan turns the picked names into sentences and does no filtering of its own, so two pickers can never disagree.
- `shap` becomes a dependency of `ml/` and `backend/`. The backend builds the tree explainer once, when it loads the model at start-up, not on every scan.
- The scan time with reasons has to be measured again on the gradient boosting model, against the 2 second limit.
- The hand check on five sample links compares the picked reasons with the full list of contributions for each link.

### Work this decision affects

- **Which features raised each link's score**: works out the contributions and picks the reasons by the steps above, with tests for a link with several raising features and a link with none.
- **Plain sentence for each feature**: `docs/reason-sentences.md` points to this record for the never-shown features.
- **Reasons in the scan response**: returns the picked sentences, zero to three.
- **Reasons on the result page**: shows them, and handles a risky link with no reasons.

## Open questions

- **A Suspicious or High risk link with no reasons**: show a general sentence instead (for example "Several small signs together make this link look risky"), or accept an empty list. A product decision for the Product Owner.
