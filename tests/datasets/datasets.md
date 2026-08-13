# Datasets

## wikipedia.json — committed, used by the tests

24,433 rows of Wikipedia edit records (the same sample Druid's tutorials use). Small
enough to live in git, so `pytest` works on a fresh clone with no setup.

## artists.json — a toy, for kicking the tyres

20-odd rows, six columns, hand-written. Useful when you want to see a query run in a
couple of seconds without ingesting anything real:

```sh
mastidb ingest -d /tmp/artists -s tests/datasets/artists.json
mastidb console -d /tmp/artists
```

## The menu dataset — downloaded on demand

The New York Public Library's "What's on the Menu?" dump: `Dish.csv`, `Menu.csv`,
`MenuItem.csv`, `MenuPage.csv`. `MenuItem.csv` is ~1.3M rows and is what
`tests/million_test.py` benchmarks against. ~146 MB extracted, so it stays out of git.

```sh
python scripts/download_menu_dataset.py
```

That drops the four CSVs into `tests/dataset_menu/` (gitignored) and skips the work if
they're already there. Then build a table to query:

```sh
python -c "from mastidb import Table; Table.from_ingest_source('/tmp/menuitem', 'tests/dataset_menu/MenuItem.csv')"
python tests/million_test.py
```

Source: <http://menus.nypl.org/data> · also used by
[ClickHouse's menus example](https://clickhouse.com/docs/en/getting-started/example-datasets/menus)
