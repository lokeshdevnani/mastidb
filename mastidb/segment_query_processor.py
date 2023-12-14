import logging
from typing import Union, Dict

from pyroaring import BitMap  # type: ignore

from . import parse_helpers
from .aggregator import Aggregator
from .parse_helpers import ParsedQuery
from .segment import Segment

logger = logging.getLogger(__name__)

class SegmentQueryProcessor:
    def __init__(self, segment: Segment, parsed_query: ParsedQuery):
        self.segment = segment
        self.parsed_query: ParsedQuery = parsed_query
        self.aggregators: list[Aggregator] = []
        self.finalize_values = True
            
    def generate_value_matrix(self, bitmap: BitMap, cols_to_fetch: list[str], cols_to_early_materialize: list[str]):
        value_matrix: Dict[str, list[Union[str, int]]] = {}
        for col in cols_to_fetch:
            value_matrix[col] = self.segment.get_dictionary_ids_for_index_batch(col, bitmap)

        for col in cols_to_early_materialize:
            col_obj = self.segment.get_column(col)
            # Writing a batch version for this is quite difficult since -
            #  dict_ids in a batch can lie in extremes of the entire dictionary.
            #  Therefore, sequential IO scan for entire dict might get repeated for each batch
            #  This isn't the case for indexes - since list indexes are sorted physically on disk.
            value_matrix[col] = [col_obj.get_dictionary_value_for_dictionary_id(dict_id) for dict_id in
                                value_matrix[col]]
        return value_matrix
    
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
