from django.contrib import admin
from .models import NutritionLog

class NutritionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'food_name', 'calories', 'protein_g', 'carbs_g', 'fats_g', 'meal_type', 'date']
    list_filter = ['meal_type', 'date', 'user']
    search_fields = ['user__email', 'food_name']

admin.site.register(NutritionLog, NutritionLogAdmin)
