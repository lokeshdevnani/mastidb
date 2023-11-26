import pyroaring
from pyroaring import BitMap


def break_bitmap_into_chunks(bitmap: BitMap, bitmap_density_threshold: float = 0.25, chunk_size: int = 10) -> list[BitMap]:
    if len(bitmap) == 0:
        return []

    b_min, b_max, b_size = bitmap.min(), bitmap.max(), len(bitmap)
    if b_size/(b_max - b_min) >= bitmap_density_threshold: # dense bitmap
        return [bitmap]
    else:
        results = []
        chunk_start = b_min
        while chunk_start <= b_max:
            results.append(BitMap.intersection(BitMap(pyroaring.range(chunk_start, chunk_start + chunk_size)), bitmap))
            if chunk_start + chunk_size >= b_max:
                break

            chunk_start = bitmap.next_set_bit(chunk_start + chunk_size)


        return results


# Input: # BitMap([5, 20, 32, 54, 100, 104, 200, 201])