from django.urls import path
from . import views

urlpatterns = [
    path("rooms/", views.room_list, name="room_list"),
    path("rooms/auto-create-classrooms/", views.room_auto_create_classrooms, name="room_auto_create_classrooms"),
    path("rooms/create/", views.room_create, name="room_create"),
    path("rooms/<int:pk>/update/", views.room_update, name="room_update"),
    path("rooms/<int:pk>/delete/", views.room_delete, name="room_delete"),
    path("rooms/bulk-delete/", views.room_bulk_delete, name="room_bulk_delete"),
]
