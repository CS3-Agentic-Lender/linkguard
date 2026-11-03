# Random forest importance on held-out training hosts

| Rank | Feature | Accuracy drop |
|---|---|---|
| 1 | `NoOfSubDomain` | 0.0595 |
| 2 | `TLDLength` | 0.0497 |
| 3 | `HostnameLength` | 0.0120 |
| 4 | `NoOfDigitsInHostname` | 0.0101 |
| 5 | `NoOfSpecialCharsInHostname` | 0.0045 |
| 6 | `DigitRatioInHostname` | 0.0024 |
| 7 | `LetterRatioInHostname` | 0.0020 |
| 8 | `SpecialCharRatioInHostname` | 0.0005 |
| 9 | `NoOfLettersInHostname` | 0.0004 |
| 10 | `IsDomainIP` | 0.0000 |

The forest learned from 150,532 training rows and was scored on 37,763 rows from held-out training hosts. No host is on both sides. The test split is never used.

Accuracy on the rows it learned from: 0.812. On the held-out hosts: 0.800. Seed: 0. Trees: 100. Shuffles per feature: 5.

Made by `uv run python -m ranking.held_out_importance`.
