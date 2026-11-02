from django.urls import path
from . import views

urlpatterns = [
    path('', views.nutrition_daily_view, name='nutrition_daily'),
    path('log/', views.nutrition_log_create, name='nutrition_log_add'),
    path('<int:pk>/delete/', views.nutrition_delete_view, name='nutrition_delete'),
    path('api/search/', views.nutrition_search_api, name='nutrition_search_api'),
    path('api/history/', views.nutrition_history_api, name='nutrition_history_api'),
]
