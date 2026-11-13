# backend

FastAPI service that checks a pasted link for LinkGuard. The link is only ever handled as text: the backend never opens, fetches or follows it.

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). From `backend/`:

```bash
uv sync                                   # once, and after dependencies change
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

`uv sync` also installs the shared feature extractor from `ml/features` as the local package `linkguard-features`.

### The model files

At start-up the backend loads the risk-level cut-offs, the scaler and the model once, and keeps them for every `/scan` call:

| File | Made by |
|---|---|
| `ml/models/cutoffs.json` | the cut-offs story, committed to git (see `ml/README.md`) |
| `ml/models/scaler.joblib` | the train/test split (see `ml/README.md`) |
| `ml/models/model.joblib` | the final model training (see `ml/README.md`) |

The scaler and the model are shared outside git, like the dataset. If any of the three files is missing, start-up stops with a message naming it, for example `Can't start: ...\ml\models\model.joblib is missing.` Start-up also stops if the scaler expects the ten features in a different order from the extractor's, or if `cutoffs.json` isn't exactly `{"lower": <number>, "upper": <number>}` with both between 0 and 1 and lower below upper. Set `LINKGUARD_MODEL_DIR` to load them from another folder.

Each `/scan` call cleans the link, works out its ten hostname features with the shared extractor from `ml/features` (the same function the training code uses, never a copy), scales them, then asks the model for a phishing score. The features come from the link's text alone: the link is never opened or looked up. The score then becomes a risk level:

| Phishing score | Risk level |
|---|---|
| below `lower` | Safe |
| from `lower` up to below `upper` | Suspicious |
| `upper` or above | High risk |

The cut-offs are read from `cutoffs.json`, never typed into the code, so changing the file and restarting the backend changes the levels with no code change.

The tests build a small scaler, model and cut-offs file of their own in a temporary folder, shaped like the real ones (a Pipeline that keeps the final features, then gradient boosting), so they never need the real files.

The interactive API docs are at http://127.0.0.1:8000/docs while it runs.

## Test it

From `backend/`:

```bash
uv run pytest
```

Or from the repo root: `uv run --project backend pytest backend/tests`.

## `POST /scan`

Send the pasted text as JSON:

```json
{"url": "https://login.example/verify"}
```

### Reply (status 200)

This is the one shape the page and the trained model both use, so the field names never change.

| Field | What it holds |
|---|---|
| `url` | The cleaned link, including `https://` if the user omitted the scheme |
| `risk_level` | `"Safe"`, `"Suspicious"` or `"High risk"`, or `null` in a placeholder reply |
| `score` | The model's phishing score, a number from 0 to 1, or `null` in a placeholder reply |
| `reasons` | Up to three plain-language reasons, empty for a Safe result or a placeholder reply |
| `placeholder` | `false` now that the trained model is served |

For example:

```json
{
  "url": "https://login.example/verify",
  "risk_level": "Suspicious",
  "score": 0.41,
  "reasons": [],
  "placeholder": false
}
```

`reasons` stays empty until the reasons are added to the reply.

### Placeholder reply

Before the trained model was served, every successful reply was a placeholder. It never contained a made-up risk level or score. The page still handles one:

```json
{
  "url": "https://login.example/verify",
  "risk_level": null,
  "score": null,
  "reasons": [],
  "placeholder": true
}
```

The page shows "Checking isn't switched on yet, so we can't give a result for this link." while `placeholder` is `true`.

### Error reply (status 400)

When the pasted text fails the cleaning and checking rules, the reply has status 400 and one message, using the exact wording from the clear-errors story:

```json
{"error": "Paste a link first"}
```

The possible messages are:

- `Paste a link first`
- `That link is too long to check. Links over 2,000 characters can't be checked.`
- `That doesn't look like a web address. It usually starts with www. or https://`

`app.links.clean_link()` removes surrounding whitespace and internal line breaks,
then enclosing quotes or angle brackets, then trailing sentence punctuation. It
adds `https://` when omitted, and returns a `CleanedLink` containing `url` and
`added_https`. The flag is internal metadata; it does not add a field to the API
reply. Length is checked after cleaning, with exactly 2,000 characters allowed.
The host must be a dotted hostname or an IP address. Parsing never fetches the
link or resolves its host. Invalid input returns before the link is scored.

### Missing `url` field (status 422)

A request with no `url` field gets FastAPI's standard validation error, not a crash:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "url"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```
