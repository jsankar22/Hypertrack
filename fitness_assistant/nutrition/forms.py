from django import forms
from decimal import Decimal

class NutritionLogCreateForm(forms.Form):
    food_name = forms.CharField(max_length=255)
    calories_per_100g = forms.IntegerField(min_value=0)
    protein_per_100g = forms.DecimalField(min_value=Decimal('0.0'), max_digits=6, decimal_places=2)
    carbs_per_100g = forms.DecimalField(min_value=Decimal('0.0'), max_digits=6, decimal_places=2)
    fats_per_100g = forms.DecimalField(min_value=Decimal('0.0'), max_digits=6, decimal_places=2)
    portion_grams = forms.DecimalField(min_value=Decimal('0.01'), max_digits=6, decimal_places=2)
    meal_type = forms.ChoiceField(choices=[
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('snack', 'Snack'),
    ])
    date = forms.DateField()
