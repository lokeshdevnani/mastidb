import logging
import time

from .common_utils import ensure_directory_exists
from .data_accessor import DataAccessor
from .segment import Segment
from .segment_column import SegmentColumn
from .source_reader import ParsedSource, read_source


logger = logging.getLogger(__name__)


class SegmentIngester:
    @staticmethod
    def ingest(data_dir: str, file_path: str) -> Segment:
        start_time = time.time()
        segment = SegmentIngester.ingest_from_parsed(data_dir, read_source(file_path))
        logger.info("[create] Segment created. Took %.2f seconds", time.time() - start_time)
        return segment

    @staticmethod
    def ingest_from_parsed(data_dir: str, source: ParsedSource) -> Segment:
        logger.info("[create] Creating a segment")
        segment_columns: dict[str, SegmentColumn] = {}

        ensure_directory_exists(data_dir)

        for column, values in source.columns.items():
            logger.info("[create] Building column: %s", column)
            segment_columns[column] = SegmentColumn.create(
                DataAccessor(f"{data_dir}/{column}").open('wb'),
                values,
            )
        return Segment(segment_columns)
