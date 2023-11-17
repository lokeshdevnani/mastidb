import struct
from dataclasses import dataclass


@dataclass
class SegmentColumnMetadata:
    uniq_value_count: int
    row_count: int
    offset_dictionary: int
    offset_list: int
    offset_bitmap_offsets: int
    offset_bitmaps_list: int
    end_offset: int

    @staticmethod
    def load_from_serialized_data(serialized_data: bytes) -> 'SegmentColumnMetadata':
        return SegmentColumnMetadata(*struct.unpack('iiiiiii', serialized_data))

    def serialize(self) -> bytes:
        serialized_metadata = struct.pack('iiiiiii', *self.__dict__.values())
        return serialized_metadata

    def stats(self) -> dict:
        return {
            'dict_size': self.offset_list - self.offset_dictionary,
            'list_size': self.offset_bitmap_offsets - self.offset_list,
            'offsets_size': self.offset_bitmaps_list - self.offset_bitmap_offsets,
            'bitmaps_size': self.end_offset - self.offset_bitmaps_list
        }
