
from django.db.models import Count, Sum
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from Accounts.utils import school_context_for_request
from .models import School
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def _setup_completion_items(school):
    if not school:
        return []

    academic_year_count = AcademicYear.objects.filter(school=school, is_active=True).count()
    working_day_count = Day.objects.filter(school=school, is_working=True).count()
    teaching_period_count = Period.objects.filter(school=school, is_teaching_period=True).count()
    class_level_count = ClassLevel.objects.filter(school=school, is_active=True).count()
    division_count = Division.objects.filter(school=school, is_active=True).count()
    class_section_count = ClassSection.objects.filter(school=school, is_active=True).count()
    teacher_count = Teacher.objects.filter(school=school, is_active=True).count()
    subject_count = Subject.objects.filter(school=school, is_active=True).count()
    room_count = Room.objects.filter(school=school, is_active=True).count()
    capability_count = TeacherSubjectCapability.objects.filter(school=school).count()
    allocation_count = LessonAllocation.objects.filter(school=school, is_active=True).count()
    timetable_count = Timetable.objects.filter(school=school, is_active=True).count()
    timetable_entry_count = TimetableEntry.objects.filter(timetable__school=school).count()

    return [
        {
            "title": "Institute profile",
            "description": "School name, code, and contact identity are ready.",
            "completed": bool(school.name and school.school_code),
            "metric": "Profile created",
            "url_name": "school_dashboard",
            "icon": "bi-building-check",
        },
        {
            "title": "Academic calendar",
            "description": "Academic year, working days, and teaching periods are configured.",
            "completed": academic_year_count > 0 and working_day_count > 0 and teaching_period_count > 0,
            "metric": f"{academic_year_count} year, {working_day_count} days, {teaching_period_count} periods",
            "url_name": "academic_setup_list",
            "icon": "bi-calendar2-week",
        },
        {
            "title": "Classes and sections",
            "description": "Class levels, divisions, and class sections are available.",
            "completed": class_level_count > 0 and division_count > 0 and class_section_count > 0,
            "metric": f"{class_level_count} classes, {division_count} divisions, {class_section_count} sections",
            "url_name": "class_setup_list",
            "icon": "bi-diagram-3",
        },
        {
            "title": "Teachers, subjects, and rooms",
            "description": "Core teaching resources and teacher-subject capability mapping are ready.",
            "completed": teacher_count > 0 and subject_count > 0 and room_count > 0 and capability_count > 0,
            "metric": f"{teacher_count} teachers, {subject_count} subjects, {room_count} rooms",
            "url_name": "teacher_list",
            "icon": "bi-person-workspace",
        },
        {
            "title": "Lesson allocation",
            "description": "Weekly subject load is assigned to sections and teachers.",
            "completed": allocation_count > 0,
            "metric": f"{allocation_count} allocations",
            "url_name": "lesson_allocation_list",
            "icon": "bi-list-check",
        },
        {
            "title": "Timetable readiness",
            "description": "An active timetable exists and contains generated timetable entries.",
            "completed": timetable_count > 0 and timetable_entry_count > 0,
            "metric": f"{timetable_count} timetable, {timetable_entry_count} slots",
            "url_name": "timetable_builder",
            "icon": "bi-calendar-check",
        },
    ]


@login_required
@log_exceptions
def setup_completion_status(request):
    school_context = school_context_for_request(request)
    active_school = school_context["current_school"]
    if not active_school:
        messages.error(request, "No active school is linked with your session.")
        return redirect("login")

    items = _setup_completion_items(active_school)
    completed_count = sum(1 for item in items if item["completed"])
    setup_percent = round((completed_count / len(items)) * 100) if items else 0

    return render(
        request,
        "setup_completion_status.html",
        {
            "active_school": active_school,
            "setup_items": items,
            "completed_count": completed_count,
            "setup_percent": setup_percent,
            **school_context,
        },
    )

# Create your views here.
@login_required
@log_exceptions
def school_dashboard(request):
    today = timezone.localdate()
    school_context = school_context_for_request(request)

    active_school = school_context["current_school"]
    if not active_school:
        messages.error(request, "No active school is linked with your session.")
        return redirect("login")

    current_school_user = school_context["current_school_user"]
    if current_school_user and not current_school_user.has_completed_onboarding:
        return redirect("feature_onboarding")

    active_timetable = Timetable.objects.select_related(
        "school",
        "academic_year",
    ).filter(is_active=True)

    if active_school:
        active_timetable = active_timetable.filter(school=active_school)

    active_timetable = active_timetable.order_by("-id").first()

    academic_years = AcademicYear.objects.filter(school=active_school)
    days = Day.objects.filter(school=active_school)
    periods = Period.objects.filter(school=active_school)
    class_levels = ClassLevel.objects.filter(school=active_school)
    divisions = Division.objects.filter(school=active_school)
    teachers = Teacher.objects.filter(school=active_school)
    subjects = Subject.objects.filter(school=active_school)
    rooms = Room.objects.filter(school=active_school)
    class_sections = ClassSection.objects.filter(school=active_school)
    lesson_allocations = LessonAllocation.objects.filter(school=active_school)
    timetables = Timetable.objects.filter(school=active_school)
    teacher_capabilities = TeacherSubjectCapability.objects.filter(school=active_school)
    timetable_entries = TimetableEntry.objects.filter(timetable__school=active_school)
    unavailable_statuses = TeacherDailyStatus.objects.filter(school=active_school)

    total_weekly_periods = lesson_allocations.filter(is_active=True).aggregate(
        total=Sum("weekly_periods")
    )["total"] or 0

    today_adjustments = LectureAdjustment.objects.filter(date=today)
    if active_school:
        today_adjustments = today_adjustments.filter(timetable__school=active_school)
    if active_timetable:
        today_adjustments = today_adjustments.filter(timetable=active_timetable)

    pending_adjustments = today_adjustments.filter(status="PENDING")
    assigned_adjustments = today_adjustments.filter(status="ASSIGNED")
    cancelled_adjustments = today_adjustments.filter(status="CANCELLED")

    unavailable_today = unavailable_statuses.filter(date=today)

    latest_adjustments = today_adjustments.select_related(
        "original_teacher",
        "proxy_teacher",
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "room",
    ).order_by("-updated_at")[:5]

    coverage_total = timetable_entries.count()
    locked_slots = timetable_entries.filter(is_locked=True).count()
    assigned_slots = timetable_entries.filter(
        teacher__isnull=False,
        subject__isnull=False,
    ).count()
    coverage_percent = round((assigned_slots / coverage_total) * 100) if coverage_total else 0
    locked_percent = round((locked_slots / coverage_total) * 100) if coverage_total else 0

    setup_total = (
        academic_years.count()
        + class_levels.count()
        + divisions.count()
        + teachers.count()
        + subjects.count()
        + rooms.count()
        + lesson_allocations.count()
    )
    setup_active = (
        academic_years.filter(is_active=True).count()
        + class_levels.filter(is_active=True).count()
        + divisions.filter(is_active=True).count()
        + teachers.filter(is_active=True).count()
        + subjects.filter(is_active=True).count()
        + rooms.filter(is_active=True).count()
        + lesson_allocations.filter(is_active=True).count()
    )
    setup_percent = round((setup_active / setup_total) * 100) if setup_total else 0

    department_load = teachers.filter(is_active=True).values("department").annotate(
        total=Count("id")
    ).order_by("-total", "department")[:5]

    context = {
        "active_school": active_school,
        "active_timetable": active_timetable,
        "today": today,
        "total_schools": 1,
        "active_academic_years": academic_years.filter(is_active=True).count(),
        "active_teachers": teachers.filter(is_active=True).count(),
        "active_subjects": subjects.filter(is_active=True).count(),
        "active_rooms": rooms.filter(is_active=True).count(),
        "active_class_sections": class_sections.filter(is_active=True).count(),
        "active_allocations": lesson_allocations.filter(is_active=True).count(),
        "total_weekly_periods": total_weekly_periods,
        "active_timetables": timetables.filter(is_active=True).count(),
        "teacher_capabilities": teacher_capabilities.count(),
        "working_days": days.filter(is_working=True).count(),
        "teaching_periods": periods.filter(is_teaching_period=True).count(),
        "pending_adjustments": pending_adjustments.count(),
        "assigned_adjustments": assigned_adjustments.count(),
        "cancelled_adjustments": cancelled_adjustments.count(),
        "unavailable_today": unavailable_today.count(),
        "latest_adjustments": latest_adjustments,
        "coverage_percent": coverage_percent,
        "locked_percent": locked_percent,
        "setup_percent": setup_percent,
        "department_load": department_load,
        **school_context,
    }
    
    return render(request, 'school_dashboard.html', context)

 
