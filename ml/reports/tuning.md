# Tuning the chosen model

**In-dataset cross-validation results, not real-world accuracy.**

## How it was made

- 188,295 training rows. They are the training part of the shared host-grouped split. The test rows were not used.
- The model is gradient boosting (HistGradientBoostingClassifier), on the 8 final features.
- Stratified 5-fold cross-validation, grouped by host, with seed 0. These are the same folds as the model comparison.
- Inside each fold the scaler and the model are fitted together on the fold's training rows only.
- Every combination below was tried. The scoring measure is ROC-AUC, chosen before the search ran.
- Combinations within 0.001 of the best mean ROC-AUC count as a tie, and the simplest wins: fewer leaves, then fewer trees, then larger leaves, then a smaller learning rate.
- Phishing (label 1) is the positive class. Each score is the mean over the folds ± the standard deviation. Recall, precision, F1, F2 and accuracy use the default 0.5 flag line. The risk-level cut-offs set the real ones.

## Before and after

| Model | Phishing recall | Precision | F1 | ROC-AUC | Accuracy | F2 |
|---|---|---|---|---|---|---|
| Before tuning (learning rate 0.1, up to 100 trees, 31 leaves, min leaf 20) | 0.605 ± 0.013 | 0.906 ± 0.003 | 0.725 ± 0.009 | 0.836 ± 0.003 | 0.804 ± 0.004 | 0.648 ± 0.012 |
| After tuning (learning rate 0.1, up to 100 trees, 15 leaves, min leaf 100) | 0.605 ± 0.014 | 0.903 ± 0.005 | 0.725 ± 0.009 | 0.835 ± 0.003 | 0.804 ± 0.005 | 0.648 ± 0.013 |

Mean ROC-AUC changed by -0.000. The before row is scikit-learn's default settings, which the model comparison scored.

## Every combination, best ROC-AUC first

| Learning rate | Max trees | Leaves | Min leaf | ROC-AUC | Phishing recall | Precision |
|---|---|---|---|---|---|---|
| 0.05 | 100 | 31 | 20 | 0.836 ± 0.003 | 0.607 ± 0.013 | 0.902 ± 0.006 |
| 0.1 | 100 | 31 | 20 | 0.836 ± 0.003 | 0.605 ± 0.013 | 0.906 ± 0.003 |
| 0.05 | 100 | 31 | 100 | 0.836 ± 0.003 | 0.607 ± 0.014 | 0.902 ± 0.006 |
| 0.1 | 100 | 15 | 20 | 0.836 ± 0.003 | 0.605 ± 0.015 | 0.904 ± 0.005 |
| 0.2 | 100 | 15 | 20 | 0.835 ± 0.003 | 0.606 ± 0.015 | 0.904 ± 0.007 |
| 0.2 | 300 | 15 | 20 | 0.835 ± 0.003 | 0.605 ± 0.015 | 0.906 ± 0.006 |
| 0.05 | 300 | 15 | 20 | 0.835 ± 0.003 | 0.605 ± 0.013 | 0.905 ± 0.005 |
| 0.2 | 100 | 31 | 100 | 0.835 ± 0.003 | 0.606 ± 0.014 | 0.903 ± 0.004 |
| 0.2 | 300 | 31 | 100 | 0.835 ± 0.003 | 0.606 ± 0.014 | 0.903 ± 0.004 |
| 0.1 | 100 | 15 | 100 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.903 ± 0.005 |
| 0.05 | 100 | 63 | 20 | 0.835 ± 0.003 | 0.607 ± 0.013 | 0.902 ± 0.005 |
| 0.05 | 300 | 15 | 100 | 0.835 ± 0.003 | 0.604 ± 0.013 | 0.905 ± 0.005 |
| 0.2 | 100 | 15 | 100 | 0.835 ± 0.003 | 0.604 ± 0.014 | 0.906 ± 0.006 |
| 0.05 | 300 | 31 | 20 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.904 ± 0.004 |
| 0.1 | 300 | 31 | 20 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.905 ± 0.004 |
| 0.05 | 300 | 31 | 100 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.904 ± 0.004 |
| 0.05 | 100 | 63 | 100 | 0.835 ± 0.003 | 0.608 ± 0.013 | 0.900 ± 0.003 |
| 0.1 | 300 | 31 | 100 | 0.835 ± 0.003 | 0.606 ± 0.014 | 0.904 ± 0.006 |
| 0.05 | 300 | 63 | 20 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.903 ± 0.005 |
| 0.1 | 100 | 31 | 100 | 0.835 ± 0.003 | 0.606 ± 0.015 | 0.904 ± 0.008 |
| 0.2 | 300 | 15 | 100 | 0.835 ± 0.003 | 0.606 ± 0.014 | 0.904 ± 0.006 |
| 0.1 | 100 | 63 | 100 | 0.835 ± 0.003 | 0.607 ± 0.013 | 0.901 ± 0.003 |
| 0.1 | 300 | 63 | 100 | 0.835 ± 0.003 | 0.607 ± 0.013 | 0.901 ± 0.003 |
| 0.1 | 100 | 63 | 20 | 0.835 ± 0.003 | 0.606 ± 0.012 | 0.904 ± 0.003 |
| 0.1 | 300 | 63 | 20 | 0.835 ± 0.003 | 0.606 ± 0.012 | 0.904 ± 0.003 |
| 0.2 | 100 | 31 | 20 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.905 ± 0.005 |
| 0.2 | 300 | 31 | 20 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.905 ± 0.005 |
| 0.05 | 300 | 63 | 100 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.903 ± 0.005 |
| 0.2 | 100 | 63 | 100 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.903 ± 0.005 |
| 0.2 | 300 | 63 | 100 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.903 ± 0.005 |
| 0.05 | 100 | 15 | 20 | 0.835 ± 0.002 | 0.607 ± 0.014 | 0.902 ± 0.005 |
| 0.05 | 100 | 15 | 100 | 0.835 ± 0.003 | 0.606 ± 0.015 | 0.902 ± 0.005 |
| 0.1 | 300 | 15 | 100 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.904 ± 0.005 |
| 0.2 | 100 | 63 | 20 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.904 ± 0.004 |
| 0.2 | 300 | 63 | 20 | 0.835 ± 0.003 | 0.606 ± 0.013 | 0.904 ± 0.004 |
| 0.1 | 300 | 15 | 20 | 0.835 ± 0.003 | 0.605 ± 0.014 | 0.904 ± 0.003 |

Made by `uv run python -m training.tuning`.
