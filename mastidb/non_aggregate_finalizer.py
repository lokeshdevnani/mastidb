from .parse_helpers import ParsedQuery
from .partial_result import NonAggregatePartial
from .result_set import ResultSet


class NonAggregateFinalizer:
    """Build a ResultSet from a NonAggregatePartial (ORDER BY/LIMIT already applied per segment)."""

    def __init__(self, parsed_query: ParsedQuery):
        self.parsed_query = parsed_query

    def finalize(self, partial: NonAggregatePartial) -> ResultSet:
        result_set = ResultSet(columns=self.parsed_query.output_columns)
        for row in partial.rows:
            result_set.append(row)
        return result_set
