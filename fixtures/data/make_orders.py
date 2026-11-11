#!/usr/bin/env python3
"""Seeded generator for the data-analysis fixture.

240 plausible B2B sales orders, Jan-Jun 2026. Ground truth is NOT
stored here: the scorer recomputes every answer from the CSV with
its own code path, and the specialist's executed code is a third
path. The generator only has to make a CSV whose aggregates cannot
be eyeballed reliably.
"""
import csv, random, sys
from datetime import date, timedelta

PRODUCTS = {  # product -> base unit price
    "Aurora Lamp": 49.0, "Bison Chair": 189.0, "Cobalt Desk": 349.0,
    "Drift Shelf": 129.0, "Ember Kettle": 39.0, "Fjord Table": 499.0,
}
REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["Consumer", "SMB", "Enterprise"]
DISCOUNTS = [0, 0, 0, 5, 5, 10, 10, 15, 20, 25, 30]


def main(path):
    rng = random.Random(20261110)
    start = date(2026, 1, 1)
    rows = []
    for i in range(240):
        day = start + timedelta(days=rng.randrange(181))
        product = rng.choice(list(PRODUCTS))
        price = round(PRODUCTS[product] * rng.uniform(0.92, 1.08), 2)
        rows.append({
            "order_id": f"ORD-{1001 + i}",
            "date": day.isoformat(),
            "region": rng.choice(REGIONS),
            "segment": rng.choice(SEGMENTS),
            "product": product,
            "units": rng.randint(1, 40),
            "unit_price": f"{price:.2f}",
            "discount_pct": rng.choice(DISCOUNTS),
        })
    rows.sort(key=lambda r: r["date"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main(sys.argv[1])
