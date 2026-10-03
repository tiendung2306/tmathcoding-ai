from datetime import datetime, timezone


def utc_now() -> datetime:
    """MySQL DATETIME stores UTC without a timezone suffix across dashboard tables."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
