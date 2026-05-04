from __future__ import annotations

from datetime import date, datetime, time, timedelta

DAY_TO_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
INDEX_TO_DAY = {v: k for k, v in DAY_TO_INDEX.items()}


def ceil_to_slot(dt: datetime, slot_minutes: int = 30) -> datetime:
    discard = timedelta(minutes=dt.minute % slot_minutes, seconds=dt.second, microseconds=dt.microsecond)
    dt = dt - discard
    if discard:
        dt += timedelta(minutes=slot_minutes)
    return dt.replace(second=0, microsecond=0)


def floor_to_slot(dt: datetime, slot_minutes: int = 30) -> datetime:
    discard = timedelta(minutes=dt.minute % slot_minutes, seconds=dt.second, microseconds=dt.microsecond)
    return (dt - discard).replace(second=0, microsecond=0)


def combine_day_time(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def iter_dates(start_date: date, days: int):
    for i in range(days):
        yield start_date + timedelta(days=i)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def subtract_interval(
    interval: tuple[datetime, datetime],
    blocker: tuple[datetime, datetime],
) -> list[tuple[datetime, datetime]]:
    start, end = interval
    b_start, b_end = blocker
    if not overlaps(start, end, b_start, b_end):
        return [(start, end)]
    pieces: list[tuple[datetime, datetime]] = []
    if start < b_start:
        pieces.append((start, min(b_start, end)))
    if b_end < end:
        pieces.append((max(b_end, start), end))
    return [(s, e) for s, e in pieces if e > s]


def subtract_many(
    intervals: list[tuple[datetime, datetime]],
    blockers: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    result = intervals[:]
    for blocker in blockers:
        next_result: list[tuple[datetime, datetime]] = []
        for interval in result:
            next_result.extend(subtract_interval(interval, blocker))
        result = next_result
    return result
