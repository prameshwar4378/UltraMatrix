# urls.py
from django.urls import path
from . import views
urlpatterns = [
    path('', views.school_dashboard, name='school_dashboard'), 
]
