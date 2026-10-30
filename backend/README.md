# backend

FastAPI service that checks a pasted link for LinkGuard. The link is only ever handled as text: the backend never opens, fetches or follows it.

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). From `backend/`:

```bash
uv sync                                   # once, and after dependencies change
uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

`uv sync` also installs the shared feature extractor from `ml/features` as the local package `linkguard-features`.

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
| `score` | A number from 0 to 1, or `null` in a placeholder reply |
| `reasons` | Up to three plain-language reasons, empty for a Safe result or a placeholder reply |
| `placeholder` | `true` until the trained model is served, then `false` |

### Placeholder reply

Until the trained model is served, every successful reply is a placeholder. It never contains a made-up risk level or score.

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
link or resolves its host. Invalid input returns before the placeholder response
is built.

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
