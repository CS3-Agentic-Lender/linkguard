# ml

Dataset, feature engineering and model training for LinkGuard.

## Get the dataset

We train on the **PhiUSIIL Phishing URL (Website)** dataset from the UCI Machine Learning Repository: 235,795 labelled URLs with 54 features. The CSV is about 54 MB, so it is not in git. Each person downloads their own copy.

### 1. Download

Go to the dataset page and click **Download** (top right):

https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset

You get a zip called `phiusiil+phishing+url+dataset.zip` (about 15 MB).

Or, from the repo root on macOS or Linux:

```bash
curl -L -o phiusiil.zip "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"
```

### 2. Put the CSV in `ml/data/`

Unzip it and move the CSV so the path is exactly:

```
ml/data/PhiUSIIL_Phishing_URL_Dataset.csv
```

From the repo root:

```bash
mkdir -p ml/data
unzip -o phiusiil.zip -d ml/data
rm phiusiil.zip
```

Keep the file name as it is. Code in `ml/` reads it from that path.

### 3. Check it

```bash
ls -lh ml/data/PhiUSIIL_Phishing_URL_Dataset.csv   # about 54M
git status                                          # nothing new to commit
```

If `git status` lists the CSV, stop and tell the team. It means the ignore rules have changed, and the file must never be committed.

## Where files live

| Path | Holds | In git? |
|---|---|---|
| `ml/data/` | The downloaded dataset and any cleaned copies | No, the whole folder is ignored |
| `ml/models/` | Trained model and scaler files (`*.joblib`, `*.pkl`). The final model is `ml/models/model.joblib` (see "The final model" below). | No, those file types are ignored |

Training code saves the model and scaler to `ml/models/`, and the backend loads them from there. Like the dataset, they are shared outside git.

## The label is flipped during cleaning

The raw file and our cleaned data use **opposite** label codes:

| `label` | Raw file | After cleaning (what every LinkGuard model uses) |
|---|---|---|
| `1` | legitimate | **phishing** |
| `0` | phishing | **legitimate** |

Cleaning sets new label = 1 − raw label (`ml/cleaning/labels.py`), so phishing, the class we warn users about, is 1. Anything that reads the raw CSV directly, such as `01_load_dataset.ipynb`, still sees the raw coding.

## The cleaned file

`ml/notebooks/03_clean_dataset.ipynb` saves the cleaned data to `ml/data/phiusiil_cleaned.csv`, which is ignored by git like the raw file. Read it with `load_cleaned()` from `ml/cleaning/storage.py`, not a plain `pd.read_csv`. pandas' defaults would turn blank titles and the `na` (Namibia) domain into missing values.

It keeps all 56 columns, but not all of them are model inputs:

| Columns | Use |
|---|---|
| `URL` | Raw text only. The feature extractor reads it to work out URL features. It is never a feature itself. |
| `FILENAME`, `Domain`, `TLD`, `Title` | **Not features.** Kept for reference and checks. |
| `label` | The target: 1 = phishing, 0 = legitimate (flipped from the raw file). |
| Every other column | Numeric features. The leakage check decides which ones the model uses: columns it leaves out are listed with a reason in `ml/leakage/excluded.py`, and the findings are in `ml/reports/leakage_report.md` (made by `04_leakage_check.ipynb`). |

## URL features

The shared function `extract_features` in `ml/features/hostname.py` turns a link into ten hostname features for both training and live scans. The backend installs `ml/features` as a local package (`linkguard-features`), so it imports the same code with no copy. The features follow the template-bias decision record in `docs/adr/`.

The function cleans the link in this order:

1. Remove spaces at the start and end. An empty link is refused.
2. If the link has neither a scheme (such as `https://`) nor a leading `//`, add `//` in front, so `example.com/path` has `example.com` as its host. A link that already starts with `//` is used as is.
3. Keep only the host: drop the scheme, any `user:password@` part, the port, the path, the query and the fragment. The port is not checked. Lowercase the host.
4. Refuse the link if it has no host, or if the host contains a space.
5. Remove one trailing dot.
6. Remove one leading `www.`. A host of only `www.` is treated as `www`. Passing `strip_www=False` skips this step. Only the dataset comparison below does that.
7. If the host is an IP address (IPv4 or IPv6), keep it as written.
8. Otherwise convert non-English names to ASCII (`bücher.de` becomes `xn--bcher-kva.de`). Refuse the link if a part of the name is empty (such as `example.com..`) or longer than 63 characters.

The ten features are:

| Feature | What it counts, and how | Type |
|---|---|---|
| `HostnameLength` | Characters in the cleaned host, dots and hyphens included | Whole number |
| `IsDomainIP` | `1` if the host is an IP address, otherwise `0` | Whole number (0 or 1) |
| `TLDLength` | Characters in the last part of the host. `0` for an IP address | Whole number |
| `NoOfSubDomain` | Parts before the last two, so `shop.example.com` gives 1. `0` for an IP address or a two-part name | Whole number |
| `NoOfLettersInHostname` | Letters `a` to `z` | Whole number |
| `LetterRatioInHostname` | Letters divided by `HostnameLength` | Decimal |
| `NoOfDigitsInHostname` | Digits `0` to `9` | Whole number |
| `DigitRatioInHostname` | Digits divided by `HostnameLength` | Decimal |
| `NoOfSpecialCharsInHostname` | Everything that is not a letter or digit: dots, hyphens, and the colons in an IPv6 address | Whole number |
| `SpecialCharRatioInHostname` | Special characters divided by `HostnameLength` | Decimal |

**Checked against the dataset.** [`reports/feature_comparison.md`](reports/feature_comparison.md) compares `IsDomainIP`, `TLDLength`, `NoOfSubDomain` and `HostnameLength` with the dataset's own columns. It gives a reason for each kind of difference. Each example is a row number in the raw file. The report shows no links from the dataset, because many of them are live phishing sites. Regenerate it from `ml/` with `uv run python -m comparison.compare`.

**Limitation: `.co.uk` and similar endings.** The code does not have a list of two-part endings such as `.co.uk` or `.com.au`, so it always treats the last part as the ending. For a name such as `shop.example.co.uk`, `NoOfSubDomain` is 2 when the real count is 1, because `co` is counted as a subdomain. `TLDLength` is the length of `uk`, not of `co.uk`. Keep this in mind when reading these two features for names under those endings.

## The training feature set

`ml/featureset/build.py` works out the ten features above for every row of the cleaned file. It saves them to `ml/data/training_features.csv`. It is the input for training. It is ignored by git like the other data files, so each person builds their own copy.

It has one row for each row of the cleaned file, with these columns in this order:

| Column | Holds |
|---|---|
| `row` | The row's number in `phiusiil_cleaned.csv`, counting from 0. It links each row back to the cleaned file. |
| The ten features | Worked out by `extract_features`, in the order of the table above |
| `label` | Copied from the cleaned file: 1 = phishing, 0 = legitimate |
| `host` | The cleaned host from `cleaned_host` in `ml/features/hostname.py`. It is the host the features measure: `www.` removed, lowercase, non-English names in ASCII. An IP address stays as written. |

The script imports the shared extractor. It holds no copy of the feature code. It only reads each link as text and never opens it.

### Build it

From the raw dataset, in two steps:

1. Make the cleaned file. Open `ml/notebooks/03_clean_dataset.ipynb` and run every cell. It writes `ml/data/phiusiil_cleaned.csv`.
2. Build the feature set. From `ml/`, run:

```bash
uv run python -m featureset.build
```

If the cleaned file is already there, step 2 is enough.

Every row is checked before anything is saved. If a link can't be read, the script prints how many rows failed for each reason, with an example row number. It then stops with exit code 1 and saves nothing. No row is dropped without being reported.

### Leakage recheck

`ml/leakage/recheck.py` reruns the single-feature leakage check on the ten features. The result is in `ml/reports/leakage_recheck_hostname_features.md`. To make it again, run `uv run python -m leakage.recheck` from `ml/`. It needs the cleaned file too.

### Hosts with both labels

Some hosts have legitimate rows as well as phishing rows. These rows share the same ten features but have different labels. In the cleaned data there are:

| | Hosts | Rows |
|---|---|---|
| All rows | 58 | 159 of 235,370 |
| Training set | 46 | 133 |
| Test set | 12 | 26 |

Each host is in one set only, because the split groups rows by host.

**Rule: keep every row. None is dropped.** The reasons:

- **No leakage.** These hosts were found with the labels of every row, test rows included. No row is removed because of its label. So nothing about the test labels can reach training or shape the test set. Dropping these rows from the whole data would also take the hardest cases out of the test set. Scores would then look better than they are.
- **They are real.** A hosting platform or a hacked site can serve safe links as well as phishing links.
- **Too few to matter.** 159 rows out of 235,370 are too few to change a model.
- **Dropping them from training only gains nothing.** It would need a rule that filters the saved split. The split must never be rebuilt for it, because that would move about 31% of the rows to another set. The gain would be too small to measure.

The rule is `apply_conflicting_hosts_rule()` in `ml/leakage/conflicting_hosts.py`. It returns every row unchanged and never reads the labels. A test checks that it keeps every test-set row of these hosts.

To count them again, run this from `ml/`. It needs the training feature set and the split first (`uv run python -m featureset.build`, then `uv run python -m splitting.build`).

```bash
uv run python -m leakage.conflicting_hosts
```

## The train/test split and the scaler

Every model is trained and tested on one shared split. Make it once, from `ml/`:

```bash
uv run python -m splitting.build
```

It needs `ml/data/phiusiil_cleaned.csv` and takes about 25 seconds. It works out the ten hostname features for every row with the shared extractor, then:

- **Splits by host.** 80% training, 20% test, with every link on one host in the same set and the phishing share kept the same in both (scikit-learn's `StratifiedGroupKFold`, seed 42). The features only read the hostname, so a host in both sets would let the model be tested on rows it has already seen.
- **Scales on training rows only.** A `StandardScaler` (mean 0, spread 1) is fitted on the training rows and only applied to the test rows. It keeps a long count such as `HostnameLength` from swamping a 0-to-1 ratio in models such as logistic regression.
- **Stops before saving** if a set is empty, any host or link is in both sets, or a set's phishing share is more than 0.5 percentage points from the whole data's. The host check reads each link's host with Python's own URL parser (`plain_host`), not the clean-up the split groups by, so a mistake in the grouping is caught instead of passing its own check.

| Output | Holds | In git? |
|---|---|---|
| `ml/data/split.csv` | Each cleaned row's index and its set (`train` or `test`). Load it with `load_split()` from `ml/splitting/split.py`. | No |
| `ml/data/split_check.json` | The number of cleaned rows and a fingerprint of every row's host, saved with the split | No |
| `ml/models/scaler.joblib` | The fitted scaler. Load it with `load_scaler()` from `ml/splitting/scaling.py`. | No |
| `ml/reports/scaling_distributions.png` | Each feature on the training rows, before and after scaling | Yes |

Training and evaluation load these files and never make a split of their own. Rerunning gives exactly the same split.

`load_split(path, hosts)` takes the cleaned hosts of the data it will be used with, one per row (the training feature set's `host` column, for example). It stops with a message if the cleaned data has been rebuilt or reordered since the split was made, if a row is missing or listed twice, or if the check file is missing. Without this, an old split used with reordered cleaned data would quietly put about 2,200 hosts in both sets. The fix is always to rerun `uv run python -m splitting.build`.

The saved scaler is fitted on the whole training set. Any later step that fits a scaler of its own, for example inside cross-validation or after feature selection, fits it on training rows only, never on test rows.

## Feature ranking

The code in `ml/ranking/` ranks the ten features by how much they help. It only reads the training split: the feature set's rows that `ml/data/split.csv` marks `train`. Test rows are dropped before anything is scored. It needs both files. The split is read with `load_split`, so its check file must match the feature set. If a file is missing, the split was made from different cleaned data, or a training row is not in the feature set, it stops with a message naming the step to run.

### PCA

PCA finds the directions in which the training rows spread out the most. Each direction is a component, a weighted mix of the ten features. The rows are scaled with the saved scaler from `ml/models/scaler.joblib`, which is only used to transform. It is never fitted again. PCA keeps all ten components and uses a fixed seed, so a second run gives the same result. From `ml/`, run:

```bash
uv run python -m ranking.pca
```

It saves [`ml/reports/pca.md`](reports/pca.md) and the chart [`ml/reports/pca_explained_variance.png`](reports/pca_explained_variance.png). The report has the variance of each component, the chart and each feature's weight on the main components, with the two largest on each marked. The main components are the fewest that reach 95% of the variance.

**Result:** 5 of the 10 components reach 95% of the variance (95.5%).

PCA ignores the label. Its weights guide which real features go on the final list. The components are never model inputs. Any later cross-validation puts the scaler and PCA in one scikit-learn Pipeline, fitted on each fold's training part.

### Mutual information

Mutual information is 0 when a feature tells nothing about the label and grows the more it does. It also catches relationships that are not a straight line. The seven whole-number features are scored as discrete values. The three ratios are continuous. The seed is fixed, so a second run gives the same scores. From `ml/`, run:

```bash
uv run python -m ranking.mutual_info
```

It prints the ranking and saves it to `ml/reports/mutual_information.md`.

### Random forest importance

A random forest is many decision trees, each trained on a random sample of the training rows. A feature's importance is how much its splits cut the mix of labels, averaged over every tree. The ten importances add up to 1. The forest uses the unscaled features, because scale makes no difference to a tree. It has 100 trees and a fixed seed, so a second run gives the same order. This built-in importance tends to favour features with many different values, so it is a cross-check, not a verdict. From `ml/`, run:

```bash
uv run python -m ranking.forest_importance
```

It prints the ranking and saves it to `ml/reports/forest_importance.md`.

### Random forest importance on held-out training hosts

The built-in importance is measured on the rows the forest learned from. This is the fairer check. 80% of the training hosts teach the forest. The other 20% are held out, with no host on both sides. Each feature is then shuffled on the held-out rows, and the drop in accuracy shows how much the forest relies on it. The test split is never used. From `ml/`, run:

```bash
uv run python -m ranking.held_out_importance
```

It saves `ml/reports/held_out_importance.md`.

### The final feature list

The model trains on 8 of the ten features. The list, with a reason for every feature kept or dropped, is in [`ml/reports/final_feature_list.md`](reports/final_feature_list.md). It is made from the four rankings above with one chart that compares them. From `ml/`, run:

```bash
uv run python -m ranking.final_list
```

It saves `ml/reports/final_feature_list.md` and `ml/reports/feature_ranking_comparison.png`. The list is in code as `FINAL_FEATURES` in `ml/ranking/final_list.py`.

## Chart numbers for the charts page

The phishing charts page reads a small summary file of counts and percentages, not the dataset. Make it from `ml/`:

```bash
uv run python -m charts.summary
```

It reads the cleaned data and writes `ml/reports/chart_summary.json` (committed, about 3 KB). The first chart is the class balance: how many links are phishing and how many are legitimate, as a share of all links. Its takeaway says whether the dataset is balanced, using the share of the smaller class: 45% or more is balanced, 20% to 45% is mildly imbalanced, and under 20% is heavily imbalanced. Three more charts each compare phishing with legitimate links: links that use HTTPS, links longer than 50 characters and links that contain a hyphen. Each chart has a one-line takeaway, worked out from the unrounded shares, and the file carries the dataset note and the source line the licence asks for.

| Field | Holds |
|---|---|
| `source` | The credit and the "modified version" line the licence asks for |
| `dataset_note` | Every legitimate link here is a homepage, so the charts show warning signs, not proof of safety |
| `totals` | Phishing and legitimate link counts |
| `charts[]` | `id`, `title`, `takeaway`, `unit` (`percent`) and `groups`: for Phishing and Legitimate, the `value` (percent, 1 decimal), the `count` with the sign and the `total` |

**A value of 0.0 is not always zero.** `value` is rounded to one decimal, so a small share shows as `0.0`. For example, 13 of the 134,850 legitimate links are longer than 50 characters, which is 0.01%. The charts page should check `count`, and show something like "under 0.1%" when `value` is `0.0` but `count` is not 0.

It stops without saving if the totals differ from `ml/reports/cleaning_report.md`, which would mean the label is the wrong way round. No link from the dataset goes into the file, and no takeaway may say that HTTPS, a padlock or a short link means safe (a test checks every takeaway). Another test checks the committed file against its own counts and the cleaning report, so a hand edit is caught: rerun the script instead.

## Training pipeline

`ml/training/pipeline.py` loads the training rows every classifier trains on. It reads three files that earlier steps save, and makes none of its own:

| File | Saved by | Holds |
|---|---|---|
| `ml/data/training_features.csv` | the training feature set (above) | One line per cleaned row, in row order: `row` (the cleaned row number), the ten hostname features in the extractor's order, `label` (1 = phishing, 0 = legitimate) and `host` |
| `ml/data/split.csv` | the train/test split (above) | Columns `row` and `set`: each feature-set row number (counting from 0) and whether it is `train` or `test` |
| `ml/models/scaler.joblib` | the train/test split (above) | The scaler, fitted on the training rows only |

Run it from `ml/` with one command:

```bash
uv run python -m training.pipeline
```

`--features`, `--split` and `--scaler` point it at other files. It prints the number of training rows and the class counts, with phishing as label 1, and stops with a message naming the problem if a file is missing or does not match.

What it guarantees:

- **No new split.** The training rows are exactly the `train` rows of the saved split.
- **No scaler is fitted.** The saved scaler only transforms. The pipeline checks it was fitted on the ten features in the same order.
- **Test rows are never read.** Only the training row numbers are taken from the split, and every other line of the feature file is skipped by the reader.
- **Rows can't slip.** Every line read must carry the `row` number the split asked for. If the feature set were ever out of step with the split, the run stops instead of training on the wrong rows.
- **Only the agreed features are model inputs.** The feature matrix must be the ten hostname features in order. Any column from the excluded list (`ml/leakage/excluded.py`) stops the run by name. `row` and `host` are never features. `host` is kept for grouping the cross-validation folds.

The classifier story uses it from Python:

```python
from training.pipeline import hand_to_classifiers, load_training_set

training_set = load_training_set()   # .scaled, .labels, .hostnames, .features (unscaled), .rows
fitted = hand_to_classifiers({"baseline": DummyClassifier()}, training_set)
```

`hand_to_classifiers` fits a fresh copy of each classifier on the same scaled training rows. Cross-validation, where the scaler is refitted inside each fold's own pipeline, belongs to the classifier story and uses `.features` and `.hostnames`.

The tests (`ml/tests/test_training_pipeline.py`) run on a small made-up sample, because CI has no dataset. Its numbers say nothing about real model performance.

## Training the classifiers

`ml/training/classifiers.py` trains every model through the training pipeline, on the 8 features in the final feature list. The models are a baseline that always guesses the most common class, logistic regression, logistic regression with balanced class weights, a random forest and gradient boosting.

Each model is scored with 5-fold cross-validation on the training rows. The folds are grouped by host, so no website is in two folds. They are stratified, so each fold keeps the phishing share. The seed is fixed. Inside each fold the scaler and the model sit in one Pipeline, so the scaler only learns from that fold's training rows. The test split is never loaded. From `ml/`, run:

```bash
uv run python -m training.classifiers
```

It saves `ml/reports/cv_results.json`: for every model and fold, phishing recall, precision, F1, ROC-AUC and accuracy on the held-out fold and on the fold's own training rows, plus the held-out fold's confusion counts. Phishing is the positive class.

## Model comparison

`ml/training/model_comparison.py` turns the cross-validation results into one comparison table and picks the model. It reads `ml/reports/cv_results.json`, which `uv run python -m training.classifiers` saves, and trains nothing itself. Run it from `ml/`:

```bash
uv run python -m training.model_comparison
```

It writes:

| File | Holds |
|---|---|
| `ml/reports/model_comparison.md` | For each model and the baseline, the mean and standard deviation over the 5 folds of phishing recall, precision, F1, ROC-AUC and accuracy (last). A second table puts each model's training recall and F1 next to its cross-validation ones, with the note on over- and underfitting under it. Then the chosen model, the reason and what the choice costs on the other measures. The class balance note comes last. |
| `ml/reports/confusion_matrices/<model>.png` | One confusion matrix per model. It adds up the held-out folds, so every training row is predicted once by a model that never trained on it. |

How the model is chosen:

1. The highest mean phishing recall wins.
2. If models are within 0.01 of the best recall, the highest mean F1 wins.
3. If they are also within 0.01 of the best F1 among them, the simpler model wins (logistic regression, then the balanced one, then random forest, then gradient boosting).
4. The baseline is never chosen. It is there to show what always guessing the most common class scores.

This was the Sprint 2 rule. At Sprint 3 planning the team changed it to the highest ROC-AUC, because the risk-level cut-offs set our own flag lines. That picks gradient boosting (0.836). See "Tuning the chosen model" below.

A model looks overfit when its training recall or F1 is more than 0.05 above its cross-validation score. It looks underfit when its F1 on its own training rows is under 0.70.

The run stops and saves nothing if the results file:

- is cut off or is not valid JSON
- is missing a model, a score or any other value the report reads, or does not have exactly 5 folds
- was trained on a different feature list
- has held-out counts that do not add up to every training row once, or are not whole numbers of 0 or more
- has a fold whose recall, precision, F1 or accuracy does not match its own confusion counts

The report also names a known limitation. The split keeps each host in one set but not each parent domain. On the shared split, 23.5% of test links share a parent domain (such as `web.app`) with training links. So the scores may look better than they really are.

These are in-dataset cross-validation results, not real-world accuracy. The tests (`ml/tests/test_model_comparison.py`) use a made-up results file.

## Tuning the chosen model

`ml/training/tuning.py` tunes the chosen model, gradient boosting (`HistGradientBoostingClassifier`). Sprint 3 planning picked it by ROC-AUC (0.836 in the model comparison), because the risk-level cut-offs set our own flag lines. It tries every combination of these settings:

| Setting | Values | Why |
|---|---|---|
| `learning_rate` | 0.05, 0.1, 0.2 | How big a step each new tree takes. The default is 0.1. |
| `max_iter` | 100, 300 | The most trees allowed. Early stopping can stop sooner. The default is 100. |
| `max_leaf_nodes` | 15, 31, 63 | How detailed each tree may be. The default is 31. |
| `min_samples_leaf` | 20, 100 | The fewest rows a leaf may hold. A larger value stops a tree learning from a few odd rows. The default is 20. |
| Early stopping, seed, class weight | on, 0, none (fixed) | These match the model comparison, so its settings are the "before" row. |

Each combination is scored with the same host-grouped, stratified 5-fold cross-validation as the model comparison (same folds, seed 0). The scaler and the model sit in one Pipeline per fold. The scoring measure is **ROC-AUC**, chosen before the search ran. Combinations within 0.001 of the best mean ROC-AUC count as a tie, and the simplest wins: fewer leaves, then fewer trees, then larger leaves, then a smaller learning rate. The test split is never loaded. Run it from `ml/` (about 30 seconds on 10 cores):

```bash
uv run python -m training.tuning
```

**Known limitation:** on the real data early stopping is on, so gradient boosting holds back 10% of each fold's training rows to decide when to stop. That hold-out is not grouped by host, so a host can be on both sides of it. The outer held-out fold and the test split are never touched, so the scores stay honest, but early stopping may stop a little late.

It writes `ml/reports/tuning_results.json` (every combination's scores on every fold) and `ml/reports/tuning.md` (the before and after table in the model comparison's layout, with F2 added, then every combination).

### Seed check

The search uses one seed. `ml/training/seed_check.py` scores the before and after settings again with seeds 0 to 4. Each seed makes its own host-grouped fold split and sets the model's own randomness. It reports whether after beats before on every seed, and by how much. It only measures stability. It never picks a seed, because picking the luckiest seed would be fitting to noise. Run it after the tuning (about 1.5 minutes):

```bash
uv run python -m training.seed_check
```

It writes `ml/reports/seed_check.json` and `ml/reports/seed_check.md`.

## The final model

`ml/training/final_model.py` fits the tuned gradient boosting model on every training row and saves it to **`ml/models/model.joblib`**. It reads the chosen settings from `ml/reports/tuning_results.json`, so run the tuning first. From `ml/`:

```bash
uv run python -m training.tuning        # if tuning_results.json is not there yet
uv run python -m training.final_model
```

Gradient boosting does not need scaled inputs, because each tree only compares a feature with a split value. The model still sits after the saved scaler, so the backend has one fixed chain whatever model we use. The test split is never loaded. Like the scaler, the model file is gitignored and shared outside git. Anyone can rebuild it with the two commands above.

How to use the two files for one link:

1. Work out the ten hostname features with `extract_features`, in the order of `FEATURE_NAMES`.
2. Transform them with the saved scaler, `ml/models/scaler.joblib` (transform only).
3. Pass all ten scaled values to the model. Its first step keeps only the 8 in the final feature list, so the backend never picks columns itself. `predict_proba(...)[:, 1]` is the phishing score.

The script first saves to a temporary file. A fresh Python session loads it and predicts 10 training rows, spread from the first to the last. If those predictions differ from the ones the model made before saving, the run stops and the file is deleted. Only a file that passes is moved to `ml/models/model.joblib`. Both files are pickles, and loading a pickle runs code. Only load the files these scripts saved to `ml/models/`.

## The precision/recall curve

`ml/training/precision_recall.py` draws the precision/recall curve for the phishing class. The risk-level cut-offs are chosen from it. From `ml/`:

```bash
uv run python -m training.precision_recall                      # the curve
uv run python -m training.precision_recall --cutoffs 0.2 0.6    # the curve with two cut-offs marked
```

The scores come from cross-validation on the training rows, never from the test split, so the test results stay fair. The training rows are cut into the same 5 host-grouped folds as the model comparison and the tuning (seed 0). For each fold, the tuned gradient boosting model learns from the other 4 folds and scores the held-out one. Each row is scored once, by a model that never saw its host. The settings come from `ml/reports/tuning_results.json`, so run the tuning first.

It writes two files:

- `ml/reports/precision_recall.png`: the chart. Recall (the share of phishing links caught) is along the bottom, precision (the share of flagged links that really are phishing) up the side. The dashed line is what guessing would give.
- `ml/reports/precision_recall.json`: recall, precision and the share of all links flagged at every cut-off from 0.00 to 1.00, in steps of 0.01. Use it to read off the values for a cut-off (rounded to six decimals).

A link counts as flagged when its phishing score is at or above the cut-off. Lowering the cut-off catches more phishing but flags more safe links too.

## Reasons for a link

`features/explain.py` works out which features raised a link's score, by the method in `docs/adr/0004-explanation-method.md`. It lives in the shared `features` package, so the backend's scan can call it. Importing it loads no SHAP, numpy or scikit-learn.

The final model is gradient boosting, so each feature's push on the score comes from SHAP's tree explainer. Build the explainer once, when the model is loaded, and pass it in:

```python
from features.explain import reasons_for_link
from features.reasons import reason_for
from features.explain import tree_explainer

explainer = tree_explainer(model)                     # once, after loading ml/models/model.joblib
reasons = reasons_for_link(model, explainer, scaled)  # scaled: the ten scaled values by name
sentences = [reason_for(name) for name in reasons]
```

`explainer` is a function that takes one link's kept feature values, in the model's order, and returns one push per value. `tree_explainer` wraps `shap.TreeExplainer` on the model's last step that way. It lives in `features`, so the hand check and the backend use the same code. It imports `shap` and `numpy` only when it is called, so importing `features.explain` needs neither. Whoever calls it needs `shap` pinned to the version in `ml/uv.lock`.

Up to three features that pushed the score up, and whose sentence is true for the link, are returned, largest first. Features that are never shown are left out. The result can be empty.

`training/explanation_check.py` checks the reasons by hand on five made-up links. It needs the saved scaler and model, and writes `ml/reports/explanation_check.md`: each link's full explanation next to the reasons picked from it, and the time a scan with reasons takes. From `ml/`:

```bash
uv run python -m training.explanation_check
```

The links are made up (documentation-only addresses) and are only handled as text.

## Evaluating the chosen model on the test split

`ml/evaluation/evaluate.py` scores the one saved chosen model on the held-back test rows. It is the only code in `ml/` that scores a model on the test rows, and it fits and tunes nothing. (The split code and the conflicting-hosts audit also name the test set, but neither loads a model. `ml/tests/test_evaluate.py` lists every module that does and fails if a new one appears.) It needs the feature set, the shared split, the scaler and the saved model (`ml/models/model.joblib`). Run it from `ml/`:

```bash
uv run python -m evaluation.evaluate
```

It prints the scores and writes `ml/reports/evaluation_results.json`, which holds:

- phishing recall (the main measure), precision, F1, ROC-AUC and accuracy on the test rows, plus the false alarm rate on legitimate links, read off the confusion matrix;
- the confusion matrix counts, with rows (actual) and columns (predicted) named "phishing" and "legitimate";
- the same model's training recall and F1, and a one-line note on over- or underfitting, using the same limits as the model comparison (a gap of more than 0.05, or a training F1 under 0.70);
- the ROC curve's points, so the chart can be drawn without reading the test rows again.

Phishing (label 1) is the positive class, and a link counts as phishing when the model's phishing score is above 0.5 (its own `predict()`). The split is read with `load_split`, so the run stops if the split was made from different cleaned data. Before scoring, the run also stops and saves nothing if any cleaned host has rows in both the training and the test set. That guard runs on the real split every time.

Accuracy is not the headline number: a simple pattern rule with nothing learned scores over 99% on PhiUSIIL. These are in-dataset results, not real-world accuracy. The tests (`ml/tests/test_evaluate.py`) use a small made-up set with known answers.

## Source and licence

| | |
|---|---|
| Dataset | PhiUSIIL Phishing URL (Website), by Arvind Prasad and Shalini Chandra |
| Where | UCI Machine Learning Repository, dataset 967: https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset |
| Licence | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| Downloaded | 26 October 2026, file `PhiUSIIL_Phishing_URL_Dataset.csv` (235,795 rows) |
| When the URLs were collected | Not stated. Neither the UCI page nor its metadata gives a collection date. |

**Cite it as:**

> Prasad, A., & Chandra, S. (2024). PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning. *Computers & Security*, 136, 103545. https://doi.org/10.1016/j.cose.2023.103545

**What CC BY 4.0 asks of us:** we may use, share and change the data, including for this project, as long as we credit it. In practice:

- Name the dataset and its authors, and use the citation above wherever we describe or show results from it (reports, presentation, the app's about page).
- Link to the licence.
- Say that we changed it. Our cleaning removes duplicate and invalid rows and recodes the label, so anything built from the cleaned data must say it is based on a modified version.

Because the collection date is unknown, we can't say how current the phishing examples are. Treat this as a limitation when reporting how well the model will do on new links.
