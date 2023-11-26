import unittest
from pyroaring import BitMap
from bitmap_utils import break_bitmap_into_chunks


class TestBreakBitmapIntoChunks(unittest.TestCase):
    def test_empty_bitmap(self):
        empty_bitmap = BitMap()
        result = break_bitmap_into_chunks(empty_bitmap)
        self.assertEqual(result, [], f"Test Case 1 failed: {result}")

    def test_dense_bitmap(self):
        dense_bitmap = BitMap([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = break_bitmap_into_chunks(dense_bitmap)
        self.assertEqual(result, [dense_bitmap], f"Test Case 2 failed: {result}")

    def test_sparse_bitmap(self):
        sparse_bitmap = BitMap([5, 20, 32, 54, 100, 104, 200, 201])
        result = break_bitmap_into_chunks(sparse_bitmap, bitmap_density_threshold=0.99, chunk_size=25)
        expected_result = [BitMap([5, 20]), BitMap([32, 54]), BitMap([100, 104]), BitMap([200, 201])]
        self.assertEqual(result, expected_result, f"Test Case 3 failed: {result}")

    def test_chunk_threshold(self):
        sparse_bitmap = BitMap([5, 20, 32, 54, 100, 104, 200, 201])
        result = break_bitmap_into_chunks(sparse_bitmap, bitmap_density_threshold=0.02)
        self.assertEqual(result, [sparse_bitmap], f"Test Case 4 failed: {result}")

    def test_custom_chunk_size(self):
        sparse_bitmap = BitMap([5, 20, 32, 54, 100, 104, 200, 201])
        result = break_bitmap_into_chunks(sparse_bitmap, chunk_size=50)
        expected_result = [BitMap([5, 20, 32, 54]), BitMap([100, 104]), BitMap([200, 201])]
        self.assertEqual(result, expected_result, f"Test Case 5 failed: {result}")

if __name__ == '__main__':
    unittest.main()
