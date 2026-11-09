---
status: proposed
---

# Explain each link by how much each feature pushed its score

When a link is Suspicious or High risk, the result shows up to three plain reasons: the features that raised that link's score most. We measure **how much each feature pushed this link's score towards phishing, compared with an average training link**. For logistic regression that comes straight from the model's coefficients. For gradient boosting it comes from SHAP's tree explainer. Both give the same kind of number, so the code that picks the reasons does not depend on the model. Two features marked "watch" in the final feature list, `TLDLength` and `NoOfSubDomain`, are never shown as reasons.

Proposed by Ibrahima on 9 November 2026 (Sprint 3). It stays **proposed** until two things are settled:

- **Which model is final.** The model comparison chose logistic regression (balanced) by phishing recall, and the tuning work tunes it. A later discussion leaned towards gradient boosting by ROC-AUC. This record covers both, so it can be accepted as soon as the Product Owner confirms one.
- **The team agrees the "never shown" rule** for the two watched features (see below).

## Why we need it

The reasons story asks for reasons that are about _this_ link, ordered by how much each raised its score, and checked by hand on five sample links against the full explanation. So we need a per-link measure that:

- gives every feature a signed amount: above zero means it pushed the score towards phishing, below zero means away;
- is exact and repeatable, so the hand check on five links can agree with it, and the same link always gets the same reasons;
- runs in well under the 2 seconds a scan is allowed;
- works on the 8 final features the model uses, after the saved scaler.

## Decision

### The measure

For each of the 8 model features, work out its **contribution**: how much it moved this link's phishing log-odds (the model's score before it is turned into a probability) away from an average training link's. The contributions add up to the difference between this link's log-odds and the average link's, so they split the score between the features with nothing left over.

- **Logistic regression.** The model's log-odds is the intercept plus each coefficient times its scaled feature value. The scaler is fitted on the training rows, so an average training link has every scaled value at 0. So each feature's contribution is simply **its coefficient times its scaled value**. This is exact, needs no new library, and gives the same numbers SHAP would for this model.
- **Gradient boosting** (scikit-learn's `HistGradientBoostingClassifier`). There is no single coefficient per feature, so we use **SHAP's tree explainer** on the fitted model, in log-odds. It is exact for tree models and gives the same additive split. This adds the `shap` library to `ml/` and `backend/`, pinned to one version, and only if gradient boosting is the final model.

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

4. If both digit features qualify, keep only the larger. Their two sentences say nearly the same thing ("a lot of numbers", "numbers make up a large part"), and showing both would use up two of the three reasons on one sign.
5. Sort what is left by contribution, largest first, and keep at most three.

### Features that are never shown

The plain sentence for each feature, and every never-shown feature with its reason, are listed in `docs/reason-sentences.md` and kept in `ml/features/reasons.py`.

- **`TLDLength` and `NoOfSubDomain`.** The final feature list keeps both but marks them to watch. The dataset's legitimate links are mostly front pages of big sites, so a short common ending like `.com`, or few subdomains, may look safe only because of how the dataset was built (the template problem in `0002-hostname-features-for-template-bias.md`). The model still uses them, but we don't tell a user "this link looks dangerous because of its ending" when that may not be a real warning sign.
- **`NoOfLettersInHostname` and `SpecialCharRatioInHostname`.** The model does not use them, because they copy other features. They can never have a contribution.

`0002-hostname-features-for-template-bias.md` set the ten features but did not say which ones may be shown as reasons. This record is where that rule lives.

## Considered options

- **Per-feature contributions in log-odds: coefficients for logistic regression, SHAP's tree explainer for gradient boosting** (chosen): exact, repeatable, per link, fast, and the same kind of number for both models. It needs a new library only if gradient boosting is final.
- **SHAP for every model, including logistic regression** (turned down): gives the same numbers for logistic regression, but adds a library we would not otherwise need.
- **Contributions in probability instead of log-odds** (turned down): easier to read, but they do not add up neatly, and the model's own sum is in log-odds. Users never see the numbers, only the order.
- **One feature importance for the whole model** (permutation importance, or the forest's importances; turned down): every link would get the same reasons, which breaks "about this link".
- **LIME** (turned down): it fits a small model on random samples around each link, so the same link can get different reasons on different runs. It is also slower, and the hand check needs a stable answer.
- **Fixed rules, such as "website name longer than 30 characters"** (turned down): simple, but not tied to what the model did. A reason could appear for a feature that did not raise this link's score.

## Consequences

- Reasons explain **what the model did**, not whether the link is truly dangerous. They are hostname-based signals only, as `0002-hostname-features-for-template-bias.md` says.
- A hidden feature can be the biggest push on a link's score. The user then sees the next largest shown features instead, or none.
- **A risky link can get no reasons**, when only hidden features raised its score, or none passes step 3. The reasons story asks for one to three reasons on a Suspicious or High risk result, so this case needs a decision before the result page is built (see Open questions).
- Correlated features (website name length, digit count and digit share) share the push between them, so each one's contribution can look smaller than the sign it stands for. Step 4 stops two near-duplicate sentences.
- If gradient boosting is final, `shap` becomes a backend dependency, loaded once with the model, not on every scan.
- The hand check on five sample links compares the picked reasons with the full list of contributions for each link.

### Work this decision affects

- **Which features raised each link's score**: works out the contributions and picks the reasons by the steps above, with tests for a link with several raising features and a link with none.
- **Plain sentence for each feature**: `docs/reason-sentences.md` points to this record for the never-shown features.
- **Reasons in the scan response**: returns the picked sentences, zero to three.
- **Reasons on the result page**: shows them, and handles a risky link with no reasons.

## Open questions

- **Final model**: logistic regression (balanced) or gradient boosting. This decides whether `shap` is added.
- **The never-shown rule** for `TLDLength` and `NoOfSubDomain` needs the team's agreement.
- **A Suspicious or High risk link with no reasons**: show a general sentence instead (for example "Several small signs together make this link look risky"), or accept an empty list. A product decision for the Product Owner.
