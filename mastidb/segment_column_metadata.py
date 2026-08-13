import struct
from dataclasses import dataclass
from enum import Enum


class SegmentColumnType(Enum):
    DIMENSION = 1
    METRIC = 2


@dataclass
class SegmentColumnMetadata:
    version: int
    uniq_value_count: int
    row_count: int
    offset_dictionary_offsets: int
    offset_dictionary: int
    offset_list: int
    offset_bitmap_offsets: int
    offset_bitmaps_list: int
    end_offset: int
    type: SegmentColumnType

    @staticmethod
    def load_from_serialized_data(serialized_data: bytes) -> 'SegmentColumnMetadata':
        # Unpack the data
        values: tuple = struct.unpack('i'*10, serialized_data)
        # Create an instance using attribute names
        return SegmentColumnMetadata(
            version=values[0],
            uniq_value_count=values[1],
            row_count=values[2],
            offset_dictionary_offsets=values[3],
            offset_dictionary=values[4],
            offset_list=values[5],
            offset_bitmap_offsets=values[6],
            offset_bitmaps_list=values[7],
            end_offset=values[8],
            type=SegmentColumnType(values[9])
        )

    def serialize(self) -> bytes:
        values = (
            self.version,
            self.uniq_value_count,
            self.row_count,
            self.offset_dictionary_offsets,
            self.offset_dictionary,
            self.offset_list,
            self.offset_bitmap_offsets,
            self.offset_bitmaps_list,
            self.end_offset,
            self.type.value
        )
        serialized_metadata = struct.pack('i'*10, *values)
        return serialized_metadata

    def stats(self) -> dict:
        return {
            'dict_size': self.offset_list - self.offset_dictionary,
            'list_size': self.offset_bitmap_offsets - self.offset_list,
            'offsets_size': self.offset_bitmaps_list - self.offset_bitmap_offsets,
            'bitmaps_size': self.end_offset - self.offset_bitmaps_list
        }
