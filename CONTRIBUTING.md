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

The integration tests under `tests/` are the real specification of query behaviour — if you change execution, they should still pass, and if you fix something they didn't catch, add a case. They run against `tests/datasets/wikipedia.json`, which is committed, so a fresh clone needs no setup.

For anything performance-related, `tests/million_test.py` is the yardstick. It needs the ~1.3M-row menu dataset, which is too big for git:

```sh
python scripts/download_menu_dataset.py     # ~35 MB download, ~146 MB on disk
python tests/million_test.py
```

That script only uses the standard library and skips itself if the files are already there. `tests/datasets/datasets.md` has the details. `million_test.py` keeps a running log of timings as comments; paste your before/after numbers into the PR so the next person can see what moved.

## Cutting a release

Version lives in `setup.py`. PyPI won't let you re-upload a version, so bump first.

```sh
pip install --upgrade build twine
rm -rf dist build
python -m build --sdist          # compiles nothing, but does type-check via mypycify
twine check dist/*
twine upload --repository testpypi dist/*     # rehearse here first
twine upload dist/*
```

Two things to know. `pyproject.toml` declares `mypy` as a build requirement, which is what lets `pip install mastidb` compile with mypyc inside pip's isolated build. And the extensions are marked optional in `setup.py`, so a machine without a C compiler still installs — it just falls back to the pure-Python modules.

Wheels are platform-specific once mypyc is involved, so a source distribution is the honest default. If you want prebuilt wheels later, `cibuildwheel` in CI is the way.

## A few house rules

- Keep diffs focused. No drive-by refactors bundled with a fix.
- Don't commit build artefacts (`*.so`, `build/`, `.mypy_cache/`), large datasets, or editor settings.
- If you change how something works, update the docs in the same PR. Stale docs are worse than no docs.
