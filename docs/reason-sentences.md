# Reason sentences

When a link is Suspicious or High risk, the result shows up to three reasons: the features that raised its score most, each as one plain sentence. This page lists the sentence for every feature, and the features that are never shown, with the reason.

The sentences live in one place in the code, `ml/features/reasons.py`. The result page and the /scan reply read them from there. A test (`ml/tests/test_reasons.py`) checks this page matches that file word for word, so change both together.

Each sentence describes the side of a feature that points to phishing: a long website name, many numbers, many dots or hyphens, few letters. The code that picks the reasons should only show a sentence when the link really is on that side.

## Shown to users

| Feature | Sentence |
| --- | --- |
| `HostnameLength` | The website name in this link is unusually long. |
| `IsDomainIP` | This link uses a string of numbers instead of a website name. |
| `LetterRatioInHostname` | Much of the website name is numbers or symbols, not letters. |
| `NoOfDigitsInHostname` | The website name contains a lot of numbers. |
| `DigitRatioInHostname` | Numbers make up a large part of the website name. |
| `NoOfSpecialCharsInHostname` | The website name has a lot of dots or hyphens. |

## Never shown

| Feature | Why |
| --- | --- |
| `TLDLength` | Marked to watch: common endings like .com are typical of the big sites' front pages that make up the dataset's legitimate links, so it may not be a real warning sign (see ml/reports/final_feature_list.md). |
| `NoOfSubDomain` | Marked to watch: few subdomains is typical of the big sites' front pages that make up the dataset's legitimate links, so it may not be a real warning sign (see ml/reports/final_feature_list.md). |
| `NoOfLettersInHostname` | The model does not use it, because it copies other features (see ml/reports/final_feature_list.md). |
| `SpecialCharRatioInHostname` | The model does not use it, because it copies other features (see ml/reports/final_feature_list.md). |
