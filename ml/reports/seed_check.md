# Seed check for the tuned model

**In-dataset cross-validation results, not real-world accuracy.**

- Before: learning rate 0.1, up to 100 trees, 31 leaves, min leaf 20.
- After: learning rate 0.1, up to 100 trees, 15 leaves, min leaf 100.
- Each seed makes its own host-grouped, stratified 5-fold split of the 188,295 training rows and sets the model's own randomness. The test rows were not used.
- The check only measures stability. It never picks a seed.

| Seed | Before ROC-AUC | After ROC-AUC | Difference |
|---|---|---|---|
| 0 | 0.8356 | 0.8353 | -0.0002 |
| 1 | 0.8354 | 0.8358 | +0.0004 |
| 2 | 0.8353 | 0.8356 | +0.0003 |
| 3 | 0.8357 | 0.8358 | +0.0001 |
| 4 | 0.8358 | 0.8353 | -0.0005 |

After beats before on 3 of 5 seeds. The mean gain is +0.0000 ± 0.0004 (smallest -0.0005, largest +0.0004). That is within the seed-to-seed noise: no consistent improvement across these five seeds.

Made by `uv run python -m training.seed_check`.
