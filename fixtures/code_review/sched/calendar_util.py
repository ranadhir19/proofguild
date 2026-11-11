"""Date parsing helpers."""
from datetime import datetime


def parse_day(text):
    """Parse 'YYYY-MM-DD' to a date. Returns None on bad input."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except:
        pass
