from django.urls import path
from core import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('slaughter/', views.slaughter, name='slaughter'),
    path('cutout/', views.cutout, name='cutout'),
    path('cash-futures/', views.cash_futures, name='cash_futures'),
    path('lrp/', views.lrp, name='lrp'),
    path('wasde/', views.wasde, name='wasde'),
    path('chatbot/', views.chatbot_page, name='chatbot'),
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/insights/<str:module>/', views.api_insights, name='api_insights'),
]
