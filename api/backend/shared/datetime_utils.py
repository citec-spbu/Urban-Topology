"""Date and time helpers shared across backend modules."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)
