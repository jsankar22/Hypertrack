import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from .models import NutritionLog
from .forms import NutritionLogCreateForm
from .services import search_usda_foods

@login_required
def nutrition_daily_view(request):
    user = request.user
    date_str = request.GET.get('date', '')
    
    if date_str:
        try:
            active_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            active_date = timezone.localdate()
    else:
        active_date = timezone.localdate()
        
    logs = NutritionLog.objects.filter(user=user, date=active_date)
    
    # Calculate daily targets dynamically
    weight = float(user.weight_kg) if user.weight_kg else 70.0
    if user.goal == 'lose_weight':
        caloric_goal = int(weight * 25)
        protein_goal = int(weight * 2.0)
        carbs_goal = int(weight * 2.2)
        fats_goal = int(weight * 0.7)
    elif user.goal == 'gain_muscle':
        caloric_goal = int(weight * 38)
        protein_goal = int(weight * 2.2)
        carbs_goal = int(weight * 4.5)
        fats_goal = int(weight * 1.0)
    else:
        caloric_goal = int(weight * 32)
        protein_goal = int(weight * 1.8)
        carbs_goal = int(weight * 3.5)
        fats_goal = int(weight * 0.9)
        
    # Group meals by type and sum aggregates
    grouped_meals = {
        'breakfast': logs.filter(meal_type='breakfast'),
        'lunch': logs.filter(meal_type='lunch'),
        'dinner': logs.filter(meal_type='dinner'),
        'snack': logs.filter(meal_type='snack'),
    }
    
    totals = logs.aggregate(
        total_calories=Sum('calories'),
        total_protein=Sum('protein_g'),
        total_carbs=Sum('carbs_g'),
        total_fats=Sum('fats_g')
    )
    
    total_calories = totals['total_calories'] or 0
    total_protein = float(totals['total_protein'] or 0.0)
    total_carbs = float(totals['total_carbs'] or 0.0)
    total_fats = float(totals['total_fats'] or 0.0)
    
    # Percentages for progress bars (capped at 100)
    calorie_percent = min(int((total_calories / caloric_goal) * 100), 100) if caloric_goal > 0 else 0
    protein_percent = min(int((total_protein / protein_goal) * 100), 100) if protein_goal > 0 else 0
    carbs_percent = min(int((total_carbs / carbs_goal) * 100), 100) if carbs_goal > 0 else 0
    fats_percent = min(int((total_fats / fats_goal) * 100), 100) if fats_goal > 0 else 0
    
    context = {
        'active_date': active_date,
        'prev_date': active_date - datetime.timedelta(days=1),
        'next_date': active_date + datetime.timedelta(days=1),
        'grouped_meals': grouped_meals,
        'total_calories': total_calories,
        'total_protein': total_protein,
        'total_carbs': total_carbs,
        'total_fats': total_fats,
        'caloric_goal': caloric_goal,
        'protein_goal': protein_goal,
        'carbs_goal': carbs_goal,
        'fats_goal': fats_goal,
        'calorie_percent': calorie_percent,
        'protein_percent': protein_percent,
        'carbs_percent': carbs_percent,
        'fats_percent': fats_percent,
        'active_tab': 'nutrition',
    }
    
    return render(request, 'nutrition/daily.html', context)


@login_required
def nutrition_search_api(request):
    query = request.GET.get('q', '')
    results = search_usda_foods(query)
    return JsonResponse(results, safe=False)


@login_required
def nutrition_log_create(request):
    if request.method == 'POST':
        form = NutritionLogCreateForm(request.POST)
        if form.is_valid():
            portion = form.cleaned_data['portion_grams']
            scale = Decimal(str(portion)) / Decimal('100.0')
            
            # Compute macro profiles based on scale
            calories = int(float(form.cleaned_data['calories_per_100g']) * float(scale))
            protein_g = form.cleaned_data['protein_per_100g'] * scale
            carbs_g = form.cleaned_data['carbs_per_100g'] * scale
            fats_g = form.cleaned_data['fats_per_100g'] * scale
            
            log = NutritionLog.objects.create(
                user=request.user,
                food_name=form.cleaned_data['food_name'],
                calories=calories,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fats_g=fats_g,
                meal_type=form.cleaned_data['meal_type'],
                date=form.cleaned_data['date']
            )
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success', 
                    'id': log.id,
                    'food_name': log.food_name,
                    'calories': log.calories,
                    'meal_type': log.get_meal_type_display()
                })
            return redirect(f"/nutrition/?date={log.date}")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'errors': form.errors}, status=400)
                
    return redirect('nutrition_daily')


@login_required
def nutrition_delete_view(request, pk):
    log = get_object_or_404(NutritionLog, pk=pk, user=request.user)
    if request.method == 'POST':
        date_str = str(log.date)
        log.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        return redirect(f"/nutrition/?date={date_str}")
        
    return redirect('nutrition_daily')


@login_required
def nutrition_history_api(request):
    user = request.user
    today = timezone.localdate()
    days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    
    data = []
    for day in days:
        daily_logs = NutritionLog.objects.filter(user=user, date=day)
        aggregates = daily_logs.aggregate(
            total_calories=Sum('calories'),
            total_protein=Sum('protein_g')
        )
        data.append({
            'date': day.strftime('%Y-%m-%d'),
            'calories': aggregates['total_calories'] or 0,
            'protein': float(aggregates['total_protein'] or 0.0)
        })
        
    return JsonResponse(data, safe=False)
