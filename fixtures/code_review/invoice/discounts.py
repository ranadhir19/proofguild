"""Discount helpers. Spec: percentage discounts round HALF-UP to
whole cents (commercial rounding)."""
from decimal import Decimal, ROUND_HALF_EVEN


def apply_discount(amount, pct):
    factor = Decimal("1") - (Decimal(str(pct)) / Decimal("100"))
    cents = (Decimal(str(amount)) * factor * 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_EVEN)
    return float(cents) / 100.0
