import logging
import math
import time
from typing import Union, Any, Tuple, Dict

from pyroaring import BitMap  # type: ignore

import parse_helpers
from aggregate_buffer import AggregateBuffer
from aggregator import Aggregator
from parse_helpers import ParsedQuery
from common_utils import map_reduce_op
from result_set import ResultSet
from segment import Segment

logger = logging.getLogger(__name__)


class SegmentQueryProcessor:
    def __init__(self, segment: Segment, parsed_query: ParsedQuery):
        self.segment = segment
        self.parsed_query: ParsedQuery = parsed_query
        self.aggregators: list[Aggregator] = []
        self.finalize_values = True

    def process_query(self) -> ResultSet:
        logger.info("[process_query] Filtering data")
        filter_bitmap = self._convert_to_bitmap(self.parsed_query.where_conditions)
        logger.info("[process_query] Aggregating data")
        aggregate_buffer = AggregateBuffer(value_length=len(self.parsed_query.aggregate_expressions))
        self.aggregators = self.build_aggregators(aggregate_buffer)
        self.set_default_values_in_aggregator_buffer(aggregate_buffer)
        logger.info("[process_query] Performing Aggregation")
        self.perform_aggregation(self.parsed_query.group_by_columns, filter_bitmap, aggregate_buffer)
        logger.info("[process_query] Performing Post-aggregation")
        result_set = self.perform_post_aggregation(aggregate_buffer)
        return result_set

    def resolve_aggregation_expression(self, index: int, expression: Union[str, dict[str, Any]],
                                       value_matrix: Dict[str, list[Union[str, int]]]) -> Union[int, str]:
        if isinstance(expression, str):
            val = value_matrix[expression][index]
            float_val: float = float(val)
            if math.isnan(float_val):
                return 0

            return int(float_val)
        elif parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)
        elif parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            if op == 'add':
                return map_reduce_op(args,
                                     lambda arg: self.resolve_aggregation_expression(index, arg, value_matrix),
                                     lambda a, b: a + b)
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")
        else:
            raise NotImplementedError(f"Unknown type: {expression}")

    def resolve_post_aggregation_expression(self, expression: Union[str, Dict], variable_values: list[Any],
                                            key_name_to_idx_map: dict[str, int], decoded_keys: Tuple[Any, ...]):
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
        agg_start_time = time.time()
        value_matrix: Dict[str, list[Union[str, int]]] = {}
        # Materialize non-group-by columns - Only required coz we don't have metric columns
        # group by columns will be materialized post-aggregation.
        cols_to_early_materialize = list(set(self.parsed_query.dependent_columns) - set(group_by_columns))

        logger.info('aggregation fetch time: %s', str(time.time() - agg_start_time))

        for list_index, index in enumerate(bitmap):
            # value matrix population
            for col in self.parsed_query.dependent_columns:
                value_matrix[col] = [self.segment.get_column(col).get_dictionary_id_for_index(index)]

            for col in cols_to_early_materialize:
                value_matrix[col] = [self.segment.get_value_for_index(col, index)]

            aggregation_key = self.aggregation_key_for_index_from_value_matrix(group_by_columns, 0,
                                                                               value_matrix=value_matrix)
            aggregate_buffer.init_empty_buffer_for_keys(keys=aggregation_key)
            for aggregator in self.aggregators:
                resolved_expression = self.resolve_aggregation_expression(0, aggregator.expression_args[0],
                                                                          value_matrix=value_matrix)
                aggregator.record(aggregation_key, resolved_expression)
        logger.info('aggregation time: %s', time.time() - agg_start_time)

    def set_default_values_in_aggregator_buffer(self, aggregate_buffer: AggregateBuffer) -> None:
        default_aggregation_row = []
        for aggregator in self.aggregators:
            default_aggregation_row.append(aggregator.aggregation_function.initial_value)
        aggregate_buffer.set_default_value(default_aggregation_row)

    def build_aggregators(self, aggregate_buffer: AggregateBuffer) -> list[Aggregator]:
        aggregators = []
        for select_idx, select_expression in enumerate(self.parsed_query.aggregate_expressions.values()):
            aggregators.append(Aggregator.create_from_expression(select_expression, aggregate_buffer, select_idx))
        return aggregators

    def perform_post_aggregation(self, aggregate_buffer: AggregateBuffer) -> ResultSet:
        group_by_columns = self.parsed_query.group_by_columns

        def transform_fn(keys: Tuple[int, ...]) -> Tuple[Any, ...]:
            return tuple(
                self.segment.get_column(group_by_columns[i]).get_dictionary_value_for_dictionary_id(keys[i])
                for i in range(len(group_by_columns))
            )

        key_name_to_idx_map = {group_by_column: idx for idx, group_by_column in enumerate(group_by_columns)}

        result_set = ResultSet(columns=self.parsed_query.output_columns)

        for keys, values in aggregate_buffer.get_results().items():
            if self.finalize_values:
                values = [aggregator.finalize_values(value) for value, aggregator in zip(values, self.aggregators)]

            # Optimisation idea: Don't transform keys unless being selected in an expression.
            decoded_keys = transform_fn(keys=keys)
            result_row = []
            for idx, post_aggregation in enumerate(self.parsed_query.post_aggregate_expressions):
                calculated_value = self.resolve_post_aggregation_expression(post_aggregation, values,
                                                                            key_name_to_idx_map, decoded_keys)
                result_row.append(calculated_value)
            result_set.append(result_row)
        return result_set

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

    def _convert_to_bitmap(self, expression) -> BitMap:
        if len(expression) == 0:
            return self._empty_bitmap(True)

        op, args = parse_helpers.unpack_op_args(expression)

        if op == 'and':
            res = self._convert_to_bitmap(args[0])
            for i in range(1, len(args)):
                res = res.intersection(self._convert_to_bitmap(args[i]))
            return res
        elif op == 'or':
            res = self._convert_to_bitmap(args[0])
            for i in range(1, len(args)):
                res = res.union(self._convert_to_bitmap(args[i]))
            return res
        elif op == 'eq':
            lhs, rhs = args[0], args[1]
            if parse_helpers.is_column(lhs) and parse_helpers.is_literal(rhs):
                # Case 1: column = 'literal'
                return self.segment.get_bitmap_for_column_value(lhs, parse_helpers.unpack_literal_value(rhs))
            elif parse_helpers.is_column(rhs) and parse_helpers.is_literal(lhs):
                # Case 2: 'literal' = column
                return self.segment.get_bitmap_for_column_value(rhs, parse_helpers.unpack_literal_value(lhs))
            elif parse_helpers.is_literal(lhs) and parse_helpers.is_literal(rhs):
                # Case 3: 'literal1' = 'literal2'
                is_set = lhs['literal'] == rhs['literal']
                return self._empty_bitmap(is_set)
            else:
                # Case 4: column_lhs = column_rhs
                raise NotImplementedError("Handling comparison between two columns is not implemented yet.")
        else:
            raise NotImplementedError(f"Operation not supported: {op}")

    def _empty_bitmap(self, value: bool = False) -> BitMap:
        if value:
            bitmap = BitMap()
            bitmap.add_range(0, self.segment.get_row_count())
            return bitmap
        else:
            return BitMap()
