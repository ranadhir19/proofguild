"""Money helpers (reviewed, known clean)."""


def to_cents(amount):
    return int(round(amount * 100))


def to_dollars(cents):
    return cents / 100.0
