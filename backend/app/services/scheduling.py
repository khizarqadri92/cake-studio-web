"""Delivery/pickup scheduling (pure). All datetimes are naive *store-local* time."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class SlotSpec:
    id: int
    start: time
    end: time
    max_orders: int
    weekdays: frozenset[int]  # 0=Mon..6=Sun
    is_active: bool = True


@dataclass(frozen=True)
class SlotAvailability:
    slot_id: int
    start: time
    end: time
    remaining: int


class ScheduleError(ValueError):
    pass


def earliest_ready(now: datetime, prep_hours: int, min_prep_hours: int = 0) -> datetime:
    return now + timedelta(hours=max(prep_hours, min_prep_hours))


def available_slots(day: date, now: datetime, prep_hours: int, slots: list[SlotSpec], blocked: set[date],
                    booked: dict[int, int], *, min_prep_hours: int = 0, max_days_ahead: int = 90) -> list[SlotAvailability]:
    """Slots on `day` that are active, on an allowed weekday, not full, and start after the order can be ready."""
    if day in blocked or day < now.date() or (day - now.date()).days > max_days_ahead:
        return []
    ready = earliest_ready(now, prep_hours, min_prep_hours)
    out = []
    for s in sorted(slots, key=lambda s: s.start):
        if not s.is_active or day.weekday() not in s.weekdays:
            continue
        if datetime.combine(day, s.start) < ready:
            continue
        remaining = s.max_orders - booked.get(s.id, 0)
        if remaining > 0:
            out.append(SlotAvailability(s.id, s.start, s.end, remaining))
    return out


def validate_choice(slot_id: int, **kw) -> SlotAvailability:
    """kw are the arguments of `available_slots` (day, now, prep_hours, slots, blocked, booked, ...)."""
    for a in available_slots(**kw):
        if a.slot_id == slot_id:
            return a
    raise ScheduleError("That date and time slot is no longer available")
