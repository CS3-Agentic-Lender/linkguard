---
status: accepted
---

# Ten normalized hostname features to fix the URL template bias

The PhiUSIIL dataset has a template problem. Every legitimate link in it is a bare site front page, such as `www.example.com`, while most phishing links are not. A model trained on the full URL text can learn that template instead of real warning signs. We use **one shared extractor** that reads only the hostname and computes **ten hostname features**, both for training rows and for live scans. Dataset scores are reported only as an upper bound.

Accepted: agreed by the team at the 29 October standup and confirmed by the Product Owner on 30 October. Nikoloz, Ibrahima and Nic supported it.

## Why we need it

The leakage check (`ml/reports/leakage_report.md`, sections 1 and 2) ran on the cleaned file of 235,370 rows. Bare homepage links make up 100.00% of legitimate links and 1.03% of phishing links. A rule that calls a bare homepage legitimate is **99.56%** accurate on its own.

Single columns also predict the label well. Each column below was tested alone with a one-split decision tree, 5-fold cross-validated:

| URL-only column | Accuracy alone (%) |
|---|---|
| `NoOfOtherSpecialCharsInURL` | 79.53 |
| `IsHTTPS` | 79.02 |
| `URLLength` | 74.24 |

None of the 19 URL-only columns scores over 95% alone, so the one-column check does not catch the problem. Together, though, they can describe the legitimate template: no path, no query string, `https`, a `www.` prefix and low character counts. Removing the obviously leaked columns alone does not fix this.

The leakage check excludes 36 columns (`EXCLUDED_FEATURES` in `ml/leakage/excluded.py`): 3 derived from the legitimate class (`URLSimilarityIndex`, `TLDLegitimateProb`, `URLCharProb`), 5 identifiers (`FILENAME`, `URL`, `Domain`, `TLD`, `Title`) and 28 page-content columns that need the fetched page.

## Decision

Use one shared, deterministic extractor for training rows and live scans. It reads the hostname from the URL text and recomputes every feature below. Training does not use the CSV's original URL-wide values, and the raw hostname or URL is never used as a categorical model feature.

### What the extractor does before counting

Every class and every call uses the same steps, in this order:

1. Parse the host and discard the port. The scheme, user part (user name and password), path, query and fragment never become features.
2. Lowercase the host, remove a trailing dot, and remove **one** leading `www.` only.
3. Convert internationalized domain names to ASCII `xn--` form with Python's built-in `idna` codec. This adds no dependency and no online lookup. IP literals are detected locally and handled as IPs, not as IDNA domain names.
4. Count on the resulting non-empty normalized host. Invalid or missing hosts belong to input validation. The extractor never makes a zero-length feature row.

For domain names, the labels are the dot-separated labels of the normalized ASCII host. The suffix rule uses the **last label** and does not use a public suffix list. For IP literals, `TLDLength` and `NoOfSubDomain` are both 0.

### The ten features

The frozen schema, in this order:

| Feature | Definition | Value type |
|---|---|---|
| `HostnameLength` | Number of characters in the normalized host | Integer |
| `IsDomainIP` | 1 if the parsed host is a valid IPv4 or IPv6 literal, otherwise 0 | Integer flag |
| `TLDLength` | Length of the last dot-separated label; 0 for an IP | Integer |
| `NoOfSubDomain` | max(number of labels - 2, 0); 0 for an IP | Integer |
| `NoOfLettersInHostname` | Count of ASCII letters a-z after IDNA conversion | Integer |
| `LetterRatioInHostname` | Letter count / `HostnameLength` | Float |
| `NoOfDigitsInHostname` | Count of ASCII digits 0-9 | Integer |
| `DigitRatioInHostname` | Digit count / `HostnameLength` | Float |
| `NoOfSpecialCharsInHostname` | Count of characters that are neither ASCII letters nor digits, including dots, hyphens and IPv6 colons | Integer |
| `SpecialCharRatioInHostname` | Special count / `HostnameLength` | Float |

Ratios are not rounded and not cast to integers. Names, order, normalization and types stay the same in training and inference. Any later schema change needs an explicit update to both training and serving.

### What the model no longer sees

- The 36 existing exclusions stay excluded.
- Scheme and query features are not carried forward: `IsHTTPS`, and the equals, question-mark and ampersand counts.
- `URLLength` and `DomainLength` are not carried forward: `HostnameLength` replaces them.
- The URL-wide letter, digit and special-character counts and ratios (`NoOfLettersInURL`, `LetterRatioInURL`, `NoOfDegitsInURL`, `DegitRatioInURL`, `NoOfOtherSpecialCharsInURL`, `SpacialCharRatioInURL`) are replaced by their hostname versions.
- The URL-only obfuscation columns (`HasObfuscation`, `NoOfObfuscatedChar`, `ObfuscationRatio`) are not carried forward.
- `CharContinuationRate` is dropped, because no reproducible published formula was established.

The ten hostname features are the only URL-derived model inputs. They are recomputed from the cleaned URL text and are not copied from the CSV.

Training reads the cleaned CSV with `cleaning.storage.load_cleaned()`, preserving blank text and the literal values `na` and `NULL`. Target 1 means phishing and 0 means legitimate.

Nothing in extraction may open, fetch, resolve, preview or follow a dataset or user-provided URL.

## Considered options

- **Ten normalized hostname features** (chosen): removes the strongest scheme, path and query shortcut, keeps training and serving consistent, and fits a small local extractor. It deliberately gives up some useful full-URL signals.
- **Keep all nineteen URL candidates** (turned down): needs less extractor work, but combinations of columns can rebuild the homepage template even though each column passes the one-column check.
- **Only drop scheme and query counts, or only remove the scheme and a leading `www.`** (turned down): a small change, but the remaining full-URL length and character counts still encode path differences.
- **Collect representative legitimate deep links from another source** (turned down for this slice): matches full-URL use better, but adds data collection, labelling, validation and security work. It needs a separate team plan and a second data-source decision.
- **Keep the full URL and only report scores as an upper bound** (turned down as the fix): keeps the feature contract and discloses the limit, but does not correct it. Upper-bound reporting is still part of the chosen fix.
- **Use a bundled public suffix list** (turned down): handles compound suffixes more accurately, offline. The Product Owner chose the simpler last-label rule for this slice to avoid a new dependency.

## Consequences

- Results are described as **hostname-based signals**. A legitimate-looking host can still serve a malicious page. Plain HTTP, user-part, path and query warning signs are outside this model's input.
- Removing the universal `www.` before counting stops that template from leaking into lengths and subdomain counts. It does not prove that domain sampling or other bias is gone.
- Dataset accuracy is an upper bound. It is never the headline claim of live performance, and the evaluation report says so.
- Compound suffixes are not handled. For `example.co.uk`, this rule gives `TLDLength` = 2 and `NoOfSubDomain` = 1, because `co` counts as a subdomain. The rule is not public-suffix-aware.
- The ten values are expected to be correlated. Any zero-variance filtering or feature selection is fitted on training data only and carried into inference.

### Work this decision affects

- **Feature extractor**: a new hostname extractor replaces the URL-wide features for both training and live scans.
- **Final feature list (ranking and selection)**: ranking and selection work on the ten hostname features only. Any zero-variance filter or selection step is fitted on training data and reused at inference.
- **Model training**:
  - Split training and evaluation by normalized hostname, so one host never appears on both sides.
  - Recheck leakage using the recomputed features, and reproduce the grouping counts with the final normalization.
  - Handle the conflicting-label host groups. Ibrahima reported 219,094 hostnames across 235,370 cleaned rows after removing `www.`, with 21,949 rows sharing a host. 58 hostnames have conflicting labels, covering 159 rows. A hostname-only model cannot tell those apart. Ibrahima's proposed exclusion of those rows must be recorded and verified in training preparation. This decision does not delete any rows.
