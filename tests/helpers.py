"""Thin wrapper around a query result, for tests.

The engine returns a grid (column names + list of lists). This names the
cells so a test can say `rows.by('cityName')['Bengaluru']['SUM(added)']`
instead of remembering column indexes. Compare to a list of lists with `==`
when you care about the whole grid.
"""

from __future__ import annotations

from mastidb.query_executor import QueryExecutor
from mastidb.table import Table


class QueryRows:
    def __init__(self, columns: list[str], rows: list[list]):
        if len(columns) != len(set(columns)):
            raise ValueError(
                f"Duplicate column names {columns}; give them SQL aliases (AS ...)"
            )
        self.columns = columns
        self.lists = rows
        self._rows = [dict(zip(columns, row)) for row in rows]

    def __len__(self) -> int:
        return len(self.lists)

    def __iter__(self):
        return iter(self._rows)

    def __getitem__(self, index: int) -> dict:
        return self._rows[index]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return self.lists == other
        return NotImplemented

    def by(self, column: str) -> dict:
        """Index unique rows by a column — the natural shape of GROUP BY."""
        return {row[column]: row for row in self._rows}

    def col(self, column: str) -> list:
        return [row[column] for row in self._rows]


class QueryingTestCase:
    """Mixin: `self.query(sql)` against `self.table`."""

    table: Table

    def query(self, sql: str) -> QueryRows:
        result = QueryExecutor(self.table).execute(sql)
        return QueryRows(result.columns, result.get_results())
