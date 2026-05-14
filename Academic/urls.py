from django.urls import path
from . import views

urlpatterns = [
    path("academic-setup/", views.academic_setup, name="academic_setup"),
    path("academic-setup/list/", views.academic_setup_list, name="academic_setup_list"),
    path("academic-setup/<int:pk>/update/", views.academic_setup_update, name="academic_setup_update"),
    path("academic-setup/<int:pk>/delete/", views.academic_setup_delete, name="academic_setup_delete"),
]
