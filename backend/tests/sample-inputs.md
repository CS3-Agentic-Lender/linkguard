# Backend sample inputs

All links below are made-up examples and are handled as text only. `\n` and
`\r` denote actual line-break characters in the test input. Quotes in the Input
column delimit strings; they are not pasted unless escaped.

This table describes the backend cleaning change in
[PR #28](https://github.com/CS3-Agentic-Lender/linkguard/pull/28), tested at
commit `464c3de7081ead18ba60afd9320a8e890246b49a` and merged into `dev` as
`8c0f7a80bd9036571d39829d98a2daeecdfa45a5`. The corresponding tests already
exist in that merged change; this table maps them rather than duplicating them.

## Expected results and test mapping

| ID | Input | Expected cleaned URL or exact error message | HTTP | Existing pytest case in `test_scan.py` |
|---|---|---|---|---|
| E01 | `""` | `Paste a link first` | 400 | `test_empty_input_gets_the_paste_link_error` — empty parameter |
| E02 | `"   "` | `Paste a link first` | 400 | `test_empty_input_gets_the_paste_link_error` — spaces parameter |
| E03 | `"hello there"` | `That doesn't look like a web address. It usually starts with www. or https://` | 400 | `test_invalid_links_return_only_the_agreed_error` — plain words |
| E04 | `"www.example.com/path"` | `https://www.example.com/path`; `added_https=True` | 200 | `test_clean_link_examples` — missing scheme |
| E05 | `" example.com/page. \n"` | `https://example.com/page`; `added_https=True` | 200 | `test_clean_link_examples` — copied whitespace and full stop |
| E06 | `"https://exam\r\nple.com/path"` | `https://example.com/path`; `added_https=False` | 200 | `test_clean_link_examples` — internal line breaks |
| E07 | `"<https://example.com/login>"` | `https://example.com/login`; `added_https=False` | 200 | `test_clean_link_examples` — angle brackets |
| E08 | `"https://example.com/" + "x" * 2000` (2,020 characters) | `That link is too long to check. Links over 2,000 characters can't be checked.` | 400 | `test_invalid_links_return_only_the_agreed_error` — long web link |
| E09 | `"https://127.0.0.1/path"` | `https://127.0.0.1/path`; `added_https=False` | 200 | `test_clean_link_examples` — IP host |
| E10 | `"http://example.com/path?q=1"` | `http://example.com/path?q=1`; `added_https=False` | 200 | `test_clean_link_examples` — explicit HTTP |
| E11 | `"mailto:person@example.com"` | `That doesn't look like a web address. It usually starts with www. or https://` | 400 | `test_invalid_links_return_only_the_agreed_error` — non-web scheme |

For failures, `/scan` returns only `{"error":"<message>"}` with status 400.
For successful inputs it returns the existing placeholder shape with the
cleaned URL, null risk level and score, empty reasons, and `placeholder=true`.
`added_https` is internal function metadata, not an additional API field.

## Boundary and network evidence

- `test_length_limit_uses_the_cleaned_link` accepts exactly 2,000 cleaned
  characters and rejects 2,001. Surrounding wrappers/whitespace are removed
  before counting, and an automatically added scheme counts toward the limit.
- Every test mapped above uses the `no_network` fixture. It rejects outbound
  DNS resolution and socket connections; Windows loopback remains available
  for TestClient's event loop.
- `test_network_block_catches_a_fetch` proves that the fixture actually fails
  when an outgoing connection is attempted. A future cleaner that attempts a
  fetch therefore fails the mapped cases instead of silently using the network.

## Running the tests

From `backend/`:

```powershell
uv run pytest -q
```

The recorded run at the commit above passed **33 tests**, with **100% app
statement coverage (66 statements)**. The backend, ml and secret checks on
the referenced PR passed. The existing httpx dependency warning is separate
work. This table must also be attached to the parent story, and its own PR
must merge before this deliverable is marked Done.
