from django.db import migrations, models
from django.conf import settings
import django.core.validators
from decimal import Decimal

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkoutLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exercise', models.CharField(choices=[('Squat', 'Squat'), ('Deadlift', 'Deadlift'), ('Bench Press', 'Bench Press'), ('Overhead Press', 'Overhead Press'), ('Barbell Row', 'Barbell Row'), ('Pull-up', 'Pull-up'), ('Dip', 'Dip'), ('Leg Press', 'Leg Press'), ('Romanian Deadlift', 'Romanian Deadlift'), ('Lateral Raise', 'Lateral Raise')], max_length=50)),
                ('sets', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1, message='Sets must be a positive integer.')])),
                ('reps', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1, message='Reps must be a positive integer.')])),
                ('weight_kg', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0.01'), message='Weight must be greater than zero.')])),
                ('volume', models.DecimalField(decimal_places=2, editable=False, max_digits=10)),
                ('date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workouts', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='workoutlog',
            index=models.Index(fields=['user', 'date'], name='workouts_wo_user_id_449db1_idx'),
        ),
    ]
