from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

class NutritionLog(models.Model):
    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('snack', 'Snack'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='nutrition_logs'
    )
    food_name = models.CharField(max_length=255)
    calories = models.PositiveIntegerField(
        validators=[MinValueValidator(0, message="Calories cannot be negative.")]
    )
    protein_g = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.0'), message="Protein cannot be negative.")]
    )
    carbs_g = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.0'), message="Carbs cannot be negative.")]
    )
    fats_g = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.0'), message="Fats cannot be negative.")]
    )
    meal_type = models.CharField(
        max_length=20, 
        choices=MEAL_TYPE_CHOICES
    )
    date = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.food_name} ({self.meal_type}) on {self.date}"
