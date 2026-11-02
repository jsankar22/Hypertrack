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
            name='NutritionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('food_name', models.CharField(max_length=255)),
                ('calories', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(0, message='Calories cannot be negative.')])),
                ('protein_g', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0.0'), message='Protein cannot be negative.')])),
                ('carbs_g', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0.0'), message='Carbs cannot be negative.')])),
                ('fats_g', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0.0'), message='Fats cannot be negative.')])),
                ('meal_type', models.CharField(choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner'), ('snack', 'Snack')], max_length=20)),
                ('date', models.DateField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nutrition_logs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='nutritionlog',
            index=models.Index(fields=['user', 'date'], name='nutrition_n_user_id_8dfad6_idx'),
        ),
    ]
