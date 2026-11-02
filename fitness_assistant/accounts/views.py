import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from .forms import RegistrationForm, LoginForm, ProfileForm
from workouts.models import WorkoutLog
from nutrition.models import NutritionLog

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = RegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    error_message = None
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                error_message = "Invalid email or password."
    else:
        form = LoginForm()
        
    return render(request, 'accounts/login.html', {
        'form': form,
        'error_message': error_message
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.localdate()
    start_of_week = today - datetime.timedelta(days=today.weekday())  # Monday
    
    # 1. Weekly Workout Volume
    weekly_workout_volume = WorkoutLog.objects.filter(
        user=user,
        date__gte=start_of_week,
        date__lte=today
    ).aggregate(total_volume=Sum('volume'))['total_volume'] or 0
    
    # 2. Today's Calories
    today_calories = NutritionLog.objects.filter(
        user=user,
        date=today
    ).aggregate(total_calories=Sum('calories'))['total_calories'] or 0
    
    # 3. Simple daily target logic based on user goal
    # Custom formula: 
    # Lose weight: 12 * weight_lb or standard 2000 kcal
    # Gain muscle: weight_kg * 35 kcal/kg or standard 2800 kcal
    # Maintain: weight_kg * 30 kcal/kg or standard 2400 kcal
    weight = float(user.weight_kg) if user.weight_kg else 70.0
    if user.goal == 'lose_weight':
        caloric_goal = int(weight * 25)  # e.g., 70 * 25 = 1750 kcal
    elif user.goal == 'gain_muscle':
        caloric_goal = int(weight * 38)  # e.g., 70 * 38 = 2660 kcal
    else:
        caloric_goal = int(weight * 32)  # e.g., 70 * 32 = 2240 kcal
        
    goal_display = user.get_goal_display()
    
    # 4. Recent logs to display on the dashboard quick view
    recent_workouts = WorkoutLog.objects.filter(user=user).order_by('-date', '-created_at')[:3]
    recent_nutrition = NutritionLog.objects.filter(user=user).order_by('-date', '-id')[:3]
    
    context = {
        'user': user,
        'weekly_volume': weekly_workout_volume,
        'today_calories': today_calories,
        'caloric_goal': caloric_goal,
        'goal_display': goal_display,
        'recent_workouts': recent_workouts,
        'recent_nutrition': recent_nutrition,
        'active_tab': 'dashboard'
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=request.user)
        
    return render(request, 'accounts/profile.html', {
        'form': form,
        'active_tab': 'profile'
    })
