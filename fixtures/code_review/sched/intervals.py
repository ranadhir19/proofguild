"""Interval arithmetic. Spec: intervals that merely TOUCH (one ends
exactly when the other starts) count as overlapping for room
bookings, so back-to-back meetings are flagged for a buffer check."""


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end
