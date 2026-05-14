from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Room
from .forms import RoomForm
from Classes.models import ClassLevel, Division
from Schools.models import School
from Timetables.models import ClassSection

def room_list(request):

    # Timetable.objects.filter(is_active=True).delete()


    rooms = Room.objects.select_related("school").all().order_by("-id")

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

    auto_room_targets = []
    for school in School.objects.all().order_by("name"):
        class_count = ClassLevel.objects.filter(school=school, is_active=True).count()
        division_count = Division.objects.filter(school=school, is_active=True).count()
        expected_count = class_count * division_count
        if expected_count:
            auto_room_targets.append({
                "school": school,
                "expected_count": expected_count,
            })

    context = {
        "rooms": rooms,
        "total_rooms": Room.objects.count(),
        "active_rooms": Room.objects.filter(is_active=True).count(),
        "classrooms": Room.objects.filter(room_type="CLASSROOM").count(),
        "computer_labs": Room.objects.filter(room_type="COMPUTER_LAB").count(),
        "science_labs": Room.objects.filter(room_type="SCIENCE_LAB").count(),
        "schools": School.objects.all().order_by("name"),
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

def room_create(request):
    if request.method == "POST":
        form = RoomForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Room created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = RoomForm()

    return render(request, "room_form.html", {
        "form": form,
        "title": "Create Room",
        "subtitle": "Add classrooms, labs, library, playground and activity rooms.",
        "button_text": "Save Room",
    })


def room_update(request, pk):
    room = get_object_or_404(Room, pk=pk)

    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)

        if form.is_valid():
            form.save()
            messages.success(request, "Room updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = RoomForm(instance=room)

    return render(request, "room_form.html", {
        "form": form,
        "title": "Update Room",
        "subtitle": "Update room information, capacity and active status.",
        "button_text": "Update Room",
    })


@require_POST
def room_delete(request, pk):
    room = get_object_or_404(Room, pk=pk)
    room_name = room.name
    room.delete()
    messages.success(request, f"Room '{room_name}' deleted successfully.")
    return redirect("room_list")


@require_POST
def room_auto_create_classrooms(request):
    school_id = request.POST.get("school")
    capacity = request.POST.get("capacity") or 40

    try:
        capacity = max(0, int(capacity))
    except ValueError:
        capacity = 40

    schools = School.objects.all().order_by("name")
    if school_id:
        schools = schools.filter(pk=school_id)

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
