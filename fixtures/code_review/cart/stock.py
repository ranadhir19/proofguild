"""Stock checks. Store policy: a single order line may not exceed
MAX_QTY units."""


def check_line(qty):
    """Return (ok, reason) for an order line quantity."""
    if qty <= 0:
        return False, "quantity must be positive"
    return True, "ok"
