# Tuning the chosen model

**In-dataset cross-validation results, not real-world accuracy.**

## How it was made

- 188,295 training rows. They are the training part of the shared host-grouped split. The test rows were not used.
- The model is logistic regression with balanced class weights and the liblinear solver, on the 8 final features.
- Stratified 5-fold cross-validation, grouped by host, with seed 0. These are the same folds as the model comparison.
- Inside each fold the scaler and the model are fitted together on the fold's training rows only.
- Every combination below was tried. The scoring measure is F2, chosen before the search ran.
- Phishing (label 1) is the positive class. Each score is the mean over the folds ± the standard deviation.

## Before and after

| Model | Phishing recall | Precision | F1 | ROC-AUC | Accuracy | F2 |
|---|---|---|---|---|---|---|
| Before tuning (C = 1, l2) | 0.644 ± 0.011 | 0.797 ± 0.009 | 0.712 ± 0.007 | 0.785 ± 0.002 | 0.778 ± 0.005 | 0.669 ± 0.009 |
| After tuning (C = 0.01, l2) | 0.646 ± 0.011 | 0.799 ± 0.004 | 0.714 ± 0.007 | 0.786 ± 0.002 | 0.779 ± 0.004 | 0.671 ± 0.009 |

Mean F2 changed by +0.002. On an exact tie the smaller C wins, because it is the simpler model.

The before row uses the model comparison's settings (C = 1, l2), scored again here with the liblinear solver on the same folds. The comparison used the default lbfgs solver, which cannot do l1, so its numbers differ slightly.

## Every combination

| C | Penalty | F2 | Phishing recall | Precision |
|---|---|---|---|---|
| 0.001 | l2 | 0.665 ± 0.013 | 0.638 ± 0.018 | 0.804 ± 0.014 |
| 0.01 | l2 | 0.671 ± 0.009 | 0.646 ± 0.011 | 0.799 ± 0.004 |
| 0.1 | l2 | 0.670 ± 0.009 | 0.644 ± 0.011 | 0.801 ± 0.007 |
| 1 | l2 | 0.669 ± 0.009 | 0.644 ± 0.011 | 0.797 ± 0.009 |
| 10 | l2 | 0.670 ± 0.009 | 0.644 ± 0.011 | 0.797 ± 0.010 |
| 100 | l2 | 0.670 ± 0.009 | 0.644 ± 0.011 | 0.797 ± 0.010 |
| 1000 | l2 | 0.670 ± 0.009 | 0.644 ± 0.011 | 0.797 ± 0.010 |
| 0.001 | l1 | 0.666 ± 0.011 | 0.640 ± 0.015 | 0.798 ± 0.013 |
| 0.01 | l1 | 0.669 ± 0.010 | 0.642 ± 0.012 | 0.802 ± 0.006 |
| 0.1 | l1 | 0.670 ± 0.009 | 0.644 ± 0.012 | 0.801 ± 0.007 |
| 1 | l1 | 0.670 ± 0.009 | 0.644 ± 0.011 | 0.799 ± 0.007 |
| 10 | l1 | 0.669 ± 0.010 | 0.644 ± 0.011 | 0.797 ± 0.009 |
| 100 | l1 | 0.669 ± 0.010 | 0.644 ± 0.011 | 0.797 ± 0.009 |
| 1000 | l1 | 0.669 ± 0.010 | 0.644 ± 0.011 | 0.797 ± 0.009 |

Made by `uv run python -m training.tuning`.
