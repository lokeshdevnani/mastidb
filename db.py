import pandas as pd
from pyroaring import BitMap
import struct
import pickle


def create_roaring_bitmap(encoded_list, value_index):
    return BitMap([i for i, encoded_value in enumerate(encoded_list) if encoded_value == value_index])


def encode_column(data):
    # Create a dictionary mapping unique values to integer IDs
    unique_values = data.unique()
    dictionary = {value: i for i, value in enumerate(unique_values)}

    # Create a list of integer IDs using the dictionary
    encoded_list = data.map(dictionary)

    # Create roaring bitmaps for each unique value in the column
    bitmaps = {value: create_roaring_bitmap(encoded_list, index) for value, index in dictionary.items()}

    return dictionary, encoded_list.tolist(), bitmaps

def serialize(data):
    # Serialize dictionary
    dictionary_binary = serialize_dict(data[0])

    # Serialize list
    list_length = len(data[1])
    list_binary = struct.pack(f'I{list_length}i', list_length, *data[1])

    # Serialize bitmaps and offsets
    bitmaps_binary = b''
    offsets = []
    offset = 0
    for value, bitmap in data[2].items():
        offsets.append(offset)
        bitmap_content = bitmap.serialize()
        bitmap_length_binary = struct.pack('I', len(bitmap_content))
        bitmap_binary = struct.pack(f'{len(bitmap_content)}B', *bitmap_content)
        bitmaps_binary += (bitmap_length_binary + bitmap_binary)
        offset += len(bitmap_content) + 4  # for the length

    offsets_binary = struct.pack(f'I{len(offsets)}i', len(offsets), *offsets)

    print(len(dictionary_binary), len(list_binary), len(offsets_binary), len(bitmaps_binary))

    return dictionary_binary + list_binary + offsets_binary + bitmaps_binary


def deserialize(data):
    dictionary, dictionary_length, dictionary_length_bytes = load_dictionary(data)

    encoded_list, list_length = load_list(data, dictionary_length_bytes)

    offsets = load_bitmap_offsets(data, dictionary_length_bytes, list_length)

    bitmaps = load_bitmaps(data, dictionary_length, dictionary_length_bytes, list_length)

    return dictionary, list(encoded_list), offsets, bitmaps


def deserialize_get_bitmap_for_value(data, value):
    # search for value in dict
    dictionary, dictionary_length, dictionary_length_bytes = load_dictionary(data)
    list_index = dictionary.get(value)

    encoded_list, list_length = load_list(data, dictionary_length_bytes)

    # seek to that offset
    relative_bitmap_offset_for_value = load_bitmap_offset_by_list_index(data, dictionary_length_bytes, list_length, list_index)
    absolute_bitmap_offset = get_byte_offset_for_bitmaps(dictionary_length_bytes, dictionary_length, list_length) + relative_bitmap_offset_for_value

    return load_single_bitmap(data, absolute_bitmap_offset)


def load_bitmaps(data, dictionary_length, dictionary_length_bytes, list_length):
    current = get_byte_offset_for_bitmaps(dictionary_length_bytes, dictionary_length, list_length)

    # Unpack bitmaps
    bitmaps = {}
    for i in range(dictionary_length):
        bitmap, bitmap_length = load_single_bitmap(data, current)
        bitmaps[i] = bitmap
        current += 4 + bitmap_length
    return bitmaps


def get_byte_offset_for_bitmaps(dictionary_length_bytes, dictionary_length, list_length):
    return 8 + dictionary_length_bytes + (list_length * 4) + 4 + (4 * dictionary_length)


def load_single_bitmap(data, byte_offset):
    # Unpack the bitmap length and content
    bitmap_length = struct.unpack('I', data[byte_offset:byte_offset + 4])[0]
    bitmap_content = struct.unpack(f'{bitmap_length}s', data[byte_offset + 4 : byte_offset + 4 + bitmap_length])[0]
    bitmap = BitMap.deserialize(bitmap_content)
    return bitmap, bitmap_length


def load_bitmap_offsets(data, dictionary_length, list_length):
    current = 8 + dictionary_length + list_length * 4
    offsets_length = struct.unpack('I', data[current:current + 4])[0]
    offsets = struct.unpack(f'{offsets_length}i', data[current + 4: current + 4 + offsets_length * 4])
    return offsets


def load_bitmap_offset_by_list_index(data, dictionary_length, list_length, list_index):
    current = 8 + dictionary_length + list_length * 4
    offset = struct.unpack(f'i',
                            data[current + 4 + list_index * 4: current + 4 + (list_index + 1) * 4])[0]
    return offset


def load_list(data, dictionary_length):
    list_length = struct.unpack('I', data[4 + dictionary_length:8 + dictionary_length])[0]
    encoded_list = struct.unpack(f'{list_length}i', data[8 + dictionary_length:8 + dictionary_length + list_length * 4])
    return encoded_list, list_length


def load_dictionary(data):
    size_format = "I"
    size = struct.unpack(size_format, data[:struct.calcsize(size_format)])[0]
    serialized_data = data[struct.calcsize(size_format):]
    dictionary = pickle.loads(serialized_data)
    return dictionary, len(dictionary), size


def serialize_dict(data):
    serialized_data = pickle.dumps(data)
    return struct.pack(f"I{len(serialized_data)}s", len(serialized_data), serialized_data)


if __name__ == '__main__':
    # Example data
    data = pd.Series(["kustin Bieber", "kustin Bieber", "Eminem", "Eminem", "Akon", "kustin Bieber"])
    encoded_data = encode_column(data)

    # Serialize data
    serialized_data = serialize(encoded_data)
    print("serialized data: \n", serialized_data)

    # Deserialize data
    decoded_data = deserialize(serialized_data)
    print(decoded_data)

    x = deserialize_get_bitmap_for_value(serialized_data, "Eminem")
    print(x[0])
