import csv
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Subject, TeacherSubjectCapability
from .forms import SubjectForm, TeacherSubjectCapabilityForm
from Timetables.models import ClassSection, LessonAllocation, TimetableEntry
from Teachers.models import Teacher

from django.contrib import messages
from django.http import HttpResponse
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
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
@log_exceptions
def subject_list(request):
    current_school = get_current_school(request)
    subjects, search_query, section_filter, subject_type_filter, status_filter = _filtered_subjects(request)
    capabilities = school_queryset(request, TeacherSubjectCapability.objects.select_related(
        "school", "teacher", "subject"
    ).prefetch_related(
        "class_levels",
        "class_sections",
        "class_sections__class_level",
        "class_sections__division",
    )).order_by("-id")

    active_sections = school_queryset(request, ClassSection.objects.select_related("class_level", "division")).filter(
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")
    active_subjects = subjects.filter(is_active=True)
    active_teachers = school_queryset(request, Teacher.objects.filter(is_active=True)).order_by("name")
    missing_mappings = []
    mapped_pairs = set()

    for capability in capabilities:
        for section in capability.class_sections.all():
            mapped_pairs.add((capability.subject_id, section.id))
        for level in capability.class_levels.all():
            for section in active_sections:
                if section.class_level_id == level.id:
                    mapped_pairs.add((capability.subject_id, section.id))

    for subject in active_subjects:
        for section in active_sections:
            subject_section = subject.section_type
            section_type = section.class_level.section_type
            if subject_section != "BOTH" and subject_section != section_type:
                continue
            if (subject.id, section.id) not in mapped_pairs:
                missing_mappings.append({
                    "subject": subject,
                    "section": section,
                })

    teacher_mapping_summary = []
    for teacher in active_teachers[:8]:
        teacher_mapping_summary.append({
            "teacher": teacher,
            "count": capabilities.filter(teacher=teacher).count(),
        })

    subject_mapping_summary = []
    for subject in active_subjects.order_by("name")[:8]:
        subject_mapping_summary.append({
            "subject": subject,
            "count": capabilities.filter(subject=subject).count(),
        })

    for subject in subjects:
        subject.impact_capabilities = TeacherSubjectCapability.objects.filter(subject=subject).count()
        subject.impact_allocations = LessonAllocation.objects.filter(subject=subject).count()
        subject.impact_entries = TimetableEntry.objects.filter(subject=subject).count()

    context = {
        "subjects": subjects,
        "capabilities": capabilities,

        "total_subjects": subjects.count(),
        "active_subjects": subjects.filter(is_active=True).count(),
        "theory_subjects": subjects.filter(subject_type="THEORY").count(),
        "practical_subjects": subjects.filter(subject_type="PRACTICAL").count(),
        "total_capabilities": capabilities.count(),
        "active_sections_count": active_sections.count(),
        "active_teachers_count": active_teachers.count(),
        "subjects_setup_done": active_subjects.exists(),
        "sections_setup_done": active_sections.exists(),
        "teachers_setup_done": active_teachers.exists(),
        "capabilities_setup_done": capabilities.exists(),
        "missing_mappings": missing_mappings[:10],
        "missing_mapping_count": len(missing_mappings),
        "teacher_mapping_summary": teacher_mapping_summary,
        "subject_mapping_summary": subject_mapping_summary,
        "current_school": current_school,

        "search_query": search_query,
        "section_filter": section_filter,
        "subject_type_filter": subject_type_filter,
        "status_filter": status_filter,
    }

    return render(request, "subject_list.html", context)


@log_exceptions
def _default_subject_rows():
    return [
        {"name": "English", "short_name": "Eng", "code": "ENG", "section_type": "BOTH", "subject_type": "THEORY", "color_code": "#2563eb", "is_active": True},
        {"name": "Mathematics", "short_name": "Maths", "code": "MATH", "section_type": "BOTH", "subject_type": "THEORY", "color_code": "#dc2626", "is_active": True},
        {"name": "Science", "short_name": "Sci", "code": "SCI", "section_type": "SECONDARY", "subject_type": "THEORY", "color_code": "#16a34a", "is_active": True},
        {"name": "Social Science", "short_name": "SS", "code": "SOC", "section_type": "SECONDARY", "subject_type": "THEORY", "color_code": "#9333ea", "is_active": True},
        {"name": "Hindi", "short_name": "Hin", "code": "HIN", "section_type": "BOTH", "subject_type": "THEORY", "color_code": "#ea580c", "is_active": True},
        {"name": "Computer", "short_name": "Comp", "code": "COMP", "section_type": "BOTH", "subject_type": "PRACTICAL", "color_code": "#0891b2", "is_active": True},
        {"name": "Drawing", "short_name": "Draw", "code": "DRAW", "section_type": "PRIMARY", "subject_type": "ACTIVITY", "color_code": "#db2777", "is_active": True},
        {"name": "Physical Education", "short_name": "PE", "code": "PE", "section_type": "BOTH", "subject_type": "ACTIVITY", "color_code": "#65a30d", "is_active": True},
    ]


@login_required
@log_exceptions
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
@log_exceptions
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
@log_exceptions
def subject_quick_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        subject_rows = json.loads(request.POST.get("subjects_json") or "[]")
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for subject_data in subject_rows:
                name = str(subject_data.get("name") or "").strip()
                code = str(subject_data.get("code") or "").strip().upper()
                if not name:
                    skipped_count += 1
                    continue
                duplicate = Subject.objects.filter(school=current_school, name__iexact=name)
                if code:
                    duplicate = duplicate | Subject.objects.filter(school=current_school, code__iexact=code)
                if duplicate.exists():
                    skipped_count += 1
                    continue

                Subject.objects.create(
                    school=current_school,
                    name=name,
                    short_name=str(subject_data.get("short_name") or "").strip(),
                    code=code,
                    section_type=subject_data.get("section_type") or "BOTH",
                    subject_type=subject_data.get("subject_type") or "THEORY",
                    color_code=subject_data.get("color_code") or "#0d6efd",
                    is_active=bool(subject_data.get("is_active", True)),
                )
                created_count += 1

        messages.success(request, f"Quick subject setup completed. Created: {created_count}, skipped: {skipped_count}.")
        return HttpResponse("""
        <script>
        window.close();
        </script>
        """)

    return render(request, "subject_form.html", {
        "form": SubjectForm(current_school=current_school),
        "title": "Quick Subjects",
        "subtitle": "Create multiple subjects from editable local rows.",
        "button_text": "Save Subjects",
        "bulk_create": True,
        "initial_subjects_json": _default_subject_rows(),
    })


@log_exceptions
def _class_section_options(current_school):
    return [{
        "id": section.id,
        "name": f"{section.class_level.name}-{section.division.name}",
        "class_level_id": section.class_level_id,
    } for section in ClassSection.objects.select_related(
        "class_level",
        "division",
    ).filter(
        school=current_school,
        is_active=True,
        class_level__is_active=True,
        division__is_active=True,
    ).order_by("class_level__sort_order", "division__sort_order")]


@log_exceptions
def _mapping_form_context(form, title, subtitle, button_text, current_school, **extra):
    context = {
        "form": form,
        "title": title,
        "subtitle": subtitle,
        "button_text": button_text,
        "class_sections_json": _class_section_options(current_school),
    }
    context.update(extra)
    return context


@login_required
@log_exceptions
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
@log_exceptions
def subject_delete(request, pk):
    subject = get_school_object_or_404(request, Subject.objects.all(), pk=pk)
    name = subject.name
    subject.delete()
    messages.success(request, f"Subject '{name}' deleted successfully.")
    return redirect("subject_list")


@login_required
@require_POST
@log_exceptions
def subject_bulk_delete(request):
    selected_ids = request.POST.getlist("subject_ids")
    if not selected_ids:
        messages.warning(request, "Select at least one subject to delete.")
        return redirect("subject_list")

    subjects = school_queryset(
        request,
        Subject.objects.filter(id__in=selected_ids),
    )
    deleted_count = subjects.count()
    subjects.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected subject(s).")
    else:
        messages.info(request, "No subjects were deleted.")

    return redirect("subject_list")


@login_required
@require_POST
@log_exceptions
def subject_toggle_status(request, pk):
    subject = get_school_object_or_404(request, Subject.objects.all(), pk=pk)
    subject.is_active = not subject.is_active
    subject.save(update_fields=["is_active"])

    status = "activated" if subject.is_active else "deactivated"
    messages.success(request, f"Subject '{subject.name}' {status} successfully.")
    return redirect("subject_list")


@login_required
@log_exceptions
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

    return render(request, "teacher_subject_form.html", _mapping_form_context(
        form,
        "Create Teacher Subject Capability",
        "Map which teacher can teach which subject and class sections.",
        "Save Mapping",
        current_school,
    ))


@login_required
@log_exceptions
def teacher_subject_quick_create(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    if request.method == "POST":
        mapping_rows = json.loads(request.POST.get("mappings_json") or "[]")
        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for row in mapping_rows:
                teacher_id = str(row.get("teacher_id") or "").strip()
                subject_id = str(row.get("subject_id") or "").strip()
                section_ids = [
                    str(item).strip()
                    for item in row.get("class_section_ids", [])
                    if str(item).strip().isdigit()
                ]

                if not teacher_id.isdigit() or not subject_id.isdigit() or not section_ids:
                    skipped_count += 1
                    continue

                teacher = Teacher.objects.filter(id=teacher_id, school=current_school, is_active=True).first()
                subject = Subject.objects.filter(id=subject_id, school=current_school, is_active=True).first()
                sections = list(ClassSection.objects.filter(id__in=section_ids, school=current_school))

                if not teacher or not subject or not sections:
                    skipped_count += 1
                    continue

                sections_by_priority = {"PRIMARY": [], "SECONDARY": [], "BACKUP": []}
                for section in sections:
                    already_mapped_to_teacher = TeacherSubjectCapability.objects.filter(
                        school=current_school,
                        teacher=teacher,
                        subject=subject,
                        class_sections=section,
                    ).exists()
                    if already_mapped_to_teacher:
                        skipped_count += 1
                        continue

                    assigned_priorities = set(TeacherSubjectCapability.objects.filter(
                        school=current_school,
                        subject=subject,
                        class_sections=section,
                    ).exclude(teacher=teacher).values_list("priority", flat=True))

                    if "PRIMARY" not in assigned_priorities:
                        sections_by_priority["PRIMARY"].append(section)
                    elif "SECONDARY" not in assigned_priorities:
                        sections_by_priority["SECONDARY"].append(section)
                    else:
                        sections_by_priority["BACKUP"].append(section)

                for priority, priority_sections in sections_by_priority.items():
                    if not priority_sections:
                        continue

                    capability = TeacherSubjectCapability.objects.filter(
                        school=current_school,
                        teacher=teacher,
                        subject=subject,
                        priority=priority,
                    ).first()
                    created = capability is None
                    if created:
                        capability = TeacherSubjectCapability.objects.create(
                            school=current_school,
                            teacher=teacher,
                            subject=subject,
                            priority=priority,
                        )
                    capability.class_sections.add(*priority_sections)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

        messages.success(
            request,
            f"Quick mapping completed. Created: {created_count}, updated: {updated_count}, skipped: {skipped_count}. Priority was assigned automatically."
        )
        return HttpResponse("""
        <script>
        window.close();
        </script>
        """)

    teachers = Teacher.objects.filter(school=current_school, is_active=True).order_by("name")
    subjects = Subject.objects.filter(school=current_school, is_active=True).order_by("name")

    return render(request, "teacher_subject_form.html", _mapping_form_context(
        TeacherSubjectCapabilityForm(current_school=current_school),
        "Quick Teacher Subject Mapping",
        "Create multiple teacher-subject-section mappings from editable rows.",
        "Save Mappings",
        current_school,
        bulk_create=True,
        teachers_json=[{"id": teacher.id, "name": teacher.name} for teacher in teachers],
        subjects_json=[{"id": subject.id, "name": subject.name} for subject in subjects],
        initial_mappings_json=[{"teacher_id": "", "subject_id": "", "class_section_ids": []}],
    ))

@login_required
@log_exceptions
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

    return render(request, "teacher_subject_form.html", _mapping_form_context(
        form,
        "Update Teacher Subject Capability",
        "Update teacher, subject and class-section mapping.",
        "Update Mapping",
        current_school,
    ))


@login_required
@require_POST
@log_exceptions
def teacher_subject_delete(request, pk):
    capability = get_school_object_or_404(request, TeacherSubjectCapability.objects.all(), pk=pk)
    name = str(capability)
    capability.delete()
    messages.success(request, f"Teacher subject mapping '{name}' deleted successfully.")
    return redirect("subject_list")


@login_required
@require_POST
@log_exceptions
def teacher_subject_bulk_delete(request):
    selected_ids = request.POST.getlist("teacher_subject_ids")
    if not selected_ids:
        messages.warning(request, "Select at least one teacher mapping to delete.")
        return redirect("subject_list")

    capabilities = school_queryset(
        request,
        TeacherSubjectCapability.objects.filter(id__in=selected_ids),
    )
    deleted_count = capabilities.count()
    capabilities.delete()

    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} selected teacher mapping(s).")
    else:
        messages.info(request, "No teacher mappings were deleted.")

    return redirect("subject_list")
