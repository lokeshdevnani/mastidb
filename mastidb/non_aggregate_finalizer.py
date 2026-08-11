from typing import Any

from .parse_helpers import ParsedQuery
from .partial_result import NonAggregatePartial
from .result_set import ResultSet
from .sort_keys import ascending_key


class NonAggregateFinalizer:
    """Combine NonAggregatePartials, apply global ORDER BY/LIMIT, project to output columns.

    Intermediate row layout: [SELECT projections..., resolved ORDER BY values...]
    Merging logic here is fairly simple - we just concat the rows and sort them using the sort keys.
    Performance fix: We can replace the concat-then-sort with an N-way merge later.
    """

    def __init__(self, parsed_query: ParsedQuery):
        self.parsed_query = parsed_query

    def finalize(self, partials: list[NonAggregatePartial]) -> ResultSet:
        # FIXME: swap concat for an N-way merge of already-sorted segment runs.
        rows: list[list[Any]] = []
        for partial in partials:
            rows.extend(partial.rows)

        rows = self._sort_and_limit(rows)

        # Drop trailing ORDER BY payloads; only SELECT/output columns go to the client.
        output_width = len(self.parsed_query.output_columns)
        result_set = ResultSet(columns=self.parsed_query.output_columns)
        for row in rows:
            result_set.append(row[:output_width])
        return result_set

    def _sort_and_limit(self, rows: list[list[Any]]) -> list[list[Any]]:
        limit = self.parsed_query.limit or 10
        order_by_cols = self.parsed_query.order_by_columns
        if not order_by_cols:
            return rows[:limit]

        # ORDER BY values sit after the SELECT columns on each intermediate row.
        order_by_start = len(self.parsed_query.select_statements)

        def sort_key(row: list[Any]) -> tuple:
            return tuple(
                ascending_key(row[order_by_start + i], col.get('sort'))
                for i, col in enumerate(order_by_cols)
            )

        return sorted(rows, key=sort_key)[:limit]
