# PhiUSIIL Phishing URL Dataset: features, leakage, and what LinkGuard can reproduce live

Research date: 2026-09-28. Scope: the 54 feature columns of the PhiUSIIL Phishing URL Dataset (UCI id 967) [1][2], how they were computed, leakage, and what this means for LinkGuard's live feature extractor.

**Read this first: the paper was not available.** The paper that defines the features, Prasad & Chandra (2024) [3], is closed-access (OpenAlex: `is_oa: false`, `oa_status: closed` [6]). ScienceDirect, ResearchGate and ACM DL all refused automated access. No author preprint, code release or supplementary file could be found. The UCI page [1][2], Mendeley Data record [4] and the authors' Kaggle page [5] give column names and types but **no per-column definitions**. For formulas they all point back to the paper [4]. So:

- Column names, types, counts, labels and the list of "derived" features are **confirmed** from primary sources [1][2][4][5].
- The definitions below come either from the column name (marked *name*) or from secondary sources (marked *secondary*). None of them has been checked against the paper. The team member who owns the model should get the PDF through the MTU library and check section 3 against it (see Open questions).

---

## 1. Summary

- **Column breakdown.** 56 columns: `FILENAME` (role "Other", "can be ignored"), 54 "Feature" columns, and `label` (1 = legitimate, 0 = phishing; the reverse of the usual convention) [1][2][5]. Of the 54 features:
  - 4 are raw strings or identifiers (`URL`, `Domain`, `TLD`, `Title`).
  - **19 are computable from the URL string alone.**
  - **3 need external reference data**: `URLSimilarityIndex`, `TLDLegitimateProb`, `URLCharProb`.
  - **28 need the fetched page**: HTML, title, forms, links, resources.
- **Where the data came from.** The authors built the dataset by extracting URL features, downloading each webpage to extract HTML features, and deriving new features from those [3] (abstract, seen via search-engine excerpt). UCI and Mendeley name the derived ones as `CharContinuationRate`, `URLTitleMatchScore`, `URLCharProb` and `TLDLegitimateProb` [1][4]. Secondary sources say the legitimate URLs came from the Open PageRank domain list and the phishing URLs from PhishTank, OpenPhish and MalwareWorld [14]. This is unconfirmed against the paper.
- **Leakage verdict: yes, and it is severe.**
  - `URLSimilarityIndex` restates the label. Independent analyses report it is exactly 100 for all 134,850 legitimate rows. On its own it gives about 99.6–99.7% accuracy [8][10][11].
  - Separately, every legitimate URL follows one template: `https://www.<domain>` with no path and no query string. A regex with no learned parameters for that template reports 99.56% accuracy [9][12].
  - Many "URL-only" features (length, special-character counts, `IsHTTPS`, `?`/`=`/`&` counts) therefore also encode the class through this template, not through anything about phishing.
- **Published scores tell you little.**
  - The authors report 99.79% (pre-trained) and 99.24% (fully incremental) [3].
  - Follow-up work reports 99.6–100% [7][8].
  - A secondary replication reports a random forest trained on PhiUSIIL fell to a True Skill Statistic of 0.000 on live OpenPhish plus Common Crawl URLs: it flagged everything as phishing [9].
- **Train/serve skew risk is high.** People will paste real links with paths, query strings and sometimes `http://`. A model trained on PhiUSIIL's legitimate homepages will read exactly those traits as "phishing", so false alarms on normal links are likely.
- **Recommendation for the live extractor:**
  1. Do not train on the authors' precomputed columns. The CSV contains the raw `URL`, so recompute URL-only features from `URL` with the same code the backend runs at scan time. That guarantees train/serve parity.
  2. Drop `URLSimilarityIndex`, `TLDLegitimateProb`, `URLCharProb`, `FILENAME`, `URL`, `Domain`, `TLD` and `Title` as model inputs.
  3. Leave page features out of v1. The definitions are unpublished, fetching needs the sandboxed fetcher, and phishing pages go offline quickly.
  4. Most important: neutralise the legitimate-URL template (normalise URLs, or add legitimate URLs with paths from another source), and evaluate on a test set that is **not** drawn from PhiUSIIL.
- **Separate lookalike check.** Lookalike-domain detection, which is what `URLSimilarityIndex` was meant to capture, is still worth having in LinkGuard. Build it as a separate rule outside the model that produces a "reason", computed against a published top-sites list.

---

## 2. Feature table

Categories:

- **URL**: URL-only.
- **REF**: URL plus an external reference table.
- **PAGE**: needs the fetched page. `Robots` may need a second fetch.
- **ID**: identifier or raw string, not a model feature.

The UCI "Type" column is quoted as published [2]. Note that UCI lists several ratio columns as Integer, which looks like a metadata error (see Open questions).

"Def. source" says where each one-line definition comes from:

- *name*: the definition is read off the column name only. The paper was not read.
- *secondary*: a secondary source, cited in the row.

Every column name and type comes from [2].

| # | Column | UCI type | Category | One-line definition | Def. source |
|---|---|---|---|---|---|
| – | `FILENAME` | Categorical (role Other) | ID | Source file name; UCI says "can be ignored" [2] | [2] |
| 1 | `URL` | Categorical | ID | The full URL string | name |
| 2 | `URLLength` | Integer | URL | Number of characters in the URL | name |
| 3 | `Domain` | Categorical | ID | Host or domain part of the URL | name |
| 4 | `DomainLength` | Integer | URL | Characters in the domain | name |
| 5 | `IsDomainIP` | Integer | URL | 1 if the host is an IP address | name |
| 6 | `TLD` | Categorical | ID | Top-level domain string | name |
| 7 | `URLSimilarityIndex` | Integer (values up to 100.0) | REF | Similarity of the URL to a list of known legitimate URLs; 100 = exact match. See §3 | secondary [10][11] |
| 8 | `CharContinuationRate` | Integer (a ratio in practice) | URL | Longest runs of letters, digits and symbols, relative to length. Derived feature [1]. See §3 | secondary [13] + search excerpt |
| 9 | `TLDLegitimateProb` | Continuous | REF | Probability that this TLD is legitimate, taken from a legitimate-domain list. Derived feature [1]. See §3 | secondary [11][13] |
| 10 | `URLCharProb` | Continuous | REF | Average per-character probability under a legitimate-URL character distribution. Derived feature [1]. See §3 | secondary [11][13] |
| 11 | `TLDLength` | Integer | URL | Characters in the TLD | name |
| 12 | `NoOfSubDomain` | Integer | URL | Number of subdomain labels | name |
| 13 | `HasObfuscation` | Integer | URL | 1 if the URL contains obfuscated characters. See §3 | name |
| 14 | `NoOfObfuscatedChar` | Integer | URL | Count of obfuscated characters | name |
| 15 | `ObfuscationRatio` | Integer (a ratio in practice) | URL | Obfuscated characters ÷ URL length | name |
| 16 | `NoOfLettersInURL` | Integer | URL | Count of letters | name |
| 17 | `LetterRatioInURL` | Continuous | URL | Letters ÷ URL length | name |
| 18 | `NoOfDegitsInURL` | Integer | URL | Count of digits ("Degit" is the authors' spelling) | name |
| 19 | `DegitRatioInURL` | Integer (a ratio in practice) | URL | Digits ÷ URL length | name |
| 20 | `NoOfEqualsInURL` | Integer | URL | Count of `=` | name |
| 21 | `NoOfQMarkInURL` | Integer | URL | Count of `?` | name |
| 22 | `NoOfAmpersandInURL` | Integer | URL | Count of `&` | name |
| 23 | `NoOfOtherSpecialCharsInURL` | Integer | URL | Count of other special characters | name |
| 24 | `SpacialCharRatioInURL` | Continuous | URL | Special characters ÷ URL length ("Spacial" is the authors' spelling) | name |
| 25 | `IsHTTPS` | Integer | URL | 1 if the scheme is `https`. It is unconfirmed whether this is the scheme as submitted or after redirects | name |
| 26 | `LineOfCode` | Integer | PAGE | Number of lines in the HTML source. See §3 | name |
| 27 | `LargestLineLength` | Integer | PAGE | Length of the longest line of HTML source. See §3 | name |
| 28 | `HasTitle` | Integer | PAGE | 1 if the page has a `<title>` | name |
| 29 | `Title` | Categorical | ID (page-derived) | The page title text | name |
| 30 | `DomainTitleMatchScore` | Integer | PAGE | How far the domain matches the page title. See §3 | name |
| 31 | `URLTitleMatchScore` | Integer | PAGE | How far the URL matches the page title. Derived feature [1]. See §3 | secondary [13] |
| 32 | `HasFavicon` | Integer | PAGE | 1 if a favicon is declared | name |
| 33 | `Robots` | Integer | PAGE | robots.txt presence or a robots meta tag; which one is unconfirmed | name |
| 34 | `IsResponsive` | Integer | PAGE | 1 if the page looks responsive, for example it has a viewport meta tag. See §3 | name |
| 35 | `NoOfURLRedirect` | Integer | PAGE | Count of redirects. See §3 | name |
| 36 | `NoOfSelfRedirect` | Integer | PAGE | Count of redirects to the same domain. See §3 | name |
| 37 | `HasDescription` | Integer | PAGE | 1 if there is a meta description | name |
| 38 | `NoOfPopup` | Integer | PAGE | Count of popup constructs in the page | name |
| 39 | `NoOfiFrame` | Integer | PAGE | Count of `<iframe>` elements | name |
| 40 | `HasExternalFormSubmit` | Integer | PAGE | 1 if a form posts to another domain | name |
| 41 | `HasSocialNet` | Integer | PAGE | 1 if there are social-network links | name |
| 42 | `HasSubmitButton` | Integer | PAGE | 1 if there is a submit button | name |
| 43 | `HasHiddenFields` | Integer | PAGE | 1 if there is an `<input type="hidden">` | name |
| 44 | `HasPasswordField` | Integer | PAGE | 1 if there is an `<input type="password">` | name |
| 45 | `Bank` | Integer | PAGE (probably) | 1 if banking keywords are present. Whether they were searched in the HTML or the URL is unconfirmed | name; grouped as "keyword-based" in [13] |
| 46 | `Pay` | Integer | PAGE (probably) | Same as `Bank`, for payment keywords | name |
| 47 | `Crypto` | Integer | PAGE (probably) | Same as `Bank`, for cryptocurrency keywords | name |
| 48 | `HasCopyrightInfo` | Integer | PAGE | 1 if a copyright notice is present | name |
| 49 | `NoOfImage` | Integer | PAGE | Count of images | name |
| 50 | `NoOfCSS` | Integer | PAGE | Count of stylesheets | name |
| 51 | `NoOfJS` | Integer | PAGE | Count of scripts | name |
| 52 | `NoOfSelfRef` | Integer | PAGE | Count of links to the same domain | name |
| 53 | `NoOfEmptyRef` | Integer | PAGE | Count of empty links (for example `href="#"`) | name |
| 54 | `NoOfExternalRef` | Integer | PAGE | Count of links to other domains | name |
| – | `label` | Integer (Target) | – | 1 = legitimate, 0 = phishing [1][5] | [1][5] |

Tally of the 54 feature columns: URL 19, REF 3, PAGE 28 (counting `Bank`/`Pay`/`Crypto` as page), ID 4 (`URL`, `Domain`, `TLD`, `Title`). `FILENAME` and `label` are outside the 54.

---

## 3. Non-obvious features

The authors' own sources [1][4][5] say only that these features are "derived from existing features" (`CharContinuationRate`, `URLTitleMatchScore`, `URLCharProb`, `TLDLegitimateProb`) and refer to the paper for method [4]. Everything below beyond that is secondary or inferred, and is marked as such.

### `URLSimilarityIndex`
- **What is confirmed.** The paper's abstract says the similarity index is the framework's centrepiece. It is meant to catch visual-similarity attacks: zero-width characters, homographs, punycode, homophones, bit-squatting and combosquatting [3] (abstract, via search excerpt).
- **Definition (secondary).** The URL's similarity to a whitelist of known legitimate URLs, scored 0–100 [11].
- **Observed values (secondary, computed from the UCI CSV by third parties):**
  - All 134,850 legitimate rows are exactly 100.0, and only 0.78% of phishing rows are [10].
  - The single rule `URLSimilarityIndex < 100 → phishing` scores 99.67% (precision 1.000, recall 0.992) [10].
  - Its AUC on its own is 0.9961 [11].
  - A separate paper found XGBoost reaches 99.6% accuracy with this one feature [8].
- **Likely mechanism (inference, unconfirmed).** The legitimate URLs appear to have been taken from the same legitimate list the index compares against. If so, every legitimate URL is an exact match and scores 100 by construction.
- **Reference data.** The legitimate list is reported to be Open PageRank's top-domains list [14] (search excerpt only). Open PageRank publishes a top-10-million-domains list, but the version and date the authors used are not known. The per-position weighting and the exact algorithm are **not confirmed**.

### `CharContinuationRate`
- **Confirmed:** it is a derived feature [1][4].
- **Definition (secondary, search excerpt).** Split the string into runs of the same character type (letter, digit, symbol). Take the longest run of each type, add the three lengths, and divide by the total length.
- **An MSc thesis gives a different description [13].** It says the feature computes "the longest contiguous sequences of similar characters".
- **Unknowns.** Whether the input is the whole URL or only the domain is unconfirmed. So is the exact character-class split.

### `TLDLegitimateProb`
- **Confirmed:** it is a derived feature [1][4].
- **Definition (secondary).** The empirical probability that a URL is legitimate given its TLD [11]. An MSc thesis describes it as the probability that the TLD belongs to a legitimate site [13].
- **Two possible sources for the probability, unconfirmed:**
  - TLD frequency in the external legitimate-domain list, which would be reference data.
  - P(legit | TLD) computed on the dataset itself, which would be label leakage by construction.
- **Observed (secondary):** AUC 0.6089 on its own [11]. Weak, but it can only have been built with knowledge of the legitimate class [11].

### `URLCharProb`
- **Confirmed:** it is a derived feature [1][4].
- **Definition (secondary).**
  - An empirical, character-level legitimacy probability [11].
  - A search-engine excerpt describes counting character patterns across "10 million legitimate URLs" and averaging each character's probability over the URL length. This could not be traced to a readable source.
- **Observed (secondary):** AUC 0.7679 on its own [11].
- **Reference data.** The character-probability table is not published anywhere found.

### `HasObfuscation`, `NoOfObfuscatedChar`, `ObfuscationRatio`
- **Name only.** The URL contains obfuscated characters; the count; the count ÷ URL length.
- **Unknown:** which characters count as "obfuscated". Candidates are percent-encoding (`%xx`), `@`, and zero-width or homoglyph characters. **Unconfirmed.**
- UCI types `ObfuscationRatio` as Integer [2], which does not fit a ratio.

### `DegitRatioInURL`, `LetterRatioInURL`, `SpacialCharRatioInURL`
- **Name only:** count ÷ URL length. The authors' misspellings are the real column names.
- UCI types `LetterRatioInURL` and `SpacialCharRatioInURL` as Continuous but `DegitRatioInURL` as Integer [2]. That inconsistency is probably a UCI metadata error, but is unconfirmed without the data.

### `LineOfCode`, `LargestLineLength`
- **Name only:** number of lines in the downloaded HTML source, and the length of its longest line.
- These depend heavily on how the page was fetched (raw HTTP body or rendered DOM, and whether redirects were followed) and on minification. None of this is documented.

### `DomainTitleMatchScore`, `URLTitleMatchScore`
- **Confirmed:** `URLTitleMatchScore` is a derived feature [1][4].
- **Name and secondary:** the degree to which the domain, or the whole URL, matches the page `<title>`. A low score suggests a mismatch [13].
- **Unknown:** the scoring function (token overlap, substring match or edit distance) and the scale. Both need the page title.

### `IsResponsive`
- **Name only:** whether the page is built to be responsive, most likely detected by a `<meta name="viewport">` tag or media queries. **Unconfirmed.**

### `NoOfURLRedirect`, `NoOfSelfRedirect`
- **Name only.** Either HTTP redirect hops or redirect constructs in the HTML/JS (meta refresh, `window.location`). "Self" presumably means the redirect target is on the same domain. **Unconfirmed.**
- Both are listed with the page features because redirects can only be observed by fetching.

### `HasHiddenFields`, `HasPasswordField`, `HasExternalFormSubmit`, `HasSubmitButton`
- **Name only.** Form-structure checks on the HTML. These are the classic credential-harvesting signals and are conceptually the most useful page features.

### `Bank`, `Pay`, `Crypto`
- **Name only:** binary keyword indicators. An MSc thesis groups them as "keyword-based" [13].
- **Unknown:** whether they were matched against the HTML text, the title or the URL, and what the keyword lists are. **Unconfirmed.**

---

## 4. Leakage and reported accuracy

### Leakage findings

| Finding | Evidence | Source type |
|---|---|---|
| `URLSimilarityIndex` restates the label | All 134,850 legitimate rows = 100.0. The rule `<100 → phishing` scores 99.67% (P = 1.000, R = 0.992). Evaluated on 234,987 rows, which suggests about 808 duplicate URLs were removed; unverified | Secondary [10] (seen via search excerpt; the repo returned 404 on direct fetch) |
| One feature is enough | XGBoost reaches 99.6% with `URLSimilarityIndex` alone; 100% with 17 features after recursive feature elimination (RFE) | Preprint [8] |
| Three "legitimacy-derived" features | `URLSimilarityIndex` (AUC 0.9961), `URLCharProb` (0.7679) and `TLDLegitimateProb` (0.6089) are "computed from knowledge of the legitimate class". A fuzzy classifier fell from 0.997 to 0.440 when they were dropped | Secondary [11] |
| Legitimate URLs follow one template | Legitimate: 100% `https`, 100% `www.`, 0% path, 0% query string. Phishing: 48.74% `https`, 41.35% `www.`, 27.19% path, 6.02% query. A zero-parameter regex for `https://www.<domain>` with no path scores 99.56%, TSS 0.9897, zero false alarms | Secondary [9] |
| Independent confirmation of the template | "every one of its legitimate URLs is `https://`, ≤58 characters, without a path", while phishing URLs reach 6,097 characters | Secondary [12] |
| Leakage is spread out, not in a few columns | 14 greedy removals by SHAP rank were needed before accuracy fell below 0.99 | Secondary [10] (search excerpt) |
| Collapse on live data | RF: TSS 0.996 on PhiUSIIL, **0.000** on live OpenPhish plus Common Crawl URLs (labelled everything as phishing). 99.1% of the collapse is attributed to the legitimate-URL template | Secondary [9] |

**How the data description supports these findings.** Where the metadata lets us check, it is consistent with them:

- The authors describe the rows as "URLs and their corresponding webpages" [2].
- The reported legitimate source is a *domain* ranking list [14]. That would explain legitimate URLs being synthesised as `https://www.<domain>`, and their pages being homepages rather than login pages.

We could not verify the numeric claims ourselves because the hard rules say not to download the CSV. They come from several independent analyses that agree with each other. `ml/` should re-check them on the local copy as a first task.

**Identifier columns.** `URL`, `Domain`, `Title` and `FILENAME` identify rows. Using them directly (for example one-hot encoding `Domain`, or TF-IDF on `Title`) would let a model memorise sites. Whether `FILENAME` encodes the class is unconfirmed; UCI says to ignore it [2]. Drop all four.

**Does the paper acknowledge leakage?** Unknown, because the paper could not be read. The abstract presents the similarity index as a strength [3].

### Reported accuracy on PhiUSIIL

| Work | Model | Result | Note |
|---|---|---|---|
| Prasad & Chandra 2024 [3] | Incremental learners (BernoulliNB, PassiveAggressive, SGD per [13]) | 99.79% with pre-training; 99.24% fully incremental | Abstract, via search excerpt |
| Etem & Teke 2024 [7] | Decision Tree / kNN / Naive Bayes on 51 numeric features | 99.7% / 99.6% / 99.4% | Same paper reports LR 42.1% and RF 57.2%. Those are roughly the phishing share (42.8%) and the legitimate share (57.2%), so both models were predicting a single class. That points to pipeline problems. It also wrongly describes the dataset as containing email data |
| Fajar, Yazid & Budi (arXiv 2411.06860) [8] | XGBoost / CatBoost | 100% (17 features); 99.6% (1 feature) | Notes the single-feature dominance but does not call it leakage |
| phish-drift [9] | Regex, no ML | 99.56% | Beats the published models |

---

## 5. Implications for LinkGuard's live extractor

The key fact is that **the CSV contains the raw `URL`**. We do not have to trust the authors' unpublished formulas for URL features: we can recompute them from `URL` with our own extractor and train on those. The same function then runs in the backend at scan time, which removes train/serve skew for this group of features by construction.

### Reproduce: re-extract ourselves from the `URL` column
`URLLength`, `DomainLength`, `IsDomainIP`, `TLDLength`, `NoOfSubDomain`, `NoOfLettersInURL`, `LetterRatioInURL`, `NoOfDegitsInURL`, `DegitRatioInURL`, `NoOfEqualsInURL`, `NoOfQMarkInURL`, `NoOfAmpersandInURL`, `NoOfOtherSpecialCharsInURL`, `SpacialCharRatioInURL`, `IsHTTPS`, and our own definitions of `CharContinuationRate` and the obfuscation trio.

These are faithful in the sense that matters: training and serving use the same code. They will not exactly match the authors' numbers. Don't try to match them; the definitions are unknown.

**Caveat: URL-only does not mean safe.** Because of the legitimate-URL template, most of these features still separate the classes for the wrong reason. Pick at least one mitigation and record it as an ADR in `docs/adr/`:

1. **Normalise before extraction**, at both train and serve time. For example, compute lexical features on the hostname only, or strip the scheme and a leading `www.`. This removes the template signal, but also real path-based signal.
2. **Add legitimate URLs with realistic paths and query strings** from another source (for example Tranco domains plus Common Crawl paths). This means a team decision on a second data source.
3. **At minimum, evaluate on a held-out set not drawn from PhiUSIIL**: recent OpenPhish or PhishTank plus real legitimate links with paths. Don't report the PhiUSIIL test-split accuracy as the headline number.

### Approximate, outside the model: the lookalike check
`URLSimilarityIndex` targets a real threat (typosquatting and homographs) that LinkGuard's "reasons" should explain. Build it as a **rule outside the model**:

- Compute edit or visual distance to a published top-sites list such as Tranco.
- Flag "near but not equal to" a well-known domain, for example "looks like paypal.com but isn't".
- Don't train the model on it with PhiUSIIL data. There, every legitimate row is by construction an exact match to the list, so the model would learn "on the list = safe" and nothing about lookalikes.

### Drop
- **`URLSimilarityIndex`, `TLDLegitimateProb`, `URLCharProb`.** They leak or were built from knowledge of the class, and their reference data is unpublished. A `TLDLegitimateProb`-style feature can be rebuilt later from a published list, but only if the same list is used at train and serve time, and only after the template problem is fixed.
- **`URL`, `Domain`, `TLD`, `Title`, `FILENAME`.** Identifiers. `TLD` could be one-hot encoded from our own parser if wanted, but that is not a first-sprint feature.
- **All 28 PAGE features, for v1.** Three reasons:
  - The authors' definitions are unpublished, so our versions would be approximations with unknown skew.
  - LinkGuard may only fetch through the backend's sandboxed fetcher (AGENTS.md). That fetcher does not exist yet.
  - Phishing pages go offline within hours. At scan time many will be dead, while in training every row has a page. That is a structural train/serve mismatch.

  The PhiUSIIL legitimate pages also appear to be top-site homepages (inferred from the template), so page features probably share the template bias.

  **Revisit later.** Once the sandboxed fetcher exists, the form signals (`HasPasswordField`, `HasExternalFormSubmit`, `HasHiddenFields`, `DomainTitleMatchScore`) are the ones worth rebuilding. Re-extract them from pages we fetch ourselves, not from the CSV columns.

### Risk summary
Training on columns we can't reproduce live, or that encode how the dataset was built, will produce a model that scores about 99% in the notebook and fails on real input. The reported live collapse (TSS 0.996 → 0.000 [9]) is exactly that failure. For the older, less confident users LinkGuard targets, the likely symptom is ordinary links being flagged as phishing, which destroys trust.

---

## 6. Sources

Direct reads are marked **read**. Items seen only through search-engine excerpts are marked **excerpt**.

1. UCI Machine Learning Repository, *PhiUSIIL Phishing URL (Website)*, dataset 967. https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset (read)
2. UCI dataset metadata API for id 967 (variables table, `variable_info`, `instances_represent`). https://archive.ics.uci.edu/api/dataset?id=967 (read)
3. Prasad, A. & Chandra, S. (2024). *PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning.* Computers & Security 136, 103545. https://doi.org/10.1016/j.cose.2023.103545. Closed access, and the full text was **not read**. Abstract claims (99.79% / 99.24%, the attack types, and "extracts URL features, downloads the webpage … derives new features") come from search excerpts of https://www.sciencedirect.com/science/article/abs/pii/S0167404823004558 and the ResearchGate listing (excerpt).
4. Prasad, A. & Chandra, S. (2023). *PhiUSIIL Phishing URL Dataset*, Mendeley Data v2, doi:10.17632/shwpxscxy2.2. https://data.mendeley.com/datasets/shwpxscxy2/2 (read)
5. Arvind Prasad (dataset author), *PhiUSIIL Phishing URL Dataset*, Kaggle. https://www.kaggle.com/datasets/ndarvind/phiusiil-phishing-url-dataset, read through https://www.kaggle.com/api/v1/datasets/view/ndarvind/phiusiil-phishing-url-dataset (read)
6. OpenAlex record for the paper, which shows it is closed access. https://api.openalex.org/works/doi:10.1016/j.cose.2023.103545 (read)
7. Etem, T. & Teke, M. (2024). *Advanced Phishing Detection: Leveraging t-SNE Feature Extraction and Machine Learning on a Comprehensive URL Dataset.* Acta Infologica 8(2), 213–221. https://doi.org/10.26650/acin.1521835 (PDF: https://dergipark.org.tr/en/download/article-file/4095302) (read)
8. Fajar, A., Yazid, S. & Budi, I. *Enhancing Phishing Detection through Feature Importance Analysis and Explainable AI: A Comparative Study of CatBoost, XGBoost, and EBM Models.* arXiv:2411.06860. https://arxiv.org/abs/2411.06860 (read; preprint)
9. **Secondary.** *phish-drift* (GitHub). https://github.com/awesomedudeworld13/phish-drift (read)
10. **Secondary.** *phishing-attribution-consistency* (GitHub). https://github.com/itsprofarul/phishing-attribution-consistency. Direct fetch returned 404; figures are from search excerpts (excerpt).
11. **Secondary.** fundthmcalculus/grad-school PR #248, "PhiUSIIL loader drops the three legitimacy-derived leaks". https://github.com/fundthmcalculus/grad-school/pull/248 (read)
12. **Secondary.** Hugging Face model card *valezion/url-phishing-detector*. https://huggingface.co/valezion/url-phishing-detector (read)
13. **Secondary.** Varghese, E. *Detection of Phishing URLs using Machine Learning*, MSc Research Project, National College of Ireland. https://norma.ncirl.ie/8277/1/eminvarghese.pdf (read). Its feature definitions are loose and in places garbled; treat them as weak.
14. **Secondary.** Data-source claim ("legitimate URLs sourced from the Open PageRank Initiative … phishing URLs fetched from PhishTank, OpenPhish, and MalwareWorld"). Seen in search excerpts attributed to *LegitPhish: A large-scale annotated dataset for URL-based phishing detection*, Data in Brief (2025). https://www.sciencedirect.com/science/article/pii/S2352340925006961 (excerpt; the page returned 403).

---

## 7. Open questions

Most of these are answered by reading the paper. MTU library access to *Computers & Security* should cover it.

1. **Exact formulas** for `URLSimilarityIndex` (weighting, comparison set, how the maximum is taken), `CharContinuationRate`, `URLCharProb`, `TLDLegitimateProb`, the obfuscation trio, and the two title-match scores.
2. **Reference data.** Which legitimate list, which version and date, and how many entries (the "10 million" figure is unconfirmed). Is the character-probability table or the TLD table published anywhere? None was found.
3. **Source of legitimate URLs.** Were they really synthesised as `https://www.<domain>` from a domain list? The template evidence [9][12] suggests so, but the paper should say.
4. **Page fetching.** How were pages fetched (raw HTTP or headless browser, redirects followed or not, timeouts)? What happened to phishing URLs that were already offline? Were they dropped, which would bias the sample towards long-lived phishing?
5. **Ambiguous columns.** Is `Robots` about robots.txt or a meta tag? Is `IsHTTPS` taken from the submitted URL or the final URL? Were `Bank`/`Pay`/`Crypto` matched against HTML, title or URL? Are `NoOfURLRedirect`/`NoOfSelfRedirect` HTTP hops or in-page redirects?
6. **Data types.** UCI lists `CharContinuationRate`, `URLSimilarityIndex`, `ObfuscationRatio` and `DegitRatioInURL` as Integer. Check actual dtypes and ranges on the local CSV.
7. **Duplicates.** A secondary source evaluates on 234,987 rows [10], which implies about 808 duplicates. Confirm locally and deduplicate by `URL` before splitting.
8. **`FILENAME`.** Does it encode the class or the collection batch? Check locally, then drop it either way.
9. **Collection dates.** They are not stated in any primary source found. This matters for how stale the phishing patterns are.
