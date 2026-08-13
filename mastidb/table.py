import os

from .common_utils import find_column_files
from .segment import Segment
from .segment_ingester import SegmentIngester
from .source_reader import ParsedSource, read_source


def _ingest_chunks(data_dir: str, source: ParsedSource, num_segments: int) -> None:
    if num_segments == 1:
        SegmentIngester.ingest_from_parsed(data_dir, source)
        return

    chunk_size = (source.num_rows() + num_segments - 1) // num_segments
    for i in range(num_segments):
        chunk = source.slice(i * chunk_size, (i + 1) * chunk_size)
        if chunk.num_rows() == 0:
            break
        SegmentIngester.ingest_from_parsed(f'{data_dir}/seg_{i}', chunk)


class Table:
    """Logical table: one or more segments with a shared schema."""

    def __init__(self, segments: list[Segment]):
        if not segments:
            raise ValueError("Table requires at least one segment")
        self.segments = segments

    def column_names(self) -> list[str]:
        return self.segments[0].column_names()

    @staticmethod
    def from_data_dir(data_dir: str) -> 'Table':
        # Flat segment: column files live directly under data_dir.
        if find_column_files(data_dir):
            return Table([Segment.load(data_dir)])

        # Multi-segment: each subdirectory is a segment.
        segment_dirs = sorted(
            f'{data_dir}/{name}'
            for name in os.listdir(data_dir)
            if os.path.isdir(f'{data_dir}/{name}')
        )
        if not segment_dirs:
            raise ValueError(f"No segments found in {data_dir}")
        return Table([Segment.load(path) for path in segment_dirs])

    @staticmethod
    def from_ingest_source(data_dir: str, source_file: str,
                           num_segments: int = 1) -> 'Table':
        if num_segments < 1:
            raise ValueError("num_segments must be >= 1")
        _ingest_chunks(data_dir, read_source(source_file), num_segments)
        return Table.from_data_dir(data_dir)
