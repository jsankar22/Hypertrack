"""
Stage 2 - LSTM progression model (optional, PyTorch).

Design
------
* Input  : last SEQ_LEN sessions of ONE exercise, each as a feature vector
           [weight_rel, reps, volume_rel, e1rm_rel, gap_days]  (relative to the
           first session in the window, so it works for any lifter/exercise).
* Output : probabilities for [PUSH, MAINTAIN, REDUCE].
* Training: `python manage.py train_progression_lstm`. Labels come from the
           Stage-1 rule engine (weak supervision) on real windows from all
           users + synthetic lifters, so the LSTM learns the rule logic and
           can then generalise to noisy, real-world patterns.
* Safety : if torch or the trained weights are missing, or the user has fewer
           than LSTM_MIN_SESSIONS sessions for an exercise, the app silently
           uses Stage 1. The LSTM is NEVER used while the user is on a break
           (>= 7 days) - missed workouts are never judged as performance.
"""
import datetime
import os
import random

from . import rules

try:                                    # torch is optional
    import torch
    import torch.nn as nn
    TORCH_OK = True
except Exception:                       # pragma: no cover
    torch = nn = None
    TORCH_OK = False

SEQ_LEN = 6
N_FEATURES = 5
LSTM_MIN_SESSIONS = 6
CLASSES = [rules.PUSH, rules.MAINTAIN, rules.REDUCE]
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'weights', 'progression_lstm.pt')

_model_cache = {'model': None, 'loaded': False}


def featurize(entries):
    """entries: list[Entry] (len >= 1). Returns SEQ_LEN x N_FEATURES list (left-padded)."""
    window = entries[-SEQ_LEN:]
    w0 = window[0].weight or 1.0
    v0 = window[0].volume or 1.0
    e0 = w0 * (1 + min(window[0].reps, 12) / 30)
    rows, prev_date = [], None
    for e in window:
        gap = (e.date - prev_date).days if prev_date else 0
        prev_date = e.date
        e1rm = e.weight * (1 + min(e.reps, 12) / 30)
        rows.append([e.weight / w0, e.reps / 10.0, e.volume / v0, e1rm / e0,
                     min(gap, 28) / 14.0])
    while len(rows) < SEQ_LEN:
        rows.insert(0, rows[0][:])
    return rows


if TORCH_OK:
    class ProgressionLSTM(nn.Module):
        def __init__(self, hidden=32):
            super().__init__()
            self.lstm = nn.LSTM(N_FEATURES, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 3))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :])


def load_model():
    if _model_cache['loaded']:
        return _model_cache['model']
    _model_cache['loaded'] = True
    if not TORCH_OK or not os.path.exists(MODEL_PATH):
        return None
    try:
        m = ProgressionLSTM()
        m.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
        m.eval()
        _model_cache['model'] = m
    except Exception:
        _model_cache['model'] = None
    return _model_cache['model']


def lstm_available():
    return load_model() is not None


def predict_probs(entries):
    """Returns {'PUSH': p, 'MAINTAIN': p, 'REDUCE': p} or None if unavailable."""
    model = load_model()
    if model is None or len(entries) < LSTM_MIN_SESSIONS:
        return None
    x = torch.tensor([featurize(entries)], dtype=torch.float32)
    with torch.no_grad():
        p = torch.softmax(model(x), dim=-1)[0].tolist()
    return dict(zip(CLASSES, p))


# ---------------------------------------------------------------- training --

def synthetic_lifter(n_sessions=14, seed=None):
    """Generates a plausible noisy lifter history as a list of Entry."""
    from .history import Entry
    rnd = random.Random(seed)
    w = rnd.choice([20, 30, 40, 50, 60, 80, 100])
    skill = rnd.uniform(0.0, 1.0)           # how well they respond to progression
    date = datetime.date(2025, 1, 1)
    entries = []
    for _ in range(n_sessions):
        date += datetime.timedelta(days=rnd.choice([2, 3, 3, 4, 5, 7]))
        base = 8 if rnd.random() < 0.4 + 0.4 * skill else rnd.randint(4, 8)
        reps = max(1, min(12, base + rnd.choice([-2, -1, 0, 0, 1, 2])))
        entries.append(Entry(date=date, weight=float(w), reps=reps, sets=3,
                             volume=float(w * reps * 3), best_reps_at_top=reps))
        if reps >= 8 and rnd.random() < 0.8:
            w += rules.weight_step(w)
        elif reps <= 4 and rnd.random() < 0.3:
            w = max(5, w - 2.5)
    return entries


def build_dataset(user_histories, n_synthetic=1500, seed=7):
    """Windows ending at each session i (i >= LSTM_MIN_SESSIONS-1), labelled by rules."""
    X, y = [], []
    sources = list(user_histories)
    sources += [synthetic_lifter(random.Random(seed + i).randint(8, 20), seed + i)
                for i in range(n_synthetic)]
    for entries in sources:
        for end in range(LSTM_MIN_SESSIONS, len(entries) + 1):
            window = entries[:end]
            today = window[-1].date + datetime.timedelta(days=2)   # normal gap only
            label = rules.predict('x', window, today=today)['recommendation']
            X.append(featurize(window))
            y.append(CLASSES.index(label))
    return X, y


def train(user_histories, epochs=25, lr=3e-3, seed=7, log=print):
    if not TORCH_OK:
        raise RuntimeError("PyTorch is not installed. Run: pip install torch")
    torch.manual_seed(seed)
    X, y = build_dataset(user_histories, seed=seed)
    n = len(X)
    idx = list(range(n))
    random.Random(seed).shuffle(idx)
    cut = int(n * 0.85)
    tr, va = idx[:cut], idx[cut:]
    Xt = torch.tensor(X, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.long)

    model = ProgressionLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    for ep in range(epochs):
        model.train()
        random.shuffle(tr)
        for i in range(0, len(tr), 64):
            b = tr[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(model(Xt[b]), yt[b])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            acc = (model(Xt[va]).argmax(1) == yt[va]).float().mean().item()
        if ep % 5 == 0 or ep == epochs - 1:
            log(f"epoch {ep + 1:>2}/{epochs}  val_acc={acc:.3f}")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    _model_cache.update(model=None, loaded=False)
    return acc, n
