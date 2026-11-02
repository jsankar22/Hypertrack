from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    # Redirect root to dashboard (which handles auth redirect automatically)
    path('', lambda r: redirect('dashboard'), name='root_redirect'),
    path('', include('accounts.urls')),
    path('workouts/', include('workouts.urls')),
    path('nutrition/', include('nutrition.urls')),
    path('chatbot/', include('chatbot.urls')),
]
