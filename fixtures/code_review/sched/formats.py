"""Display formats (reviewed, known clean)."""

DAY_FMT = "%a %d %b"
TIME_FMT = "%H:%M"


def fmt_day(d):
    return d.strftime(DAY_FMT)
