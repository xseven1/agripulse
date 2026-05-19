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
    path('compare/', views.comparable, name='comparable'),
    # API
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/insight/<str:module>/', views.api_module_insight, name='api_module_insight'),
    path('api/chart-insight/<str:chart_id>/', views.api_chart_insight, name='api_chart_insight'),
    path('api/chart-ask/<str:chart_id>/', views.api_chart_ask, name='api_chart_ask'),
    path('api/chart-period/<str:chart_id>/', views.api_chart_period, name='api_chart_period'),
]
