# Mutual information of the ten hostname features

| Rank | Feature | Score |
|---|---|---|
| 1 | `LetterRatioInHostname` | 0.1582 |
| 2 | `NoOfSpecialCharsInHostname` | 0.1362 |
| 3 | `DigitRatioInHostname` | 0.1177 |
| 4 | `NoOfDigitsInHostname` | 0.1157 |
| 5 | `HostnameLength` | 0.1155 |
| 6 | `SpecialCharRatioInHostname` | 0.1094 |
| 7 | `NoOfSubDomain` | 0.1093 |
| 8 | `NoOfLettersInHostname` | 0.0744 |
| 9 | `TLDLength` | 0.0176 |
| 10 | `IsDomainIP` | 0.0023 |

Training rows: 188,295. Seed: 0.

Scores are in nats. 0 means the feature tells nothing about the label.

Made by `uv run python -m ranking.mutual_info`.
