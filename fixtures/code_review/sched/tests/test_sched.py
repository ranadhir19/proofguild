import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from intervals import overlaps


class TestSched(unittest.TestCase):
    def test_real_overlap(self):
        self.assertTrue(overlaps(0, 10, 5, 15))

    def test_touching_counts(self):
        # back-to-back: 10-11 and 11-12 touch at 11 -> overlap per spec
        self.assertTrue(overlaps(10, 11, 11, 12))

    def test_disjoint(self):
        self.assertFalse(overlaps(0, 5, 6, 9))


if __name__ == "__main__":
    unittest.main()
