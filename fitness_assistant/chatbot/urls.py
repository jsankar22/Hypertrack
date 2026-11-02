from django.urls import path

from . import views

urlpatterns = [
    path('', views.chat_view, name='chatbot'),
    path('api/message/', views.chat_message_api, name='chatbot_message_api'),
    path('api/clear/', views.chat_clear_api, name='chatbot_clear_api'),
]
