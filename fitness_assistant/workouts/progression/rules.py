"""
Stage 1 - personalised rule-based progression.

Inputs per exercise: chronological list of Entry (top set per session).
Output: dict with recommendation PUSH / MAINTAIN / REDUCE, next weight, reasons.

Missed-workout handling
-----------------------
A gap in training is NEVER treated as failed performance:
  * days_since_last_workout / break_duration are tracked
  * the baseline is the last *successful* weight (not the last logged one if
    that one was a failure caused by return-from-break)
  * 0-6 days  -> normal evaluation
  * 7-13 days -> resume at last successful weight, then re-check ("RESUME")
  * 14-27 days-> resume at ~95 % of last successful weight (rounded)
  * 28+ days  -> resume at ~90 %
  In every break case the advice is to prove performance first; only if the
  resumed session is successful is a bump considered for the next session.
"""
import datetime
import statistics

PUSH, MAINTAIN, REDUCE = 'PUSH', 'MAINTAIN', 'REDUCE'

MIN_SESSIONS = 3          # sessions of one exercise needed for a prediction
TARGET_REPS = 8           # default "ready to progress" rep goal at working weight
REP_FLOOR = 5             # below this at same weight => struggling
RECENT_WINDOW = 4         # sessions used for trend
SHORT_BREAK_DAYS = 3      # up to this: totally normal, no flag at all
RESUME_BREAK_DAYS = 7     # from here: resume-and-check mode


def _round_to(x, step):
    return round(x / step) * step


def weight_step(weight, exercise_name=''):
    """Smallest sensible plate jump. Lower-body / big lifts jump more."""
    lower = any(k in exercise_name.lower() for k in
                ('squat', 'deadlift', 'leg press', 'rdl', 'hip thrust'))
    if weight < 20:
        return 1.0 if not lower else 2.5
    return 5.0 if lower and weight >= 100 else 2.5


def _fmt(w):
    return f"{w:g}"


def _is_success(entry, prev, goal_reps):
    """A session counts as successful if the lifter hit the rep goal, or
    matched/improved the previous session at the same-or-higher load."""
    if entry.reps >= goal_reps:
        return True
    if prev is None:
        return False
    if entry.weight > prev.weight and entry.reps >= max(REP_FLOOR, prev.reps - 2):
        return True
    if entry.weight == prev.weight and entry.reps >= prev.reps:
        return True
    return False


def break_info(entries, today):
    last = entries[-1].date
    days = (today - last).days
    # break_duration = the longest recent gap (between sessions or to today)
    gaps = [(b.date - a.date).days for a, b in zip(entries, entries[1:])]
    return {
        'days_since_last_workout': days,
        'break_duration': max(days, gaps[-1] if gaps else 0),
    }


def _last_successful(entries, goal_reps):
    last_ok = None
    for i, e in enumerate(entries):
        prev = entries[i - 1] if i else None
        if _is_success(e, prev, goal_reps):
            last_ok = e
    return last_ok


def _trend(entries):
    """Performance trend over recent sessions using estimated 1RM (Epley)."""
    recent = entries[-RECENT_WINDOW:]
    e1rm = [e.weight * (1 + min(e.reps, 12) / 30) for e in recent]
    if len(e1rm) < 2:
        return 'flat', 0.0
    change = (e1rm[-1] - e1rm[0]) / e1rm[0] * 100
    if change > 2:
        return 'up', change
    if change < -3:
        return 'down', change
    return 'flat', change


def _volume_trend(entries):
    recent = entries[-RECENT_WINDOW:]
    if len(recent) < 2:
        return 0.0
    base = statistics.mean(e.volume for e in recent[:-1])
    return (recent[-1].volume - base) / base * 100 if base else 0.0


def predict(name, entries, today=None, goal_reps=TARGET_REPS):
    today = today or datetime.date.today()
    last = entries[-1]
    info = break_info(entries, today)
    days = info['days_since_last_workout']
    trend, trend_pct = _trend(entries)
    vol_pct = _volume_trend(entries)
    ok = _last_successful(entries, goal_reps)
    base = ok.weight if ok else last.weight
    base_reps = ok.reps if ok else last.reps
    step = weight_step(base, name)

    result = {
        'exercise': name,
        'current_weight': last.weight, 'current_reps': last.reps,
        'last_successful_weight': base,
        'trend': trend, 'trend_pct': round(trend_pct, 1),
        'volume_trend_pct': round(vol_pct, 1),
        'sessions': len(entries),
        'last_date': last.date,
        'engine': 'rules',
        **info,
        'on_break': days >= RESUME_BREAK_DAYS,
    }

    # ---- Missed workouts: never a failure -------------------------------
    if days >= RESUME_BREAK_DAYS:
        if days >= 28:
            resume = _round_to(base * 0.90, 2.5)
        elif days >= 14:
            resume = _round_to(base * 0.95, 2.5)
        else:
            resume = base
        resume = max(resume, step)
        result.update(
            recommendation=MAINTAIN, next_weight=resume, next_reps=base_reps,
            headline='RESUME' if resume == base else 'RESUME LIGHTER',
            reasons=[
                f"{days}-day break - this is not counted as failed performance.",
                f"Last successful weight: {_fmt(base)} kg.",
                (f"Resume at {_fmt(resume)} kg and check how it feels."
                 if resume == base else
                 f"Ease back in at {_fmt(resume)} kg after a longer layoff."),
                f"If it goes well, consider {_fmt(resume + step)} kg next session.",
            ])
        return result

    # ---- Normal evaluation ---------------------------------------------
    prev = entries[-2] if len(entries) > 1 else None
    success = _is_success(last, prev, goal_reps)
    recent = entries[-3:]
    struggling = (last.reps < REP_FLOOR and prev is not None and last.weight >= prev.weight)
    two_bad = (len(recent) == 3 and trend == 'down' and not success)

    reasons = []
    if struggling or two_bad:
        rec = REDUCE
        nxt = _round_to(last.weight * 0.9, 2.5) if two_bad else last.weight
        nxt = max(nxt, step)
        if struggling and not two_bad:
            reasons.append(f"Only {last.reps} reps at {_fmt(last.weight)} kg - below the {REP_FLOOR}-rep floor.")
            reasons.append("Hold the weight (or drop slightly) and rebuild reps before adding load.")
        else:
            reasons.append("Performance has dropped across recent sessions.")
            reasons.append("Take a lighter week to recover, then build back up.")
        headline = 'RECOVER'
    elif success and last.reps >= goal_reps and trend != 'down':
        rec = PUSH
        nxt = last.weight + step
        reasons.append(f"You hit {last.reps} reps at {_fmt(last.weight)} kg (goal: {goal_reps}).")
        if trend == 'up':
            reasons.append(f"Strength trend is up ({trend_pct:+.1f}% est. 1RM).")
        if vol_pct > 5:
            reasons.append(f"Volume is climbing ({vol_pct:+.0f}%).")
        if days >= SHORT_BREAK_DAYS:
            reasons.append(f"{days} days since last session - short gap, no penalty applied.")
        headline = 'PUSH WEIGHT'
    else:
        rec = MAINTAIN
        nxt = last.weight
        reasons.append(f"{last.reps} reps at {_fmt(last.weight)} kg - aim for {goal_reps} before adding weight.")
        if trend == 'flat':
            reasons.append("Progress is steady; keep building reps at this weight.")
        if days >= SHORT_BREAK_DAYS:
            reasons.append(f"{days} days since last session - short gap, no penalty applied.")
        headline = 'MAINTAIN'

    result.update(
        recommendation=rec, next_weight=nxt,
        next_reps=last.reps if rec != PUSH else min(last.reps, goal_reps),
        headline=headline, reasons=reasons)
    return result
