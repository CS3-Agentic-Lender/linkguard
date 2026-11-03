# Random forest importance of the ten hostname features

| Rank | Feature | Importance |
|---|---|---|
| 1 | `NoOfSubDomain` | 0.1809 |
| 2 | `NoOfSpecialCharsInHostname` | 0.1539 |
| 3 | `NoOfDigitsInHostname` | 0.1394 |
| 4 | `TLDLength` | 0.1346 |
| 5 | `HostnameLength` | 0.1160 |
| 6 | `DigitRatioInHostname` | 0.1037 |
| 7 | `LetterRatioInHostname` | 0.0749 |
| 8 | `NoOfLettersInHostname` | 0.0656 |
| 9 | `SpecialCharRatioInHostname` | 0.0308 |
| 10 | `IsDomainIP` | 0.0002 |

Training rows: 188,295. Seed: 0. Trees: 100.

The ten importances add up to 1. This built-in importance tends to favour features with many different values, so read it as a cross-check.

Made by `uv run python -m ranking.forest_importance`.
