import logging
import math
import time
import timeit

from pyroaring import BitMap  # type: ignore

import parse_helpers
from aggregate_buffer import AggregateBuffer
from aggregator import Aggregator
from parse_helpers import ParsedQuery
from common_utils import map_reduce_op
from segment import Segment


class ResultSet:
    def __init__(self):
        self._results = []

    def append(self, row):
        self._results.append(row)

    def get_results(self):
        return self._results


logger = logging.getLogger(__name__)


class SegmentQueryProcessor:
    def __init__(self, segment: Segment, parsed_query: ParsedQuery):
        self.segment = segment
        self.parsed_query: ParsedQuery = parsed_query
        self.aggregators: list[Aggregator] = []
        self.finalize_values = True

    def process_query(self) -> list:
        logger.info("[process_query] Filtering data")
        filter_bitmap = self._convert_to_bitmap(self.parsed_query.where_conditions)
        logger.info("[process_query] Aggregating data")
        aggregate_buffer = AggregateBuffer(value_length=len(self.parsed_query.aggregate_expressions))
        self.aggregators = self.build_aggregators(aggregate_buffer)
        logger.info("[process_query] Performing Aggregation")
        self.perform_aggregation(self.parsed_query.group_by_columns, filter_bitmap)
        logger.info("[process_query] Performing Post-aggregation")
        result_set = self.perform_post_aggregation(aggregate_buffer)
        return result_set.get_results()

    def resolve_aggregation_expression(self, index, expression):
        if parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)

        if parse_helpers.is_column(expression):
            # If a column is used more than once in select expressions, it will be fetched twice
            # TODO: Optimise this by computing dependencies first
            val = self.segment.get_value_for_index(expression, index)
            # if len(val) == 0:
            #     return 0
            #
            # val = float(val)
            # if math.isnan(val):
            #     return 0

            return int(val)

        if parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            if op == 'add':
                return map_reduce_op(args,
                                     lambda arg: self.resolve_aggregation_expression(index, arg),
                                     lambda a, b: a + b)
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")

    def resolve_post_aggregation_expression(self, expression, variable_values, key_name_to_idx_map, decoded_keys):
        if parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)

        if parse_helpers.is_column(expression):
            # This happens when a 'group'ed column is `selected` in post_aggregation expression.
            # In this case, we just return the decoded dictionary values for that aggregated row.
            if expression in key_name_to_idx_map:
                key_idx = key_name_to_idx_map[expression]
                return decoded_keys[key_idx]
            else:
                raise ValueError(f"Unsupported operation in post-aggregation stage: {expression}")

        if parse_helpers.is_variable(expression):
            # These are variables which were resolved/computed during aggregation phase
            # E.g. { 'variable': 'p2' } => 2
            variable_values_index = int(expression['variable'][1:])
            return variable_values[variable_values_index]

        if parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            recurse_fn = lambda arg: self.resolve_post_aggregation_expression(arg, variable_values, key_name_to_idx_map,
                                                                              decoded_keys)
            if op == 'add':
                return map_reduce_op(args, recurse_fn, lambda a, b: a + b)
            elif op == 'div':
                return map_reduce_op(args, recurse_fn, lambda a, b: a / b)
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")

    def perform_aggregation(self, group_by_columns: list[str], bitmap: BitMap):
        agg_start_time = time.time()
        aggregate_expressions: list[dict] = list(self.parsed_query.aggregate_expressions.values())
        for index in bitmap:
            aggregation_key = self.aggregation_key_for_index(group_by_columns, index)
            for aggregator, select_expression in zip(self.aggregators, aggregate_expressions):
                op, args = parse_helpers.unpack_op_args(select_expression)
                resolved_expression = self.resolve_aggregation_expression(index, args[0])
                aggregator.record(aggregation_key, resolved_expression)
        print('aggregation time:', time.time() - agg_start_time)

    def build_aggregators(self, aggregate_buffer: AggregateBuffer):
        aggregators = []
        for select_idx, select_expression in enumerate(self.parsed_query.aggregate_expressions.values()):
            aggregators.append(Aggregator.create_from_expression(select_expression, aggregate_buffer, select_idx))
        return aggregators

    def perform_post_aggregation(self, aggregate_buffer: AggregateBuffer) -> ResultSet:
        group_by_columns = self.parsed_query.group_by_columns

        def transform_fn(keys: tuple):
            return tuple(
                self.segment.get_column(group_by_columns[i]).get_dictionary_value_for_dictionary_id(keys[i])
                for i in range(len(group_by_columns))
            )

        key_name_to_idx_map = {group_by_column: idx for idx, group_by_column in enumerate(group_by_columns)}

        result_set = ResultSet()

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

    def aggregation_key_for_index(self, group_by_columns: list[str], index: int) -> tuple:
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
            raise ValueError(f"Unsupported operation: {op}")

    def _empty_bitmap(self, value: bool = False) -> BitMap:
        if value:
            bitmap = BitMap()
            bitmap.add_range(0, self.segment.get_row_count())
            return bitmap
        else:
            return BitMap()
