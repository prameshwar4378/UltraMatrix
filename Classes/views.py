import json

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.views.decorators.http import require_POST

from .models import ClassLevel, Division
from .forms import ClassLevelForm, DivisionForm, ClassSectionForm
from Timetables.models import ClassSection, LessonAllocation, TimetableEntry
from Rooms.models import Room
from Schools.models import School
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@login_required
@log_exceptions
def class_setup_list(request):
    current_school = get_current_school(request)
    search_query = request.GET.get("search", "")
    section_filter = request.GET.get("section_type", "")
    status_filter = request.GET.get("status", "")

    class_sections = school_queryset(request, ClassSection.objects.select_related(
        "school",
        "class_level",
        "division",
        "class_teacher",
        "default_room"
    )).order_by("class_level__sort_order", "division__sort_order")

    class_levels = school_queryset(request, ClassLevel.objects.select_related("school")).order_by("school__name", "sort_order", "name")
    divisions = school_queryset(request, Division.objects.select_related("school")).order_by("school__name", "sort_order", "name")
    rooms = school_queryset(request, Room.objects.select_related("school")).order_by("room_type", "name")
    active_class_levels = class_levels.filter(is_active=True)
    active_divisions = divisions.filter(is_active=True)
    active_rooms = rooms.filter(is_active=True)
    auto_expected_sections = active_class_levels.count() * active_divisions.count()
    existing_section_pairs = set()
    if current_school:
        existing_section_pairs = set(ClassSection.objects.filter(
            school=current_school,
            class_level__is_active=True,
            division__is_active=True,
        ).values_list("class_level_id", "division_id"))
    auto_missing_sections = sum(
        1
        for class_level in active_class_levels
        for division in active_divisions
        if (class_level.id, division.id) not in existing_section_pairs
    )
    sections_without_rooms = class_sections.filter(default_room__isnull=True).count()

    if search_query:
        class_sections = class_sections.filter(
            Q(class_level__name__icontains=search_query) |
            Q(division__name__icontains=search_query) |
            Q(school__name__icontains=search_query)
        )

    if section_filter:
        class_sections = class_sections.filter(class_level__section_type=section_filter)

    if status_filter == "active":
        class_sections = class_sections.filter(is_active=True)

    if status_filter == "inactive":
        class_sections = class_sections.filter(is_active=False)

    for class_level in class_levels:
        related_sections = ClassSection.objects.filter(school=class_level.school, class_level=class_level)
        class_level.impact_sections = related_sections.count()
        class_level.impact_allocations = LessonAllocation.objects.filter(class_section__in=related_sections).count()
        class_level.impact_entries = TimetableEntry.objects.filter(class_section__in=related_sections).count()

    for class_section in class_sections:
        class_section.impact_allocations = LessonAllocation.objects.filter(class_section=class_section).count()
        class_section.impact_entries = TimetableEntry.objects.filter(class_section=class_section).count()

    context = {
        "class_sections": class_sections,
        "class_levels": class_levels,
        "divisions": divisions,
        "rooms": rooms[:8],
        "total_rooms": rooms.count(),
        "active_rooms": active_rooms.count(),
        "sections_without_rooms": sections_without_rooms,
        "divisions_setup_done": active_divisions.exists(),
        "class_levels_setup_done": active_class_levels.exists(),
        "sections_setup_done": auto_expected_sections > 0 and auto_missing_sections == 0,
        "rooms_setup_done": active_rooms.exists(),
        "total_sections": class_sections.count(),
        "active_sections": class_sections.filter(is_active=True).count(),
        "primary_sections": class_sections.filter(class_level__section_type="PRIMARY").count(),
        "secondary_sections": class_sections.filter(class_level__section_type="SECONDARY").count(),
        "total_schools": 1 if current_school else 0,
        "auto_expected_sections": auto_expected_sections,
        "auto_missing_sections": auto_missing_sections,
        "search_query": search_query,
        "section_filter": section_filter,
        "status_filter": status_filter,
    }

    return render(request, "class_setup_list.html", context)

#import HttpResponse for returning a simple response to close the popup after form submission
from django.http import HttpResponse
from django.contrib import messages


@log_exceptions
def _default_class_levels():
    return [
        {"name": "1st", "short_name": "1st", "sort_order": 1, "section_type": "PRIMARY"},
        {"name": "2nd", "short_name": "2nd", "sort_order": 2, "section_type": "PRIMARY"},
        {"name": "3rd", "short_name": "3rd", "sort_order": 3, "section_type": "PRIMARY"},
        {"name": "4th", "short_name": "4th", "sort_order": 4, "section_type": "PRIMARY"},
        {"name": "5th", "short_name": "5th", "sort_order": 5, "section_type": "PRIMARY"},
        {"name": "6th", "short_name": "6th", "sort_order": 6, "section_type": "SECONDARY"},
        {"name": "7th", "short_name": "7th", "sort_order": 7, "section_type": "SECONDARY"},
        {"name": "8th", "short_name": "8th", "sort_order": 8, "section_type": "SECONDARY"},
        {"name": "9th", "short_name": "9th", "sort_order": 9, "section_type": "SECONDARY"},
        {"name": "10th", "short_name": "10th", "sort_order": 10, "section_type": "SECONDARY"},
    ]


@log_exceptions
def _positive_int(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


@login_required
@require_POST
@log_exceptions
def class_sections_quick_create(request):
    current_school = get_current_school(request)
    if not current_school:
        messages.error(request, "No active school is linked with your session.")
        return redirect("class_setup_list")

    class_levels = ClassLevel.objects.filter(
        school=current_school,
        is_active=True,
    ).order_by("sort_order", "name")
    divisions = Division.objects.filter(
        school=current_school,
        is_active=True,
    ).order_by("sort_order", "name")

    if not class_levels.exists() or not divisions.exists():
        messages.warning(request, "Add active class levels and active divisions first, then use Quick Classes.")
        return redirect("class_setup_list")

    created_count = 0
    skipped_count = 0
    room_created_count = 0
    room_skipped_count = 0
    assigned_room_count = 0

    with transaction.atomic():
        for class_level in class_levels:
            for division in divisions:
                short_level = class_level.short_name or class_level.name
                room_name = f"{short_level}-{division.name}"[:100]
                old_room_name = f"{class_level.name} {division.name}"

                room = Room.objects.filter(
                    Q(name__iexact=room_name) |
                    Q(short_name__iexact=room_name[:30]) |
                    Q(name__iexact=old_room_name),
                    school=current_school,
                    room_type="CLASSROOM",
                ).first()

                if room:
                    room_skipped_count += 1
                else:
                    room = Room.objects.create(
                        school=current_school,
                        name=room_name,
                        short_name=room_name[:30],
                        room_type="CLASSROOM",
                        capacity=40,
                        is_active=True,
                    )
                    room_created_count += 1

                existing_section = ClassSection.objects.filter(
                    school=current_school,
                    class_level=class_level,
                    division=division,
                ).first()

                if existing_section:
                    skipped_count += 1
                    if existing_section.default_room_id is None:
                        existing_section.default_room = room
                        existing_section.save(update_fields=["default_room"])
                        assigned_room_count += 1
                    continue

                ClassSection.objects.create(
                    school=current_school,
                    class_level=class_level,
                    division=division,
                    default_room=room,
                    capacity=0,
                    is_active=True,
                )
                created_count += 1
                assigned_room_count += 1

    if created_count:
        messages.success(
            request,
            f"Quick-created {created_count} class section(s) and {room_created_count} classroom(s). {skipped_count} existing section(s) and {room_skipped_count} existing classroom(s) were skipped. Assigned default rooms to {assigned_room_count} section(s)."
        )
    else:
        messages.info(
            request,
            f"No new class sections were needed. {skipped_count} matching section(s) already exist. Created {room_created_count} missing classroom(s) and assigned default rooms to {assigned_room_count} section(s)."
        )

    return redirect("class_setup_list")

@login_required
@log_exceptions
def class_level_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        if request.POST.get("class_levels_json"):
            class_levels_data = json.loads(request.POST.get("class_levels_json") or "[]")
            created_count = 0
            skipped_count = 0

            with transaction.atomic():
                for class_data in class_levels_data:
                    name = str(class_data.get("name") or "").strip()
                    section_type = class_data.get("section_type") or "PRIMARY"
                    valid_section_types = {choice[0] for choice in ClassLevel.SECTION_CHOICES}
                    if section_type not in valid_section_types:
                        section_type = "PRIMARY"

                    if not name:
                        skipped_count += 1
                        continue

                    if ClassLevel.objects.filter(school=current_school, name__iexact=name).exists():
                        skipped_count += 1
                        continue

                    ClassLevel.objects.create(
                        school=current_school,
                        name=name,
                        short_name=str(class_data.get("short_name") or "").strip(),
                        sort_order=_positive_int(class_data.get("sort_order"), created_count + skipped_count + 1),
                        section_type=section_type,
                        is_active=bool(class_data.get("is_active", True)),
                    )
                    created_count += 1

            if created_count:
                messages.success(request, f"Created {created_count} class level(s). {skipped_count} blank or duplicate row(s) were skipped.")
            else:
                messages.info(request, f"No class levels were created. {skipped_count} row(s) were blank or already existed.")

            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)

        form = ClassLevelForm(request.POST, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Class level created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassLevelForm(current_school=current_school)

    return render(request, "class_level_form.html", {
        "form": form,
        "title": "Create Class Level",
        "subtitle": "Add Nursery, LKG, UKG, Class 1 to Class 10.",
        "button_text": "Save Class Level",
        "bulk_create": True,
        "initial_class_levels_json": _default_class_levels(),
    })


@login_required
@log_exceptions
def class_level_update(request, pk):
    class_level = get_school_object_or_404(request, ClassLevel.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = ClassLevelForm(request.POST, instance=class_level, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Class level updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassLevelForm(instance=class_level, current_school=current_school)

    return render(request, "class_level_form.html", {
        "form": form,
        "title": "Update Class Level",
        "subtitle": "Update class level information and section grouping.",
        "button_text": "Update Class Level",
    })


@login_required
@require_POST
@log_exceptions
def class_level_delete(request, pk):
    class_level = get_school_object_or_404(request, ClassLevel.objects.all(), pk=pk)
    name = class_level.name
    class_level.delete()
    messages.success(request, f"Class level '{name}' deleted successfully.")
    return redirect("class_setup_list")


@login_required
@require_POST
@log_exceptions
def class_level_bulk_delete(request):
    selected_ids = request.POST.getlist("class_level_ids")
    if not selected_ids:
        messages.warning(request, "Select at least one class level to delete.")
        return redirect("class_setup_list")

    class_levels = school_queryset(
        request,
        ClassLevel.objects.filter(id__in=selected_ids),
    )
    deleted_count = class_levels.count()
    class_levels.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected class level(s).")
    else:
        messages.info(request, "No class levels were deleted.")

    return redirect("class_setup_list")


@login_required
@log_exceptions
def division_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = DivisionForm(request.POST, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Division created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = DivisionForm(current_school=current_school)

    return render(request, "division_form.html", {
        "form": form,
        "title": "Create Division",
        "subtitle": "Add divisions like A, B, C or D.",
        "button_text": "Save Division",
    })


@login_required
@log_exceptions
def division_update(request, pk):
    division = get_school_object_or_404(request, Division.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = DivisionForm(request.POST, instance=division, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Division updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = DivisionForm(instance=division, current_school=current_school)

    return render(request, "division_form.html", {
        "form": form,
        "title": "Update Division",
        "subtitle": "Update division name, order and active status.",
        "button_text": "Update Division",
    })


@login_required
@require_POST
@log_exceptions
def division_delete(request, pk):
    division = get_school_object_or_404(request, Division.objects.all(), pk=pk)
    name = division.name
    division.delete()
    messages.success(request, f"Division '{name}' deleted successfully.")
    return redirect("class_setup_list")


@login_required
@log_exceptions
def class_section_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = ClassSectionForm(request.POST, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Class section created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassSectionForm(current_school=current_school)

    return render(request, "class_section_form.html", {
        "form": form,
        "title": "Create Class Section",
        "subtitle": "Create actual class section like Class 1A, Class 10B.",
        "button_text": "Save Class Section",
    })


@login_required
@log_exceptions
def class_section_update(request, pk):
    class_section = get_school_object_or_404(request, ClassSection.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = ClassSectionForm(request.POST, instance=class_section, current_school=current_school)
        if form.is_valid():
            form.save()
            messages.success(request, "Class section updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassSectionForm(instance=class_section, current_school=current_school)

    return render(request, "class_section_form.html", {
        "form": form,
        "title": "Update Class Section",
        "subtitle": "Update class section, teacher, room, capacity and status.",
        "button_text": "Update Class Section",
    })


@login_required
@require_POST
@log_exceptions
def class_section_delete(request, pk):
    class_section = get_school_object_or_404(request, ClassSection.objects.all(), pk=pk)
    name = str(class_section)
    class_section.delete()
    messages.success(request, f"Class section '{name}' deleted successfully.")
    return redirect("class_setup_list")


@login_required
@require_POST
@log_exceptions
def class_section_bulk_delete(request):
    selected_ids = request.POST.getlist("class_section_ids")
    if not selected_ids:
        messages.warning(request, "Select at least one class section to delete.")
        return redirect("class_setup_list")

    class_sections = school_queryset(
        request,
        ClassSection.objects.filter(id__in=selected_ids),
    )
    deleted_count = class_sections.count()
    class_sections.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected class section(s).")
    else:
        messages.info(request, "No class sections were deleted.")

    return redirect("class_setup_list")
