import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cart import Cart
from stock import check_line


class TestCart(unittest.TestCase):
    def test_total_repeatable(self):
        c = Cart()
        c.add("A", 100.0, 1)
        first = c.total(10)
        second = c.total(10)
        self.assertEqual(first, second)

    def test_qty_cap(self):
        ok, _ = check_line(150)
        self.assertFalse(ok)

    def test_qty_ok(self):
        ok, _ = check_line(5)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
