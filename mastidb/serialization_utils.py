import pickle
import struct
from functools import lru_cache
from typing import Tuple, Any, List

from pyroaring import BitMap # type: ignore


class SerializationUtils:
    @staticmethod
    def serialize_strlist(items: list[str]) -> bytes:
        return pickle.dumps(items)

    @staticmethod
    def deserialize_strlist(serialized_data: bytes) -> list[str]:
        return pickle.loads(serialized_data)

    @staticmethod
    def serialize_strlist_with_offsets(strlist: list[str]) -> tuple[bytes, bytes]:
        offsets = [0]
        encoded_list=[]
        for item in strlist:
            encoded = item.encode("utf-8")
            offsets.append(offsets[-1] + len(encoded))
            encoded_list.append(encoded)
        serialized_list = b"".join(encoded_list)
        return serialized_list, SerializationUtils.serialize_intlist(offsets)

    @staticmethod
    def deserialize_string(str_bytes: bytes) -> str:
        return str_bytes.decode("utf-8")

    @staticmethod
    def serialize_intlist(list: list[int]) -> bytes:
        return struct.pack(f"{len(list)}i", *list)

    @staticmethod
    def deserialize_intlist(serialized_data: bytes, length: int) -> tuple[int, ...]:
        return struct.unpack(f"{length}i", serialized_data)

    @staticmethod
    def serialize_bitmap(bitmap: BitMap) -> bytes:
        bitmap_content = bitmap.serialize()
        return struct.pack(f'I{len(bitmap_content)}B', len(bitmap_content), *bitmap_content)

    @staticmethod
    def deserialize_bitmap(serialized_data: bytes, byte_offset: int=0) -> tuple[BitMap, int]:
        bitmap_length = struct.unpack('I', serialized_data[byte_offset:byte_offset + 4])[0]
        bitmap_content = \
            struct.unpack(f'{bitmap_length}s', serialized_data[byte_offset + 4: byte_offset + 4 + bitmap_length])[0]
        return BitMap.deserialize(bitmap_content), bitmap_length

    @staticmethod
    def deserialize_bitmap_list(serialized_data: bytes, length: int) -> list[BitMap]:
        byte_offset = 0
        bitmap_list: list[BitMap] = []
        for i in range(length):
            bitmap, serialized_bitmap_length = SerializationUtils.deserialize_bitmap(serialized_data, byte_offset)
            bitmap_list.append(bitmap)
            byte_offset += serialized_bitmap_length + struct.calcsize('I')
        return bitmap_list

    @staticmethod
    def deserialize_int(serialized_data: bytes) -> int:
        return struct.unpack('I', serialized_data[0: 4])[0]
