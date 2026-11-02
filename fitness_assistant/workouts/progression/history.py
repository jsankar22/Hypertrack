"""
Builds per-exercise training history for a user.

Primary source: SessionSet rows (one row per set, from the Workout Log page).
Fallback: legacy/manual WorkoutLog rows that are NOT mirrors of a session
(session is NULL), so nothing is counted twice.

Each history entry is one exercise on one date, summarised by its "top set"
(heaviest weight, then most reps) plus total volume.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from ..models import SessionSet, WorkoutLog


@dataclass
class Entry:
    date: object            # datetime.date
    weight: float           # top-set weight (kg)
    reps: int               # reps on the top set
    sets: int               # number of working sets at/near top weight
    volume: float           # total volume that day for this exercise
    best_reps_at_top: int   # best reps achieved at the top weight


def _summarise(date, rows):
    """rows: list of (reps, weight). Returns Entry or None."""
    rows = [(r, float(w)) for r, w in rows if w and float(w) > 0 and r > 0]
    if not rows:
        return None
    top_w = max(w for _, w in rows)
    at_top = [r for r, w in rows if w == top_w]
    volume = sum(r * w for r, w in rows)
    return Entry(
        date=date, weight=top_w, reps=max(at_top), sets=len(at_top),
        volume=volume, best_reps_at_top=max(at_top),
    )


def _key(name):
    return (name or '').strip().lower()


def load_history(user):
    """Returns {exercise_key: {'name': str, 'entries': [Entry, ...] sorted by date}}"""
    raw = defaultdict(lambda: defaultdict(list))   # key -> date -> [(reps, weight)]
    names = {}

    sets = (SessionSet.objects
            .filter(exercise__session__user=user)
            .select_related('exercise', 'exercise__session')
            .values_list('exercise__name', 'exercise__session__date', 'reps', 'weight'))
    for name, date, reps, weight in sets:
        k = _key(name)
        names.setdefault(k, name.strip())
        raw[k][date].append((reps, weight))

    legacy = (WorkoutLog.objects.filter(user=user, session__isnull=True)
              .values_list('exercise', 'date', 'sets', 'reps', 'weight_kg'))
    for name, date, n_sets, reps, weight in legacy:
        k = _key(name)
        names.setdefault(k, name.strip())
        raw[k][date].extend([(reps, weight)] * max(1, n_sets))

    out = {}
    for k, by_date in raw.items():
        entries = [e for e in (_summarise(d, rows) for d, rows in by_date.items()) if e]
        entries.sort(key=lambda e: e.date)
        if entries:
            out[k] = {'name': names[k], 'entries': entries}
    return out
