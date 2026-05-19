import csv
import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Academic.models import AcademicYear, BellSchedule, Day, Period
from Schools.models import School
from Subjects.models import Subject, TeacherSubjectCapability
from Timetables.models import ClassSection, LessonAllocation, Timetable, TimetableConfiguration, TimetableEntry
from Teachers.models import Teacher
from Rooms.models import Room
from .forms import LessonAllocationForm, TimetableForm
from .readiness import attach_timetable_readiness
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@login_required
@log_exceptions
def timetable_list(request):
    current_school = get_current_school(request)
    timetables = school_queryset(
        request,
        Timetable.objects.select_related("school", "academic_year"),
    ).order_by("-id")

    search_query = request.GET.get("search", "")
    academic_year_filter = request.GET.get("academic_year", "")
    status_filter = request.GET.get("status", "")
    setup_status_filter = request.GET.get("setup_status", "")

    if search_query:
        timetables = timetables.filter(
            Q(name__icontains=search_query) |
            Q(academic_year__name__icontains=search_query)
        )

    if academic_year_filter:
        timetables = timetables.filter(academic_year_id=academic_year_filter)

    if status_filter == "active":
        timetables = timetables.filter(is_active=True)

    if status_filter == "inactive":
        timetables = timetables.filter(is_active=False)

    timetables = list(timetables)
    for timetable in timetables:
        attach_timetable_readiness(timetable)

    if setup_status_filter:
        timetables = [
            timetable for timetable in timetables
            if timetable.readiness_status == setup_status_filter
        ]

    academic_years = AcademicYear.objects.none()
    if current_school:
        academic_years = AcademicYear.objects.filter(school=current_school).order_by("-start_date", "-id")

    context = {
        "timetables": timetables,
        "academic_years": academic_years,
        "total_timetables": len(timetables),
        "active_timetables": sum(1 for timetable in timetables if timetable.is_active),
        "configured_timetables": sum(1 for timetable in timetables if timetable.entry_count),
        "ready_timetables": sum(1 for timetable in timetables if timetable.readiness_status == "ready"),
        "pending_timetables": sum(1 for timetable in timetables if timetable.readiness_status == "pending"),
        "current_school": current_school,
        "search_query": search_query,
        "academic_year_filter": academic_year_filter,
        "status_filter": status_filter,
        "setup_status_filter": setup_status_filter,
    }
    return render(request, "timetable_list.html", context)


@login_required
@log_exceptions
def timetable_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = TimetableForm(request.POST, current_school=current_school)
        if form.is_valid():
            timetable = form.save()
            messages.success(request, "Timetable created successfully. Configure it before opening the builder.")
            return redirect("timetable_config", pk=timetable.pk)
    else:
        form = TimetableForm(current_school=current_school)

    return render(request, "timetable_form.html", {
        "form": form,
        "title": "Create Timetable",
        "subtitle": "Create a timetable record with name and academic year. Configuration happens after creation.",
        "button_text": "Create Timetable",
    })


@login_required
@log_exceptions
def timetable_update(request, pk):
    timetable = get_school_object_or_404(request, Timetable.objects.all(), pk=pk)
    current_school = get_current_school(request)
    if request.method == "POST":
        form = TimetableForm(request.POST, instance=timetable, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Timetable updated successfully.")
            return redirect("timetable_list")
    else:
        form = TimetableForm(instance=timetable, current_school=current_school)

    return render(request, "timetable_form.html", {
        "form": form,
        "title": "Update Timetable",
        "subtitle": "Update timetable name or academic year.",
        "button_text": "Update Timetable",
    })


@login_required
@require_POST
@log_exceptions
def timetable_delete(request, pk):
    timetable = get_school_object_or_404(
        request,
        Timetable.objects.prefetch_related("lesson_allocations", "entries", "versions", "lecture_adjustments"),
        pk=pk,
    )
    name = timetable.name
    deleted_summary = {
        "class_levels": timetable.class_levels.count(),
        "divisions": timetable.divisions.count(),
        "class_sections": timetable.class_sections.count(),
        "teachers": timetable.teachers.count(),
        "subjects": timetable.subjects.count(),
        "capabilities": timetable.teacher_subject_capabilities.count(),
        "rooms": timetable.rooms.count(),
        "allocations": timetable.lesson_allocations.count(),
        "entries": timetable.entries.count(),
        "versions": timetable.versions.count(),
        "adjustments": timetable.lecture_adjustments.count(),
        "configuration": 1 if hasattr(timetable, "configuration") else 0,
    }
    timetable.delete()
    messages.success(
        request,
        (
            f"Timetable '{name}' deleted with its configuration, "
            f"{deleted_summary['class_sections']} class section(s), "
            f"{deleted_summary['teachers']} teacher(s), "
            f"{deleted_summary['subjects']} subject(s), "
            f"{deleted_summary['rooms']} room(s), "
            f"{deleted_summary['allocations']} allocation(s), "
            f"{deleted_summary['entries']} slot(s), "
            f"{deleted_summary['versions']} version(s), and "
            f"{deleted_summary['adjustments']} adjustment(s)."
        )
    )
    return redirect("timetable_list")


@login_required
@log_exceptions
def timetable_config(request, pk):
    timetable = get_school_object_or_404(
        request,
        Timetable.objects.select_related("academic_year", "school"),
        pk=pk,
    )
    configuration, _ = TimetableConfiguration.objects.get_or_create(timetable=timetable)
    class_sections = ClassSection.objects.select_related(
        "class_level",
        "division",
    ).filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")
    configured_section_ids = set(configuration.class_sections.values_list("id", flat=True))
    configured_day_ids = set(configuration.working_days.values_list("id", flat=True))
    configured_period_ids = set(configuration.periods.values_list("id", flat=True))
    configured_teacher_ids = set(configuration.teachers.values_list("id", flat=True))
    configured_room_ids = set(configuration.rooms.values_list("id", flat=True))

    bell_schedules = BellSchedule.objects.filter(
        school=timetable.school,
        academic_year=timetable.academic_year,
        timetable=timetable,
        is_active=True,
    ).order_by("-id")
    selected_bell_schedule = configuration.bell_schedule or bell_schedules.first()
    working_days = Day.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_working=True,
    ).order_by("sort_order", "id")
    periods = Period.objects.none()
    if selected_bell_schedule:
        periods = Period.objects.filter(
            school=timetable.school,
            timetable=timetable,
            bell_schedule=selected_bell_schedule,
        ).order_by("day_type", "period_number", "id")
    teachers = Teacher.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
    ).order_by("name", "id")
    rooms = Room.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
    ).order_by("room_type", "name", "id")

    if request.method == "POST":
        bell_schedule_id = request.POST.get("bell_schedule")
        selected_bell_schedule = bell_schedules.filter(id=bell_schedule_id).first() if bell_schedule_id else None
        periods_for_save = Period.objects.none()
        if selected_bell_schedule:
            periods_for_save = Period.objects.filter(
                school=timetable.school,
                timetable=timetable,
                bell_schedule=selected_bell_schedule,
            )

        selected_ids = request.POST.getlist("class_section_ids")
        selected_sections = class_sections.filter(id__in=selected_ids)
        selected_day_ids = request.POST.getlist("working_day_ids")
        selected_days = working_days.filter(id__in=selected_day_ids)
        selected_period_ids = request.POST.getlist("period_ids")
        selected_periods = periods_for_save.filter(id__in=selected_period_ids)
        selected_teacher_ids = request.POST.getlist("teacher_ids")
        selected_teachers = teachers.filter(id__in=selected_teacher_ids)
        selected_room_ids = request.POST.getlist("room_ids")
        selected_rooms = rooms.filter(id__in=selected_room_ids)

        configuration.bell_schedule = selected_bell_schedule
        configuration.save(update_fields=["bell_schedule", "updated_at"])
        configuration.class_sections.set(selected_sections)
        configuration.working_days.set(selected_days)
        configuration.periods.set(selected_periods)
        configuration.teachers.set(selected_teachers)
        configuration.rooms.set(selected_rooms)
        messages.success(request, f"Configuration saved for '{timetable.name}'.")
        return redirect("timetable_config", pk=timetable.pk)

    entry_count = TimetableEntry.objects.filter(timetable=timetable).count()
    timetable.entry_count = entry_count
    readiness = attach_timetable_readiness(timetable)
    active_sections = class_sections.count()
    active_allocations = LessonAllocation.objects.filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
    ).count()
    allocation_health = _timetable_allocation_health(timetable, configuration)
    configured_sections = len(configured_section_ids)
    configured_days = len(configured_day_ids)
    configured_periods = len(configured_period_ids)
    configured_teachers = len(configured_teacher_ids)
    configured_rooms = len(configured_room_ids)
    setup_items = _timetable_configuration_items(
        timetable,
        configuration,
        readiness,
        active_sections,
        active_allocations,
        configured_sections,
        configured_teachers,
        configured_rooms,
        configured_days,
        configured_periods,
        entry_count,
    )
    completed_setup_items = sum(1 for item in setup_items if item["completed"])
    setup_percent = round((completed_setup_items / len(setup_items)) * 100) if setup_items else 0

    return render(request, "timetable_config.html", {
        "timetable": timetable,
        "class_sections": class_sections,
        "configured_section_ids": configured_section_ids,
        "teachers": teachers,
        "configured_teacher_ids": configured_teacher_ids,
        "rooms": rooms,
        "configured_room_ids": configured_room_ids,
        "bell_schedules": bell_schedules,
        "selected_bell_schedule": selected_bell_schedule,
        "working_days": working_days,
        "periods": periods,
        "configured_day_ids": configured_day_ids,
        "configured_period_ids": configured_period_ids,
        "configured_sections": configured_sections,
        "configured_days": configured_days,
        "configured_periods": configured_periods,
        "configured_teachers": configured_teachers,
        "configured_rooms": configured_rooms,
        "readiness": readiness,
        "allocation_health": allocation_health,
        "entry_count": entry_count,
        "active_sections": active_sections,
        "active_allocations": active_allocations,
        "setup_items": setup_items,
        "completed_setup_items": completed_setup_items,
        "setup_percent": setup_percent,
    })


@log_exceptions
def _timetable_configuration_items(
    timetable,
    configuration,
    readiness,
    active_sections,
    active_allocations,
    configured_sections,
    configured_teachers,
    configured_rooms,
    configured_days,
    configured_periods,
    entry_count,
):
    has_schedule = bool(configuration and configuration.bell_schedule_id)
    return [
        {
            "title": "Academic calendar",
            "description": "Bell schedule, working days, and teaching periods selected for this timetable.",
            "completed": has_schedule and configured_days > 0 and configured_periods > 0,
            "metric": f"{configured_days} day(s), {configured_periods} period(s)",
            "icon": "bi-calendar2-week",
            "href": "#calendarSetup",
            "action_url": f"{reverse('academic_setup_list')}?timetable_id={timetable.id}",
        },
        {
            "title": "Classes and sections",
            "description": "Manage Classes, Divisions & Sections for this timetable only.",
            "completed": configured_sections > 0,
            "metric": f"{configured_sections} selected of {active_sections} active",
            "icon": "bi-diagram-3",
            "href": "#sectionSetup",
            "action_url": f"{reverse('class_setup_list')}?timetable_id={timetable.id}",
        },
        {
            "title": "Teachers",
            "description": "Manage teachers for this timetable only.",
            "completed": configured_teachers > 0,
            "metric": f"{configured_teachers} teacher(s)",
            "icon": "bi-person-workspace",
            "href": "#resourceSetup",
            "action_url": f"{reverse('teacher_list')}?timetable_id={timetable.id}",
        },
        {
            "title": "Subjects & Teacher Capabilities",
            "description": "Manage subjects and teacher capability mappings for this timetable only.",
            "completed": timetable.subjects.filter(is_active=True).exists() and timetable.teacher_subject_capabilities.exists(),
            "metric": f"{timetable.subjects.filter(is_active=True).count()} subject(s), {timetable.teacher_subject_capabilities.count()} mapping(s)",
            "icon": "bi-journal-bookmark",
            "href": "#subjectSetup",
            "action_url": f"{reverse('subject_list')}?timetable_id={timetable.id}",
        },
        {
            "title": "Rooms, Labs & Facilities",
            "description": "Manage classrooms, labs, library, playground and facilities for this timetable only.",
            "completed": configured_rooms > 0,
            "metric": f"{configured_rooms} room(s)",
            "icon": "bi-door-open",
            "href": "#resourceSetup",
            "action_url": f"{reverse('room_list')}?timetable_id={timetable.id}",
        },
        {
            "title": "Lesson allocation",
            "description": "Weekly subject load assigned for this timetable only.",
            "completed": active_allocations > 0 and readiness["scope_counts"]["allocations"] > 0,
            "metric": f"{readiness['scope_counts']['allocations']} scoped allocation(s)",
            "icon": "bi-list-check",
            "href": "#allocationHealth",
            "action_url": f"{reverse('lesson_allocation_list')}?timetable={timetable.id}",
        },
        {
            "title": "Timetable builder",
            "description": "Builder opens only after this timetable setup is complete.",
            "completed": readiness["can_open_builder"],
            "metric": readiness["label"],
            "icon": "bi-calendar-check",
            "href": "#builderReadiness",
        },
        {
            "title": "Saved timetable slots",
            "description": "Generated slots saved against this timetable record only.",
            "completed": entry_count > 0,
            "metric": f"{entry_count} slot(s)",
            "icon": "bi-grid-3x3-gap",
            "href": "#builderReadiness",
        },
    ]


@log_exceptions
def _timetable_allocation_health(timetable, configuration):
    selected_section_ids = set(configuration.class_sections.values_list("id", flat=True)) if configuration else set()
    selected_teacher_ids = set(configuration.teachers.values_list("id", flat=True)) if configuration else set()
    selected_room_ids = set(configuration.rooms.values_list("id", flat=True)) if configuration else set()

    if not selected_section_ids:
        return {
            "issue_count": 0,
            "is_clean": False,
            "not_configured": True,
            "allocation_count": 0,
            "missing_sections": [],
            "unselected_teacher_allocations": [],
            "unselected_room_allocations": [],
        }

    sections = ClassSection.objects.select_related("class_level", "division").filter(
        school=timetable.school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")
    if selected_section_ids:
        sections = sections.filter(id__in=selected_section_ids)

    allocations = LessonAllocation.objects.select_related(
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "teacher",
        "default_room",
    ).filter(
        school=timetable.school,
        timetable=timetable,
        is_active=True,
    )

    section_ids = set(sections.values_list("id", flat=True))
    scoped_allocations = allocations.filter(class_section_id__in=section_ids)
    allocated_section_ids = set(scoped_allocations.values_list("class_section_id", flat=True))
    missing_sections = list(sections.exclude(id__in=allocated_section_ids)[:8])

    unselected_teacher_allocations = []
    if selected_teacher_ids:
        unselected_teacher_allocations = list(
            scoped_allocations.exclude(teacher_id__in=selected_teacher_ids)[:8]
        )

    unselected_room_allocations = []
    if selected_room_ids:
        unselected_room_allocations = list(
            scoped_allocations.filter(default_room__isnull=False).exclude(default_room_id__in=selected_room_ids)[:8]
        )

    issue_count = len(missing_sections) + len(unselected_teacher_allocations) + len(unselected_room_allocations)
    return {
        "issue_count": issue_count,
        "is_clean": issue_count == 0,
        "allocation_count": scoped_allocations.count(),
        "missing_sections": missing_sections,
        "unselected_teacher_allocations": unselected_teacher_allocations,
        "unselected_room_allocations": unselected_room_allocations,
    }


@log_exceptions
def _positive_int(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, number)


@log_exceptions
@log_exceptions
def _timetable_scope_from_request(request, current_school):
    timetable_id = request.GET.get("timetable_id") or request.POST.get("timetable_id")
    if not timetable_id:
        return None, set(), set(), set()

    timetable = Timetable.objects.filter(pk=timetable_id, school=current_school).first()
    if not timetable:
        return None, set(), set(), set()

    configuration = TimetableConfiguration.objects.filter(timetable=timetable).first()
    section_ids = set(configuration.class_sections.values_list("id", flat=True)) if configuration else set()
    teacher_ids = set(configuration.teachers.values_list("id", flat=True)) if configuration else set()
    room_ids = set(configuration.rooms.values_list("id", flat=True)) if configuration else set()
    return timetable, section_ids, teacher_ids, room_ids


@log_exceptions
def _allocation_bulk_setup_context(current_school, form, initial_rows=None, timetable=None, section_ids=None, teacher_ids=None):
    section_ids = section_ids or set()
    teacher_ids = teacher_ids or set()
    class_sections = ClassSection.objects.select_related(
        "class_level",
        "division",
        "default_room",
    ).filter(
        school=current_school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")
    if timetable:
        class_sections = class_sections.filter(timetable=timetable)
    if section_ids:
        class_sections = class_sections.filter(id__in=section_ids)

    capabilities = TeacherSubjectCapability.objects.select_related(
        "teacher",
        "subject",
    ).prefetch_related(
        "class_levels",
        "class_sections",
    ).filter(
        school=current_school,
        timetable=timetable,
        teacher__is_active=True,
        subject__is_active=True,
    ).order_by("teacher__name", "subject__name", "priority")
    if teacher_ids:
        capabilities = capabilities.filter(teacher_id__in=teacher_ids)

    if timetable and teacher_ids:
        form.fields["teacher"].queryset = form.fields["teacher"].queryset.filter(id__in=teacher_ids)
    if timetable and section_ids:
        form.fields["class_section"].queryset = form.fields["class_section"].queryset.filter(id__in=section_ids)
    if timetable:
        form.fields["teacher"].queryset = form.fields["teacher"].queryset.filter(timetable=timetable)
    if timetable:
        form.fields["subject"].queryset = form.fields["subject"].queryset.filter(timetable=timetable)
        form.fields["default_room"].queryset = form.fields["default_room"].queryset.filter(timetable=timetable)

    class_sections_list = list(class_sections)
    section_ids_by_level = {}
    for section in class_sections_list:
        section_ids_by_level.setdefault(section.class_level_id, []).append(section.id)

    capability_options = []
    priority_rank = {"PRIMARY": 1, "SECONDARY": 2, "BACKUP": 3}
    for capability in capabilities:
        section_ids = set(capability.class_sections.values_list("id", flat=True))
        level_ids = set(capability.class_levels.values_list("id", flat=True))

        if not section_ids:
            if level_ids:
                for level_id in level_ids:
                    section_ids.update(section_ids_by_level.get(level_id, []))
            else:
                section_ids.update(section.id for section in class_sections_list)

        capability_options.append({
            "teacher_id": capability.teacher_id,
            "subject_id": capability.subject_id,
            "priority": capability.priority,
            "priority_rank": priority_rank.get(capability.priority, 99),
            "section_ids": sorted(section_ids),
            "requires_double_period": capability.subject.subject_type == "PRACTICAL",
        })

    return {
        "class_sections_json": [
            {
                "id": section.id,
                "name": str(section),
                "class_level_id": section.class_level_id,
                "division_name": section.division.name,
                "room_name": section.default_room.name if section.default_room else "",
            }
            for section in class_sections_list
        ],
        "subjects_json": [
            {
                "id": subject.id,
                "name": subject.name,
                "short_name": subject.short_name,
                "requires_double_period": subject.subject_type == "PRACTICAL",
            }
            for subject in form.fields["subject"].queryset
        ],
        "capabilities_json": capability_options,
        "initial_allocation_rows_json": initial_rows or [],
    }


@log_exceptions
def _teacher_capability_missing_rows(current_school, teacher, academic_year, existing_keys, section_ids=None, timetable=None):
    if not teacher or not academic_year:
        return []

    section_ids = set(section_ids or [])
    class_sections = ClassSection.objects.select_related(
        "class_level",
        "division",
    ).filter(
        school=current_school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    )
    if section_ids:
        class_sections = class_sections.filter(id__in=section_ids)
    class_sections = list(class_sections.order_by("class_level__sort_order", "division__sort_order"))

    section_ids_by_level = defaultdict(list)
    for section in class_sections:
        section_ids_by_level[section.class_level_id].append(section.id)

    sections_by_id = {section.id: section for section in class_sections}
    capabilities = TeacherSubjectCapability.objects.select_related(
        "subject",
    ).prefetch_related(
        "class_levels",
        "class_sections",
    ).filter(
        school=current_school,
        teacher=teacher,
        teacher__is_active=True,
        subject__is_active=True,
    )
    if timetable:
        capabilities = capabilities.filter(timetable=timetable)

    missing_rows = []
    added_keys = set()
    priority_rank = {"PRIMARY": 1, "SECONDARY": 2, "BACKUP": 3}

    for capability in sorted(capabilities, key=lambda item: (priority_rank.get(item.priority, 99), item.subject.name)):
        section_ids = set(capability.class_sections.values_list("id", flat=True))
        level_ids = set(capability.class_levels.values_list("id", flat=True))

        if not section_ids:
            if level_ids:
                for level_id in level_ids:
                    section_ids.update(section_ids_by_level.get(level_id, []))
            else:
                section_ids.update(sections_by_id.keys())

        for section_id in sorted(
            section_ids,
            key=lambda item: (
                sections_by_id[item].class_level.sort_order if item in sections_by_id else 9999,
                sections_by_id[item].division.sort_order if item in sections_by_id else 9999,
            ),
        ):
            section = sections_by_id.get(section_id)
            if not section:
                continue

            subject_section = capability.subject.section_type
            class_section_type = section.class_level.section_type
            if subject_section != "BOTH" and subject_section != class_section_type:
                continue

            key = (section_id, capability.subject_id)
            if key in existing_keys or key in added_keys:
                continue

            missing_rows.append({
                "class_section_id": section_id,
                "subject_id": capability.subject_id,
                "subject_ids": [capability.subject_id],
                "weekly_periods": 5,
                "requires_double_period": capability.subject.subject_type == "PRACTICAL",
                "is_active": True,
                "locked": True,
                "from_capability": True,
            })
            added_keys.add(key)

    return missing_rows


@log_exceptions
def _save_lesson_allocation_rows(request, current_school):
    timetable_id = request.POST.get("timetable_id")
    academic_year_id = request.POST.get("academic_year")
    teacher_id = request.POST.get("teacher")
    timetable = Timetable.objects.filter(pk=timetable_id, school=current_school).first() if timetable_id else None
    if timetable:
        academic_year_id = timetable.academic_year_id
    academic_year = AcademicYear.objects.filter(pk=academic_year_id, school=current_school).first() if academic_year_id else None
    teacher = Teacher.objects.filter(pk=teacher_id, school=current_school, timetable=timetable, is_active=True).first() if teacher_id and timetable else None
    try:
        rows = json.loads(request.POST.get("allocation_rows_json") or "[]")
    except ValueError:
        rows = []

    if not timetable or not academic_year or not teacher:
        messages.warning(request, "Open lesson allocation from a timetable configuration and select a teacher before saving.")
        return None

    if not rows:
        messages.warning(request, "Add at least one lesson allocation row before saving.")
        return None

    created_count = 0
    updated_count = 0
    skipped_count = 0
    capacity_skipped_count = 0
    configuration = TimetableConfiguration.objects.filter(timetable=timetable).first()
    allowed_section_ids = set(configuration.class_sections.values_list("id", flat=True)) if configuration else set()
    allowed_teacher_ids = set(configuration.teachers.values_list("id", flat=True)) if configuration else set()
    allowed_room_ids = set(configuration.rooms.values_list("id", flat=True)) if configuration else set()

    if allowed_teacher_ids and teacher.id not in allowed_teacher_ids:
        messages.warning(request, "Selected teacher is not included in this timetable configuration.")
        return None

    teacher_load = LessonAllocation.objects.filter(
        timetable=timetable,
        teacher=teacher,
        is_active=True,
    ).aggregate(total=Sum("weekly_periods"))["total"] or 0
    teacher_limit = teacher.max_periods_per_week or 0

    with transaction.atomic():
        for row in rows:
            class_section_id = row.get("class_section_id")
            subject_id = row.get("subject_id")
            if not class_section_id or not subject_id:
                skipped_count += 1
                continue

            class_section = ClassSection.objects.filter(
                pk=class_section_id,
                school=current_school,
                timetable=timetable,
                is_active=True,
            ).select_related("default_room").first()
            subject = Subject.objects.filter(
                pk=subject_id,
                school=current_school,
                timetable=timetable,
                is_active=True,
            ).first()

            if not class_section or not subject:
                skipped_count += 1
                continue

            if allowed_section_ids and class_section.id not in allowed_section_ids:
                skipped_count += 1
                continue

            weekly_periods = _positive_int(row.get("weekly_periods"), 1)
            row_is_active = bool(row.get("is_active", True))
            existing = LessonAllocation.objects.filter(
                timetable=timetable,
                class_section=class_section,
                subject=subject,
            ).first()
            existing_teacher_load = existing.weekly_periods if existing and existing.teacher_id == teacher.id and existing.is_active else 0
            active_weekly_periods = weekly_periods if row_is_active else 0
            new_teacher_load = teacher_load - existing_teacher_load + active_weekly_periods

            if row_is_active and teacher_limit and new_teacher_load > teacher_limit:
                capacity_skipped_count += 1
                continue

            defaults = {
                "school": current_school,
                "timetable": timetable,
                "academic_year": academic_year,
                "teacher": teacher,
                "default_room": class_section.default_room if not allowed_room_ids or not class_section.default_room_id or class_section.default_room_id in allowed_room_ids else None,
                "weekly_periods": weekly_periods,
                "requires_double_period": bool(row.get("requires_double_period")),
                "is_active": row_is_active,
            }

            if existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated_count += 1
            else:
                LessonAllocation.objects.create(
                    class_section=class_section,
                    subject=subject,
                    **defaults,
                )
                created_count += 1

            teacher_load = new_teacher_load

    if created_count or updated_count:
        messages.success(
            request,
            f"Lesson allocation saved. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}, Capacity skipped: {capacity_skipped_count}."
        )
        return HttpResponse("""
        <script>
        window.close();
        </script>
        """)

    messages.warning(
        request,
        f"No lesson allocations were saved. Skipped: {skipped_count}, Capacity skipped: {capacity_skipped_count}."
    )
    return None


@log_exceptions
def _filtered_allocations(request):
    allocations = school_queryset(request, LessonAllocation.objects.select_related(
        "school",
        "timetable",
        "academic_year",
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "teacher",
        "default_room",
    )).order_by("-id")

    search_query = request.GET.get("search", "")
    school_filter = request.GET.get("school", "")
    timetable_filter = request.GET.get("timetable", "") or request.GET.get("timetable_id", "")
    academic_year_filter = request.GET.get("academic_year", "")
    status_filter = request.GET.get("status", "")

    if search_query:
        allocations = allocations.filter(
            Q(class_section__class_level__name__icontains=search_query) |
            Q(class_section__division__name__icontains=search_query) |
            Q(subject__name__icontains=search_query) |
            Q(teacher__name__icontains=search_query) |
            Q(default_room__name__icontains=search_query) |
            Q(school__name__icontains=search_query)
        )

    if school_filter:
        allocations = allocations.filter(school_id=school_filter)

    if timetable_filter:
        allocations = allocations.filter(timetable_id=timetable_filter)
    else:
        allocations = allocations.none()

    if academic_year_filter:
        allocations = allocations.filter(academic_year_id=academic_year_filter)

    if status_filter == "active":
        allocations = allocations.filter(is_active=True)

    if status_filter == "inactive":
        allocations = allocations.filter(is_active=False)

    return allocations, search_query, school_filter, timetable_filter, academic_year_filter, status_filter


@login_required
@log_exceptions
def lesson_allocation_list(request):
    current_school = get_current_school(request)
    allocations, search_query, school_filter, timetable_filter, academic_year_filter, status_filter = _filtered_allocations(request)

    total_weekly_periods = 0
    schools = School.objects.none()
    academic_years = AcademicYear.objects.none()
    timetables = Timetable.objects.none()
    selected_timetable = None
    if current_school:
        schools = School.objects.filter(pk=current_school.pk).order_by("name")
        academic_years = AcademicYear.objects.select_related("school").filter(school=current_school).order_by("school__name", "-start_date")
        timetables = Timetable.objects.filter(school=current_school, is_active=True).order_by("-id")
        selected_timetable = timetables.filter(pk=timetable_filter).first() if timetable_filter else None
        total_weekly_periods = allocations.aggregate(total=Sum("weekly_periods"))["total"] or 0

    teacher_groups_map = {}
    for allocation in allocations:
        key = (allocation.timetable_id, allocation.academic_year_id, allocation.teacher_id)
        if key not in teacher_groups_map:
            teacher_groups_map[key] = {
                "timetable": allocation.timetable,
                "academic_year": allocation.academic_year,
                "teacher": allocation.teacher,
                "school": allocation.school,
                "allocation_ids": [],
                "sections": set(),
                "subjects": set(),
                "rooms": set(),
                "weekly_periods": 0,
                "active_count": 0,
                "inactive_count": 0,
                "double_count": 0,
            }

        group = teacher_groups_map[key]
        group["allocation_ids"].append(allocation.id)
        group["sections"].add(str(allocation.class_section))
        group["subjects"].add(allocation.subject.name)
        if allocation.default_room:
            group["rooms"].add(allocation.default_room.name)
        group["weekly_periods"] += allocation.weekly_periods
        group["active_count"] += 1 if allocation.is_active else 0
        group["inactive_count"] += 0 if allocation.is_active else 1
        group["double_count"] += 1 if allocation.requires_double_period else 0

    teacher_allocation_groups = []
    for group in teacher_groups_map.values():
        allocation_ids = group.pop("allocation_ids")
        group["allocation_ids_csv"] = ",".join(str(item) for item in allocation_ids)
        group["allocation_count"] = len(allocation_ids)
        group["sections"] = sorted(group["sections"])
        group["subjects"] = sorted(group["subjects"])
        group["rooms"] = sorted(group["rooms"])
        teacher_allocation_groups.append(group)

    teacher_allocation_groups.sort(
        key=lambda group: (
            group["teacher"].name.lower(),
            str(group["academic_year"].start_date or ""),
            group["academic_year"].id,
        )
    )

    context = {
        "allocations": allocations,
        "teacher_allocation_groups": teacher_allocation_groups,
        "total_allocations": allocations.count(),
        "active_allocations": allocations.filter(is_active=True).count(),
        "double_period_allocations": allocations.filter(requires_double_period=True).count(),
        "total_weekly_periods": total_weekly_periods,
        "active_sections": school_queryset(request, ClassSection.objects.all()).filter(is_active=True).count(),
        "active_subject_capabilities": school_queryset(request, TeacherSubjectCapability.objects.all()).filter(
            teacher__is_active=True,
            subject__is_active=True,
        ).count(),
        "schools": schools,
        "academic_years": academic_years,
        "timetables": timetables,
        "selected_timetable": selected_timetable,
        "current_school": current_school,
        "search_query": search_query,
        "school_filter": school_filter,
        "timetable_filter": timetable_filter,
        "academic_year_filter": academic_year_filter,
        "status_filter": status_filter,
    }

    return render(request, "lesson_allocation_list.html", context)


@login_required
@log_exceptions
def lesson_allocation_export_csv(request):
    allocations, search_query, school_filter, timetable_filter, academic_year_filter, status_filter = _filtered_allocations(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="lesson_allocations.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Timetable",
        "School",
        "Academic Year",
        "Class Section",
        "Subject",
        "Teacher",
        "Default Room",
        "Weekly Periods",
        "Requires Double Period",
        "Status",
    ])

    for allocation in allocations:
        writer.writerow([
            allocation.timetable.name if allocation.timetable else "",
            allocation.school.name,
            allocation.academic_year.name,
            str(allocation.class_section),
            allocation.subject.name,
            allocation.teacher.name,
            allocation.default_room.name if allocation.default_room else "",
            allocation.weekly_periods,
            "Yes" if allocation.requires_double_period else "No",
            "Active" if allocation.is_active else "Inactive",
        ])

    return response


@login_required
@log_exceptions
def lesson_allocation_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    timetable, section_ids, teacher_ids, _room_ids = _timetable_scope_from_request(request, current_school)
    if not timetable:
        messages.warning(request, "Create lesson allocations from a specific timetable configuration.")
        return redirect("timetable_list")

    if request.method == "POST":
        response = _save_lesson_allocation_rows(request, current_school)
        if response:
            return response

    initial = {}
    academic_year_id = request.GET.get("academic_year_id")
    if timetable:
        initial["timetable"] = timetable
        initial["academic_year"] = timetable.academic_year
    elif academic_year_id:
        academic_year = AcademicYear.objects.filter(pk=academic_year_id, school=current_school).first()
        if academic_year:
            initial["academic_year"] = academic_year

    form = LessonAllocationForm(current_school=current_school, initial=initial)
    setup_context = _allocation_bulk_setup_context(
        current_school,
        form,
        timetable=timetable,
        section_ids=section_ids,
        teacher_ids=teacher_ids,
    )

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": "Create Lesson Allocation",
        "subtitle": f"Create allocations for {timetable.name}." if timetable else "Select a teacher and allocation rows are prepared from Subject & Teacher Capabilities.",
        "button_text": "Save Allocations",
        "bulk_create": True,
        "source_timetable": timetable,
        **setup_context,
    })


@login_required
@log_exceptions
def lesson_allocation_update(request, pk):
    allocation = get_school_object_or_404(request, LessonAllocation.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = LessonAllocationForm(request.POST, instance=allocation, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Lesson allocation updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = LessonAllocationForm(instance=allocation, current_school=current_school)

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": "Update Lesson Allocation",
        "subtitle": "Update subject, teacher, room and weekly period details.",
        "button_text": "Update Allocation",
    })


@login_required
@log_exceptions
def lesson_allocation_teacher_update(request, teacher_id):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    teacher = get_object_or_404(Teacher, pk=teacher_id, school=current_school, is_active=True)
    timetable_id = request.GET.get("timetable_id") or request.POST.get("timetable_id")
    timetable = Timetable.objects.filter(pk=timetable_id, school=current_school).first() if timetable_id else None
    if not timetable:
        messages.warning(request, "Update lesson allocations from a specific timetable configuration.")
        return redirect("timetable_list")

    academic_year = timetable.academic_year
    configuration = TimetableConfiguration.objects.filter(timetable=timetable).first()
    section_ids = set(configuration.class_sections.values_list("id", flat=True)) if configuration else set()

    if request.method == "POST":
        response = _save_lesson_allocation_rows(request, current_school)
        if response:
            return response

    allocations = LessonAllocation.objects.select_related(
        "class_section",
        "class_section__division",
        "class_section__default_room",
        "subject",
        "default_room",
    ).filter(
        school=current_school,
        timetable=timetable,
        teacher=teacher,
    )

    allocation_list = list(allocations.order_by("class_section__class_level__sort_order", "class_section__division__sort_order", "subject__name"))
    initial_rows = [
        {
            "class_section_id": allocation.class_section_id,
            "subject_id": allocation.subject_id,
            "subject_ids": [allocation.subject_id],
            "weekly_periods": allocation.weekly_periods,
            "requires_double_period": allocation.requires_double_period,
            "is_active": allocation.is_active,
            "locked": True,
        }
        for allocation in allocation_list
    ]
    existing_keys = {(allocation.class_section_id, allocation.subject_id) for allocation in allocation_list}
    initial_rows.extend(_teacher_capability_missing_rows(current_school, teacher, academic_year, existing_keys, section_ids=section_ids, timetable=timetable))

    form = LessonAllocationForm(
        current_school=current_school,
        initial={
            "timetable": timetable,
            "academic_year": academic_year,
            "teacher": teacher,
        },
    )
    teacher_ids = {teacher.id}
    setup_context = _allocation_bulk_setup_context(
        current_school,
        form,
        initial_rows=initial_rows,
        timetable=timetable,
        section_ids=section_ids,
        teacher_ids=teacher_ids,
    )

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": f"Update Lesson Allocation - {teacher.name}",
        "subtitle": "Update this teacher's allocations in one panel.",
        "button_text": "Update Allocations",
        "bulk_create": True,
        "bulk_update": True,
        "source_timetable": timetable,
        **setup_context,
    })


@login_required
@require_POST
@log_exceptions
def lesson_allocation_delete(request, pk):
    allocation = get_school_object_or_404(request, LessonAllocation.objects.all(), pk=pk)
    name = str(allocation)
    allocation.delete()
    messages.success(request, f"Lesson allocation '{name}' deleted successfully.")
    return redirect("lesson_allocation_list")


@login_required
@require_POST
@log_exceptions
def lesson_allocation_bulk_delete(request):
    selected_ids = []
    for value in request.POST.getlist("allocation_ids"):
        selected_ids.extend([item for item in str(value).split(",") if item])
    if not selected_ids:
        messages.warning(request, "Select at least one lesson allocation to delete.")
        return redirect("lesson_allocation_list")

    allocations = school_queryset(
        request,
        LessonAllocation.objects.filter(id__in=selected_ids),
    )
    deleted_count = allocations.count()
    allocations.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected lesson allocation(s).")
    else:
        messages.info(request, "No lesson allocations were deleted.")

    return redirect("lesson_allocation_list")


@login_required
@require_POST
@log_exceptions
def lesson_allocation_toggle_status(request, pk):
    allocation = get_school_object_or_404(request, LessonAllocation.objects.all(), pk=pk)
    allocation.is_active = not allocation.is_active
    allocation.save(update_fields=["is_active"])

    status = "activated" if allocation.is_active else "deactivated"
    messages.success(request, f"Lesson allocation '{allocation}' {status} successfully.")
    return redirect("lesson_allocation_list")


@login_required
@require_POST
@log_exceptions
def lesson_allocation_quick_create(request):
    current_school = get_current_school(request)
    if not current_school:
        messages.error(request, "No active school is linked with your session.")
        return redirect("lesson_allocation_list")

    school_id = current_school.id if current_school else request.POST.get("school")
    academic_year_id = request.POST.get("academic_year")
    timetable, timetable_section_ids, timetable_teacher_ids, timetable_room_ids = _timetable_scope_from_request(request, current_school)
    if not timetable:
        messages.warning(request, "Open a timetable configuration before quick creating lesson allocations.")
        return redirect("timetable_list")

    if timetable:
        school_id = timetable.school_id
        academic_year_id = timetable.academic_year_id
    weekly_periods = request.POST.get("weekly_periods") or 5
    include_backup = request.POST.get("include_backup") == "on"

    try:
        weekly_periods = max(1, int(weekly_periods))
    except ValueError:
        weekly_periods = 5

    if not school_id or not academic_year_id:
        messages.error(request, "Select school and academic year before quick creating allocations.")
        return redirect("lesson_allocation_list")

    school = get_object_or_404(School, pk=school_id, school_users__user=request.user, school_users__is_active=True)
    academic_year = get_object_or_404(AcademicYear, pk=academic_year_id, school=school)

    capabilities = TeacherSubjectCapability.objects.select_related(
        "school",
        "teacher",
        "subject",
    ).prefetch_related("class_levels", "class_sections").filter(
        school=school,
        timetable=timetable,
        teacher__is_active=True,
        subject__is_active=True,
    ).order_by("subject__name", "priority", "teacher__name")

    if not include_backup:
        capabilities = capabilities.exclude(priority="BACKUP")

    if timetable_teacher_ids:
        capabilities = capabilities.filter(teacher_id__in=timetable_teacher_ids)

    priority_order = {"PRIMARY": 0, "SECONDARY": 1, "BACKUP": 2}
    capabilities = sorted(
        capabilities,
        key=lambda capability: (
            0 if capability.class_sections.all() else 1,
            capability.subject.name,
            priority_order.get(capability.priority, 99),
            capability.teacher.name,
        )
    )

    class_sections = ClassSection.objects.select_related(
        "school",
        "class_level",
        "division",
        "default_room",
    ).filter(
        school=school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")
    if timetable_section_ids:
        class_sections = class_sections.filter(id__in=timetable_section_ids)

    created_count = 0
    skipped_count = 0
    capacity_skipped_count = 0
    seen_subject_sections = set()
    teacher_weekly_loads = {
        teacher_id: total or 0
        for teacher_id, total in LessonAllocation.objects.filter(
            school=school,
            timetable=timetable,
            academic_year=academic_year,
            is_active=True,
        ).values_list("teacher_id").annotate(total=Sum("weekly_periods"))
    }

    for capability in capabilities:
        capability_sections = set(capability.class_sections.values_list("id", flat=True))
        capability_levels = set(capability.class_levels.values_list("id", flat=True))

        for section in class_sections:
            if capability_sections and section.id not in capability_sections:
                continue

            if not capability_sections and capability_levels and section.class_level_id not in capability_levels:
                continue

            subject_section = capability.subject.section_type
            class_section_type = section.class_level.section_type
            if subject_section != "BOTH" and subject_section != class_section_type:
                continue

            subject_section_key = (academic_year.id, section.id, capability.subject_id)
            if subject_section_key in seen_subject_sections:
                skipped_count += 1
                continue
            seen_subject_sections.add(subject_section_key)

            allocation_exists = LessonAllocation.objects.filter(
                timetable=timetable,
                class_section=section,
                subject=capability.subject,
            ).exists()

            if allocation_exists:
                skipped_count += 1
                continue

            teacher_limit = capability.teacher.max_periods_per_week or 0
            teacher_load = teacher_weekly_loads.get(capability.teacher_id, 0)
            if teacher_limit and teacher_load + weekly_periods > teacher_limit:
                capacity_skipped_count += 1
                continue

            default_room = section.default_room
            if timetable_room_ids and (not default_room or default_room.id not in timetable_room_ids):
                default_room = None

            LessonAllocation.objects.create(
                school=school,
                timetable=timetable,
                academic_year=academic_year,
                class_section=section,
                subject=capability.subject,
                teacher=capability.teacher,
                default_room=default_room,
                weekly_periods=weekly_periods,
                requires_double_period=capability.subject.subject_type == "PRACTICAL",
                is_active=True,
            )
            teacher_weekly_loads[capability.teacher_id] = teacher_load + weekly_periods
            created_count += 1

    if created_count:
        messages.success(
            request,
            f"Quick-created {created_count} lesson allocation(s). {skipped_count} duplicate or lower-priority option(s) were skipped. {capacity_skipped_count} option(s) were skipped because teacher weekly limits would be exceeded."
        )
    else:
        messages.info(
            request,
            f"No new lesson allocations were needed. {skipped_count} matching allocation(s) already exist or were skipped. {capacity_skipped_count} option(s) were skipped because teacher weekly limits would be exceeded."
        )

    if timetable:
        return redirect(f"{reverse('timetable_config', kwargs={'pk': timetable.pk})}#allocationHealth")

    return redirect("lesson_allocation_list")
