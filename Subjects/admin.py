from django.contrib import admin
from .models import Subject, TeacherSubjectCapability


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "code", "section_type", "subject_type", "is_active")
    list_filter = ("school", "section_type", "subject_type", "is_active")
    search_fields = ("name", "short_name", "code", "school__name")
    list_editable = ("is_active",)


@admin.register(TeacherSubjectCapability)
class TeacherSubjectCapabilityAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject", "school", "priority")
    list_filter = ("school", "priority", "subject")
    search_fields = ("teacher__name", "subject__name", "school__name")
    filter_horizontal = ("class_levels",)
