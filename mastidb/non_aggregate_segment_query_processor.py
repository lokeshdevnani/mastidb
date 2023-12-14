import heapq
import logging
from typing import Any, Dict, Tuple, Union
from mastidb import parse_helpers
from mastidb.common_utils import map_reduce_op
from mastidb.parse_helpers import ParsedQuery
from mastidb.result_set import ResultSet
from mastidb.segment import Segment
from mastidb.segment_query_processor import SegmentQueryProcessor
from .bitmap_utils import break_bitmap_into_chunks

from pyroaring import BitMap  # type: ignore


logger = logging.getLogger(__name__)

class NonAggregateSegmentQueryProcessor(SegmentQueryProcessor):
    def __init__(self, segment: Segment, parsed_query: ParsedQuery):
        super().__init__(segment, parsed_query)

    def process_query(self) -> ResultSet:
        logger.info("[process_query] Filtering data")
        filter_bitmap = self._convert_to_bitmap(self.parsed_query.where_conditions)
        
        logger.info("[process_query] Selecting data")
        result_set = self.process_non_aggregation_query(filter_bitmap)

        return result_set

    def process_non_aggregation_query(self, bitmap: BitMap) -> ResultSet:
        # ORDER AND LIMIT clause processing logic for non-aggregation queries
        # if len(order_by_columns) > 0 and len(limit) > 0:
        #     # iterate till the end
        #     # Use heap to maintain LIMIT elements
        #     query_type = QueryType.NON_AGGREGATION_TOP_N
        #   elif len(order_by_columns) > 0:
        #     # iterate till the end
        #     # Do full sorting on the results -> quick sort
        #     pass
        #   elif len(order_by_columns) == 0 and limit is not None:
        #     # Get first N rows and stop -> no sort required
        #     pass
        #   else:
        #     # iterate till the end.
        #     # return all rows as is.
        #     pass

        order_by_cols = self.parsed_query.order_by_columns
        limit = self.parsed_query.limit or 10

        bitmap_chunks = break_bitmap_into_chunks(bitmap, bitmap_density_threshold=2, chunk_size=100000)
        logger.info('Breaking bitmap into chunk_count=%d', len(bitmap_chunks))

        if len(order_by_cols) > 0:
            limited_bitmap, row_number_to_result_row_index = self.top_k_sort(bitmap_chunks, order_by_cols, limit)

            bitmap_chunks = break_bitmap_into_chunks(limited_bitmap, bitmap_density_threshold=2, chunk_size=100000)
            logger.info('Breaking bitmap into chunk_count=%d', len(bitmap_chunks))

            result_set = ResultSet(columns=self.parsed_query.output_columns, row_count=len(limited_bitmap))
            for bitmap_chunk in bitmap_chunks:
                value_matrix = self.generate_value_matrix(
                    bitmap_chunk, self.parsed_query.dependent_columns, self.parsed_query.dependent_columns)

                for list_index, index in enumerate(bitmap_chunk):
                    result_row = []
                    for _, select_statement in enumerate(self.parsed_query.select_statements):
                        calculated_value = self.resolve_select_expression(
                            select_statement['value'], list_index, value_matrix)
                        result_row.append(calculated_value)
                    result_set.insert_at(row_number_to_result_row_index[index], result_row)

        return result_set

    def resolve_select_expression(self, expression: Union[str, Dict], index: int,
                                  value_matrix: Dict[str, list[Union[str, int]]]) -> Union[int, str]:
        # Same as calling parse_helpers.is_column(expression),
        # but calling inline helps the compiler with strict typing the expression inside this block
        if isinstance(expression, str):
            return value_matrix[expression][index]
        elif parse_helpers.is_literal(expression):
            return parse_helpers.unpack_literal_value(expression)
        elif parse_helpers.is_operation(expression):
            op, args = parse_helpers.unpack_op_args(expression)
            def recurse_fn(arg): return self.resolve_select_expression(arg, index, value_matrix)
            if op == 'add':
                return map_reduce_op(args, recurse_fn, lambda a, b: a + b)
            elif op == 'div':
                return map_reduce_op(args, recurse_fn, lambda a, b: a / b)
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")
        else:
            raise NotImplementedError("Unknown state in resolve_post_aggregation_expression")

    @staticmethod
    def order_by_key_for_index_from_value_matrix(order_by_columns: list[dict[str, str]], index: int,
                                                 value_matrix: dict[str, list]) -> Tuple[int, ...]:
        return tuple(value_matrix[col['value']][index] * (1 if col.get('sort') == 'desc' else -1)
                     for col in order_by_columns)

    def top_k_sort(self, bitmap_chunks: list[BitMap], order_by_cols: list[dict], limit: int) -> Tuple[BitMap, Dict[int, int]]:
        # fetch order by columns and run the heap logic keeping a window of size=limit
        # The winner items will go through full materialization.
        # this reduces the number of items fetched from storage considering limit << total_row_count
        min_heap: list[Tuple[Any, ...]] = []
        for bitmap_chunk in bitmap_chunks:
            order_by_value_matrix = self.generate_value_matrix(bitmap_chunk, [col['value'] for col in order_by_cols], [])
            for list_index, index in enumerate(bitmap_chunk):
                key = self.order_by_key_for_index_from_value_matrix(order_by_cols, list_index, order_by_value_matrix) + (index,)
                if len(min_heap) < limit:
                    heapq.heappush(min_heap, key)
                elif key > min_heap[0]:
                    heapq.heappushpop(min_heap, key)
        min_heap = heapq.nlargest(limit, min_heap)

        row_number_to_result_row_index = {tpl[-1]: i for i, tpl in enumerate(min_heap)}

        limited_bitmap = BitMap()
        for tuple in min_heap:
            limited_bitmap.add(tuple[-1])

        return limited_bitmap, row_number_to_result_row_index
