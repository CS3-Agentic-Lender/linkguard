# Reasons hand check

The reasons picked for five made-up links, next to the full explanation they come from. Each push is the coefficient times the scaled value, in log-odds, compared with an average training link (every scaled value 0). Above zero pushed the score towards phishing. The rules for picking up to 3 are in `docs/adr/0004-explanation-method.md`.

The links are made up and were only handled as text. The phishing score is the model's probability. Whether a result is Suspicious or High risk depends on the risk cut-offs, which are set elsewhere, so reasons are shown here for every link.

### `http://192.0.2.44/account/verify`

Host measured: `192.0.2.44`. Phishing score: 0.997.

| Feature | Scaled value | Coefficient | Push on the score | Shown? |
|---|---|---|---|---|
| `LetterRatioInHostname` | -7.656 | -0.512 | +3.923 | **Reason 1** |
| `NoOfDigitsInHostname` | +2.174 | +1.617 | +3.514 | **Reason 2** |
| `NoOfSpecialCharsInHostname` | +1.111 | +0.806 | +0.895 | **Reason 3** |
| `IsDomainIP` | +19.189 | +0.012 | +0.231 | not in the top 3 |
| `NoOfSubDomain` | -0.613 | +0.235 | -0.144 | never shown |
| `HostnameLength` | -0.867 | +0.490 | -0.424 | lowered the score |
| `DigitRatioInHostname` | +6.758 | -0.157 | -1.063 | lowered the score |
| `TLDLength` | -4.493 | +0.337 | -1.512 | never shown |

Reasons picked:

1. Much of the website name is numbers or symbols, not letters. (`LetterRatioInHostname`)
2. The website name contains a lot of numbers. (`NoOfDigitsInHostname`)
3. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)

### `https://secure-login-account-update-verification.example.com/`

Host measured: `secure-login-account-update-verification.example.com`. Phishing score: 0.993.

| Feature | Scaled value | Coefficient | Push on the score | Shown? |
|---|---|---|---|---|
| `NoOfSpecialCharsInHostname` | +3.677 | +0.806 | +2.963 | **Reason 1** |
| `HostnameLength` | +3.412 | +0.490 | +1.671 | **Reason 2** |
| `NoOfSubDomain` | +0.867 | +0.235 | +0.203 | never shown |
| `TLDLength` | +0.388 | +0.337 | +0.131 | never shown |
| `DigitRatioInHostname` | -0.341 | -0.157 | +0.054 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.012 | -0.001 | lowered the score |
| `LetterRatioInHostname` | +0.122 | -0.512 | -0.062 | lowered the score |
| `NoOfDigitsInHostname` | -0.316 | +1.617 | -0.511 | lowered the score |

Reasons picked:

1. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)
2. The website name in this link is unusually long. (`HostnameLength`)

### `https://pay8812-34ref77.example.net/`

Host measured: `pay8812-34ref77.example.net`. Phishing score: 0.999.

| Feature | Scaled value | Coefficient | Push on the score | Shown? |
|---|---|---|---|---|
| `NoOfDigitsInHostname` | +2.529 | +1.617 | +4.089 | **Reason 1** |
| `LetterRatioInHostname` | -2.446 | -0.512 | +1.253 | **Reason 2** |
| `NoOfSpecialCharsInHostname` | +1.111 | +0.806 | +0.895 | **Reason 3** |
| `HostnameLength` | +0.865 | +0.490 | +0.424 | not in the top 3 |
| `NoOfSubDomain` | +0.867 | +0.235 | +0.203 | never shown |
| `TLDLength` | +0.388 | +0.337 | +0.131 | never shown |
| `IsDomainIP` | -0.052 | +0.012 | -0.001 | lowered the score |
| `DigitRatioInHostname` | +2.664 | -0.157 | -0.419 | lowered the score |

Reasons picked:

1. The website name contains a lot of numbers. (`NoOfDigitsInHostname`)
2. Much of the website name is numbers or symbols, not letters. (`LetterRatioInHostname`)
3. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)

### `https://www.example.com/`

Host measured: `example.com`. Phishing score: 0.270.

| Feature | Scaled value | Coefficient | Push on the score | Shown? |
|---|---|---|---|---|
| `TLDLength` | +0.388 | +0.337 | +0.131 | never shown |
| `DigitRatioInHostname` | -0.341 | -0.157 | +0.054 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.012 | -0.001 | lowered the score |
| `NoOfSubDomain` | -0.613 | +0.235 | -0.144 | never shown |
| `LetterRatioInHostname` | +0.337 | -0.512 | -0.173 | lowered the score |
| `HostnameLength` | -0.765 | +0.490 | -0.375 | lowered the score |
| `NoOfSpecialCharsInHostname` | -0.600 | +0.806 | -0.483 | lowered the score |
| `NoOfDigitsInHostname` | -0.316 | +1.617 | -0.511 | lowered the score |

Reasons picked: none.


### `https://mail.service.example.co.uk/`

Host measured: `mail.service.example.co.uk`. Phishing score: 0.931.

| Feature | Scaled value | Coefficient | Push on the score | Shown? |
|---|---|---|---|---|
| `NoOfSpecialCharsInHostname` | +1.966 | +0.806 | +1.584 | **Reason 1** |
| `NoOfSubDomain` | +3.827 | +0.235 | +0.898 | never shown |
| `HostnameLength` | +0.763 | +0.490 | +0.374 | **Reason 2** |
| `LetterRatioInHostname` | -0.216 | -0.512 | +0.111 | **Reason 3** |
| `DigitRatioInHostname` | -0.341 | -0.157 | +0.054 | its sentence is not true for this link |
| `IsDomainIP` | -0.052 | +0.012 | -0.001 | lowered the score |
| `TLDLength` | -1.239 | +0.337 | -0.417 | never shown |
| `NoOfDigitsInHostname` | -0.316 | +1.617 | -0.511 | lowered the score |

Reasons picked:

1. The website name has a lot of dots or hyphens. (`NoOfSpecialCharsInHostname`)
2. The website name in this link is unusually long. (`HostnameLength`)
3. Much of the website name is numbers or symbols, not letters. (`LetterRatioInHostname`)

## Timing

The slowest of 200 scans of each link (features, scaling, score and reasons): **1.1 ms**, under the 2 s limit. Loading the model and scaler happens once at start-up and is not included.

Made by `uv run python -m training.explanation_check`.
