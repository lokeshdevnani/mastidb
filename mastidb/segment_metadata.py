import struct
from dataclasses import dataclass


@dataclass
class SegmentMetadata:
    version: int
    column_count: int

    @staticmethod
    def load_from_serialized_data(serialized_data: bytes) -> 'SegmentMetadata':
        return SegmentMetadata(*struct.unpack('iiiiiii', serialized_data))

    def serialize(self) -> bytes:
        serialized_metadata = struct.pack('iiiiiii', *self.__dict__.values())
        return serialized_metadata
