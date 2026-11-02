from django.urls import path
from . import views

urlpatterns = [
    # Workout Log (today's workout)
    path('', views.workout_log_view, name='workout_list'),
    path('add/', views.workout_add_view, name='workout_add'),          # kept so old links still work
    path('save/', views.session_save_view, name='workout_session_save'),

    # History
    path('history/', views.history_view, name='workout_history'),
    path('history/<int:pk>/delete/', views.session_delete_view, name='workout_session_delete'),

    # Progression prediction
    path('progression/', views.progression_view, name='workout_progression'),

    # My Splits
    path('split/', views.split_view, name='workout_split'),
    path('split/generate/', views.split_generate_view, name='workout_split_generate'),
    path('split/day/new/', views.split_day_editor_view, name='workout_split_day_add'),
    path('split/day/<int:pk>/edit/', views.split_day_editor_view, name='workout_split_day_edit'),
    path('split/day/save/', views.split_day_save_view, name='workout_split_day_save'),
    path('split/day/<int:pk>/delete/', views.split_day_delete_view, name='workout_split_day_delete'),
    path('split/reset/', views.split_reset_view, name='workout_split_reset'),
]
