"""Read an ingest file into columns.

CSV, TSV, JSON, and NDJSON all become the same thing: a `ParsedSource`
({column name: [values…]}). `SegmentIngester` never sees the file format.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Extension → how we read it. New formats add a line here, not a branch in ingest.
_DELIMITED = {
    '.csv': ',',
    '.tsv': '\t',
}


class ParsedSource:
    """One file, fully in RAM, as columns.

    The only operations ingest needs: walk the columns, and slice a row
    range when splitting into segments.
    """

    def __init__(self, columns: dict[str, list]):
        self.columns = columns

    def num_rows(self) -> int:
        if not self.columns:
            return 0
        return len(next(iter(self.columns.values())))

    def slice(self, start: int, stop: int) -> ParsedSource:
        return ParsedSource({name: values[start:stop] for name, values in self.columns.items()})


def read_source(file_path: str) -> ParsedSource:
    logger.info("Reading ingest source: %s", file_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _DELIMITED:
        source = _from_delimited(file_path, delimiter=_DELIMITED[ext])
    elif ext == '.json':
        source = _from_json(file_path)
    else:
        raise ValueError(
            f"Unsupported file type for: {file_path}. Only TSV, CSV, or JSON formats are accepted."
        )
    logger.info("Parsed %s: %d rows, %d columns", file_path, source.num_rows(), len(source.columns))
    return source


def _from_delimited(file_path: str, delimiter: str) -> ParsedSource:
    with open(file_path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"No header row in {file_path}")
        return _records_to_source(reader.fieldnames, reader)


def _from_json(file_path: str) -> ParsedSource:
    if _first_line_is_json_object(file_path):
        rows = _load_ndjson(file_path)
    else:
        rows = _load_json_array(file_path)
    if not rows:
        return ParsedSource({})
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return _records_to_source(names, rows)


def _load_ndjson(file_path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(file_path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_json_array(file_path: str) -> list[dict[str, Any]]:
    with open(file_path, encoding='utf-8') as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        return [payload]
    if not isinstance(payload, list):
        raise ValueError(f"JSON ingest expects an array of objects (or one object): {file_path}")
    return payload


def _first_line_is_json_object(file_path: str) -> bool:
    """NDJSON: a complete JSON object on the first non-empty line.

    A pretty-printed array starts with `[`, a compact array is a list — both
    fall through to `_load_json_array`.
    """
    with open(file_path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                return isinstance(json.loads(line), dict)
            except json.JSONDecodeError:
                return False
    return False


def _records_to_source(names: Iterable[str], rows: Iterable[dict]) -> ParsedSource:
    columns: dict[str, list] = {name: [] for name in names}
    for row in rows:
        for name in columns:
            columns[name].append(row.get(name))
    return ParsedSource(columns)
