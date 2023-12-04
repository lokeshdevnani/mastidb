# MastiDB - A serious OLAP database engine written in python

MastiDB is an OLAP database engine, born from the adventurous journey of crafting a disk based OLAP database engine in Python (mypyc). 

The code is intentionally written in a simple, accessible manner, making it an excellent resource for those curious about how databases operate. 


## Why?
For me, MastiDB is more than just constructing a database; it's an exploration into the core mechanisms of database technology. It's about uncovering the secrets behind a database's ability to swiftly process and sift through terabytes of data within seconds. And eventually, build 

This journey has been rewarding so far where I've seen performance improvements of >90% compared to the V0 design I started with by carefully building on mini design choices.

## Getting Started
MastiDB can be used in two primary ways: as a library in your Python projects or via its command line interface (CLI) for direct interaction. Here's a quick guide to get you started:

### Installation
You can install mastidb from pip like regular people would.
```sh
pip install mastidb
```

If you're feeling tweaking the codebase, I'd encourage you to install from source.

```sh
git clone https://github.com/lokeshdevnani/mastidb.git
cd mastidb
pip install -r requirements.txt
python setup.py install
mastidb --help
```

### Using CLI
**Ingesting a file via CLI.**

Supports CSV, TSV, JSON, ndJSON

```sh
mastidb ingest -d /path/to/a/new/dir -s /path/to/source/file.csv
```

**Running SQL queries**

```sh
mastidb console -d /path/to/mastidb/dir
```
It will open a CLI console.


```
MastiDB > select count(id)
                              MastiDB
                            ┏━━━━━━━━━━━┓
                            ┃ COUNT(id) ┃
                            ┡━━━━━━━━━━━┩
                            │ 1334792   │
                            └───────────┘
Fetched 1 rows. Took 2.12 seconds. CPU time 1.99
```

## Usage as a library

Ingestion
```python
from mastidb.segment import Segment

segment = SegmentIngester.ingest('/tmp/wikidata', 'tests/datasets/wikipedia.json')
```

Querying
```python
segment = Segment.load('/tmp/wikidata')
parsed_query = ParsedQuery.parse_from_sql("SELECT COUNT(id)")
results = SegmentQueryProcessor(segment, parsed_query=parsed_query).process_query().get_results()
print(results)
```

## Contributing
This project is in it's early phases.
Feel free to fork the repository, make your changes, and submit a pull request. Let's grow MastiDB together!