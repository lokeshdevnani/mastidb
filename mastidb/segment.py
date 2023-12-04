from typing import Iterable

from pyroaring import BitMap  # type: ignore

from .common_utils import find_column_files
from .data_accessor import DataAccessor
from .segment_column import SegmentColumn
from .segment_column_metadata import SegmentColumnType

import logging


logger = logging.getLogger(__name__)

class Segment:
    segment_columns: dict[str, SegmentColumn]

    def __init__(self, segment_columns=None):
        self.segment_columns = segment_columns

    @staticmethod
    def create(data_dir, file_path: str) -> 'Segment':
        from .segment_ingester import SegmentIngester
        return SegmentIngester.ingest(data_dir, file_path)

    @staticmethod
    def load(data_dir: str):
        logger.info("[load] Loading segment")
        column_names = find_column_files(data_dir)
        logger.info(f"[load] Found {len(column_names)} columns: {column_names}")
        segment_columns: dict[str, SegmentColumn] = {}
        for column in column_names:
            logger.info(f"[load] Loading column: {column}")
            segment_columns[column] = SegmentColumn.load(DataAccessor(f"{data_dir}/{column}").open())
        return Segment(segment_columns)

    def get_column(self, column_name) -> SegmentColumn:
        return self.segment_columns[column_name]

    def get_bitmap_for_column_value(self, column, item) -> BitMap:
        # TODO: Cache this
        logger.debug(f"Fetching bitmap for {column} = {item}")
        bitmap = self.get_column(column).get_bitmap_for_item(item)
        return bitmap

    def get_row_count(self) -> int:
        column = next(iter(self.segment_columns.values()))
        return column.metadata.row_count

    def get_value_for_index(self, column_name: str, index: int):
        column = self.get_column(column_name)
        if column.metadata.type == SegmentColumnType.DIMENSION:
            dict_id = column.get_dictionary_id_for_index(index) # takes 2s on 1.3M rows
            return column.get_dictionary_value_for_dictionary_id(dict_id) # takes 3.2s on 1.3M rows

        raise NotImplementedError(f"Unknown column type: {column.metadata.type}")

    def get_dictionary_ids_for_index_batch(self, column_name: str, indexes: BitMap):
        if len(indexes) == 0:
            return []

        column = self.get_column(column_name)
        # we can assume that the indexes is sorted
        start, end = indexes[0], indexes[-1]
        dict_id_list_in_range = column.get_dictionary_id_for_index_batch(start, end) # takes 2s on 1.3M rows
        return [dict_id_list_in_range[i - start] for i in indexes]
