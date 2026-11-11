"""Reminder scheduling."""
from datetime import datetime, timezone


def due_before(moment, deadline):
    """True if moment is before deadline. Inputs may be naive or
    timezone-aware datetimes."""
    return moment < deadline


def minutes_until(moment, now=None):
    now = now or datetime.now(timezone.utc)
    return int((moment - now).total_seconds() // 60)
