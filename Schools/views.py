
from django.db.models import Count, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from Academic.models import AcademicYear, Day, Period
from Classes.models import ClassLevel, Division
from Rooms.models import Room
from Subjects.models import Subject, TeacherSubjectCapability
from Teachers.models import Teacher
from Timetables.models import (
    ClassSection,
    LectureAdjustment,
    LessonAllocation,
    TeacherDailyStatus,
    Timetable,
    TimetableEntry,
)
from .models import School


# Create your views here.
def school_dashboard(request):
    today = timezone.localdate()

    active_school = School.objects.filter(is_active=True).order_by("name").first()
    active_timetable = Timetable.objects.select_related(
        "school",
        "academic_year",
    ).filter(is_active=True).order_by("-id").first()

    total_weekly_periods = LessonAllocation.objects.filter(is_active=True).aggregate(
        total=Sum("weekly_periods")
    )["total"] or 0

    today_adjustments = LectureAdjustment.objects.filter(date=today)
    if active_timetable:
        today_adjustments = today_adjustments.filter(timetable=active_timetable)

    pending_adjustments = today_adjustments.filter(status="PENDING")
    assigned_adjustments = today_adjustments.filter(status="ASSIGNED")
    cancelled_adjustments = today_adjustments.filter(status="CANCELLED")

    unavailable_today = TeacherDailyStatus.objects.filter(date=today)
    if active_timetable:
        unavailable_today = unavailable_today.filter(school=active_timetable.school)

    latest_adjustments = today_adjustments.select_related(
        "original_teacher",
        "proxy_teacher",
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "room",
    ).order_by("-updated_at")[:5]

    coverage_total = TimetableEntry.objects.count()
    locked_slots = TimetableEntry.objects.filter(is_locked=True).count()
    assigned_slots = TimetableEntry.objects.filter(
        teacher__isnull=False,
        subject__isnull=False,
    ).count()
    coverage_percent = round((assigned_slots / coverage_total) * 100) if coverage_total else 0
    locked_percent = round((locked_slots / coverage_total) * 100) if coverage_total else 0

    setup_total = (
        AcademicYear.objects.count()
        + ClassLevel.objects.count()
        + Division.objects.count()
        + Teacher.objects.count()
        + Subject.objects.count()
        + Room.objects.count()
        + LessonAllocation.objects.count()
    )
    setup_active = (
        AcademicYear.objects.filter(is_active=True).count()
        + ClassLevel.objects.filter(is_active=True).count()
        + Division.objects.filter(is_active=True).count()
        + Teacher.objects.filter(is_active=True).count()
        + Subject.objects.filter(is_active=True).count()
        + Room.objects.filter(is_active=True).count()
        + LessonAllocation.objects.filter(is_active=True).count()
    )
    setup_percent = round((setup_active / setup_total) * 100) if setup_total else 0

    department_load = Teacher.objects.filter(is_active=True).values("department").annotate(
        total=Count("id")
    ).order_by("-total", "department")[:5]

    context = {
        "active_school": active_school,
        "active_timetable": active_timetable,
        "today": today,
        "total_schools": School.objects.count(),
        "active_academic_years": AcademicYear.objects.filter(is_active=True).count(),
        "active_teachers": Teacher.objects.filter(is_active=True).count(),
        "active_subjects": Subject.objects.filter(is_active=True).count(),
        "active_rooms": Room.objects.filter(is_active=True).count(),
        "active_class_sections": ClassSection.objects.filter(is_active=True).count(),
        "active_allocations": LessonAllocation.objects.filter(is_active=True).count(),
        "total_weekly_periods": total_weekly_periods,
        "active_timetables": Timetable.objects.filter(is_active=True).count(),
        "teacher_capabilities": TeacherSubjectCapability.objects.count(),
        "working_days": Day.objects.filter(is_working=True).count(),
        "teaching_periods": Period.objects.filter(is_teaching_period=True).count(),
        "pending_adjustments": pending_adjustments.count(),
        "assigned_adjustments": assigned_adjustments.count(),
        "cancelled_adjustments": cancelled_adjustments.count(),
        "unavailable_today": unavailable_today.count(),
        "latest_adjustments": latest_adjustments,
        "coverage_percent": coverage_percent,
        "locked_percent": locked_percent,
        "setup_percent": setup_percent,
        "department_load": department_load,
    }
    
    return render(request, 'school_dashboard.html', context)

 
