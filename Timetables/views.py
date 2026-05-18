import csv
import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from Academic.models import AcademicYear
from Schools.models import School
from Subjects.models import Subject, TeacherSubjectCapability
from Timetables.models import ClassSection, LessonAllocation
from Teachers.models import Teacher
from .forms import LessonAllocationForm
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def _positive_int(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, number)


@log_exceptions
def _allocation_bulk_setup_context(current_school, form, initial_rows=None):
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
    capabilities = TeacherSubjectCapability.objects.select_related(
        "teacher",
        "subject",
    ).prefetch_related(
        "class_levels",
        "class_sections",
    ).filter(
        school=current_school,
        teacher__is_active=True,
        subject__is_active=True,
    ).order_by("teacher__name", "subject__name", "priority")

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
def _teacher_capability_missing_rows(current_school, teacher, academic_year, existing_keys):
    if not teacher or not academic_year:
        return []

    class_sections = list(ClassSection.objects.select_related(
        "class_level",
        "division",
    ).filter(
        school=current_school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order"))

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
    academic_year_id = request.POST.get("academic_year")
    teacher_id = request.POST.get("teacher")
    academic_year = AcademicYear.objects.filter(pk=academic_year_id, school=current_school).first() if academic_year_id else None
    teacher = Teacher.objects.filter(pk=teacher_id, school=current_school, is_active=True).first() if teacher_id else None
    try:
        rows = json.loads(request.POST.get("allocation_rows_json") or "[]")
    except ValueError:
        rows = []

    if not academic_year or not teacher:
        messages.warning(request, "Select academic year and teacher before saving lesson allocations.")
        return None

    if not rows:
        messages.warning(request, "Add at least one lesson allocation row before saving.")
        return None

    created_count = 0
    updated_count = 0
    skipped_count = 0
    capacity_skipped_count = 0
    teacher_load = LessonAllocation.objects.filter(
        academic_year=academic_year,
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
                is_active=True,
            ).select_related("default_room").first()
            subject = Subject.objects.filter(
                pk=subject_id,
                school=current_school,
                is_active=True,
            ).first()

            if not class_section or not subject:
                skipped_count += 1
                continue

            weekly_periods = _positive_int(row.get("weekly_periods"), 1)
            row_is_active = bool(row.get("is_active", True))
            existing = LessonAllocation.objects.filter(
                academic_year=academic_year,
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
                "teacher": teacher,
                "default_room": class_section.default_room,
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
                    academic_year=academic_year,
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

    if academic_year_filter:
        allocations = allocations.filter(academic_year_id=academic_year_filter)

    if status_filter == "active":
        allocations = allocations.filter(is_active=True)

    if status_filter == "inactive":
        allocations = allocations.filter(is_active=False)

    return allocations, search_query, school_filter, academic_year_filter, status_filter


@login_required
@log_exceptions
def lesson_allocation_list(request):
    current_school = get_current_school(request)
    allocations, search_query, school_filter, academic_year_filter, status_filter = _filtered_allocations(request)

    total_weekly_periods = 0
    schools = School.objects.none()
    academic_years = AcademicYear.objects.none()
    if current_school:
        schools = School.objects.filter(pk=current_school.pk).order_by("name")
        academic_years = AcademicYear.objects.select_related("school").filter(school=current_school).order_by("school__name", "-start_date")
        total_weekly_periods = allocations.aggregate(total=Sum("weekly_periods"))["total"] or 0

    teacher_groups_map = {}
    for allocation in allocations:
        key = (allocation.academic_year_id, allocation.teacher_id)
        if key not in teacher_groups_map:
            teacher_groups_map[key] = {
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
        "current_school": current_school,
        "search_query": search_query,
        "school_filter": school_filter,
        "academic_year_filter": academic_year_filter,
        "status_filter": status_filter,
    }

    return render(request, "lesson_allocation_list.html", context)


@login_required
@log_exceptions
def lesson_allocation_export_csv(request):
    allocations, search_query, school_filter, academic_year_filter, status_filter = _filtered_allocations(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="lesson_allocations.csv"'

    writer = csv.writer(response)
    writer.writerow([
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
    if request.method == "POST":
        response = _save_lesson_allocation_rows(request, current_school)
        if response:
            return response

    form = LessonAllocationForm(current_school=current_school)
    setup_context = _allocation_bulk_setup_context(current_school, form)

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": "Create Lesson Allocation",
        "subtitle": "Select a teacher and allocation rows are prepared from Subject & Teacher Capabilities.",
        "button_text": "Save Allocations",
        "bulk_create": True,
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
    academic_year_id = request.GET.get("academic_year_id") or request.POST.get("academic_year")
    academic_year = AcademicYear.objects.filter(pk=academic_year_id, school=current_school).first() if academic_year_id else None

    if request.method == "POST":
        response = _save_lesson_allocation_rows(request, current_school)
        if response:
            return response

    if not academic_year:
        academic_year = AcademicYear.objects.filter(school=current_school).order_by("-start_date", "-id").first()

    allocations = LessonAllocation.objects.select_related(
        "class_section",
        "class_section__division",
        "class_section__default_room",
        "subject",
        "default_room",
    ).filter(
        school=current_school,
        teacher=teacher,
    )
    if academic_year:
        allocations = allocations.filter(academic_year=academic_year)

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
    initial_rows.extend(_teacher_capability_missing_rows(current_school, teacher, academic_year, existing_keys))

    form = LessonAllocationForm(
        current_school=current_school,
        initial={
            "academic_year": academic_year,
            "teacher": teacher,
        },
    )
    setup_context = _allocation_bulk_setup_context(current_school, form, initial_rows=initial_rows)

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": f"Update Lesson Allocation - {teacher.name}",
        "subtitle": "Update this teacher's allocations in one panel.",
        "button_text": "Update Allocations",
        "bulk_create": True,
        "bulk_update": True,
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
        teacher__is_active=True,
        subject__is_active=True,
    ).order_by("subject__name", "priority", "teacher__name")

    if not include_backup:
        capabilities = capabilities.exclude(priority="BACKUP")

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

    created_count = 0
    skipped_count = 0
    capacity_skipped_count = 0
    seen_subject_sections = set()
    teacher_weekly_loads = {
        teacher_id: total or 0
        for teacher_id, total in LessonAllocation.objects.filter(
            school=school,
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
                academic_year=academic_year,
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

            LessonAllocation.objects.create(
                school=school,
                academic_year=academic_year,
                class_section=section,
                subject=capability.subject,
                teacher=capability.teacher,
                default_room=section.default_room,
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

    return redirect("lesson_allocation_list")
