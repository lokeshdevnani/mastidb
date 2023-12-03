import logging
import struct
from functools import lru_cache
from typing import Tuple

from pyroaring import BitMap  # type: ignore

from common_utils import binary_search_with_reader
from data_accessor import DataAccessor

from segment_column_metadata import SegmentColumnMetadata, SegmentColumnType
from serialization_utils import SerializationUtils

logger = logging.getLogger(__name__)

"""
Terminology for data structures
# Dictionary
    {[dictionary_id]: [dictionary_value]}
    dictionary_value can also be referred to as `item`
    Eg. ["Eminem", "Jay-Z", "Linkin Park"]
    
# List
    Contains list of encoded values in range [0, count(rows)) indexed by list_index
    It will contain dictionary_id in range (0, max(dictionary_id))
    Eg. [2, 2, 1, 0, 1, 1, 2]

# Bitmap indexes
    Contains bitmap indexes for each of the dictionary items i.e. total of len(dictionary) bitmap indexes
     BitMap[3], BitMap[2,4,5], BitMap[0,1,6]
"""


class SegmentColumn:
    metadata: SegmentColumnMetadata
    data_accessor: DataAccessor

    def __init__(self, metadata: SegmentColumnMetadata, data_accessor: DataAccessor):
        self.metadata = metadata
        self.data_accessor = data_accessor

    @staticmethod
    def load(data_accessor: DataAccessor) -> 'SegmentColumn':
        metadata = SegmentColumnMetadata.load_from_serialized_data(data_accessor.fetch_metadata())
        return SegmentColumn(metadata, data_accessor)

    @staticmethod
    def create(data_accessor: DataAccessor, raw_column_data: list) -> 'SegmentColumn':
        logger.debug("Encoding column")
        encoded_data = SegmentColumn.encode_column(raw_column_data)

        logger.debug("Serializing column")
        metadata_binary, data_binary = SegmentColumn.serialize(encoded_data)

        logger.debug("Writing column to disk")
        data_accessor.write_metadata(metadata_binary)
        data_accessor.write(data_binary)

        return SegmentColumn.load(data_accessor.open("rb"))

    @staticmethod
    def encode_column(column_data: list) -> Tuple[dict, list, list]:
        column_data = list(map(str, column_data))

        # Create a dictionary mapping unique values to integer IDs
        unique_values = sorted(set(column_data))
        dictionary = {value: i for i, value in enumerate(unique_values)}

        # Create a list of integer IDs using the dictionary
        encoded_list = [dictionary[value] for value in column_data]

        # Create roaring bitmaps for each unique value in the column
        bitmaps = SegmentColumn.create_bitmap_indexes(encoded_list, len(unique_values))

        return dictionary, encoded_list, bitmaps

    @staticmethod
    def create_bitmap_indexes(encoded_array: list[int], cardinality: int) -> list[BitMap]:
        grouped_indexes: list[list[int]] = [[] for _ in range(cardinality)]

        for index, encoded_value in enumerate(encoded_array):
            grouped_indexes[encoded_value].append(index)

        return [BitMap(set_values) for set_values in grouped_indexes]

    @staticmethod
    def serialize(encoded_data: Tuple[dict, list[int], list[BitMap]]) -> Tuple[bytes, bytes]:
        dictionary, encoded_list, bitmaps = encoded_data

        logger.debug("Serializing dictionary and dictionary offsets")
        dictionary_binary, dictionary_offsets_binary = SerializationUtils.serialize_strlist_with_offsets(
            list(dictionary.keys()))

        logger.debug("Serializing encoded list")
        encoded_list_binary = SerializationUtils.serialize_intlist(encoded_list)

        logger.debug("Serializing bitmaps and bitmap offsets")
        bitmaps_binary_list = []
        offsets = []
        current_offset = len(dictionary_offsets_binary) + len(dictionary_binary) + len(encoded_list_binary) + len(
            dictionary) * struct.calcsize("I")
        for value, bitmap in enumerate(bitmaps):
            offsets.append(current_offset)
            varlen_bitmap_binary = SerializationUtils.serialize_bitmap(bitmap)
            bitmaps_binary_list.append(varlen_bitmap_binary)
            current_offset += len(varlen_bitmap_binary)

        bitmaps_binary = b''.join(bitmaps_binary_list)
        offsets_binary = SerializationUtils.serialize_intlist(offsets)

        metadata = SegmentColumnMetadata(
            version=1,
            uniq_value_count=len(dictionary),
            row_count=len(encoded_list),
            offset_dictionary_offsets=0,
            offset_dictionary=len(dictionary_offsets_binary),
            offset_list=len(dictionary_offsets_binary) + len(dictionary_binary),
            offset_bitmap_offsets=len(dictionary_offsets_binary) + len(dictionary_binary) + len(encoded_list_binary),
            offset_bitmaps_list=len(dictionary_offsets_binary) + len(dictionary_binary) + len(
                encoded_list_binary) + len(
                offsets_binary),
            end_offset=len(dictionary_offsets_binary) + len(dictionary_binary) + len(encoded_list_binary) + len(
                offsets_binary) + len(bitmaps_binary),
            type=SegmentColumnType.DIMENSION
        )

        payload_binary = dictionary_offsets_binary + dictionary_binary + encoded_list_binary + offsets_binary + bitmaps_binary
        return metadata.serialize(), payload_binary

    def deserialize(self):
        dictionary = self._get_dictionary()

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

    def get_dictionary_id_for_item(self, item) -> int:
        # lookup item in dictionary and find out the dictionary_code
        dict_id = binary_search_with_reader(self.metadata.uniq_value_count, item,
                                            lambda idx: self.get_dictionary_value_for_dictionary_id(idx))
        return dict_id

    def _get_dictionary(self):
        raise NotImplementedError()

    def get_bitmap_for_item(self, item: str) -> BitMap:
        dictionary_id = self.get_dictionary_id_for_item(item)
        if dictionary_id == -1:
            # Empty item was not found in the dictionary, return BitMap with everything set to 0
            # indicating none of the rows match
            return BitMap()
        return self.get_bitmap(dictionary_id)

    def get_dictionary_value_for_dictionary_id(self, dictionary_id) -> str:
        start = self.metadata.offset_dictionary_offsets + dictionary_id * 4
        val_offset_start, val_offset_end = SerializationUtils.deserialize_intlist(
            self.data_accessor.fetch(start, start + 8),
            2
        )
        return SerializationUtils.deserialize_string(
            self.data_accessor.fetch(self.metadata.offset_dictionary + val_offset_start,
                                     self.metadata.offset_dictionary + val_offset_end)
        )

    def get_dictionary_id_for_index(self, index) -> int:
        encoded_value = SerializationUtils.deserialize_int(
            self.data_accessor.fetch(self.metadata.offset_list + index * 4,
                                     self.metadata.offset_list + index * 4 + 4)
        )
        return encoded_value

    def get_dictionary_id_for_index_batch(self, start, end) -> Tuple[int, ...]:
        encoded_value = SerializationUtils.deserialize_intlist(
            self.data_accessor.fetch(self.metadata.offset_list + start * 4,
                                     self.metadata.offset_list + end * 4 + 4),
            (end-start+1)
        )
        return encoded_value

    def get_bitmap(self, dictionary_id: int) -> BitMap:
        if dictionary_id < 0 or dictionary_id > self.metadata.uniq_value_count - 1:
            raise Exception(f"[get_bitmap] Unknown dictionary_id: {dictionary_id}")

        # Seek to index=dictionary_id in offset_bitmap_offsets to find the bitmap
        if dictionary_id == self.metadata.uniq_value_count - 1:
            bitmap_offset_start, bitmap_offset_end = SerializationUtils.deserialize_int(
                self.data_accessor.fetch(self.metadata.offset_bitmap_offsets + dictionary_id * 4,
                                         self.metadata.offset_bitmap_offsets + dictionary_id * 4 + 4)
            ), self.metadata.end_offset
        else:
            bitmap_offset_start, bitmap_offset_end = SerializationUtils.deserialize_intlist(
                self.data_accessor.fetch(self.metadata.offset_bitmap_offsets + dictionary_id * 4,
                                         self.metadata.offset_bitmap_offsets + dictionary_id * 4 + 8),
                2
            )

        # Get the bitmap
        bitmap, _ = SerializationUtils.deserialize_bitmap(
            self.data_accessor.fetch(bitmap_offset_start, bitmap_offset_end)
        )
        return bitmap
