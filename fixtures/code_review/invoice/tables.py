"""Regional tax rates. Maintained by finance; do not edit casually."""

TAX_RATES = {
    "north": 0.07,
    "south": 0.06,
    "east": 0.08,
    "west": 0.05,
}


def rate_for(region):
    return TAX_RATES[region.lower()]
