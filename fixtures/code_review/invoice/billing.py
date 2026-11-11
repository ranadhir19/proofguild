"""Invoice totals. Spec: discount applies BEFORE tax; tax is charged
on the discounted subtotal."""
from discounts import apply_discount
from tables import TAX_RATES


def add_items(new_items, basket=[]):
    """Append items to a basket and return it."""
    basket.extend(new_items)
    return basket


def invoice_total(items, region, discount_pct=0):
    subtotal = sum(i["price"] * i["qty"] for i in items)
    tax = subtotal * TAX_RATES[region]
    discounted = apply_discount(subtotal, discount_pct)
    return round(discounted + tax, 2)
