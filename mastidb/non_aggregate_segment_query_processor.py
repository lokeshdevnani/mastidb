import heapq
import logging
from typing import Any, Dict, Tuple, Union
from mastidb import parse_helpers
from mastidb.common_utils import map_reduce_op, parse_int
from mastidb.parse_helpers import ParsedQuery
from mastidb.partial_result import NonAggregatePartial
from mastidb.segment import Segment
from mastidb.segment_query_processor import SegmentQueryProcessor
from mastidb.sort_keys import max_heap_key
from .bitmap_utils import break_bitmap_into_chunks

from pyroaring import BitMap  # type: ignore


logger = logging.getLogger(__name__)


class NonAggregateSegmentQueryProcessor(SegmentQueryProcessor):
    def __init__(self, segment: Segment, parsed_query: ParsedQuery):
        super().__init__(segment, parsed_query)

    def process_query(self) -> NonAggregatePartial:
        logger.info("[process_query] Filtering data")
        filter_bitmap = self._convert_to_bitmap(self.parsed_query.where_conditions)

        logger.info("[process_query] Selecting data")
        return self.process_non_aggregation_query(filter_bitmap)

    def _process_bitmap_chunks(self, bitmap_chunks, order_by_cols, limit=None, row_number_to_result_row_index=None):
        """Build intermediate rows: SELECT projections + resolved ORDER BY values."""
        if order_by_cols:
            rows: list[list[Any]] = [None] * len(row_number_to_result_row_index)  # type: ignore
        else:
            rows = []

        cols_to_fetch = self.parsed_query.dependent_columns

        for bitmap_chunk in bitmap_chunks:
            value_matrix = self.generate_value_matrix(bitmap_chunk, cols_to_fetch, cols_to_fetch)

            for list_index, index in enumerate(bitmap_chunk):
                select_part = [
                    self.resolve_select_expression(select_statement['value'], list_index, value_matrix)
                    for select_statement in self.parsed_query.select_statements
                ]
                order_part = [
                    self.resolve_select_expression(col['value'], list_index, value_matrix)
                    for col in order_by_cols
                ]
                result_row = select_part + order_part

                if order_by_cols:
                    rows[row_number_to_result_row_index[index]] = result_row
                else:
                    rows.append(result_row)
                    if limit and len(rows) >= limit:
                        return NonAggregatePartial(rows=rows)

        return NonAggregatePartial(rows=rows)

    def process_non_aggregation_query(self, bitmap: BitMap) -> NonAggregatePartial:
        order_by_cols = self.parsed_query.order_by_columns
        limit = self.parsed_query.limit or 10

        bitmap_chunks = break_bitmap_into_chunks(bitmap, bitmap_density_threshold=2, chunk_size=100000)
        logger.info('Breaking bitmap into chunk_count=%d', len(bitmap_chunks))

        if order_by_cols:
            limited_bitmap, row_number_to_result_row_index = self.top_k_sort(bitmap_chunks, order_by_cols, limit)
            new_bitmap_chunks = break_bitmap_into_chunks(limited_bitmap, bitmap_density_threshold=2, chunk_size=100000)
            logger.info('Breaking limited bitmap into chunk_count=%d', len(new_bitmap_chunks))
            return self._process_bitmap_chunks(new_bitmap_chunks, order_by_cols, row_number_to_result_row_index=row_number_to_result_row_index)
        else:
            return self._process_bitmap_chunks(bitmap_chunks, order_by_cols, limit=limit)

    def resolve_select_expression(self, expression: Union[str, Dict], index: int,
                                  value_matrix: Dict[str, Union[list[str], list[int]]]) -> Union[int, float, str]:
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
                return map_reduce_op(args, recurse_fn, lambda a, b: parse_int(a) + parse_int(b))
            elif op == 'div':
                return map_reduce_op(args, recurse_fn, lambda a, b: parse_int(a) / parse_int(b))
            else:
                raise NotImplementedError(f"Can't resolve op={op} for {expression}")
        else:
            raise NotImplementedError("Unknown state in resolve_post_aggregation_expression")

    @staticmethod
    def order_by_key_for_index_from_value_matrix(order_by_columns: list[dict[str, str]], index: int,
                                                 value_matrix: dict[str, list]) -> Tuple[Any, ...]:
        return tuple(
            max_heap_key(value_matrix[col['value']][index], col.get('sort'))
            for col in order_by_columns
        )

    def order_by_key_from_resolved_expressions(self, order_by_columns: list[dict], index: int,
                                               value_matrix: dict[str, list]) -> Tuple[Any, ...]:
        return tuple(
            max_heap_key(self.resolve_select_expression(col['value'], index, value_matrix), col.get('sort'))
            for col in order_by_columns
        )

    def top_k_sort(self, bitmap_chunks: list[BitMap], order_by_cols: list[dict], limit: int) -> Tuple[BitMap, Dict[int, int]]:
        # Local top-K so only winners go through full SELECT materialization (limit << matches).
        # Plain columns: compare dict IDs (no decode). Expressions: resolve order-by deps only.
        has_expression = any(not parse_helpers.is_column(col['value']) for col in order_by_cols)

        # If there are expressions in the ORDER BY columns, we need to fetch the dependent columns early.
        # Otherwise, we can just fetch the column values and sort using the dict IDs.
        if has_expression:
            cols_to_fetch = parse_helpers.get_dependent_columns(order_by_cols)
            early_materialize = cols_to_fetch
        else:
            cols_to_fetch = [col['value'] for col in order_by_cols]
            early_materialize = []

        min_heap: list[Tuple[Any, ...]] = []
        for bitmap_chunk in bitmap_chunks:
            order_by_value_matrix = self.generate_value_matrix(bitmap_chunk, cols_to_fetch, early_materialize)
            for list_index, index in enumerate(bitmap_chunk):
                if has_expression:
                    key = self.order_by_key_from_resolved_expressions(
                        order_by_cols, list_index, order_by_value_matrix) + (index,)
                else:
                    key = self.order_by_key_for_index_from_value_matrix(
                        order_by_cols, list_index, order_by_value_matrix) + (index,)
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
