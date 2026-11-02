from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

class WorkoutLog(models.Model):
    EXERCISE_CHOICES = [
        ('Squat', 'Squat'),
        ('Deadlift', 'Deadlift'),
        ('Bench Press', 'Bench Press'),
        ('Overhead Press', 'Overhead Press'),
        ('Barbell Row', 'Barbell Row'),
        ('Pull-up', 'Pull-up'),
        ('Dip', 'Dip'),
        ('Leg Press', 'Leg Press'),
        ('Romanian Deadlift', 'Romanian Deadlift'),
        ('Lateral Raise', 'Lateral Raise'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workouts'
    )
    exercise = models.CharField(
        max_length=50, 
        choices=EXERCISE_CHOICES
    )
    sets = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Sets must be a positive integer.")]
    )
    reps = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Reps must be a positive integer.")]
    )
    weight_kg = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message="Weight must be greater than zero.")]
    )
    volume = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when this row was written by saving a WorkoutSession (keeps the
    # dashboard's volume totals in sync). Null for legacy / manual rows.
    session = models.ForeignKey(
        'WorkoutSession',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='mirror_logs',
    )

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def save(self, *args, **kwargs):
        # Auto-compute volume: sets * reps * weight_kg
        self.volume = Decimal(self.sets) * Decimal(self.reps) * Decimal(self.weight_kg)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.exercise} on {self.date}"


# ---------------------------------------------------------------------------
# Workout Split feature (manual + automated)
# ---------------------------------------------------------------------------
# A user picks how many days a week they train. The system auto-suggests a
# standard split (labels + a template of exercises per day) based on that
# number, and the user can freely rename days, add/remove/reorder exercises,
# and set target sets/reps per exercise - fully manual override on top of
# the automated suggestion.

# Standard day "types": muscle focus + suggested exercises (name, sets, reps).
SPLIT_DAY_TEMPLATES = {
    'Full Body': {
        'focus': 'Full Body',
        'exercises': [('Squat', 3, 8), ('Barbell Bench Press', 3, 8), ('Barbell Row', 3, 8),
                      ('Shoulder Press', 3, 10)],
    },
    'Upper': {
        'focus': 'Chest, Back, Shoulders, Arms',
        'exercises': [('Barbell Bench Press', 4, 8), ('Barbell Row', 4, 8), ('Shoulder Press', 3, 10),
                      ('Lat Pulldown', 3, 10), ('Bicep Curl', 3, 12)],
    },
    'Lower': {
        'focus': 'Legs, Glutes, Calves',
        'exercises': [('Squat', 4, 8), ('Romanian Deadlift', 3, 10), ('Leg Press', 3, 10),
                      ('Leg Extension', 3, 12), ('Calf Raise', 4, 15)],
    },
    'Push': {
        'focus': 'Chest, Shoulders, Triceps',
        'exercises': [('Barbell Bench Press', 4, 8), ('Incline Dumbbell Press', 3, 10),
                      ('Chest Fly Machine', 3, 12), ('Shoulder Press', 3, 10),
                      ('Tricep Pushdown', 3, 12)],
    },
    'Pull': {
        'focus': 'Back, Biceps',
        'exercises': [('Deadlift', 3, 5), ('Barbell Row', 4, 8), ('Lat Pulldown', 3, 10),
                      ('Bicep Curl', 3, 12), ('Face Pull', 3, 15)],
    },
    'Leg': {
        'focus': 'Legs, Glutes, Calves',
        'exercises': [('Squat', 4, 8), ('Leg Press', 3, 10), ('Romanian Deadlift', 3, 10),
                      ('Leg Extension', 3, 12), ('Calf Raise', 4, 15)],
    },
}

# Maps a number of training days/week (1-7) to an ordered list of day types.
# This is the "automated suggestion" - the user can edit every part of it.
SPLIT_SUGGESTIONS = {
    1: ['Full Body'],
    2: ['Upper', 'Lower'],
    3: ['Push', 'Pull', 'Leg'],
    4: ['Upper', 'Lower', 'Upper', 'Lower'],
    5: ['Push', 'Pull', 'Leg', 'Upper', 'Lower'],
    6: ['Push', 'Pull', 'Leg', 'Push', 'Pull', 'Leg'],
    7: ['Push', 'Pull', 'Leg', 'Upper', 'Lower', 'Full Body', 'Push'],
}


def generate_suggested_split(days_per_week):
    """
    Returns the automated suggestion for a given number of training days,
    e.g. for days_per_week=3:
    [
        {'label': 'Push Day', 'muscle_focus': 'Chest, Shoulders, Triceps',
         'exercises': [{'exercise': 'Barbell Bench Press', 'target_sets': 4, 'target_reps': 8}, ...]},
        ...
    ]
    Purely a suggestion - nothing is saved here.
    """
    days_per_week = max(1, min(7, int(days_per_week)))
    suggestion = []
    for day_type in SPLIT_SUGGESTIONS[days_per_week]:
        template = SPLIT_DAY_TEMPLATES[day_type]
        suggestion.append({
            'label': f'{day_type} Day',
            'muscle_focus': template['focus'],
            'exercises': [
                {'exercise': ex, 'target_sets': sets, 'target_reps': reps}
                for ex, sets, reps in template['exercises']
            ],
        })
    return suggestion


class WorkoutSplit(models.Model):
    """A user's saved training split (one active split per user)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workout_split'
    )
    days_per_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1, message="Days per week must be at least 1.")]
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.days_per_week}-day split"


class SplitDay(models.Model):
    """A single day within a split, e.g. 'Push Day'. Fully renameable."""
    split = models.ForeignKey(WorkoutSplit, on_delete=models.CASCADE, related_name='days')
    order = models.PositiveSmallIntegerField(default=1)
    label = models.CharField(max_length=50)
    muscle_focus = models.CharField(max_length=100, blank=True)  # e.g. "Chest, Shoulders, Triceps"

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.split.user.email} - Day {self.order}: {self.label}"


class SplitExercise(models.Model):
    """A planned exercise within a split day, with target sets/reps."""
    day = models.ForeignKey(SplitDay, on_delete=models.CASCADE, related_name='exercises')
    exercise = models.CharField(max_length=50)
    target_sets = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Target sets must be a positive integer.")]
    )
    target_reps = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Target reps must be a positive integer.")]
    )
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.day.label} - {self.exercise}"


# ---------------------------------------------------------------------------
# Workout sessions (the Workout Log page)
# ---------------------------------------------------------------------------
# One WorkoutSession = one saved workout on one date. It holds several
# exercises, and each exercise holds one row per set (reps + weight).

class Exercise(models.Model):
    """Exercise library. user=None means built-in; otherwise it is the user's own."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='custom_exercises',
    )
    name = models.CharField(max_length=50)
    muscle_group = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkoutSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    split_day = models.ForeignKey(SplitDay, null=True, blank=True, on_delete=models.SET_NULL, related_name='sessions')
    day_label = models.CharField(max_length=50, default='Custom Workout')  # survives split edits
    duration_min = models.PositiveIntegerField(default=0)
    calories = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='one_session_per_user_per_day'),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.day_label} on {self.date}"


class SessionExercise(models.Model):
    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='exercises')
    name = models.CharField(max_length=50)
    muscle_group = models.CharField(max_length=50, blank=True)
    rest_sec = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} ({self.session.date})"


class SessionSet(models.Model):
    exercise = models.ForeignKey(SessionExercise, on_delete=models.CASCADE, related_name='sets')
    set_number = models.PositiveSmallIntegerField()
    reps = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['set_number', 'id']

    def __str__(self):
        return f"S{self.set_number}: {self.reps} @ {self.weight}"
