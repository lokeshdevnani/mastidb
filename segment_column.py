import bisect
import struct

from pyroaring import BitMap

from data_accessor import DataAccessor
from db import create_roaring_bitmap

from segment_column_metadata import SegmentColumnMetadata
from serialization_utils import SerializationUtils


class SegmentColumn:
    metadata: SegmentColumnMetadata
    data_accessor: DataAccessor

    def __init__(self, metadata, data_accessor):
        self.metadata = metadata
        self.data_accessor = data_accessor

    @staticmethod
    def load(data_accessor: DataAccessor) -> 'SegmentColumn':
        metadata = SegmentColumnMetadata.load_from_serialized_data(data_accessor.fetch_metadata())
        return SegmentColumn(metadata, data_accessor)

    @staticmethod
    def create(data_accessor: DataAccessor, raw_column_data: list) -> 'SegmentColumn':
        encoded_data = SegmentColumn.encode_column(raw_column_data)
        metadata_binary, data_binary = SegmentColumn.serialize(encoded_data)
        data_accessor.write_metadata(metadata_binary)
        data_accessor.write(data_binary)

        return SegmentColumn.load(data_accessor)

    @staticmethod
    def encode_column(column_data: list):
        column_data = list(map(str, column_data))

        # Create a dictionary mapping unique values to integer IDs
        unique_values = sorted(set(column_data))
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
        dictionary_binary = SerializationUtils.serialize_strlist(list(dictionary.keys()))

        # Serialize list
        encoded_list_binary = SerializationUtils.serialize_intlist(encoded_list)

        # Serialize bitmaps and offsets
        bitmaps_binary = b''
        offsets = []
        current_offset = len(dictionary_binary) + len(encoded_list_binary) + len(dictionary) * struct.calcsize("I")
        for value, bitmap in bitmaps.items():
            offsets.append(current_offset)
            varlen_bitmap_binary = SerializationUtils.serialize_bitmap(bitmap)
            bitmaps_binary += varlen_bitmap_binary
            current_offset += len(varlen_bitmap_binary)

        offsets_binary = SerializationUtils.serialize_intlist(offsets)

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

    def deserialize(self):
        dictionary = SerializationUtils.deserialize_strlist(
            self.data_accessor.fetch(self.metadata.offset_dictionary, self.metadata.offset_list)
        )

        encoded_list = SerializationUtils.deserialize_intlist(
            self.data_accessor.fetch(self.metadata.offset_list, self.metadata.offset_bitmap_offsets),
            self.metadata.row_count
        )

        offsets = SerializationUtils.deserialize_intlist(
            self.data_accessor.fetch(self.metadata.offset_bitmap_offsets, self.metadata.offset_bitmaps_list),
            self.metadata.uniq_value_count
        )

        bitmaps = SerializationUtils.deserialize_bitmap_list(
            self.data_accessor.fetch(self.metadata.offset_bitmaps_list, self.metadata.end_offset),
            self.metadata.uniq_value_count
        )

        return dictionary, encoded_list, offsets, bitmaps

    def decode(self):
        deserialized_data = self.deserialize()
        return [deserialized_data[0][index] for index in deserialized_data[1]]

    def get_bitmap(self, index: int) -> BitMap:
        if index < 0 or index > self.metadata.uniq_value_count - 1:
            raise Exception(f"[get_bitmap] Unknown index: {index}")

        # Seek to index in offset_bitmap_offsets to find the bitmap
        if index == self.metadata.uniq_value_count - 1:
            bitmap_offset_start, bitmap_offset_end = SerializationUtils.deserialize_int(
                self.data_accessor.fetch(self.metadata.offset_bitmap_offsets + index * 4,
                                         self.metadata.offset_bitmap_offsets + index * 4 + 4)
            ), self.metadata.end_offset
        else:
            bitmap_offset_start, bitmap_offset_end = SerializationUtils.deserialize_intlist(
                self.data_accessor.fetch(self.metadata.offset_bitmap_offsets + index * 4,
                                         self.metadata.offset_bitmap_offsets + index * 4 + 8),
                2
            )

        # Get the bitmap
        bitmap, _ = SerializationUtils.deserialize_bitmap(
            self.data_accessor.fetch(bitmap_offset_start, bitmap_offset_end)
        )
        return bitmap

    def get_bitmap_for_item(self, item: str):
        index = self.get_index_for_item(item)
        return self.get_bitmap(index)

    def get_index_for_item(self, item):
        # lookup item in dictionary and find out the dictionary_code
        dictionary = SerializationUtils.deserialize_strlist(
            self.data_accessor.fetch(self.metadata.offset_dictionary, self.metadata.offset_list)
        )
        return binary_search(dictionary, item)

    def get_encoded_value_for_index(self, index):
        encoded_value = SerializationUtils.deserialize_int(
            self.data_accessor.fetch(self.metadata.offset_list + index * 4,
                                     self.metadata.offset_list + index * 4 + 4)
        )
        return encoded_value

    def decode_keys_with_items(self, dictionary_to_replace):
        dictionary = SerializationUtils.deserialize_strlist(
            self.data_accessor.fetch(self.metadata.offset_dictionary, self.metadata.offset_list)
        )

        return {dictionary[encoded_key]: value for encoded_key, value in dictionary_to_replace.items()}


def binary_search(arr, x):
    index = bisect.bisect_left(arr, x)
    if index != len(arr) and arr[index] == x:
        return index
    else:
        return -1


if __name__ == '__main__':
    data = ["Eminem", "Jay-z", "Rihanna", "Rihanna", "Jay-z", "Akon", "Akon"]
    encoded_data = SegmentColumn.encode_column(data)
    print("Encoded:", encoded_data)

    serialized_data = SegmentColumn.serialize(encoded_data)
    print("Serialized:", serialized_data)

    meta = SegmentColumnMetadata.load_from_serialized_data(serialized_data[0])
    print("Meta:", meta)

    print("--------")

    data_accessor = DataAccessor("./binarydb")
    segment_column = SegmentColumn.create(data_accessor, data)
    # segment_column = SegmentColumn.load_from_accessor(data_accessor)
    res = segment_column.deserialize()
    print(res)

    y = segment_column.decode()
    print(y)

    bitmap1 = segment_column.get_bitmap_for_item("Eminem")
    print("Bitmap: ", bitmap1)

    bitmap2 = segment_column.get_bitmap_for_item("Akon")

    bitmap = bitmap1.union(bitmap2)

    def aggregation_count_func(index_encoded_value_map, encoded_value):
        index_encoded_value_map[encoded_value] = index_encoded_value_map.get(encoded_value, 0) + 1


