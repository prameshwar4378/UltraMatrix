# urls.py
from django.urls import path
from . import views
urlpatterns = [
    path('dashboard/', views.school_dashboard, name='school_dashboard'), 
    path('setup-status/', views.setup_completion_status, name='setup_completion_status'),
]
