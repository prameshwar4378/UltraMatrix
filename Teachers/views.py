from io import BytesIO

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .models import Teacher
from .forms import TeacherForm
from Schools.models import School


TEACHER_IMPORT_HEADERS = [
    "School Code",
    "School Name",
    "Name",
    "Short Name",
    "Employee ID",
    "Mobile Number",
    "Email",
    "Teacher Type",
    "Department",
    "Max Periods Per Day",
    "Max Periods Per Week",
    "Active",
]


def _filtered_teachers(request):
    teachers = Teacher.objects.select_related("school").all().order_by("-id")

    search_query = request.GET.get("search", "")
    teacher_type_filter = request.GET.get("teacher_type", "")
    status_filter = request.GET.get("status", "")

    if search_query:
        teachers = teachers.filter(
            Q(name__icontains=search_query) |
            Q(short_name__icontains=search_query) |
            Q(employee_id__icontains=search_query) |
            Q(mobile_number__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(school__name__icontains=search_query)
        )

    if teacher_type_filter:
        teachers = teachers.filter(teacher_type=teacher_type_filter)

    if status_filter == "active":
        teachers = teachers.filter(is_active=True)

    if status_filter == "inactive":
        teachers = teachers.filter(is_active=False)

    return teachers, search_query, teacher_type_filter, status_filter


def teacher_list(request):
    teachers, search_query, teacher_type_filter, status_filter = _filtered_teachers(request)

    context = {
        "teachers": teachers,
        "total_teachers": Teacher.objects.count(),
        "active_teachers": Teacher.objects.filter(is_active=True).count(),
        "full_time_teachers": Teacher.objects.filter(teacher_type="FULL_TIME").count(),
        "part_time_teachers": Teacher.objects.filter(teacher_type="PART_TIME").count(),
        "total_schools": School.objects.count(),
        "search_query": search_query,
        "teacher_type_filter": teacher_type_filter,
        "status_filter": status_filter,
    }

    return render(request, "teacher_list.html", context)


def teacher_create(request):
    if request.method == "POST":
        form = TeacherForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher created successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = TeacherForm()

    return render(request, "teacher_form.html", {
        "form": form,
        "title": "Create Teacher",
        "subtitle": "Add teacher details, workload limits and department information.",
        "button_text": "Save Teacher",
    })


def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)

        if form.is_valid():
            form.save()
            messages.success(request, "Teacher updated successfully.")
            return HttpResponse("""
            <script>
            window.close();
            </script>
            """)
    else:
        form = TeacherForm(instance=teacher)

    return render(request, "teacher_form.html", {
        "form": form,
        "title": "Update Teacher",
        "subtitle": "Update teacher details, workload limits and status.",
        "button_text": "Update Teacher",
    })


@require_POST
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    name = teacher.name
    teacher.delete()
    messages.success(request, f"Teacher '{name}' deleted successfully.")
    return redirect("teacher_list")


def _teacher_workbook_response(workbook, filename):
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _style_teacher_sheet(sheet, title):
    navy = "0F172A"
    blue = "2563EB"
    light_blue = "DBEAFE"
    border_color = "CBD5E1"
    thin = Side(style="thin", color=border_color)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(TEACHER_IMPORT_HEADERS))
    sheet["A1"] = title
    sheet["A1"].fill = PatternFill("solid", fgColor=navy)
    sheet["A1"].font = Font(color="FFFFFF", bold=True, size=16)
    sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
    sheet.row_dimensions[1].height = 28

    for col, header in enumerate(TEACHER_IMPORT_HEADERS, start=1):
        cell = sheet.cell(row=3, column=col, value=header)
        cell.fill = PatternFill("solid", fgColor=blue)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        sheet.column_dimensions[get_column_letter(col)].width = max(16, min(28, len(header) + 6))

    for row in range(4, 504):
        for col in range(1, len(TEACHER_IMPORT_HEADERS) + 1):
            cell = sheet.cell(row=row, column=col)
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if row % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F8FAFC")

    sheet.freeze_panes = "A4"
    sheet.sheet_view.showGridLines = False

    teacher_type_validation = DataValidation(type="list", formula1='"FULL_TIME,PART_TIME"', allow_blank=False)
    active_validation = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=False)
    sheet.add_data_validation(teacher_type_validation)
    sheet.add_data_validation(active_validation)
    teacher_type_validation.add("H4:H503")
    active_validation.add("L4:L503")

    note = sheet["A2"]
    note.value = "Required: School Code or School Name, Name. Teacher Type must be FULL_TIME or PART_TIME. Active must be TRUE or FALSE."
    note.font = Font(color=navy, italic=True)
    note.alignment = Alignment(wrap_text=True)
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(TEACHER_IMPORT_HEADERS))


def teacher_import_template(request):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Teacher Import"
    _style_teacher_sheet(sheet, "Teacher Bulk Import Template")

    sample_school = School.objects.filter(is_active=True).order_by("name").first()
    sample_school_code = sample_school.school_code if sample_school else "SCH001"
    sample_school_name = sample_school.name if sample_school else "Sample School"
    sample_rows = [
        [sample_school_code, sample_school_name, "Amit Sharma", "Amit", "EMP001", "9876543210", "amit@example.com", "FULL_TIME", "Maths", 6, 30, "TRUE"],
        [sample_school_code, sample_school_name, "Priya Patil", "Priya", "EMP002", "9876543211", "priya@example.com", "PART_TIME", "Science", 4, 18, "TRUE"],
    ]

    for row_index, row in enumerate(sample_rows, start=4):
        for col_index, value in enumerate(row, start=1):
            sheet.cell(row=row_index, column=col_index, value=value)

    schools_sheet = workbook.create_sheet("Schools")
    schools_sheet.append(["School Code", "School Name"])
    for school in School.objects.order_by("name"):
        schools_sheet.append([school.school_code, school.name])
    schools_sheet.column_dimensions["A"].width = 22
    schools_sheet.column_dimensions["B"].width = 38

    return _teacher_workbook_response(workbook, "teacher-import-template.xlsx")


def teacher_export_excel(request):
    teachers, _, _, _ = _filtered_teachers(request)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Teachers"
    _style_teacher_sheet(sheet, "Teacher Export")

    for row_index, teacher in enumerate(teachers, start=4):
        values = [
            teacher.school.school_code,
            teacher.school.name,
            teacher.name,
            teacher.short_name,
            teacher.employee_id,
            teacher.mobile_number,
            teacher.email,
            teacher.teacher_type,
            teacher.department,
            teacher.max_periods_per_day,
            teacher.max_periods_per_week,
            "TRUE" if teacher.is_active else "FALSE",
        ]
        for col_index, value in enumerate(values, start=1):
            sheet.cell(row=row_index, column=col_index, value=value)

    return _teacher_workbook_response(workbook, "teachers-export.xlsx")


def _bool_from_excel(value):
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1", "ACTIVE"}


def _int_from_excel(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _school_from_import(school_code, school_name):
    school_code = str(school_code or "").strip()
    school_name = str(school_name or "").strip()

    if school_code:
        school = School.objects.filter(school_code__iexact=school_code).first()
        if school:
            return school

    if school_name:
        return School.objects.filter(name__iexact=school_name).first()

    return None


@require_POST
def teacher_import_excel(request):
    upload = request.FILES.get("teacher_file")

    if not upload:
        messages.error(request, "Please choose an Excel file to import.")
        return redirect("teacher_list")

    try:
        workbook = load_workbook(upload, data_only=True)
        sheet = workbook.active
    except Exception:
        messages.error(request, "Invalid Excel file. Please download and use the teacher import template.")
        return redirect("teacher_list")

    headers = [str(sheet.cell(row=3, column=col).value or "").strip() for col in range(1, len(TEACHER_IMPORT_HEADERS) + 1)]

    if headers != TEACHER_IMPORT_HEADERS:
        messages.error(request, "Template headers do not match. Please download the latest teacher import template.")
        return redirect("teacher_list")

    created = 0
    updated = 0
    skipped = []

    for row_index in range(4, sheet.max_row + 1):
        values = [sheet.cell(row=row_index, column=col).value for col in range(1, len(TEACHER_IMPORT_HEADERS) + 1)]

        if not any(values):
            continue

        school = _school_from_import(values[0], values[1])
        name = str(values[2] or "").strip()

        if not school or not name:
            skipped.append(f"Row {row_index}: school and name are required")
            continue

        teacher_type = str(values[7] or "FULL_TIME").strip().upper()
        if teacher_type not in {"FULL_TIME", "PART_TIME"}:
            skipped.append(f"Row {row_index}: invalid teacher type")
            continue

        employee_id = str(values[4] or "").strip()
        defaults = {
            "name": name,
            "short_name": str(values[3] or "").strip(),
            "employee_id": employee_id,
            "mobile_number": str(values[5] or "").strip(),
            "email": str(values[6] or "").strip(),
            "teacher_type": teacher_type,
            "department": str(values[8] or "").strip(),
            "max_periods_per_day": _int_from_excel(values[9], 6),
            "max_periods_per_week": _int_from_excel(values[10], 30),
            "is_active": _bool_from_excel(values[11]),
        }

        teacher = None
        if employee_id:
            teacher = Teacher.objects.filter(school=school, employee_id__iexact=employee_id).first()

        if teacher:
            for field, value in defaults.items():
                setattr(teacher, field, value)
            teacher.school = school
            teacher.save()
            updated += 1
        else:
            Teacher.objects.create(school=school, **defaults)
            created += 1

    message = f"Teacher import completed. Created: {created}, Updated: {updated}."
    if skipped:
        message += " Skipped: " + "; ".join(skipped[:5])
        if len(skipped) > 5:
            message += f"; and {len(skipped) - 5} more."
        messages.warning(request, message)
    else:
        messages.success(request, message)

    return redirect("teacher_list")
