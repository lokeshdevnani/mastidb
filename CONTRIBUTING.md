# Contributing

MastiDB is a learning engine first, so the bar for a PR is "does this make the thing clearer or more correct", not "does this look like production code". Small fixes and readability PRs are very welcome. Big features are more fun when they line up with [ROADMAP.md](ROADMAP.md).

## Before you start

Read [ARCHITECTURE.md](ARCHITECTURE.md). It explains the on-disk format and both query paths, and it'll save you from re-deriving why group keys stay as dictionary ids.

## Setup

```sh
git clone https://github.com/lokeshdevnani/mastidb.git
cd mastidb
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python setup.py install     # compiles the hot modules with mypyc
```

## Tests

```sh
python -m pytest tests/ -q
```

The integration tests under `tests/` are the real specification of query behaviour — if you change execution, they should still pass, and if you fix something they didn't catch, add a case.

For anything performance-related, `tests/million_test.py` is the yardstick. It keeps a running log of timings as comments; paste your before/after numbers into the PR so the next person can see what moved.

## A few house rules

- Keep diffs focused. No drive-by refactors bundled with a fix.
- Don't commit build artefacts (`*.so`, `build/`, `.mypy_cache/`), large datasets, or editor settings.
- If you change how something works, update the docs in the same PR. Stale docs are worse than no docs.
