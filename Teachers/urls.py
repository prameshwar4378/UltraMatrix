from django.urls import path
from . import views

urlpatterns = [
    path("teachers/", views.teacher_list, name="teacher_list"),
    path("teachers/create/", views.teacher_create, name="teacher_create"),
    path("teachers/<int:pk>/update/", views.teacher_update, name="teacher_update"),
    path("teachers/<int:pk>/delete/", views.teacher_delete, name="teacher_delete"),
    path("teachers/export/excel/", views.teacher_export_excel, name="teacher_export_excel"),
    path("teachers/import/excel/", views.teacher_import_excel, name="teacher_import_excel"),
    path("teachers/import/template/", views.teacher_import_template, name="teacher_import_template"),
]
