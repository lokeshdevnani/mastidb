import os

import pandas as pd

from .common_utils import find_column_files
from .segment import Segment
from .segment_ingester import SegmentIngester


def _ingest_chunks(data_dir: str, df: pd.DataFrame, num_segments: int) -> None:
    if num_segments == 1:
        SegmentIngester.ingest_from_df(data_dir, df)
        return

    chunk_size = (len(df) + num_segments - 1) // num_segments
    for i in range(num_segments):
        chunk = df.iloc[i * chunk_size:(i + 1) * chunk_size]
        if len(chunk) == 0:
            break
        SegmentIngester.ingest_from_df(f'{data_dir}/seg_{i}', chunk)


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
        df = SegmentIngester.convert_file_to_pandas(source_file)
        _ingest_chunks(data_dir, df, num_segments)
        return Table.from_data_dir(data_dir)
