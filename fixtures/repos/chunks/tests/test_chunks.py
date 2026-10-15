import unittest

from src.chunks import chunk, pairs


class ChunkTest(unittest.TestCase):
    def test_even_split(self):
        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_keeps_the_remainder(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_piece_longer_than_input(self):
        self.assertEqual(chunk([1, 2], 5), [[1, 2]])

    def test_empty_input(self):
        self.assertEqual(chunk([], 3), [])

    def test_invalid_size(self):
        with self.assertRaises(ValueError):
            chunk([1], 0)

    def test_pairs(self):
        self.assertEqual(pairs("abc"), [["a", "b"], ["c"]])
