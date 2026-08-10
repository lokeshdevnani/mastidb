from .segment import Segment
from .segment_ingester import SegmentIngester


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
        return Table([Segment.load(data_dir)])

    @staticmethod
    def from_ingest_source(data_dir: str, source_file: str) -> 'Table':
        segment = SegmentIngester.ingest(data_dir, source_file)
        return Table([segment])
