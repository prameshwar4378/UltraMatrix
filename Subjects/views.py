import csv

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Subject, TeacherSubjectCapability
from .forms import SubjectForm, TeacherSubjectCapabilityForm

from django.contrib import messages
from django.http import HttpResponse
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset


def _filtered_subjects(request):
    subjects = school_queryset(
        request,
        Subject.objects.select_related("school"),
    ).order_by("-id")
    search_query = request.GET.get("search", "")
    section_filter = request.GET.get("section_type", "")
    subject_type_filter = request.GET.get("subject_type", "")
    status_filter = request.GET.get("status", "")

    if search_query:
        subjects = subjects.filter(
            Q(name__icontains=search_query) |
            Q(short_name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(school__name__icontains=search_query)
        )

    if section_filter:
        subjects = subjects.filter(section_type=section_filter)

    if subject_type_filter:
        subjects = subjects.filter(subject_type=subject_type_filter)

    if status_filter == "active":
        subjects = subjects.filter(is_active=True)

    if status_filter == "inactive":
        subjects = subjects.filter(is_active=False)

    return subjects, search_query, section_filter, subject_type_filter, status_filter


@login_required
def subject_list(request):
    subjects, search_query, section_filter, subject_type_filter, status_filter = _filtered_subjects(request)
    capabilities = school_queryset(request, TeacherSubjectCapability.objects.select_related(
        "school", "teacher", "subject"
    ).prefetch_related("class_levels")).order_by("-id")

    context = {
        "subjects": subjects,
        "capabilities": capabilities[:8],

        "total_subjects": subjects.count(),
        "active_subjects": subjects.filter(is_active=True).count(),
        "theory_subjects": subjects.filter(subject_type="THEORY").count(),
        "practical_subjects": subjects.filter(subject_type="PRACTICAL").count(),
        "total_capabilities": capabilities.count(),

        "search_query": search_query,
        "section_filter": section_filter,
        "subject_type_filter": subject_type_filter,
        "status_filter": status_filter,
    }

    return render(request, "subject_list.html", context)


@login_required
def subject_export_csv(request):
    subjects, search_query, section_filter, subject_type_filter, status_filter = _filtered_subjects(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="subject_setup.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "School",
        "Subject",
        "Short Name",
        "Code",
        "Section",
        "Subject Type",
        "Color",
        "Status",
    ])

    for subject in subjects:
        writer.writerow([
            subject.school.name,
            subject.name,
            subject.short_name,
            subject.code,
            subject.get_section_type_display(),
            subject.get_subject_type_display(),
            subject.color_code,
            "Active" if subject.is_active else "Inactive",
        ])

    return response


@login_required
def subject_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = SubjectForm(request.POST, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Subject created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = SubjectForm(current_school=current_school)

    return render(request, "subject_form.html", {
        "form": form,
        "title": "Create Subject",
        "subtitle": "Add subject details for primary, secondary or both sections.",
        "button_text": "Save Subject",
    })


@login_required
def subject_update(request, pk):
    subject = get_school_object_or_404(request, Subject.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = SubjectForm(request.POST, instance=subject, current_school=current_school)

        if form.is_valid():
            form.save()
            
            messages.success(request, "Subject updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = SubjectForm(instance=subject, current_school=current_school)

    return render(request, "subject_form.html", {
        "form": form,
        "title": "Update Subject",
        "subtitle": "Update subject information and status.",
        "button_text": "Update Subject",
    })


@login_required
@require_POST
def subject_delete(request, pk):
    subject = get_school_object_or_404(request, Subject.objects.all(), pk=pk)
    name = subject.name
    subject.delete()
    messages.success(request, f"Subject '{name}' deleted successfully.")
    return redirect("subject_list")


@login_required
@require_POST
def subject_toggle_status(request, pk):
    subject = get_school_object_or_404(request, Subject.objects.all(), pk=pk)
    subject.is_active = not subject.is_active
    subject.save(update_fields=["is_active"])

    status = "activated" if subject.is_active else "deactivated"
    messages.success(request, f"Subject '{subject.name}' {status} successfully.")
    return redirect("subject_list")


@login_required
def teacher_subject_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        form = TeacherSubjectCapabilityForm(request.POST, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher Subject Capability created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = TeacherSubjectCapabilityForm(current_school=current_school)

    return render(request, "teacher_subject_form.html", {
        "form": form,
        "title": "Create Teacher Subject Capability",
        "subtitle": "Map which teacher can teach which subject and class levels.",
        "button_text": "Save Mapping",
    })

@login_required
def teacher_subject_update(request, pk):
    capability = get_school_object_or_404(request, TeacherSubjectCapability.objects.all(), pk=pk)
    current_school = get_current_school(request)

    if request.method == "POST":
        form = TeacherSubjectCapabilityForm(request.POST, instance=capability, current_school=current_school)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher Subject Capability updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = TeacherSubjectCapabilityForm(instance=capability, current_school=current_school)

    return render(request, "teacher_subject_form.html", {
        "form": form,
        "title": "Update Teacher Subject Capability",
        "subtitle": "Update teacher, subject and class-level mapping.",
        "button_text": "Update Mapping",
    })


@login_required
@require_POST
def teacher_subject_delete(request, pk):
    capability = get_school_object_or_404(request, TeacherSubjectCapability.objects.all(), pk=pk)
    name = str(capability)
    capability.delete()
    messages.success(request, f"Teacher subject mapping '{name}' deleted successfully.")
    return redirect("subject_list")
