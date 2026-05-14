from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import ClassLevel, Division
from .forms import ClassLevelForm, DivisionForm, ClassSectionForm
from Timetables.models import ClassSection
from Schools.models import School


def class_setup_list(request):
    search_query = request.GET.get("search", "")
    section_filter = request.GET.get("section_type", "")
    status_filter = request.GET.get("status", "")

    class_sections = ClassSection.objects.select_related(
        "school",
        "class_level",
        "division",
        "class_teacher",
        "default_room"
    ).all().order_by("class_level__sort_order", "division__sort_order")

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

    context = {
        "class_sections": class_sections,
        "class_levels": ClassLevel.objects.select_related("school").all().order_by("school__name", "sort_order", "name"),
        "divisions": Division.objects.select_related("school").all().order_by("school__name", "sort_order", "name"),
        "total_sections": ClassSection.objects.count(),
        "active_sections": ClassSection.objects.filter(is_active=True).count(),
        "primary_sections": ClassSection.objects.filter(class_level__section_type="PRIMARY").count(),
        "secondary_sections": ClassSection.objects.filter(class_level__section_type="SECONDARY").count(),
        "total_schools": School.objects.count(),
        "search_query": search_query,
        "section_filter": section_filter,
        "status_filter": status_filter,
    }

    return render(request, "class_setup_list.html", context)

#import HttpResponse for returning a simple response to close the popup after form submission
from django.http import HttpResponse
from django.contrib import messages

def class_level_create(request):
    if request.method == "POST":
        form = ClassLevelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Class level created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassLevelForm()

    return render(request, "class_level_form.html", {
        "form": form,
        "title": "Create Class Level",
        "subtitle": "Add Nursery, LKG, UKG, Class 1 to Class 10.",
        "button_text": "Save Class Level",
    })


def class_level_update(request, pk):
    class_level = get_object_or_404(ClassLevel, pk=pk)

    if request.method == "POST":
        form = ClassLevelForm(request.POST, instance=class_level)
        if form.is_valid():
            form.save()
            messages.success(request, "Class level updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassLevelForm(instance=class_level)

    return render(request, "class_level_form.html", {
        "form": form,
        "title": "Update Class Level",
        "subtitle": "Update class level information and section grouping.",
        "button_text": "Update Class Level",
    })


@require_POST
def class_level_delete(request, pk):
    class_level = get_object_or_404(ClassLevel, pk=pk)
    name = class_level.name
    class_level.delete()
    messages.success(request, f"Class level '{name}' deleted successfully.")
    return redirect("class_setup_list")


def division_create(request):
    if request.method == "POST":
        form = DivisionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Division created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = DivisionForm()

    return render(request, "division_form.html", {
        "form": form,
        "title": "Create Division",
        "subtitle": "Add divisions like A, B, C or D.",
        "button_text": "Save Division",
    })


def division_update(request, pk):
    division = get_object_or_404(Division, pk=pk)

    if request.method == "POST":
        form = DivisionForm(request.POST, instance=division)
        if form.is_valid():
            form.save()
            messages.success(request, "Division updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = DivisionForm(instance=division)

    return render(request, "division_form.html", {
        "form": form,
        "title": "Update Division",
        "subtitle": "Update division name, order and active status.",
        "button_text": "Update Division",
    })


@require_POST
def division_delete(request, pk):
    division = get_object_or_404(Division, pk=pk)
    name = division.name
    division.delete()
    messages.success(request, f"Division '{name}' deleted successfully.")
    return redirect("class_setup_list")


def class_section_create(request):
    if request.method == "POST":
        form = ClassSectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Class section created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassSectionForm()

    return render(request, "class_section_form.html", {
        "form": form,
        "title": "Create Class Section",
        "subtitle": "Create actual class section like Class 1A, Class 10B.",
        "button_text": "Save Class Section",
    })


def class_section_update(request, pk):
    class_section = get_object_or_404(ClassSection, pk=pk)

    if request.method == "POST":
        form = ClassSectionForm(request.POST, instance=class_section)
        if form.is_valid():
            form.save()
            messages.success(request, "Class section updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = ClassSectionForm(instance=class_section)

    return render(request, "class_section_form.html", {
        "form": form,
        "title": "Update Class Section",
        "subtitle": "Update class section, teacher, room, capacity and status.",
        "button_text": "Update Class Section",
    })


@require_POST
def class_section_delete(request, pk):
    class_section = get_object_or_404(ClassSection, pk=pk)
    name = str(class_section)
    class_section.delete()
    messages.success(request, f"Class section '{name}' deleted successfully.")
    return redirect("class_setup_list")
