import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from billing import invoice_total
from discounts import apply_discount


class TestInvoice(unittest.TestCase):
    def test_discount_before_tax(self):
        # $100 item, 10% discount, east tax 8%: tax on $90 -> $97.20
        items = [{"price": 100.0, "qty": 1}]
        self.assertEqual(invoice_total(items, "east", 10), 97.20)

    def test_no_discount(self):
        items = [{"price": 50.0, "qty": 2}]
        self.assertEqual(invoice_total(items, "west", 0), 105.00)

    def test_half_up_rounding(self):
        # 10.005 at 0% -> 10.01 under half-up (banker's gives 10.00)
        self.assertEqual(apply_discount(10.005, 0), 10.01)


if __name__ == "__main__":
    unittest.main()
