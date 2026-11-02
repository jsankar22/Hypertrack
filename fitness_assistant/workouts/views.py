import json
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import SplitDaysForm
from .models import (
    Exercise, SessionExercise, SessionSet, SplitDay, SplitExercise,
    WorkoutLog, WorkoutSession, WorkoutSplit, generate_suggested_split,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _library(user):
    """Exercise library as {lowercase name: {'name', 'group'}}. User's own entries win."""
    rows = (
        Exercise.objects.filter(Q(user__isnull=True) | Q(user=user))
        .order_by(F('user_id').asc(nulls_first=True))
    )
    return {r.name.lower(): {'name': r.name, 'group': r.muscle_group} for r in rows}


def _get_split(user):
    return WorkoutSplit.objects.filter(user=user).prefetch_related('days__exercises').first()


def _focus(day, lib):
    """Muscle chips for a split day: its own muscle_focus, else derived from its exercises."""
    if day.muscle_focus.strip():
        return [g.strip() for g in day.muscle_focus.split(',') if g.strip()]
    groups = []
    for ex in day.exercises.all():
        g = lib.get(ex.exercise.lower(), {}).get('group')
        if g and g not in groups:
            groups.append(g)
    return groups


def _next_day(user, days, date):
    """Default day for a date: the one after the last trained split day, else the first."""
    last = (
        WorkoutSession.objects
        .filter(user=user, date__lt=date, split_day__in=days)
        .order_by('-date').first()
    )
    if last:
        ids = [d.id for d in days]
        return days[(ids.index(last.split_day_id) + 1) % len(days)]
    return days[0]


def _regenerate_split(user, days_per_week):
    """Replace the user's split with a freshly suggested one."""
    suggestion = generate_suggested_split(days_per_week)
    with transaction.atomic():
        split = WorkoutSplit.objects.filter(user=user).first()
        if split:
            split.days.all().delete()
            split.days_per_week = days_per_week
            split.save()
        else:
            split = WorkoutSplit.objects.create(user=user, days_per_week=days_per_week)
        for index, day_data in enumerate(suggestion, start=1):
            day = SplitDay.objects.create(
                split=split, order=index,
                label=day_data['label'], muscle_focus=day_data['muscle_focus'],
            )
            SplitExercise.objects.bulk_create([
                SplitExercise(
                    day=day, exercise=ex['exercise'], order=i,
                    target_sets=ex['target_sets'], target_reps=ex['target_reps'],
                )
                for i, ex in enumerate(day_data['exercises'], start=1)
            ])


def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        raise ValueError('Invalid request.')
    if not isinstance(data, dict):
        raise ValueError('Invalid request.')
    return data


def _int(value, lo, hi, label):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a whole number.')
    if not lo <= n <= hi:
        raise ValueError(f'{label} must be between {lo} and {hi}.')
    return n


def _dec(value, lo, hi, label):
    if value in (None, ''):
        return Decimal('0.00')
    try:
        d = Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label} must be a number.')
    if not Decimal(lo) <= d <= Decimal(hi):
        raise ValueError(f'{label} must be between {lo} and {hi}.')
    return d


# ---------------------------------------------------------------------------
# Workout Log (today's workout)
# ---------------------------------------------------------------------------

@login_required
def workout_add_view(request):
    """Old 'Log workout' URL - the Workout Log page replaces it."""
    return redirect('workout_list')


@login_required
def workout_log_view(request):
    user = request.user
    date = parse_date(request.GET.get('date', '')) or timezone.localdate()
    split = _get_split(user)
    days = list(split.days.all()) if split else []
    lib = _library(user)
    session = (
        WorkoutSession.objects.filter(user=user, date=date)
        .prefetch_related('exercises__sets').first()
    )

    # Which day is selected?
    day_param = request.GET.get('day', '')
    selected_day, custom = None, False
    if day_param == 'custom':
        custom = True
    elif day_param.isdigit():
        selected_day = next((d for d in days if d.id == int(day_param)), None)
    elif session:
        selected_day = next((d for d in days if d.id == session.split_day_id), None)
        custom = selected_day is None
    if selected_day is None and not custom and days:
        selected_day = _next_day(user, days, date)

    use_session = bool(session) and (
        (selected_day is not None and session.split_day_id == selected_day.id)
        or (selected_day is None and session.split_day_id is None)
    )

    if use_session:
        exercises = [
            {
                'name': e.name, 'group': e.muscle_group, 'rest': e.rest_sec,
                'sets': [{'reps': s.reps, 'weight': float(s.weight)} for s in e.sets.all()],
            }
            for e in session.exercises.all()
        ]
        notes, duration, calories = session.notes, session.duration_min, session.calories
    else:
        exercises = [
            {
                'name': ex.exercise,
                'group': lib.get(ex.exercise.lower(), {}).get('group', ''),
                'rest': None,
                'sets': [],
                'target': {'sets': ex.target_sets, 'reps': ex.target_reps},
            }
            for ex in (selected_day.exercises.all() if selected_day else [])
        ]
        notes, duration, calories = '', None, None

    state = {
        'date': date.isoformat(),
        'dayId': selected_day.id if selected_day else None,
        'dayLabel': selected_day.label if selected_day else 'Custom Workout',
        'exercises': exercises,
        'notes': notes,
        'duration': duration,
        'calories': calories,
        'hasSession': use_session,
        'hasSplit': bool(split),
        'library': sorted(lib.values(), key=lambda x: x['name']),
        'userWeight': float(user.weight_kg) if getattr(user, 'weight_kg', None) else 70.0,
        'saveUrl': reverse('workout_session_save'),
    }

    return render(request, 'workouts/log.html', {
        'active_tab': 'workouts',
        'date': date,
        'today': timezone.localdate(),
        'split': split,
        'days': days,
        'selected_day': selected_day,
        'custom': custom or selected_day is None,
        'focus': _focus(selected_day, lib) if selected_day else [],
        'plan': list(selected_day.exercises.all()) if selected_day else [],
        'day_options': range(1, 8),
        'state': state,
    })


def _clean_session(data):
    date = parse_date(str(data.get('date', '')))
    if not date:
        raise ValueError('Choose a valid date.')

    exercises = []
    for ex in (data.get('exercises') or [])[:40]:
        name = str(ex.get('name', '')).strip()[:50]
        if not name:
            continue
        sets = []
        for s in (ex.get('sets') or [])[:30]:
            sets.append({
                'reps': _int(s.get('reps'), 1, 1000, f'Reps for {name}'),
                'weight': _dec(s.get('weight'), 0, 9999, f'Weight for {name}'),
            })
        if not sets:
            continue  # planned but not performed - skipped
        rest = ex.get('rest')
        rest = None if rest in (None, '') else _int(rest, 0, 3600, f'Rest for {name}')
        exercises.append({
            'name': name,
            'group': str(ex.get('group', '')).strip()[:50],
            'rest': rest,
            'sets': sets,
        })
    if not exercises:
        raise ValueError('Add at least one exercise with sets before saving.')

    return {
        'date': date,
        'exercises': exercises,
        'notes': str(data.get('notes', ''))[:2000],
        'duration': _int(data.get('duration') or 0, 0, 1440, 'Duration'),
        'calories': _int(data.get('calories') or 0, 0, 20000, 'Calories'),
        'day_id': data.get('dayId'),
    }


@login_required
@require_POST
def session_save_view(request):
    user = request.user
    try:
        clean = _clean_session(_json_body(request))
    except (ValueError, TypeError, AttributeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Invalid request.'
        return JsonResponse({'ok': False, 'error': message}, status=400)

    day = None
    if clean['day_id']:
        try:
            day = SplitDay.objects.filter(pk=int(clean['day_id']), split__user=user).first()
        except (TypeError, ValueError):
            day = None

    lib = _library(user)
    with transaction.atomic():
        session, created = WorkoutSession.objects.update_or_create(
            user=user, date=clean['date'],
            defaults={
                'split_day': day,
                'day_label': day.label if day else 'Custom Workout',
                'duration_min': clean['duration'],
                'calories': clean['calories'],
                'notes': clean['notes'],
            },
        )
        # Re-saving a date replaces what was there before.
        session.exercises.all().delete()
        session.mirror_logs.all().delete()

        for order, ex in enumerate(clean['exercises'], start=1):
            se = SessionExercise.objects.create(
                session=session, name=ex['name'], muscle_group=ex['group'],
                rest_sec=ex['rest'], order=order,
            )
            SessionSet.objects.bulk_create([
                SessionSet(exercise=se, set_number=i, reps=s['reps'], weight=s['weight'])
                for i, s in enumerate(ex['sets'], start=1)
            ])

            # Mirror into WorkoutLog (grouped by identical reps/weight) so the
            # dashboard's weekly volume and recent workouts keep working.
            groups = OrderedDict()
            for s in ex['sets']:
                groups[(s['reps'], s['weight'])] = groups.get((s['reps'], s['weight']), 0) + 1
            for (reps, weight), count in groups.items():
                WorkoutLog.objects.create(
                    user=user, exercise=ex['name'], sets=count, reps=reps,
                    weight_kg=weight, date=clean['date'], session=session,
                )

            # New exercise names join the user's library.
            if ex['name'].lower() not in lib:
                Exercise.objects.create(user=user, name=ex['name'], muscle_group=ex['group'])
                lib[ex['name'].lower()] = {'name': ex['name'], 'group': ex['group']}

    messages.success(request, 'Workout saved.')
    return JsonResponse({'ok': True, 'redirect': reverse('workout_history')})


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@login_required
def history_view(request):
    sessions = (
        WorkoutSession.objects.filter(user=request.user)
        .prefetch_related('exercises__sets')
    )
    rows = []
    for s in sessions:
        exs = list(s.exercises.all())
        rows.append({
            'session': s,
            'count': len(exs),
            'names': ', '.join(e.name for e in exs),
            'sets': sum(len(e.sets.all()) for e in exs),
        })
    return render(request, 'workouts/history.html', {'rows': rows, 'active_tab': 'workouts'})


@login_required
@require_POST
def session_delete_view(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    session.delete()  # mirrored WorkoutLog rows are removed by cascade
    messages.success(request, 'Workout deleted.')
    return redirect('workout_history')


# ---------------------------------------------------------------------------
# My Splits
# ---------------------------------------------------------------------------

@login_required
def split_view(request):
    split = _get_split(request.user)
    lib = _library(request.user)
    days = []
    if split:
        for day in split.days.all():
            day.focus_list = _focus(day, lib)
            days.append(day)
    return render(request, 'workouts/splits.html', {
        'split': split,
        'days': days,
        'day_options': range(1, 8),
        'active_tab': 'workouts',
    })


@login_required
@require_POST
def split_generate_view(request):
    """Generate a suggested split for N days/week (replaces the current split)."""
    target = 'workout_list' if request.POST.get('next') == 'log' else 'workout_split'
    form = SplitDaysForm(request.POST)
    if form.is_valid():
        days_per_week = form.cleaned_data['days_per_week']
        _regenerate_split(request.user, days_per_week)
        messages.success(request, f'Generated a suggested {days_per_week}-day split. Customize it any time.')
    else:
        messages.error(request, 'Choose between 1 and 7 training days.')
    return redirect(target)


@login_required
def split_day_editor_view(request, pk=None):
    user = request.user
    day = get_object_or_404(SplitDay, pk=pk, split__user=user) if pk else None
    lib = _library(user)
    state = {
        'id': day.id if day else None,
        'label': day.label if day else '',
        'muscleFocus': day.muscle_focus if day else '',
        'exercises': [
            {'exercise': ex.exercise, 'sets': ex.target_sets, 'reps': ex.target_reps}
            for ex in (day.exercises.all() if day else [])
        ],
        'library': sorted(lib.values(), key=lambda x: x['name']),
        'saveUrl': reverse('workout_split_day_save'),
        'backUrl': reverse('workout_split'),
    }
    return render(request, 'workouts/split_form.html', {
        'day': day, 'state': state, 'active_tab': 'workouts',
    })


@login_required
@require_POST
def split_day_save_view(request):
    user = request.user
    try:
        data = _json_body(request)
        label = str(data.get('label', '')).strip()[:50]
        if not label:
            raise ValueError('Give this day a name.')
        focus = str(data.get('muscleFocus', '')).strip()[:100]
        exercises = []
        for ex in (data.get('exercises') or [])[:40]:
            name = str(ex.get('exercise', '')).strip()[:50]
            if not name:
                continue
            exercises.append({
                'exercise': name,
                'sets': _int(ex.get('sets'), 1, 50, f'Sets for {name}'),
                'reps': _int(ex.get('reps'), 1, 1000, f'Reps for {name}'),
            })
    except (ValueError, TypeError, AttributeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Invalid request.'
        return JsonResponse({'ok': False, 'error': message}, status=400)

    pk = data.get('id')
    with transaction.atomic():
        if pk:
            day = get_object_or_404(SplitDay, pk=pk, split__user=user)
            day.label, day.muscle_focus = label, focus
            day.save()
            day.exercises.all().delete()
        else:
            split, _ = WorkoutSplit.objects.get_or_create(user=user, defaults={'days_per_week': 1})
            next_order = (split.days.aggregate(m=Max('order'))['m'] or 0) + 1
            day = SplitDay.objects.create(split=split, order=next_order, label=label, muscle_focus=focus)
            split.days_per_week = min(7, max(split.days_per_week, split.days.count()))
            split.save()
        SplitExercise.objects.bulk_create([
            SplitExercise(
                day=day, exercise=ex['exercise'], target_sets=ex['sets'],
                target_reps=ex['reps'], order=i,
            )
            for i, ex in enumerate(exercises, start=1)
        ])

    messages.success(request, f'"{day.label}" saved.')
    return JsonResponse({'ok': True, 'redirect': reverse('workout_split')})


@login_required
@require_POST
def split_day_delete_view(request, pk):
    day = get_object_or_404(SplitDay, pk=pk, split__user=request.user)
    day.delete()
    messages.success(request, 'Day removed from your split.')
    return redirect('workout_split')


@login_required
@require_POST
def split_reset_view(request):
    """Delete the entire saved split so the user can start over."""
    WorkoutSplit.objects.filter(user=request.user).delete()
    messages.success(request, 'Split deleted. Generate a new one whenever you like.')
    return redirect('workout_split')


# ---------------------------------------------------------------------------
# Progression prediction
# ---------------------------------------------------------------------------

@login_required
def progression_view(request):
    from django.utils import timezone
    from .progression import get_progression_for_user
    data = get_progression_for_user(request.user, today=timezone.localdate())
    return render(request, 'workouts/progression.html', {'prog': data, 'active_tab': 'workouts'})
