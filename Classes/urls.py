from django.urls import path
from . import views

urlpatterns = [
    path("class-setup-list/", views.class_setup_list, name="class_setup_list"),

    path("class-level/create/", views.class_level_create, name="class_level_create"),
    path("class-level/<int:pk>/update/", views.class_level_update, name="class_level_update"),
    path("class-level/<int:pk>/delete/", views.class_level_delete, name="class_level_delete"),
    path("division/create/", views.division_create, name="division_create"),
    path("division/<int:pk>/update/", views.division_update, name="division_update"),
    path("division/<int:pk>/delete/", views.division_delete, name="division_delete"),
    path("class-section/create/", views.class_section_create, name="class_section_create"),
    path("class-section/<int:pk>/update/", views.class_section_update, name="class_section_update"),
    path("class-section/<int:pk>/delete/", views.class_section_delete, name="class_section_delete"),
]
