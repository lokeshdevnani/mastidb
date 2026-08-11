from dataclasses import dataclass
from typing import Any

from .aggregate_functions import AggregationFunction


@dataclass
class AggregatePartial:
    """Snapshot of AggregateBuffer with decoded group keys and unfinalized aggregate states."""
    groups: dict[tuple[Any, ...], list[Any]]

    @staticmethod
    def merge(partials: list['AggregatePartial'],
              aggregation_functions: list[AggregationFunction]) -> 'AggregatePartial':
        if len(partials) == 1:
            return partials[0]

        combined: dict[tuple[Any, ...], list[Any]] = {}
        for partial in partials:
            for key, values in partial.groups.items():
                if key not in combined:
                    combined[key] = list(values)
                else:
                    combined[key] = [
                        fn.merge(combined[key][i], values[i])
                        for i, fn in enumerate(aggregation_functions)
                    ]
        return AggregatePartial(groups=combined)


@dataclass
class NonAggregatePartial:
    """Projected rows from one segment (before the executor builds a ResultSet)."""
    rows: list[list[Any]]
