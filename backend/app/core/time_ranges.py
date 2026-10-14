from datetime import datetime, timedelta


def get_cutoff_date(time_range: str, reference_now: datetime) -> datetime | None:
    """Return the inclusive start of a dashboard analytics window."""
    days = {"1d": 1, "7d": 7, "30d": 30, "1y": 365}.get(time_range)
    return reference_now - timedelta(days=days) if days is not None else None
