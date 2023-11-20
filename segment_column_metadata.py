import struct
from dataclasses import dataclass
from enum import Enum


class SegmentColumnType(Enum):
    DIMENSION:int = 1
    METRIC:int = 2


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
        # Unpack the enum as an integer
        values: tuple = struct.unpack('i'*10, serialized_data)
        return SegmentColumnMetadata(*values[:-1], type=SegmentColumnType(values[-1]))

    def serialize(self) -> bytes:
        # Pack the enum as an integer
        values = list(self.__dict__.values())[:-1]  # Exclude the enum value
        values.append(self.type.value)
        serialized_metadata = struct.pack('i'*10, *values)
        return serialized_metadata

    def stats(self) -> dict:
        return {
            'dict_size': self.offset_list - self.offset_dictionary,
            'list_size': self.offset_bitmap_offsets - self.offset_list,
            'offsets_size': self.offset_bitmaps_list - self.offset_bitmap_offsets,
            'bitmaps_size': self.end_offset - self.offset_bitmaps_list
        }
