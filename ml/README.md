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
