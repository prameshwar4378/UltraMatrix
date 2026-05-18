from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Room
from .forms import RoomForm
from Classes.models import ClassLevel, Division
from Schools.models import School
from Timetables.models import ClassSection, LessonAllocation, TimetableEntry
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions

@login_required
@log_exceptions
def room_list(request):
    current_school = get_current_school(request)

    # Timetable.objects.filter(is_active=True).delete()


    rooms = school_queryset(
        request,
        Room.objects.select_related("school"),
    ).order_by("-id")

    search_query = request.GET.get("search", "")
    room_type_filter = request.GET.get("room_type", "")
    status_filter = request.GET.get("status", "")

    if search_query:
        rooms = rooms.filter(
            Q(name__icontains=search_query) |
            Q(short_name__icontains=search_query) |
            Q(school__name__icontains=search_query) |
            Q(school__school_code__icontains=search_query)
        )

    if room_type_filter:
        rooms = rooms.filter(room_type=room_type_filter)

    if status_filter == "active":
        rooms = rooms.filter(is_active=True)

    if status_filter == "inactive":
        rooms = rooms.filter(is_active=False)

    schools = School.objects.none()
    if current_school:
        schools = School.objects.filter(pk=current_school.pk).order_by("name")

    auto_room_targets = []
    for school in schools:
        class_count = ClassLevel.objects.filter(school=school, is_active=True).count()
        division_count = Division.objects.filter(school=school, is_active=True).count()
        expected_count = class_count * division_count
        if expected_count:
            auto_room_targets.append({
                "school": school,
                "expected_count": expected_count,
            })

    for room in rooms:
        room.impact_sections = ClassSection.objects.filter(default_room=room).count()
        room.impact_allocations = LessonAllocation.objects.filter(default_room=room).count()
        room.impact_entries = TimetableEntry.objects.filter(room=room).count()

    context = {
        "rooms": rooms,
        "total_rooms": rooms.count(),
        "active_rooms": rooms.filter(is_active=True).count(),
        "classrooms": rooms.filter(room_type="CLASSROOM").count(),
        "computer_labs": rooms.filter(room_type="COMPUTER_LAB").count(),
        "science_labs": rooms.filter(room_type="SCIENCE_LAB").count(),
        "schools": schools,
        "current_school": current_school,
        "auto_room_targets": auto_room_targets,
        "auto_expected_rooms": sum(item["expected_count"] for item in auto_room_targets),
        "search_query": search_query,
        "room_type_filter": room_type_filter,
        "status_filter": status_filter,
    }

    return render(request, "room_list.html", context)

#import messages and HttpResponse for success messages and closing the form after submission
from django.contrib import messages
from django.http import HttpResponse

@login_required
@log_exceptions
def room_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = RoomForm(request.POST, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Room created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = RoomForm(current_school=current_school)

    return render(request, "room_form.html", {
        "form": form,
        "title": "Create Room",
        "subtitle": "Add classrooms, labs, library, playground and activity rooms.",
        "button_text": "Save Room",
    })


@login_required
@log_exceptions
def room_update(request, pk):
    room = get_school_object_or_404(request, Room.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = RoomForm(request.POST, instance=room, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Room updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = RoomForm(instance=room, current_school=current_school)

    return render(request, "room_form.html", {
        "form": form,
        "title": "Update Room",
        "subtitle": "Update room information, capacity and active status.",
        "button_text": "Update Room",
    })


@login_required
@require_POST
@log_exceptions
def room_delete(request, pk):
    room = get_school_object_or_404(request, Room.objects.all(), pk=pk)
    room_name = room.name
    room.delete()
    messages.success(request, f"Room '{room_name}' deleted successfully.")
    return redirect("room_list")


@login_required
@require_POST
@log_exceptions
def room_bulk_delete(request):
    selected_ids = request.POST.getlist("room_ids")
    if not selected_ids:
        messages.warning(request, "Select at least one room to delete.")
        return redirect("room_list")

    rooms = school_queryset(
        request,
        Room.objects.filter(id__in=selected_ids),
    )
    deleted_count = rooms.count()
    rooms.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected room(s).")
    else:
        messages.info(request, "No rooms were deleted.")

    return redirect("room_list")


@login_required
@require_POST
@log_exceptions
def room_auto_create_classrooms(request):
    current_school = get_current_school(request)
    if not current_school:
        messages.error(request, "No active school is linked with your session.")
        return redirect("room_list")

    school_id = current_school.id if current_school else request.POST.get("school")
    capacity = request.POST.get("capacity") or 40

    try:
        capacity = max(0, int(capacity))
    except ValueError:
        capacity = 40

    schools = School.objects.filter(pk=school_id).order_by("name")

    created_count = 0
    skipped_count = 0
    assigned_count = 0

    for school in schools:
        class_levels = ClassLevel.objects.filter(
            school=school,
            is_active=True,
        ).order_by("sort_order", "name")
        divisions = Division.objects.filter(
            school=school,
            is_active=True,
        ).order_by("sort_order", "name")

        for class_level in class_levels:
            for division in divisions:
                room_name = f"{class_level.name} {division.name}"
                room = Room.objects.filter(
                    school=school,
                    name__iexact=room_name,
                    room_type="CLASSROOM",
                ).first()

                if room:
                    skipped_count += 1
                else:
                    short_level = class_level.short_name or class_level.name
                    room = Room.objects.create(
                        school=school,
                        name=room_name,
                        short_name=f"{short_level}-{division.name}"[:30],
                        room_type="CLASSROOM",
                        capacity=capacity,
                        is_active=True,
                    )
                    created_count += 1

                updated_sections = ClassSection.objects.filter(
                    school=school,
                    class_level=class_level,
                    division=division,
                    default_room__isnull=True,
                ).update(default_room=room)
                assigned_count += updated_sections

    if created_count:
        messages.success(
            request,
            f"Auto-created {created_count} classroom(s). {skipped_count} existing classroom(s) were skipped. Assigned rooms to {assigned_count} class section(s)."
        )
    else:
        messages.info(
            request,
            f"No new classrooms were needed. {skipped_count} matching classroom(s) already exist."
        )

    return redirect("room_list")
