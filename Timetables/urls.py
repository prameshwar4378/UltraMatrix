from django.urls import path
from . import views

urlpatterns = [
    path(
        "lesson-allocation/",
        views.lesson_allocation_list,
        name="lesson_allocation_list"
    ),
    path(
        "lesson-allocation/export/",
        views.lesson_allocation_export_csv,
        name="lesson_allocation_export_csv"
    ),
    path(
        "lesson-allocation/quick-create/",
        views.lesson_allocation_quick_create,
        name="lesson_allocation_quick_create"
    ),

    path(
        "lesson-allocation/create/",
        views.lesson_allocation_create,
        name="lesson_allocation_create"
    ),
    path(
        "lesson-allocation/teacher/<int:teacher_id>/update/",
        views.lesson_allocation_teacher_update,
        name="lesson_allocation_teacher_update"
    ),

    path(
        "lesson-allocation/<int:pk>/update/",
        views.lesson_allocation_update,
        name="lesson_allocation_update"
    ),
    path(
        "lesson-allocation/<int:pk>/toggle-status/",
        views.lesson_allocation_toggle_status,
        name="lesson_allocation_toggle_status"
    ),
    path(
        "lesson-allocation/<int:pk>/delete/",
        views.lesson_allocation_delete,
        name="lesson_allocation_delete"
    ),
    path(
        "lesson-allocation/bulk-delete/",
        views.lesson_allocation_bulk_delete,
        name="lesson_allocation_bulk_delete"
    ),
]
