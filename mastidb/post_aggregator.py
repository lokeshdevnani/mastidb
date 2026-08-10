from . import parse_helpers
from .aggregate_functions import AggregationFunction
from .common_utils import map_reduce_op
from .parse_helpers import ParsedQuery
from .partial_result import AggregatePartial
from .result_set import ResultSet

import heapq
from typing import Any, Dict, Tuple, Union


class PostAggregator:
    def __init__(self, parsed_query: ParsedQuery,
                 aggregation_functions: list[AggregationFunction]):
        self.parsed_query = parsed_query
        self.aggregation_functions = aggregation_functions
        self.finalize_values = True

    def resolve_post_aggregation_expression(self, expression: Union[str, Dict], variable_values: list[Any],
                                            key_name_to_idx_map: dict[str, int], decoded_keys: Tuple[Any, ...]) -> Any:
        # Same as calling parse_helpers.is_column(expression),
        # but calling inline helps the compiler with strict typing the expression inside this block
        if isinstance(expression, str):
            # This happens when a 'group'ed column is `selected` in post_aggregation expression.
            # In this case, we just return the decoded dictionary values for that aggregated row.
            if expression in key_name_to_idx_map:
                key_idx = key_name_to_idx_map[expression]
                return decoded_keys[key_idx]
            else:
                raise ValueError(f"Unsupported operation in post-aggregation stage: {expression}")
        elif parse_helpers.is_variable(expression):
            # These are variables which were resolved/computed during aggregation phase
            # E.g. { 'variable': 'p2' } => 2
            variable_values_index = int(expression['variable'][1:])
            return variable_values[variable_values_index]
        elif parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)
        elif parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            recurse_fn = lambda arg: self.resolve_post_aggregation_expression(arg, variable_values, key_name_to_idx_map,
                                                                              decoded_keys)
            if op == 'add':
                return map_reduce_op(args, recurse_fn, lambda a, b: a + b)
            elif op == 'div':
                return map_reduce_op(args, recurse_fn, lambda a, b: a / b)
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")
        else:
            raise NotImplementedError("Unknown state in resolve_post_aggregation_expression")

    def perform_post_aggregation(self, aggregate_partial: AggregatePartial) -> ResultSet:
        group_by_columns = self.parsed_query.group_by_columns
        key_name_to_idx_map = {group_by_column: idx for idx, group_by_column in enumerate(group_by_columns)}

        result_set = ResultSet(columns=self.parsed_query.output_columns)

        is_top_k = len(self.parsed_query.order_by_columns) > 0
        min_heap: list[Tuple[Any, ...]] = []
        limit = self.parsed_query.limit or 1000

        # Keys on the partial are already decoded.
        for decoded_keys, values in aggregate_partial.groups.items():
            if self.finalize_values:
                values = [fn.finalize(value) for value, fn in zip(values, self.aggregation_functions)]

            result_row = []
            for idx, post_aggregation in enumerate(self.parsed_query.post_aggregate_expressions):
                calculated_value = self.resolve_post_aggregation_expression(post_aggregation, values,
                                                                            key_name_to_idx_map, decoded_keys)
                result_row.append(calculated_value)

            if is_top_k:
              sort_tuple: Tuple[Any, ...] = self.build_sort_tuple_from_sort_order(key_name_to_idx_map, decoded_keys, values) + (result_set.current_index(),)
              self._add_to_heap(min_heap, limit, sort_tuple)

            result_set.append(result_row)

        if is_top_k:
          min_heap = heapq.nlargest(limit, min_heap)
          final_index_order = [tpl[-1] for tpl in min_heap]
          result_set.rearrange(final_index_order)

        return result_set

    def build_sort_tuple_from_sort_order(self, key_name_to_idx_map, decoded_keys, values) -> Tuple[Any, ...]:
        # FIXME: `* ±1` only works for numeric sort keys. ORDER BY on string group-by columns will fail (can't negate a str).
        return tuple(
                  self.resolve_post_aggregation_expression(col['value'], values, key_name_to_idx_map, decoded_keys) *
                  (1 if col.get('sort') == 'desc' else -1)
                  for col in self.parsed_query.order_by_columns
              )

    def _add_to_heap(self, min_heap: list[Tuple[Any, ...]], limit: int, sort_tuple: Tuple[Any, ...]):
        if len(min_heap) < limit:
            heapq.heappush(min_heap, sort_tuple)
        elif sort_tuple > min_heap[0]:
            heapq.heappushpop(min_heap, sort_tuple)
