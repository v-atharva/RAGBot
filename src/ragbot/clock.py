"""Injectable clock.

The reference course is historical, so timeline-aware features must read "now" from a
single place that can be virtualized via the ``MOCK_NOW`` environment variable. No module
should call ``datetime.now()`` directly — always go through :func:`now`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime


def now() -> datetime:
    """Return the current time, honoring the ``MOCK_NOW`` override when set.

    ``MOCK_NOW`` should be an ISO-8601 timestamp (e.g. ``2026-07-15T09:00:00``). When it is
    unset or empty, the real wall-clock time is returned.
    """
    raw = os.environ.get("MOCK_NOW", "").strip()
    if not raw:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
