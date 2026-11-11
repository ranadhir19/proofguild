import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from paginate import paginate
from wordcount import count_words


class TestTextkit(unittest.TestCase):
    def test_exact_multiple_keeps_all(self):
        pages = paginate(list(range(10)), 5)
        self.assertEqual(sum(len(p) for p in pages), 10)

    def test_remainder_page(self):
        pages = paginate(list(range(11)), 5)
        self.assertEqual(sum(len(p) for p in pages), 11)

    def test_empty_wordcount(self):
        self.assertEqual(count_words(""), 0)

    def test_simple_wordcount(self):
        self.assertEqual(count_words("one two three"), 3)


if __name__ == "__main__":
    unittest.main()
