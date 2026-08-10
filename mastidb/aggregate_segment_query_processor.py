from . import parse_helpers
from .aggregate_buffer import AggregateBuffer
from .aggregate_functions import AggregationFunction
from .aggregator import Aggregator
from .bitmap_utils import break_bitmap_into_chunks
from .common_utils import map_reduce_op, parse_int
from .parse_helpers import ParsedQuery, QueryType
from .partial_result import AggregatePartial
from .result_set import ResultSet
from .segment import Segment
from .segment_query_processor import SegmentQueryProcessor, logger
from pyroaring import BitMap  # type: ignore


import heapq
import time
from typing import Any, Dict, Tuple, Union


class AggregateSegmentQueryProcessor(SegmentQueryProcessor):
    def __init__(self, segment: Segment, parsed_query: ParsedQuery,
                 aggregation_functions: list[AggregationFunction]):
        super().__init__(segment, parsed_query)
        self.aggregation_functions = aggregation_functions
        self.aggregators: list[Aggregator] = []

    def process_query(self) -> AggregatePartial:
        logger.info("[process_query] Filtering data")
        filter_bitmap = self._convert_to_bitmap(self.parsed_query.where_conditions)

        logger.info("[process_query] Aggregating data")
        aggregate_buffer = AggregateBuffer(value_length=len(self.parsed_query.aggregate_expressions))
        self.aggregators = self.build_aggregators(aggregate_buffer)
        self.set_default_values_in_aggregator_buffer(aggregate_buffer)
        logger.info("[process_query] Performing Aggregation")
        self.perform_aggregation(self.parsed_query.group_by_columns, filter_bitmap, aggregate_buffer)

        # Decode group keys from aggregate buffer and return a partial result
        # This is still unfinalized, as the aggregate states are not finalized yet.
        # Caller will finalize the aggregate states and run perform_post_aggregation.
        return self.build_aggregate_partial(aggregate_buffer)

    def build_aggregate_partial(self, aggregate_buffer: AggregateBuffer) -> AggregatePartial:
        group_by_columns = self.parsed_query.group_by_columns
        groups: dict[tuple[Any, ...], list[Any]] = {}
        for keys, values in aggregate_buffer.get_results().items():
            decoded_keys = tuple(
                self.segment.get_column(group_by_columns[i]).get_dictionary_value_for_dictionary_id(keys[i])
                for i in range(len(group_by_columns))
            )
            groups[decoded_keys] = list(values)
        return AggregatePartial(groups=groups)

    def resolve_aggregation_expression(self, index: int, expression: Union[str, dict[str, Any]],
                                       value_matrix: Dict[str, Union[list[str], list[int]]]) -> Union[int, str]:
        if isinstance(expression, str):
            return value_matrix[expression][index]
        elif parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)
        elif parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            if op == 'add':
                return map_reduce_op(args,
                                     lambda arg: self.resolve_aggregation_expression(index, arg, value_matrix),
                                     lambda a, b: a + parse_int(b))
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")
        else:
            raise NotImplementedError(f"Unknown type: {expression}")

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

    def perform_aggregation(self, group_by_columns: list[str], bitmap: BitMap, aggregate_buffer: AggregateBuffer):
        # Materialize non-group-by columns - Only required coz we don't have metric columns
        # group by columns stay as dict IDs here; decoded when building the partial.
        cols_to_early_materialize = list(set(self.parsed_query.dependent_columns) - set(group_by_columns))

        # batching strategy
        bitmap_chunks = break_bitmap_into_chunks(bitmap, bitmap_density_threshold=2, chunk_size=100000)
        logger.info('Breaking bitmap into chunk_count=%d', len(bitmap_chunks))
        agg_start_time = time.time()
        for bitmap_chunk in bitmap_chunks:
            value_matrix = self.generate_value_matrix(bitmap_chunk, self.parsed_query.dependent_columns, cols_to_early_materialize)
            self.perform_aggregation_for_batch(group_by_columns, bitmap_chunk, aggregate_buffer, value_matrix)
        logger.info('aggregation time: %s', time.time() - agg_start_time)


    def perform_aggregation_for_batch(self, group_by_columns: list[str], bitmap: BitMap,
                                      aggregate_buffer: AggregateBuffer,
                                      value_matrix: Dict[str, Union[list[str], list[int]]]):
        for list_index, _ in enumerate(bitmap):
            aggregation_key = self.aggregation_key_for_index_from_value_matrix(group_by_columns, list_index,
                                                                               value_matrix=value_matrix)
            aggregate_buffer.init_empty_buffer_for_keys(keys=aggregation_key)
            for aggregator in self.aggregators:
                resolved_expression = self.resolve_aggregation_expression(list_index, aggregator.expression_args[0],
                                                                          value_matrix=value_matrix)
                aggregator.record(aggregation_key, resolved_expression)

    def set_default_values_in_aggregator_buffer(self, aggregate_buffer: AggregateBuffer) -> None:
        default_aggregation_row = []
        for aggregator in self.aggregators:
            default_aggregation_row.append(aggregator.aggregation_function.get_initial_value())
        aggregate_buffer.set_default_value(default_aggregation_row)

    def build_aggregators(self, aggregate_buffer: AggregateBuffer) -> list[Aggregator]:
        aggregators = []
        for select_idx, (select_expression, aggregation_function) in enumerate(
                zip(self.parsed_query.aggregate_expressions.values(), self.aggregation_functions)):
            aggregators.append(Aggregator.create_from_expression(select_expression, aggregate_buffer, select_idx,
                                                                 aggregation_function))
        return aggregators

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

    @staticmethod
    def aggregation_key_for_index_from_value_matrix(group_by_columns: list[str], index: int,
                                                    value_matrix: dict[str, list]) -> Tuple[int, ...]:
        return tuple(value_matrix[group_by_column_str][index] for group_by_column_str in group_by_columns)

    def aggregation_key_for_index(self, group_by_columns: list[str], index: int) -> Tuple[int, ...]:
        group_keys = []
        for group_by_column_str in group_by_columns:
            group_by_column = self.segment.get_column(group_by_column_str)
            group_by_dict_id = group_by_column.get_dictionary_id_for_index(index)
            group_keys.append(group_by_dict_id)
        group_keys_tuple = tuple(group_keys)
        return group_keys_tuple