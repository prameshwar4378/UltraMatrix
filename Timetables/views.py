import csv

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from Academic.models import AcademicYear
from Schools.models import School
from Subjects.models import TeacherSubjectCapability
from Timetables.models import ClassSection, LessonAllocation
from .forms import LessonAllocationForm


def _filtered_allocations(request):
    allocations = LessonAllocation.objects.select_related(
        "school",
        "academic_year",
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "teacher",
        "default_room",
    ).all().order_by("-id")

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


def lesson_allocation_list(request):
    allocations, search_query, school_filter, academic_year_filter, status_filter = _filtered_allocations(request)

    total_weekly_periods = LessonAllocation.objects.aggregate(
        total=Sum("weekly_periods")
    )["total"] or 0

    context = {
        "allocations": allocations,
        "total_allocations": LessonAllocation.objects.count(),
        "active_allocations": LessonAllocation.objects.filter(is_active=True).count(),
        "double_period_allocations": LessonAllocation.objects.filter(requires_double_period=True).count(),
        "total_weekly_periods": total_weekly_periods,
        "active_sections": ClassSection.objects.filter(is_active=True).count(),
        "active_subject_capabilities": TeacherSubjectCapability.objects.filter(
            teacher__is_active=True,
            subject__is_active=True,
        ).count(),
        "schools": School.objects.all().order_by("name"),
        "academic_years": AcademicYear.objects.select_related("school").all().order_by("school__name", "-start_date"),
        "search_query": search_query,
        "school_filter": school_filter,
        "academic_year_filter": academic_year_filter,
        "status_filter": status_filter,
    }

    return render(request, "lesson_allocation_list.html", context)


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


def lesson_allocation_create(request):
    if request.method == "POST":
        form = LessonAllocationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Lesson allocation created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = LessonAllocationForm()

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": "Create Lesson Allocation",
        "subtitle": "Assign subject, teacher and room to a class section.",
        "button_text": "Save Allocation",
    })


def lesson_allocation_update(request, pk):
    allocation = get_object_or_404(LessonAllocation, pk=pk)

    if request.method == "POST":
        form = LessonAllocationForm(request.POST, instance=allocation)

        if form.is_valid():
            form.save()
            messages.success(request, "Lesson allocation updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = LessonAllocationForm(instance=allocation)

    return render(request, "lesson_allocation_form.html", {
        "form": form,
        "title": "Update Lesson Allocation",
        "subtitle": "Update subject, teacher, room and weekly period details.",
        "button_text": "Update Allocation",
    })


@require_POST
def lesson_allocation_delete(request, pk):
    allocation = get_object_or_404(LessonAllocation, pk=pk)
    name = str(allocation)
    allocation.delete()
    messages.success(request, f"Lesson allocation '{name}' deleted successfully.")
    return redirect("lesson_allocation_list")


@require_POST
def lesson_allocation_toggle_status(request, pk):
    allocation = get_object_or_404(LessonAllocation, pk=pk)
    allocation.is_active = not allocation.is_active
    allocation.save(update_fields=["is_active"])

    status = "activated" if allocation.is_active else "deactivated"
    messages.success(request, f"Lesson allocation '{allocation}' {status} successfully.")
    return redirect("lesson_allocation_list")


@require_POST
def lesson_allocation_quick_create(request):
    school_id = request.POST.get("school")
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

    school = get_object_or_404(School, pk=school_id)
    academic_year = get_object_or_404(AcademicYear, pk=academic_year_id, school=school)

    capabilities = TeacherSubjectCapability.objects.select_related(
        "school",
        "teacher",
        "subject",
    ).prefetch_related("class_levels").filter(
        school=school,
        teacher__is_active=True,
        subject__is_active=True,
    ).order_by("subject__name", "priority", "teacher__name")

    if not include_backup:
        capabilities = capabilities.exclude(priority="BACKUP")

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
    seen_subject_sections = set()

    for capability in capabilities:
        capability_levels = set(capability.class_levels.values_list("id", flat=True))

        for section in class_sections:
            if capability_levels and section.class_level_id not in capability_levels:
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
            created_count += 1

    if created_count:
        messages.success(
            request,
            f"Quick-created {created_count} lesson allocation(s). {skipped_count} duplicate or lower-priority option(s) were skipped."
        )
    else:
        messages.info(
            request,
            f"No new lesson allocations were needed. {skipped_count} matching allocation(s) already exist or were skipped."
        )

    return redirect("lesson_allocation_list")
