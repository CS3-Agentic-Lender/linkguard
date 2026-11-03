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
| `ml/models/` | Trained model and scaler files (`*.joblib`, `*.pkl`) | No, those file types are ignored |

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
6. Remove one leading `www.`. A host of only `www.` is treated as `www`.
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
