"""Public entry point used by the dashboard card and the progression page."""
import datetime

from . import lstm, rules
from .history import load_history

INSUFFICIENT_MSG = ("Not enough workout history yet. Continue logging workouts "
                    "to unlock personalized predictions.")

EMOJI = {rules.PUSH: '🟢', rules.MAINTAIN: '🟡', rules.REDUCE: '🔴'}
LABEL = {rules.PUSH: 'PUSH', rules.MAINTAIN: 'MAINTAIN', rules.REDUCE: 'REDUCE / RECOVER'}


def _blend(res, entries):
    """Stage 2: let the LSTM refine the Stage-1 call when it is safe to do so."""
    if res['on_break']:                       # never judge performance after a break
        return res
    probs = lstm.predict_probs(entries)
    if not probs:
        return res
    best = max(probs, key=probs.get)
    res['lstm_probs'] = {k: round(v * 100) for k, v in probs.items()}
    res['confidence'] = round(probs[best] * 100)
    res['engine'] = 'lstm+rules'
    # Only change the call if the LSTM is clearly confident and disagrees by
    # at most one step (no jumping straight from PUSH to REDUCE).
    order = [rules.REDUCE, rules.MAINTAIN, rules.PUSH]
    if best != res['recommendation'] and probs[best] >= 0.75 \
            and abs(order.index(best) - order.index(res['recommendation'])) == 1:
        last_w = res['current_weight']
        step = rules.weight_step(last_w)
        res['recommendation'] = best
        res['next_weight'] = {rules.PUSH: last_w + step, rules.MAINTAIN: last_w,
                              rules.REDUCE: max(step, rules._round_to(last_w * 0.95, 2.5))}[best]
        res['headline'] = {rules.PUSH: 'PUSH WEIGHT', rules.MAINTAIN: 'MAINTAIN',
                           rules.REDUCE: 'RECOVER'}[best]
        res['reasons'].append(f"AI model ({probs[best] * 100:.0f}% confident) refined this call.")
    return res


def decorate(res):
    res['emoji'] = EMOJI[res['recommendation']]
    res['label'] = LABEL[res['recommendation']]
    return res


def get_progression_for_user(user, today=None, limit=None):
    """
    Returns {'ready': bool, 'message': str, 'items': [dict, ...]}.
    Exercises with fewer than rules.MIN_SESSIONS sessions are skipped; if none
    qualify, ready=False and the "not enough history" message is returned.
    Items are ordered by most recently trained.
    """
    today = today or datetime.date.today()
    items = []
    for data in load_history(user).values():
        entries = data['entries']
        if len(entries) < rules.MIN_SESSIONS:
            continue
        res = rules.predict(data['name'], entries, today=today)
        items.append(decorate(_blend(res, entries)))
    items.sort(key=lambda r: r['last_date'], reverse=True)
    if limit:
        items = items[:limit]
    if not items:
        return {'ready': False, 'message': INSUFFICIENT_MSG, 'items': []}
    return {'ready': True, 'message': '', 'items': items}
