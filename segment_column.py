import struct

from pyroaring import BitMap

from db import create_roaring_bitmap
import pickle
from dataclasses import dataclass
import pandas as pd


@dataclass
class SegmentColumnMetadata:
    uniq_value_count: int
    row_count: int
    offset_dictionary: int
    offset_list: int
    offset_bitmap_offsets: int
    offset_bitmaps_list: int
    end_offset: int

    def load_from_serialized_data(data):
        return SegmentColumnMetadata(*struct.unpack('iiiiiii', data))

    def serialize(self) -> bytes:
        serialized_metadata = struct.pack('iiiiiii', *self.__dict__.values())
        return serialized_metadata


class SegmentColumn:
    metadata: SegmentColumnMetadata
    payload_binary: str

    @staticmethod
    def encode_column(column_data: list):
        # Create a dictionary mapping unique values to integer IDs
        unique_values = list(set(column_data))
        dictionary = {value: i for i, value in enumerate(unique_values)}

        # Create a list of integer IDs using the dictionary
        encoded_list = [dictionary[value] for value in column_data]

        # Create roaring bitmaps for each unique value in the column
        bitmaps = {value: create_roaring_bitmap(encoded_list, index) for value, index in dictionary.items()}

        return dictionary, encoded_list, bitmaps

    @staticmethod
    def serialize(encoded_data) -> (bytes, bytes):
        dictionary, encoded_list, bitmaps = encoded_data

        # Serialize dictionary
        dictionary_binary = Helper.serialize_strlist(list(dictionary.keys()))

        # Serialize list
        encoded_list_binary = Helper.serialize_intlist(encoded_list)

        # Serialize bitmaps and offsets
        bitmaps_binary = b''
        offsets = []
        current_offset = len(dictionary_binary) + len(encoded_list_binary) + len(dictionary) * struct.calcsize("I")
        for value, bitmap in bitmaps.items():
            offsets.append(current_offset)
            varlen_bitmap_binary = Helper.serialize_bitmap(bitmap)
            bitmaps_binary += varlen_bitmap_binary
            current_offset += len(varlen_bitmap_binary)

        offsets_binary = Helper.serialize_intlist(offsets)

        metadata = SegmentColumnMetadata(
            uniq_value_count=len(dictionary),
            row_count=len(encoded_list),
            offset_dictionary=0,
            offset_list=len(dictionary_binary),
            offset_bitmap_offsets=len(dictionary_binary) + len(encoded_list_binary),
            offset_bitmaps_list=len(dictionary_binary) + len(encoded_list_binary) + len(offsets_binary),
            end_offset=len(dictionary_binary) + len(encoded_list_binary) + len(offsets_binary) + len(bitmaps_binary)
        )

        payload_binary = dictionary_binary + encoded_list_binary + offsets_binary + bitmaps_binary
        return metadata.serialize(), payload_binary

    @staticmethod
    def deserialize(metadata: SegmentColumnMetadata, data):
        dictionary = Helper.deserialize_strlist(
            Helper.read_bytes(data, metadata.offset_dictionary, metadata.offset_list)
        )

        encoded_list = Helper.deserialize_intlist(
            Helper.read_bytes(data, metadata.offset_list, metadata.offset_bitmap_offsets), metadata.row_count
        )

        offsets = Helper.deserialize_intlist(
            Helper.read_bytes(data, metadata.offset_bitmap_offsets, metadata.offset_bitmaps_list),
            metadata.uniq_value_count
        )

        bitmaps = Helper.deserialize_bitmap_list(
            Helper.read_bytes(data, metadata.offset_bitmaps_list, metadata.end_offset), metadata.uniq_value_count
        )

        return dictionary, encoded_list, offsets, bitmaps


class Helper:
    @staticmethod
    def serialize_strlist(list):
        return pickle.dumps(list)

    @staticmethod
    def deserialize_strlist(serialized_data) -> list:
        return pickle.loads(serialized_data)

    @staticmethod
    def serialize_intlist(list):
        return struct.pack(f"{len(list)}i", *list)

    @staticmethod
    def deserialize_intlist(serialized_data, length):
        return struct.unpack(f"{length}i", serialized_data)

    @staticmethod
    def serialize_bitmap(bitmap):
        bitmap_content = bitmap.serialize()
        return struct.pack(f'I{len(bitmap_content)}B', len(bitmap_content), *bitmap_content)

    @staticmethod
    def deserialize_bitmap(serialized_data, byte_offset=0):
        bitmap_length = struct.unpack('I', serialized_data[byte_offset:byte_offset + 4])[0]
        bitmap_content = \
        struct.unpack(f'{bitmap_length}s', serialized_data[byte_offset + 4: byte_offset + 4 + bitmap_length])[0]
        return BitMap.deserialize(bitmap_content), bitmap_length

    @staticmethod
    def deserialize_bitmap_list(serialized_data, length):
        byte_offset = 0
        bitmap_list = []
        for i in range(length):
            bitmap, serialized_bitmap_length = Helper.deserialize_bitmap(serialized_data, byte_offset)
            bitmap_list.append(bitmap)
            byte_offset += serialized_bitmap_length + struct.calcsize('I')
        return bitmap_list

    @staticmethod
    def read_bytes(data, start, end):
        return data[start:end]


if __name__ == '__main__':
    data = ["Eminem", "Jay-z", "Eminem", "Rihanna", "Jay-z"]
    series = pd.Series(data)
    encoded_data = SegmentColumn.encode_column(data)
    print("Encoded:", encoded_data)

    serialized_data = SegmentColumn.serialize(encoded_data)
    print("Serialized:", serialized_data)

    meta = SegmentColumnMetadata.load_from_serialized_data(serialized_data[0])
    print("Meta:", meta)

    deserialized_data = SegmentColumn.deserialize(meta, serialized_data[1])
    print("Deserialized:", deserialized_data)
