from django.db import migrations

from workouts.defaults import DEFAULT_EXERCISES


def seed(apps, schema_editor):
    Exercise = apps.get_model('workouts', 'Exercise')
    existing = set(Exercise.objects.filter(user__isnull=True).values_list('name', flat=True))
    Exercise.objects.bulk_create([
        Exercise(name=name, muscle_group=group)
        for name, group in DEFAULT_EXERCISES if name not in existing
    ])


def unseed(apps, schema_editor):
    Exercise = apps.get_model('workouts', 'Exercise')
    Exercise.objects.filter(user__isnull=True, name__in=[n for n, _ in DEFAULT_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workouts', '0003_workout_sessions'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
