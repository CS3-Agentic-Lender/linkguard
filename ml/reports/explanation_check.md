# Reasons hand check

The reasons picked for five made-up links, next to the full explanation they come from. Each push is the feature's value from SHAP's tree explainer, in log-odds, compared with an average training link. Above zero pushed the score towards phishing. A scaled value above 0 is above the training average. The rules for picking up to 3 are in `docs/adr/0004-explanation-method.md`.

The links are made up and were only handled as text. The phishing score is the model's probability. Whether a result is Suspicious or High risk depends on the risk cut-offs, which are set elsewhere, so reasons are shown here for every link.

### `http://192.0.2.44/account/verify`

Host measured: `192.0.2.44`. Phishing score: 0.989.

| Feature | Scaled value | Push on the score | Shown? |
|---|---|---|---|
| `NoOfDigitsInHostname` | +2.174 | +5.096 | **Reason 1** |
| `DigitRatioInHostname` | +6.758 | +0.582 | another number reason pushed more |
| `NoOfSpecialCharsInHostname` | +1.111 | +0.422 | **Reason 2** |
| `IsDomainIP` | +19.189 | +0.000 | did not move the score |
| `TLDLength` | -4.493 | -0.129 | never shown |
| `LetterRatioInHostname` | -7.656 | -0.195 | lowered the score |
| `HostnameLength` | -0.867 | -0.605 | lowered the score |
| `NoOfSubDomain` | -0.613 | -1.057 | never shown |

Reasons picked:

1. The website name contains a lot of numbers. (`NoOfDigitsInHostname`)
2. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)

### `https://secure-login-account-update-verification.example.com/`

Host measured: `secure-login-account-update-verification.example.com`. Phishing score: 0.999.

| Feature | Scaled value | Push on the score | Shown? |
|---|---|---|---|
| `HostnameLength` | +3.412 | +4.799 | **Reason 1** |
| `NoOfSpecialCharsInHostname` | +3.677 | +1.987 | **Reason 2** |
| `NoOfSubDomain` | +0.867 | +0.636 | never shown |
| `TLDLength` | +0.388 | +0.287 | never shown |
| `LetterRatioInHostname` | +0.122 | +0.005 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.000 | did not move the score |
| `DigitRatioInHostname` | -0.341 | -0.019 | lowered the score |
| `NoOfDigitsInHostname` | -0.316 | -0.564 | lowered the score |

Reasons picked:

1. The website name in this link is unusually long. (`HostnameLength`)
2. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)

### `https://pay8812-34ref77.example.net/`

Host measured: `pay8812-34ref77.example.net`. Phishing score: 1.000.

| Feature | Scaled value | Push on the score | Shown? |
|---|---|---|---|
| `NoOfDigitsInHostname` | +2.529 | +4.980 | **Reason 1** |
| `NoOfSpecialCharsInHostname` | +1.111 | +1.067 | **Reason 2** |
| `HostnameLength` | +0.865 | +0.721 | **Reason 3** |
| `NoOfSubDomain` | +0.867 | +0.544 | never shown |
| `LetterRatioInHostname` | -2.446 | +0.433 | another number reason pushed more |
| `TLDLength` | +0.388 | +0.293 | never shown |
| `IsDomainIP` | -0.052 | +0.000 | did not move the score |
| `DigitRatioInHostname` | +2.664 | -0.005 | lowered the score |

Reasons picked:

1. The website name contains a lot of numbers. (`NoOfDigitsInHostname`)
2. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)
3. The website name in this link is unusually long. (`HostnameLength`)

### `https://www.example.com/`

Host measured: `example.com`. Phishing score: 0.243.

| Feature | Scaled value | Push on the score | Shown? |
|---|---|---|---|
| `LetterRatioInHostname` | +0.337 | +0.084 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.000 | did not move the score |
| `DigitRatioInHostname` | -0.341 | -0.007 | lowered the score |
| `TLDLength` | +0.388 | -0.014 | never shown |
| `HostnameLength` | -0.765 | -0.326 | lowered the score |
| `NoOfSpecialCharsInHostname` | -0.600 | -0.339 | lowered the score |
| `NoOfSubDomain` | -0.613 | -0.364 | never shown |
| `NoOfDigitsInHostname` | -0.316 | -0.598 | lowered the score |

Reasons picked: none.


### `https://mail.service.example.co.uk/`

Host measured: `mail.service.example.co.uk`. Phishing score: 0.709.

| Feature | Scaled value | Push on the score | Shown? |
|---|---|---|---|
| `NoOfSpecialCharsInHostname` | +1.966 | +1.447 | **Reason 1** |
| `HostnameLength` | +0.763 | +0.944 | **Reason 2** |
| `LetterRatioInHostname` | -0.216 | +0.181 | **Reason 3** |
| `NoOfSubDomain` | +3.827 | +0.137 | never shown |
| `DigitRatioInHostname` | -0.341 | +0.002 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.000 | did not move the score |
| `NoOfDigitsInHostname` | -0.316 | -0.922 | lowered the score |
| `TLDLength` | -1.239 | -1.332 | never shown |

Reasons picked:

1. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)
2. The website name in this link is unusually long. (`HostnameLength`)
3. Much of the website name is numbers or symbols, not letters. (`LetterRatioInHostname`)

## Timing

The slowest of 200 scans of each link (features, scaling, score, pushes and reasons): **32.8 ms**, under the 2 s limit. Loading the model and scaler, and building the explainer, happen once at start-up and are not included.

Made by `uv run python -m training.explanation_check`.
