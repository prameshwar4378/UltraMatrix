import json

from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST

from Schools.models import School
from .models import AcademicYear, Day, BellSchedule, Period
from django.db.models import Q
from Accounts.utils import get_current_school, get_school_object_or_404, redirect_if_no_current_school, school_queryset


def _time_value(value):
    return value.strftime("%H:%M") if value else ""


def _default_days():
    return [
        {"name": "Monday", "short_name": "Mon", "sort_order": 1, "day_type": "WEEKDAY", "is_working": True},
        {"name": "Tuesday", "short_name": "Tue", "sort_order": 2, "day_type": "WEEKDAY", "is_working": True},
        {"name": "Wednesday", "short_name": "Wed", "sort_order": 3, "day_type": "WEEKDAY", "is_working": True},
        {"name": "Thursday", "short_name": "Thu", "sort_order": 4, "day_type": "WEEKDAY", "is_working": True},
        {"name": "Friday", "short_name": "Fri", "sort_order": 5, "day_type": "WEEKDAY", "is_working": True},
        {"name": "Saturday", "short_name": "Sat", "sort_order": 6, "day_type": "SATURDAY", "is_working": True},
    ]


def _default_weekday_periods():
    return [
        {"period_number": 1, "name": "Assembly", "start_time": "08:30", "end_time": "08:45", "period_type": "ASSEMBLY"},
        {"period_number": 2, "name": "Period 1", "start_time": "08:45", "end_time": "09:25", "period_type": "TEACHING"},
        {"period_number": 3, "name": "Period 2", "start_time": "09:25", "end_time": "10:05", "period_type": "TEACHING"},
        {"period_number": 4, "name": "Break", "start_time": "10:05", "end_time": "10:20", "period_type": "BREAK"},
        {"period_number": 5, "name": "Period 3", "start_time": "10:20", "end_time": "11:00", "period_type": "TEACHING"},
        {"period_number": 6, "name": "Period 4", "start_time": "11:00", "end_time": "11:40", "period_type": "TEACHING"},
        {"period_number": 7, "name": "Lunch", "start_time": "11:40", "end_time": "12:10", "period_type": "LUNCH"},
        {"period_number": 8, "name": "Period 5", "start_time": "12:10", "end_time": "12:50", "period_type": "TEACHING"},
        {"period_number": 9, "name": "Period 6", "start_time": "12:50", "end_time": "13:30", "period_type": "TEACHING"},
    ]


def _default_saturday_periods():
    return [
        {"period_number": 1, "name": "Assembly", "start_time": "08:30", "end_time": "08:40", "period_type": "ASSEMBLY"},
        {"period_number": 2, "name": "Period 1", "start_time": "08:40", "end_time": "09:20", "period_type": "TEACHING"},
        {"period_number": 3, "name": "Period 2", "start_time": "09:20", "end_time": "10:00", "period_type": "TEACHING"},
        {"period_number": 4, "name": "Break", "start_time": "10:00", "end_time": "10:10", "period_type": "BREAK"},
        {"period_number": 5, "name": "Period 3", "start_time": "10:10", "end_time": "10:50", "period_type": "TEACHING"},
        {"period_number": 6, "name": "Period 4", "start_time": "10:50", "end_time": "11:30", "period_type": "TEACHING"},
    ]


def _days_for_school(school):
    days = Day.objects.filter(school=school).order_by("sort_order", "id")

    if not days.exists():
        return _default_days()

    return [{
        "name": day.name,
        "short_name": day.short_name,
        "sort_order": day.sort_order,
        "day_type": day.day_type,
        "is_working": day.is_working,
    } for day in days]


def _periods_for_schedule(bell_schedule, day_type, defaults):
    if not bell_schedule:
        return defaults()

    periods = Period.objects.filter(
        bell_schedule=bell_schedule,
        day_type=day_type,
    ).order_by("period_number", "id")

    if not periods.exists():
        return defaults()

    return [{
        "period_number": period.period_number,
        "name": period.name,
        "start_time": _time_value(period.start_time),
        "end_time": _time_value(period.end_time),
        "period_type": period.period_type,
    } for period in periods]


def _save_academic_setup(request, academic_year=None):
    current_school = get_current_school(request)
    school = current_school or get_object_or_404(School, id=request.POST.get("school"))
    days_data = json.loads(request.POST.get("days_json") or "[]")
    weekday_periods = json.loads(request.POST.get("weekday_periods_json") or "[]")
    saturday_periods = json.loads(request.POST.get("saturday_periods_json") or "[]")

    with transaction.atomic():
        if academic_year is None:
            academic_year = AcademicYear.objects.create(
                school=school,
                name=request.POST.get("academic_name"),
                start_date=request.POST.get("start_date"),
                end_date=request.POST.get("end_date"),
                is_active=request.POST.get("is_active") == "on",
            )
        else:
            academic_year.school = school
            academic_year.name = request.POST.get("academic_name")
            academic_year.start_date = request.POST.get("start_date")
            academic_year.end_date = request.POST.get("end_date")
            academic_year.is_active = request.POST.get("is_active") == "on"
            academic_year.save()

        bell_schedule, _ = BellSchedule.objects.get_or_create(
            academic_year=academic_year,
            defaults={
                "school": school,
                "name": request.POST.get("bell_schedule_name"),
                "is_active": True,
            }
        )
        bell_schedule.school = school
        bell_schedule.name = request.POST.get("bell_schedule_name")
        bell_schedule.is_active = True
        bell_schedule.save()

        for day in days_data:
            day_defaults = {
                "short_name": day["short_name"],
                "sort_order": day["sort_order"],
                "day_type": day["day_type"],
                "is_working": day["is_working"],
            }
            matching_days = Day.objects.filter(
                school=school,
                name=day["name"],
            )

            if matching_days.exists():
                matching_days.update(**day_defaults)
            else:
                Day.objects.create(
                    school=school,
                    name=day["name"],
                    **day_defaults,
                )

        Period.objects.filter(bell_schedule=bell_schedule).delete()

        for day_type, period_data in (("WEEKDAY", weekday_periods), ("SATURDAY", saturday_periods)):
            for period in period_data:
                Period.objects.create(
                    school=school,
                    bell_schedule=bell_schedule,
                    day_type=day_type,
                    name=period["name"],
                    period_number=period["period_number"],
                    start_time=period["start_time"],
                    end_time=period["end_time"],
                    period_type=period["period_type"],
                    is_teaching_period=period["period_type"] == "TEACHING",
                )

    return academic_year

@login_required
def academic_setup_list(request):
    current_school = get_current_school(request)
    academic_years = school_queryset(
        request,
        AcademicYear.objects.select_related("school"),
    ).order_by("-id")

    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("search", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if status_filter == "active":
        academic_years = academic_years.filter(is_active=True)

    if status_filter == "inactive":
        academic_years = academic_years.filter(is_active=False)

    if search_query:
        academic_years = academic_years.filter(
            Q(name__icontains=search_query) |
            Q(school__name__icontains=search_query) |
            Q(school__school_code__icontains=search_query)
        )

    if date_from:
        academic_years = academic_years.filter(start_date__gte=date_from)

    if date_to:
        academic_years = academic_years.filter(end_date__lte=date_to)

    context = {
        "academic_years": academic_years,
        "total_academic_years": academic_years.count(),
        "active_academic_years": academic_years.filter(is_active=True).count(),
        "inactive_academic_years": academic_years.filter(is_active=False).count(),
        "total_schools": 1 if current_school else 0,
        "status_filter": status_filter,
        "search_query": search_query,
        "date_from": date_from,
        "date_to": date_to,
    }

    return render(request, "academic_setup_list.html", context)


@login_required
def academic_setup(request):
    no_school_response = redirect_if_no_current_school(request)
    if no_school_response:
        return no_school_response

    current_school = get_current_school(request)
    schools = School.objects.filter(is_active=True).order_by("name")
    if current_school:
        schools = schools.filter(pk=current_school.pk)

    if request.method == "POST":
        _save_academic_setup(request)
        messages.success(request, "Academic year, days, bell schedule and periods saved successfully.")

        return HttpResponse("""
        <script>
        window.close();
        </script>
        """)

    return render(request, "academic_setup.html", {
        "schools": schools,
        "current_school": current_school,
        "academic_year": None,
        "bell_schedule": None,
        "initial_days_json": _default_days(),
        "initial_weekday_periods_json": _default_weekday_periods(),
        "initial_saturday_periods_json": _default_saturday_periods(),
        "button_text": "Save Complete Setup",
        "form_title": "Academic Setup",
        "form_subtitle": "Create academic year, working days, weekday periods and Saturday separate timings.",
    })


@login_required
def academic_setup_update(request, pk):
    current_school = get_current_school(request)
    academic_year = get_school_object_or_404(
        request,
        AcademicYear.objects.select_related("school"),
        pk=pk,
    )
    schools = School.objects.filter(is_active=True).order_by("name")
    if current_school:
        schools = schools.filter(pk=current_school.pk)
    bell_schedule = BellSchedule.objects.filter(academic_year=academic_year).order_by("-is_active", "-id").first()

    if request.method == "POST":
        _save_academic_setup(request, academic_year)
        messages.success(request, "Academic setup updated successfully.")
        return HttpResponse("""
        <script>
        window.close();
        </script>
        """)

    return render(request, "academic_setup.html", {
        "schools": schools,
        "current_school": current_school,
        "academic_year": academic_year,
        "bell_schedule": bell_schedule,
        "initial_days_json": _days_for_school(academic_year.school),
        "initial_weekday_periods_json": _periods_for_schedule(bell_schedule, "WEEKDAY", _default_weekday_periods),
        "initial_saturday_periods_json": _periods_for_schedule(bell_schedule, "SATURDAY", _default_saturday_periods),
        "button_text": "Update Complete Setup",
        "form_title": "Update Academic Setup",
        "form_subtitle": "Update academic year, working days and bell period timings.",
    })


@login_required
@require_POST
def academic_setup_delete(request, pk):
    academic_year = get_school_object_or_404(request, AcademicYear.objects.all(), pk=pk)
    name = academic_year.name
    academic_year.delete()
    messages.success(request, f"Academic setup '{name}' deleted successfully.")
    return redirect("academic_setup_list")
