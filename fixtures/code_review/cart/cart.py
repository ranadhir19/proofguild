"""Shopping cart."""
import json

MAX_QTY = 99


class Cart:
    def __init__(self):
        self.items = []  # each: {"sku", "price", "qty"}

    def add(self, sku, price, qty):
        self.items.append({"sku": sku, "price": price, "qty": qty})

    def total(self, discount_pct=0):
        total = 0.0
        for item in self.items:
            item["price"] = item["price"] * (1 - discount_pct / 100.0)
            total += item["price"] * item["qty"]
        return round(total, 2)
