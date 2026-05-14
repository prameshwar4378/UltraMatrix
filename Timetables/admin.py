from django.contrib import admin
from .models import (
    ClassSection,
    LectureAdjustment,
    LessonAllocation,
    TeacherDailyStatus,
    Timetable,
    TimetableEntry,
    TimetableSlot,
    TimetableVersion,
)


@admin.register(ClassSection)
class ClassSectionAdmin(admin.ModelAdmin):
    list_display = ("school", "class_level", "division", "class_teacher", "default_room", "is_active")
    list_filter = ("school", "is_active", "class_level__section_type")
    search_fields = ("school__name", "class_level__name", "division__name", "class_teacher__name")


@admin.register(LessonAllocation)
class LessonAllocationAdmin(admin.ModelAdmin):
    list_display = ("school", "academic_year", "class_section", "subject", "teacher", "weekly_periods", "is_active")
    list_filter = ("school", "academic_year", "is_active", "requires_double_period")
    search_fields = ("class_section__class_level__name", "class_section__division__name", "subject__name", "teacher__name")


admin.site.register(Timetable)
admin.site.register(TimetableVersion)
admin.site.register(TimetableSlot)
admin.site.register(TimetableEntry)


@admin.register(TeacherDailyStatus)
class TeacherDailyStatusAdmin(admin.ModelAdmin):
    list_display = ("date", "school", "teacher", "status_type", "full_day", "reason")
    list_filter = ("school", "status_type", "full_day", "date")
    search_fields = ("teacher__name", "reason", "notes")
    filter_horizontal = ("unavailable_periods",)


@admin.register(LectureAdjustment)
class LectureAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("date", "timetable", "class_section", "subject", "original_teacher", "proxy_teacher", "status")
    list_filter = ("date", "status", "timetable__school", "is_locked")
    search_fields = ("class_section__class_level__name", "class_section__division__name", "subject__name", "original_teacher__name", "proxy_teacher__name")
