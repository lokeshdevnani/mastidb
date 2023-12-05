# MastiDB - A 'serious' OLAP database engine written in python

MastiDB is an OLAP database engine, born from the adventurous journey of crafting a disk based OLAP database engine in Python (mypyc). 

It's written in a way that's easy to get, perfect for anyone who's ever wondered, "How do databases actually work?".
See for yourself how we're mixing simplicity with serious database chops.


## Why?
For me, MastiDB is more than just building a database; it's an exploration into the core mechanisms of columnar databases. It's about uncovering the secrets behind a database's ability to swiftly process and sift through terabytes of data within seconds. 

The journey thus far has been immensely rewarding. I have witnessed performance enhancements exceeding 90% compared to the initial V0 design, all by tweaking and fiddling with the little things at the heart of it all.

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

**Please Note**: MastiDB is currently not intended for production use. The API is in a state of evolution and might undergo significant changes.

It's a great tool for learning and experimentation, but we recommend not using it for critical applications at this stage.


## Contributing
MastiDB is still a baby, just getting its bearings. If you're into databases and love tinkering, give it a shot! 
Just fork the repo, do your magic, and hit me up with a pull request.

## License
MastiDB is proudly released under the MIT License. This is pretty much as liberal as it gets – you're free to do almost anything you want with this project. Use it, change it, share it, or even sell it; just make sure to include the original copyright and license notice in your copies. 
