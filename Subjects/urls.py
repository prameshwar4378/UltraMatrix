from django.urls import path
from . import views

urlpatterns = [
    path("subjects/", views.subject_list, name="subject_list"),
    path("subjects/export/", views.subject_export_csv, name="subject_export_csv"),

    path("subjects/create/", views.subject_create, name="subject_create"),
    path("subjects/quick-create/", views.subject_quick_create, name="subject_quick_create"),
    path("subjects/<int:pk>/update/", views.subject_update, name="subject_update"),
    path("subjects/<int:pk>/delete/", views.subject_delete, name="subject_delete"),
    path("subjects/bulk-delete/", views.subject_bulk_delete, name="subject_bulk_delete"),
    path("subjects/<int:pk>/toggle-status/", views.subject_toggle_status, name="subject_toggle_status"),

    path("teacher-subject/create/", views.teacher_subject_create, name="teacher_subject_create"),
    path("teacher-subject/quick-create/", views.teacher_subject_quick_create, name="teacher_subject_quick_create"),
    path("teacher-subject/<int:pk>/update/", views.teacher_subject_update, name="teacher_subject_update"),
    path("teacher-subject/<int:pk>/delete/", views.teacher_subject_delete, name="teacher_subject_delete"),
    path("teacher-subject/bulk-delete/", views.teacher_subject_bulk_delete, name="teacher_subject_bulk_delete"),
]
