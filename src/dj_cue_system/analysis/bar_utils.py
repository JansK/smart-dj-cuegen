import bisect


def timestamp_to_bar(timestamp: float, downbeats: list[float]) -> int:
    """Return 0-indexed bar number for a timestamp (clamped to valid range)."""
    idx = bisect.bisect_right(downbeats, timestamp) - 1
    return max(0, min(idx, len(downbeats) - 1))


def bar_to_timestamp(bar: int, downbeats: list[float]) -> float:
    """Return seconds for start of bar (0-indexed, clamped)."""
    clamped = max(0, min(bar, len(downbeats) - 1))
    return downbeats[clamped]


def snap_to_bar(timestamp: float, downbeats: list[float]) -> float:
    """Snap timestamp to the nearest downbeat."""
    if not downbeats:
        return timestamp
    return min(downbeats, key=lambda db: abs(db - timestamp))
