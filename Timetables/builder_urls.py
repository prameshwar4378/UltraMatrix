from django.urls import path
from . import views_builder

urlpatterns = [
    path("timetable-builder/", views_builder.timetable_builder, name="timetable_builder"),
    path("timetable-builder/template-2/", views_builder.timetable_builder_template_2, name="timetable_builder_template_2"),
    path("timetable-builder/template-3/", views_builder.timetable_builder_template_3, name="timetable_builder_template_3"),
    path("proxy-adjustment/", views_builder.proxy_adjustment_panel, name="proxy_adjustment_panel"),
    path("teacher-timetable/<int:teacher_id>/", views_builder.teacher_timetable_builder, name="teacher_timetable_builder"),
    path("api/validate-timetable/", views_builder.validate_timetable_entries, name="validate_timetable_entries"),
    path("api/save-timetable/", views_builder.save_timetable_entries, name="save_timetable_entries"),
    path("api/save-teacher-timetable/", views_builder.save_teacher_timetable_entries, name="save_teacher_timetable_entries"),
    path("api/create-timetable/", views_builder.create_timetable_api, name="create_timetable_api"),
    path("api/load-timetable/", views_builder.load_timetable_entries, name="load_timetable_entries"),
    path("api/proxy-adjustments/", views_builder.proxy_adjustment_data, name="proxy_adjustment_data"),
    path("api/proxy-adjustments/auto-assign/", views_builder.auto_proxy_adjustments, name="auto_proxy_adjustments"),
    path("api/proxy-adjustments/teacher-status/save/", views_builder.save_teacher_daily_status, name="save_teacher_daily_status"),
    path("api/proxy-adjustments/teacher-status/<int:status_id>/delete/", views_builder.delete_teacher_daily_status, name="delete_teacher_daily_status"),
    path("api/proxy-adjustments/lecture/save/", views_builder.save_lecture_adjustment, name="save_lecture_adjustment"),
    path("api/proxy-adjustments/lecture/<int:adjustment_id>/delete/", views_builder.delete_lecture_adjustment, name="delete_lecture_adjustment"),
    path("api/proxy-adjustments/export/", views_builder.export_proxy_adjustments, name="export_proxy_adjustments"),
    path("api/export-timetable/<int:timetable_id>/<str:scope>/<str:file_format>/", views_builder.export_timetable, name="export_timetable"),
]
