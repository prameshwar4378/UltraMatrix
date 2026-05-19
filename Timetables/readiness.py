from django.db.models import Q

from Academic.models import BellSchedule, Day, Period
from Rooms.models import Room
from Teachers.models import Teacher
from Timetables.models import ClassSection, LessonAllocation, TimetableConfiguration, TimetableEntry
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def timetable_readiness(timetable):
    entry_count = getattr(timetable, "entry_count", None)
    if entry_count is None:
        entry_count = TimetableEntry.objects.filter(timetable=timetable).count()

    configuration = TimetableConfiguration.objects.filter(timetable=timetable).first()
    bell_schedule = configuration.bell_schedule if configuration and configuration.bell_schedule_id else None

    active_sections_query = ClassSection.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    )
    active_teachers_query = Teacher.objects.filter(school=timetable.school, timetable=timetable, is_active=True)
    active_rooms_query = Room.objects.filter(school=timetable.school, timetable=timetable, is_active=True)
    active_days_query = Day.objects.filter(school=timetable.school, timetable=timetable, is_working=True)
    active_periods_query = Period.objects.filter(school=timetable.school, timetable=timetable, bell_schedule=bell_schedule) if bell_schedule else Period.objects.none()
    active_allocations_query = LessonAllocation.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
    )

    selected_section_ids = set(configuration.class_sections.values_list("id", flat=True)) if configuration else set()
    selected_teacher_ids = set(configuration.teachers.values_list("id", flat=True)) if configuration else set()
    selected_room_ids = set(configuration.rooms.values_list("id", flat=True)) if configuration else set()
    selected_day_ids = set(configuration.working_days.values_list("id", flat=True)) if configuration else set()
    selected_period_ids = set(configuration.periods.values_list("id", flat=True)) if configuration else set()

    config_counts = {
        "sections": len(selected_section_ids),
        "teachers": len(selected_teacher_ids),
        "rooms": len(selected_room_ids),
        "days": len(selected_day_ids),
        "periods": len(selected_period_ids),
    }

    scoped_sections_query = active_sections_query.filter(id__in=selected_section_ids)
    scoped_teachers_query = active_teachers_query.filter(id__in=selected_teacher_ids)
    scoped_rooms_query = active_rooms_query.filter(id__in=selected_room_ids)
    scoped_days_query = active_days_query.filter(id__in=selected_day_ids)
    scoped_periods_query = active_periods_query.filter(id__in=selected_period_ids)
    scoped_allocations_query = active_allocations_query.filter(class_section_id__in=selected_section_ids)
    section_allocations_query = scoped_allocations_query

    if selected_teacher_ids:
        scoped_allocations_query = scoped_allocations_query.filter(teacher_id__in=selected_teacher_ids)

    if selected_room_ids:
        scoped_allocations_query = scoped_allocations_query.filter(Q(default_room_id__in=selected_room_ids) | Q(default_room__isnull=True))

    active_sections = active_sections_query.count()
    active_teachers = active_teachers_query.count()
    active_rooms = active_rooms_query.count()
    active_days = active_days_query.count()
    active_periods = active_periods_query.count()
    active_allocations = active_allocations_query.count()
    scoped_sections = scoped_sections_query.count()
    scoped_teachers = scoped_teachers_query.count()
    scoped_rooms = scoped_rooms_query.count()
    scoped_days = scoped_days_query.count()
    scoped_periods = scoped_periods_query.count()
    scoped_allocations = scoped_allocations_query.count()

    missing_items = []
    checks = [
        ("Selected bell schedule", bool(bell_schedule)),
        ("Selected working days", bool(selected_day_ids) and scoped_days > 0),
        ("Selected periods", bool(selected_period_ids) and scoped_periods > 0),
        ("Selected class sections", bool(selected_section_ids) and scoped_sections > 0),
        ("Selected teachers", bool(selected_teacher_ids) and scoped_teachers > 0),
        ("Selected rooms", bool(selected_room_ids) and scoped_rooms > 0),
        ("Lesson allocations inside selected scope", scoped_allocations > 0),
    ]

    for label, is_ready in checks:
        if not is_ready:
            missing_items.append(label)

    if selected_section_ids:
        allocated_section_ids = set(section_allocations_query.values_list("class_section_id", flat=True))
        missing_section_count = scoped_sections_query.exclude(id__in=allocated_section_ids).count()
        if missing_section_count:
            missing_items.append(f"Allocations for {missing_section_count} selected section(s)")

    if selected_teacher_ids:
        outside_teacher_count = active_allocations_query.filter(
            class_section_id__in=selected_section_ids or active_sections_query.values_list("id", flat=True)
        ).exclude(teacher_id__in=selected_teacher_ids).count()
        if outside_teacher_count:
            missing_items.append("Selected-scope allocations use unselected teachers")

    if selected_room_ids:
        outside_room_count = active_allocations_query.filter(
            class_section_id__in=selected_section_ids or active_sections_query.values_list("id", flat=True),
            default_room__isnull=False,
        ).exclude(default_room_id__in=selected_room_ids).count()
        if outside_room_count:
            missing_items.append("Selected-scope allocations use unselected rooms")

    missing_items = list(dict.fromkeys(missing_items))

    total_checks = len(checks)
    completed_checks = max(0, total_checks - len(missing_items))
    percent = round((completed_checks / total_checks) * 100) if total_checks else 0

    if missing_items:
        status = "pending"
        label = "Setup Pending"
        badge = "badge-warning-soft"
    elif entry_count:
        status = "generated"
        label = "Generated"
        badge = "badge-primary-soft"
    else:
        status = "ready"
        label = "Ready"
        badge = "badge-success-soft"

    return {
        "status": status,
        "label": label,
        "badge": badge,
        "percent": percent,
        "missing": missing_items,
        "missing_text": ", ".join(missing_items),
        "entry_count": entry_count,
        "can_open_builder": status in {"ready", "generated"},
        "config_counts": config_counts,
        "scope_counts": {
            "sections": scoped_sections,
            "teachers": scoped_teachers,
            "rooms": scoped_rooms,
            "days": scoped_days,
            "periods": scoped_periods,
            "allocations": scoped_allocations,
        },
    }


@log_exceptions
def attach_timetable_readiness(timetable):
    readiness = timetable_readiness(timetable)
    timetable.entry_count = readiness["entry_count"]
    timetable.readiness_status = readiness["status"]
    timetable.readiness_label = readiness["label"]
    timetable.readiness_badge = readiness["badge"]
    timetable.readiness_percent = readiness["percent"]
    timetable.readiness_missing = readiness["missing"]
    timetable.readiness_missing_text = readiness["missing_text"]
    timetable.can_open_builder = readiness["can_open_builder"]
    timetable.config_counts = readiness["config_counts"]
    timetable.scope_counts = readiness["scope_counts"]
    return readiness
