import pickle
import struct

from pyroaring import BitMap


class SerializationUtils:
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
            bitmap, serialized_bitmap_length = SerializationUtils.deserialize_bitmap(serialized_data, byte_offset)
            bitmap_list.append(bitmap)
            byte_offset += serialized_bitmap_length + struct.calcsize('I')
        return bitmap_list

    @staticmethod
    def deserialize_int(serialized_data) -> int:
        return struct.unpack('I', serialized_data[0: 4])[0]
