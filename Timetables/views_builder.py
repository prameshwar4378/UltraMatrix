import json
import re
from io import BytesIO
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from Academic.models import AcademicYear, BellSchedule, Day, Period
from Classes.models import ClassLevel, Division
from Timetables.models import (
    LectureAdjustment,
    TeacherDailyStatus,
    Timetable,
    LessonAllocation,
    ClassSection,
)
from Teachers.models import Teacher, TeacherAvailability
from Subjects.models import Subject
from Rooms.models import Room
import json
from django.views.decorators.csrf import csrf_exempt

def auto_create_class_sections():
    class_levels = ClassLevel.objects.filter(is_active=True).select_related("school")
    divisions = Division.objects.filter(is_active=True).select_related("school")

    for class_level in class_levels:
        matching_divisions = divisions.filter(school=class_level.school)

        for division in matching_divisions:
            ClassSection.objects.get_or_create(
                school=class_level.school,
                class_level=class_level,
                division=division,
                defaults={
                    "capacity": 0,
                    "is_active": True,
                }
            )


def timetable_builder(request, template_name="timetable_builder.html"):
    auto_create_class_sections()

    academic_years = AcademicYear.objects.select_related("school").all().order_by("-id")
    selected_academic_year_id = request.GET.get("academic_year_id")
    selected_timetable_id = request.GET.get("timetable_id")

    timetables = Timetable.objects.select_related(
        "school",
        "academic_year"
    ).filter(is_active=True)

    if selected_academic_year_id:
        timetables = timetables.filter(academic_year_id=selected_academic_year_id)

    timetables = timetables.order_by("-id")

    selected_timetable = None

    if selected_timetable_id:
        selected_timetable = timetables.filter(id=selected_timetable_id).first()

    if not selected_timetable:
        selected_timetable = timetables.first()

    if selected_timetable:
        selected_academic_year_id = str(selected_timetable.academic_year_id)

    selected_school = selected_timetable.school if selected_timetable else None

    class_sections = ClassSection.objects.select_related(
        "school",
        "class_level",
        "division",
        "class_teacher",
        "default_room"
    ).filter(is_active=True)

    if selected_school:
        class_sections = class_sections.filter(school=selected_school)

    class_sections = class_sections.order_by(
        "school__name",
        "class_level__sort_order",
        "division__sort_order"
    )

    teachers = Teacher.objects.select_related("school").filter(is_active=True)
    subjects = Subject.objects.select_related("school").filter(is_active=True)
    rooms = Room.objects.select_related("school").filter(is_active=True)

    if selected_school:
        teachers = teachers.filter(school=selected_school)
        subjects = subjects.filter(school=selected_school)
        rooms = rooms.filter(school=selected_school)

    teachers = teachers.order_by("name")
    subjects = subjects.order_by("name")
    rooms = rooms.order_by("name")

    periods_data = _builder_periods_data(selected_timetable)

    lesson_allocations = LessonAllocation.objects.select_related(
        "school",
        "academic_year",
        "class_section",
        "subject",
        "teacher",
        "default_room"
    ).filter(is_active=True)

    if selected_academic_year_id:
        lesson_allocations = lesson_allocations.filter(academic_year_id=selected_academic_year_id)

    if selected_school:
        lesson_allocations = lesson_allocations.filter(school=selected_school)

    class_sections_data = []

    for section in class_sections:
        class_sections_data.append({
            "id": section.id,
            "name": f"{section.class_level.name} {section.division.name}",
            "class_level": section.class_level.name,
            "division": section.division.name,
            "section_type": section.class_level.section_type,
            "school_id": section.school.id,
            "school_name": section.school.name,
            "class_teacher_id": section.class_teacher.id if section.class_teacher else None,
            "class_teacher_name": section.class_teacher.name if section.class_teacher else "",
            "default_room_id": section.default_room.id if section.default_room else None,
            "default_room_name": section.default_room.name if section.default_room else "",
        })

    teachers_data = []

    for teacher in teachers:
        teachers_data.append({
            "id": teacher.id,
            "name": teacher.name,
            "school_id": teacher.school.id,
            "department": teacher.department,
            "max_day": teacher.max_periods_per_day,
            "max_week": teacher.max_periods_per_week,
        })

    subjects_data = []

    for subject in subjects:
        subjects_data.append({
            "id": subject.id,
            "name": subject.name,
            "short_name": subject.short_name,
            "color": subject.color_code,
            "section_type": subject.section_type,
            "subject_type": subject.subject_type,
            "school_id": subject.school.id,
        })

    rooms_data = []

    for room in rooms:
        rooms_data.append({
            "id": room.id,
            "name": room.name,
            "room_type": room.room_type,
            "school_id": room.school.id,
        })

    lesson_allocations_data = []

    for allocation in lesson_allocations:
        lesson_allocations_data.append({
            "id": allocation.id,
            "class_section_id": allocation.class_section.id,
            "subject_id": allocation.subject.id,
            "subject_name": allocation.subject.name,
            "teacher_id": allocation.teacher.id,
            "teacher_name": allocation.teacher.name,
            "room_id": allocation.default_room.id if allocation.default_room else None,
            "room_name": allocation.default_room.name if allocation.default_room else "",
            "weekly_periods": allocation.weekly_periods,
            "requires_double_period": allocation.requires_double_period,
        })

    teacher_availability_data = []

    for availability in TeacherAvailability.objects.select_related("teacher", "day", "period").all():
        teacher_availability_data.append({
            "teacher_id": availability.teacher_id,
            "day_id": availability.day_id,
            "period_id": availability.period_id,
            "is_available": availability.is_available,
        })

    context = {
        "academic_years": academic_years,
        "timetables": timetables,
        "selected_academic_year_id": selected_academic_year_id or "",
        "selected_timetable_id": selected_timetable.id if selected_timetable else "",

        "class_sections_json": class_sections_data,
        "teachers_json": teachers_data,
        "subjects_json": subjects_data,
        "rooms_json": rooms_data,
        "periods_json": periods_data,
        "lesson_allocations_json": lesson_allocations_data,
        "teacher_availability_json": teacher_availability_data,
    }
    return render(request, template_name, context)


def timetable_builder_template_2(request):
    return timetable_builder(request, "timetable_builder_template_2.html")


def timetable_builder_template_3(request):
    return timetable_builder(request, "timetable_builder_template_3.html")








from .models import  TimetableEntry


def _dedupe_by(items, key_func):
    deduped = []
    seen = set()

    for item in items:
        key = key_func(item)

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def _format_period_time(value):
    return value.strftime("%H:%M") if value else ""


def _builder_bell_schedule(timetable=None):
    if timetable:
        bell_schedule = BellSchedule.objects.filter(
            school=timetable.school,
            academic_year=timetable.academic_year,
            is_active=True
        ).order_by("-id").first()

        if bell_schedule:
            return bell_schedule

    return BellSchedule.objects.filter(is_active=True).order_by("-id").first()


def _builder_periods_data(timetable=None):
    bell_schedule = _builder_bell_schedule(timetable)
    school = timetable.school if timetable else bell_schedule.school if bell_schedule else None

    days_query = Day.objects.filter(is_working=True)

    if school:
        days_query = days_query.filter(school=school)

    days = _dedupe_by(
        days_query.order_by("sort_order", "id"),
        lambda day: (day.name, day.day_type, day.sort_order)
    )

    periods_query = Period.objects.all()

    if bell_schedule:
        periods_query = periods_query.filter(bell_schedule=bell_schedule)

    weekday_periods = periods_query.filter(day_type="WEEKDAY").order_by("period_number", "id")
    saturday_periods = periods_query.filter(day_type="SATURDAY").order_by("period_number", "id")

    weekday_periods = _dedupe_by(
        weekday_periods,
        lambda period: (
            period.day_type,
            period.period_number,
            period.name,
            period.period_type,
            period.start_time,
            period.end_time,
        )
    )

    saturday_periods = _dedupe_by(
        saturday_periods,
        lambda period: (
            period.day_type,
            period.period_number,
            period.name,
            period.period_type,
            period.start_time,
            period.end_time,
        )
    )

    periods_data = []

    if days and (weekday_periods or saturday_periods):
        for day in days:
            selected_periods = saturday_periods if day.day_type == "SATURDAY" else weekday_periods

            for period in selected_periods:
                periods_data.append({
                    "day_id": day.id,
                    "day_name": day.name,
                    "day_type": day.day_type,
                    "period_id": period.id,
                    "period_name": period.name,
                    "period_number": period.period_number,
                    "period_type": period.period_type,
                    "is_teaching_period": period.is_teaching_period,
                    "start_time": _format_period_time(period.start_time),
                    "end_time": _format_period_time(period.end_time),
                })

    return periods_data


def _builder_class_sections_data():
    class_sections = ClassSection.objects.select_related(
        "school",
        "class_level",
        "division",
        "class_teacher",
        "default_room"
    ).filter(
        is_active=True
    ).order_by(
        "school__name",
        "class_level__sort_order",
        "division__sort_order"
    )

    return [{
        "id": section.id,
        "name": f"{section.class_level.name} {section.division.name}",
        "class_level": section.class_level.name,
        "division": section.division.name,
        "section_type": section.class_level.section_type,
        "school_id": section.school.id,
        "school_name": section.school.name,
        "class_teacher_id": section.class_teacher.id if section.class_teacher else None,
        "class_teacher_name": section.class_teacher.name if section.class_teacher else "",
        "default_room_id": section.default_room.id if section.default_room else None,
        "default_room_name": section.default_room.name if section.default_room else "",
    } for section in class_sections]


def _builder_subjects_data():
    subjects = Subject.objects.select_related("school").filter(is_active=True).order_by("name")

    return [{
        "id": subject.id,
        "name": subject.name,
        "short_name": subject.short_name,
        "color": subject.color_code,
        "section_type": subject.section_type,
        "subject_type": subject.subject_type,
        "school_id": subject.school.id,
    } for subject in subjects]


def _builder_rooms_data():
    rooms = Room.objects.select_related("school").filter(is_active=True).order_by("name")

    return [{
        "id": room.id,
        "name": room.name,
        "room_type": room.room_type,
        "school_id": room.school.id,
    } for room in rooms]


def _entry_data_for_teacher(timetable, teacher):
    data = {}
    occupied = {}

    if not timetable:
        return data, occupied

    entries = TimetableEntry.objects.filter(
        timetable=timetable
    ).select_related(
        "class_section",
        "teacher",
        "subject",
        "room"
    )

    for entry in entries:
        key = f"{entry.class_section_id}_{entry.day_id_value}_{entry.period_id_value}"
        payload = {
            "class_section_id": entry.class_section.id if entry.class_section else None,
            "class_section_name": str(entry.class_section) if entry.class_section else "",
            "teacher_id": entry.teacher.id if entry.teacher else None,
            "teacher_name": entry.teacher.name if entry.teacher else "",
            "subject_id": entry.subject.id if entry.subject else None,
            "subject_name": entry.subject.name if entry.subject else "",
            "room_id": entry.room.id if entry.room else None,
            "room_name": entry.room.name if entry.room else "",
            "is_locked": entry.is_locked,
        }

        if entry.teacher_id == teacher.id:
            data[key] = payload
        else:
            occupied[key] = payload

    return data, occupied


def teacher_timetable_builder(request, teacher_id):
    auto_create_class_sections()

    teacher = get_object_or_404(Teacher, id=teacher_id, is_active=True)
    timetable_id = request.GET.get("timetable_id")

    timetables = Timetable.objects.select_related(
        "school",
        "academic_year"
    ).filter(is_active=True).order_by("-id")

    timetable = None
    if timetable_id:
        timetable = get_object_or_404(Timetable, id=timetable_id)
    else:
        timetable = timetables.first()

    timetable_entries, occupied_entries = _entry_data_for_teacher(timetable, teacher)

    context = {
        "teacher": teacher,
        "timetable": timetable,
        "timetables": timetables,
        "class_sections_json": _builder_class_sections_data(),
        "subjects_json": _builder_subjects_data(),
        "rooms_json": _builder_rooms_data(),
        "periods_json": _builder_periods_data(timetable),
        "timetable_entries_json": timetable_entries,
        "occupied_entries_json": occupied_entries,
    }

    return render(request, "teacher_timetable_builder.html", context)


@csrf_exempt
def save_timetable_entries(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body)

    timetable_id = data.get("timetable_id")
    entries = data.get("entries", [])

    if not timetable_id:
        return JsonResponse({"success": False, "message": "Timetable is required"})

    timetable = Timetable.objects.get(id=timetable_id)

    TimetableEntry.objects.filter(timetable=timetable).delete()

    for entry in entries:
        class_section = ClassSection.objects.get(id=entry["class_section_id"])

        subject = Subject.objects.filter(id=entry.get("subject_id")).first()
        teacher = Teacher.objects.filter(id=entry.get("teacher_id")).first()
        room = Room.objects.filter(id=entry.get("room_id")).first()

        TimetableEntry.objects.create(
            timetable=timetable,
            class_section=class_section,
            day_id_value=entry["day_id"],
            day_name=entry["day_name"],
            period_id_value=entry["period_id"],
            period_name=entry["period_name"],
            subject=subject,
            teacher=teacher,
            room=room,
            is_locked=entry.get("is_locked", False),
        )

    return JsonResponse({
        "success": True,
        "message": "Timetable saved successfully"
    })


@csrf_exempt
def save_teacher_timetable_entries(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body)

    timetable_id = data.get("timetable_id")
    teacher_id = data.get("teacher_id")
    entries = data.get("entries", [])

    if not timetable_id or not teacher_id:
        return JsonResponse({"success": False, "message": "Timetable and teacher are required"})

    timetable = get_object_or_404(Timetable, id=timetable_id)
    teacher = get_object_or_404(Teacher, id=teacher_id)

    target_keys = [
        (
            str(entry["class_section_id"]),
            str(entry["day_id"]),
            str(entry["period_id"]),
        )
        for entry in entries
    ]
    teacher_period_keys = [(day_id, period_id) for _, day_id, period_id in target_keys]

    if len(teacher_period_keys) != len(set(teacher_period_keys)):
        return JsonResponse({
            "success": False,
            "message": "This teacher cannot be assigned to more than one class in the same period."
        })

    with transaction.atomic():
        TimetableEntry.objects.filter(timetable=timetable, teacher=teacher).delete()

        for class_section_id, day_id, period_id in target_keys:
            TimetableEntry.objects.filter(
                timetable=timetable,
                class_section_id=class_section_id,
                day_id_value=day_id,
                period_id_value=period_id,
            ).exclude(teacher=teacher).delete()

        for entry in entries:
            room_id = entry.get("room_id")

            if not room_id:
                continue

            TimetableEntry.objects.filter(
                timetable=timetable,
                room_id=room_id,
                day_id_value=str(entry["day_id"]),
                period_id_value=str(entry["period_id"]),
            ).exclude(teacher=teacher).delete()

        for entry in entries:
            class_section = ClassSection.objects.get(id=entry["class_section_id"])

            subject = Subject.objects.filter(id=entry.get("subject_id")).first()
            room = Room.objects.filter(id=entry.get("room_id")).first()

            TimetableEntry.objects.create(
                timetable=timetable,
                class_section=class_section,
                day_id_value=entry["day_id"],
                day_name=entry["day_name"],
                period_id_value=entry["period_id"],
                period_name=entry["period_name"],
                subject=subject,
                teacher=teacher,
                room=room,
                is_locked=entry.get("is_locked", False),
            )

    return JsonResponse({
        "success": True,
        "message": f"{teacher.name}'s timetable saved successfully"
    })








from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from Academic.models import AcademicYear, BellSchedule
from Timetables.models import Timetable


@csrf_exempt
def create_timetable_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body)

    name = data.get("name")
    academic_year_id = data.get("academic_year_id")
    timetable_type = data.get("timetable_type", "PRIMARY")

    if not name or not academic_year_id:
        return JsonResponse({
            "success": False,
            "message": "Timetable name and academic year are required."
        })

    academic_year = AcademicYear.objects.get(id=academic_year_id)

    bell_schedule = BellSchedule.objects.filter(
        school=academic_year.school,
        academic_year=academic_year
    ).first()

    if not bell_schedule:
        return JsonResponse({
            "success": False,
            "message": "Please create Bell Schedule first."
        })

    timetable = Timetable.objects.create(
        school=academic_year.school,
        academic_year=academic_year,
        name=name,
        timetable_type=timetable_type,
        is_active=True
    )

    return JsonResponse({
        "success": True,
        "id": timetable.id,
        "name": timetable.name,
        "message": "Timetable created successfully."
    })






@csrf_exempt
def load_timetable_entries(request):
    timetable_id = request.GET.get("timetable_id")

    if not timetable_id:
        return JsonResponse({"success": False, "entries": {}})

    entries = TimetableEntry.objects.filter(
        timetable_id=timetable_id
    ).select_related(
        "class_section",
        "teacher",
        "subject",
        "room"
    )

    data = {}

    for entry in entries:
        key = f"{entry.class_section_id}_{entry.day_id_value}_{entry.period_id_value}"

        data[key] = {
            "teacher_id": entry.teacher.id if entry.teacher else None,
            "teacher_name": entry.teacher.name if entry.teacher else "",
            "subject_id": entry.subject.id if entry.subject else None,
            "subject_name": entry.subject.name if entry.subject else "",
            "room_id": entry.room.id if entry.room else None,
            "room_name": entry.room.name if entry.room else "",
            "is_locked": entry.is_locked,
        }

    return JsonResponse({
        "success": True,
        "entries": data
    })


def _parse_adjustment_date(value):
    if not value:
        return timezone.localdate()

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


def _status_data(status):
    return {
        "id": status.id,
        "teacher_id": status.teacher_id,
        "teacher_name": status.teacher.name,
        "status_type": status.status_type,
        "status_label": status.get_status_type_display(),
        "full_day": status.full_day,
        "period_ids": [str(period_id) for period_id in status.unavailable_periods.values_list("id", flat=True)],
        "reason": status.reason,
        "notes": status.notes,
    }


def _adjustment_data(adjustment):
    return {
        "id": adjustment.id,
        "entry_id": adjustment.original_entry_id,
        "proxy_teacher_id": adjustment.proxy_teacher_id,
        "proxy_teacher_name": adjustment.proxy_teacher.name if adjustment.proxy_teacher else "",
        "status": adjustment.status,
        "reason": adjustment.reason,
        "admin_note": adjustment.admin_note,
        "is_locked": adjustment.is_locked,
    }


def _period_is_status_covered(status, period_id):
    if status.full_day:
        return True

    return str(period_id) in {str(item) for item in status.unavailable_periods.values_list("id", flat=True)}


def _teacher_unavailable_status(statuses, teacher_id, period_id):
    for status in statuses:
        if status.teacher_id == teacher_id and _period_is_status_covered(status, period_id):
            return status

    return None


def _date_day_name(adjustment_date):
    return adjustment_date.strftime("%A")


def _teacher_day_load(timetable, adjustment_date, teacher_id):
    day_name = _date_day_name(adjustment_date)
    master_count = TimetableEntry.objects.filter(
        timetable=timetable,
        teacher_id=teacher_id,
        day_name__iexact=day_name,
    ).count()
    proxy_count = LectureAdjustment.objects.filter(
        timetable=timetable,
        date=adjustment_date,
        proxy_teacher_id=teacher_id,
        status="ASSIGNED",
    ).count()
    return master_count + proxy_count


def _teaching_period_count(timetable, day_name=None):
    periods = [period for period in _builder_periods_data(timetable) if period["is_teaching_period"]]

    if day_name:
        periods = [period for period in periods if period["day_name"].lower() == day_name.lower()]

    return len(periods)


def _teacher_load_payload(timetable, adjustment_date, teacher):
    day_name = _date_day_name(adjustment_date)
    total = _teaching_period_count(timetable, day_name)
    load = _teacher_day_load(timetable, adjustment_date, teacher.id)

    return {
        "id": teacher.id,
        "name": teacher.name,
        "department": teacher.department,
        "day_load": load,
        "free_periods": max(0, total - load),
        "total_periods": total,
    }


def _teacher_has_period_conflict(timetable, adjustment_date, teacher_id, day_id, period_id, original_entry_id=None):
    master_conflict = TimetableEntry.objects.filter(
        timetable=timetable,
        teacher_id=teacher_id,
        day_id_value=str(day_id),
        period_id_value=str(period_id),
    )

    if original_entry_id:
        master_conflict = master_conflict.exclude(id=original_entry_id)

    if master_conflict.exists():
        return True

    return LectureAdjustment.objects.filter(
        timetable=timetable,
        date=adjustment_date,
        proxy_teacher_id=teacher_id,
        period_id_value=str(period_id),
        status="ASSIGNED",
    ).exclude(original_entry_id=original_entry_id).exists()


def _teacher_static_available(teacher_id, day_id, period_id):
    availability = TeacherAvailability.objects.filter(
        teacher_id=teacher_id,
        day_id=day_id,
        period_id=period_id,
    ).first()

    return not availability or availability.is_available


def _suggest_proxy_teachers(entry, adjustment_date, statuses):
    if not entry.teacher_id:
        return []

    teachers = Teacher.objects.filter(
        school=entry.timetable.school,
        is_active=True,
    ).order_by("name")
    lesson_allocations = LessonAllocation.objects.filter(
        school=entry.timetable.school,
        academic_year=entry.timetable.academic_year,
        is_active=True,
    )
    class_teacher_id = entry.class_section.class_teacher_id if entry.class_section else None
    suggestions = []

    for teacher in teachers:
        if teacher.id == entry.teacher_id:
            continue

        unavailable = _teacher_unavailable_status(statuses, teacher.id, entry.period_id_value)
        if unavailable:
            continue

        if not _teacher_static_available(teacher.id, entry.day_id_value, entry.period_id_value):
            continue

        if _teacher_has_period_conflict(
            entry.timetable,
            adjustment_date,
            teacher.id,
            entry.day_id_value,
            entry.period_id_value,
            entry.id,
        ):
            continue

        score = 0
        tags = []

        if lesson_allocations.filter(class_section=entry.class_section, teacher=teacher).exists():
            score += 45
            tags.append("teaches this class")

        if entry.subject_id and lesson_allocations.filter(subject=entry.subject, teacher=teacher).exists():
            score += 35
            tags.append("same subject")

        if class_teacher_id and teacher.id == class_teacher_id:
            score += 25
            tags.append("class teacher")

        day_load = _teacher_day_load(entry.timetable, adjustment_date, teacher.id)
        score += max(0, 20 - day_load)
        total_periods = _teaching_period_count(entry.timetable, entry.day_name)

        suggestions.append({
            "id": teacher.id,
            "name": teacher.name,
            "department": teacher.department,
            "day_load": day_load,
            "free_periods": max(0, total_periods - day_load),
            "total_periods": total_periods,
            "score": score,
            "tags": tags or ["free teacher"],
        })

    return sorted(suggestions, key=lambda item: (-item["score"], item["day_load"], item["name"]))[:8]


def _entry_adjustment_payload(entry, adjustment_date, statuses, adjustment=None):
    covered_status = _teacher_unavailable_status(statuses, entry.teacher_id, entry.period_id_value)
    effective_adjustment = adjustment

    if not effective_adjustment:
        effective_adjustment = LectureAdjustment.objects.filter(
            date=adjustment_date,
            original_entry=entry,
        ).select_related("proxy_teacher").first()

    return {
        "entry_id": entry.id,
        "class_section": str(entry.class_section),
        "subject": entry.subject.name if entry.subject else "Subject",
        "room": entry.room.name if entry.room else "",
        "original_teacher_id": entry.teacher_id,
        "original_teacher": entry.teacher.name if entry.teacher else "",
        "day_id": entry.day_id_value,
        "day_name": entry.day_name,
        "period_id": entry.period_id_value,
        "period_name": entry.period_name,
        "reason": covered_status.reason if covered_status else "",
        "status_label": covered_status.get_status_type_display() if covered_status else "Manual adjustment",
        "teacher_status_id": covered_status.id if covered_status else None,
        "adjustment": _adjustment_data(effective_adjustment) if effective_adjustment else None,
        "suggestions": _suggest_proxy_teachers(entry, adjustment_date, statuses),
    }


def proxy_adjustment_panel(request):
    auto_create_class_sections()

    timetables = Timetable.objects.select_related("school", "academic_year").filter(is_active=True).order_by("-id")
    selected_timetable = timetables.first()
    teachers = Teacher.objects.select_related("school").filter(is_active=True)

    if selected_timetable:
        teachers = teachers.filter(school=selected_timetable.school)

    context = {
        "timetables": timetables,
        "selected_timetable_id": selected_timetable.id if selected_timetable else "",
        "selected_date": timezone.localdate().strftime("%Y-%m-%d"),
        "teachers_json": [{
            "id": teacher.id,
            "name": teacher.name,
            "school_id": teacher.school_id,
            "department": teacher.department,
        } for teacher in teachers.order_by("name")],
        "periods_json": _builder_periods_data(selected_timetable),
    }
    return render(request, "proxy_adjustment_panel.html", context)


@csrf_exempt
def proxy_adjustment_data(request):
    timetable_id = request.GET.get("timetable_id")
    adjustment_date = _parse_adjustment_date(request.GET.get("date"))
    manual_teacher_id = request.GET.get("teacher_id")

    if not timetable_id:
        return JsonResponse({"success": False, "message": "Timetable is required."})

    timetable = get_object_or_404(Timetable, id=timetable_id)
    day_name = _date_day_name(adjustment_date)
    statuses = list(TeacherDailyStatus.objects.filter(
        school=timetable.school,
        date=adjustment_date,
    ).select_related("teacher").prefetch_related("unavailable_periods"))

    entries = TimetableEntry.objects.filter(
        timetable=timetable,
        day_name__iexact=day_name,
    ).select_related("timetable", "class_section", "class_section__class_teacher", "subject", "teacher", "room")

    affected_entries = []
    seen_entry_ids = set()

    for entry in entries:
        covered_status = _teacher_unavailable_status(statuses, entry.teacher_id, entry.period_id_value)
        manual_match = manual_teacher_id and str(entry.teacher_id) == str(manual_teacher_id)
        existing_adjustment = LectureAdjustment.objects.filter(date=adjustment_date, original_entry=entry).first()

        if not covered_status and not manual_match and not existing_adjustment:
            continue

        affected_entries.append(_entry_adjustment_payload(entry, adjustment_date, statuses, existing_adjustment))
        seen_entry_ids.add(entry.id)

    saved_adjustments = LectureAdjustment.objects.filter(
        timetable=timetable,
        date=adjustment_date,
    ).select_related("original_entry", "class_section", "subject", "room", "original_teacher", "proxy_teacher")

    for adjustment in saved_adjustments:
        if adjustment.original_entry_id in seen_entry_ids:
            continue

        affected_entries.append(_entry_adjustment_payload(adjustment.original_entry, adjustment_date, statuses, adjustment))

    return JsonResponse({
        "success": True,
        "date": adjustment_date.strftime("%Y-%m-%d"),
        "day_name": day_name,
        "periods": _builder_periods_data(timetable),
        "teachers": [
            _teacher_load_payload(timetable, adjustment_date, teacher)
            for teacher in Teacher.objects.filter(school=timetable.school, is_active=True).order_by("name")
        ],
        "teacher_statuses": [_status_data(status) for status in statuses],
        "lectures": affected_entries,
    })


@csrf_exempt
def save_teacher_daily_status(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})

    data = json.loads(request.body)
    teacher = get_object_or_404(Teacher, id=data.get("teacher_id"), is_active=True)
    adjustment_date = _parse_adjustment_date(data.get("date"))
    status_type = data.get("status_type") or "LEAVE"
    full_day = bool(data.get("full_day", True))
    period_ids = data.get("period_ids", [])

    if status_type not in {"LEAVE", "IN_SCHOOL_UNAVAILABLE"}:
        return JsonResponse({"success": False, "message": "Invalid status type."})

    status, _ = TeacherDailyStatus.objects.update_or_create(
        teacher=teacher,
        date=adjustment_date,
        defaults={
            "school": teacher.school,
            "status_type": status_type,
            "full_day": full_day,
            "reason": data.get("reason", ""),
            "notes": data.get("notes", ""),
        },
    )

    if full_day:
        status.unavailable_periods.clear()
    else:
        status.unavailable_periods.set(Period.objects.filter(id__in=period_ids))

    return JsonResponse({
        "success": True,
        "message": "Teacher availability status saved.",
        "teacher_status": _status_data(status),
    })


@csrf_exempt
def delete_teacher_daily_status(request, status_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})

    status = get_object_or_404(TeacherDailyStatus, id=status_id)
    LectureAdjustment.objects.filter(
        timetable__school=status.school,
        date=status.date,
    ).filter(
        Q(original_teacher=status.teacher) | Q(original_entry__teacher=status.teacher)
    ).delete()
    status.delete()

    return JsonResponse({"success": True, "message": "Teacher status and linked lecture adjustments removed."})


def _create_or_update_adjustment(entry, adjustment_date, payload, teacher_status=None):
    return LectureAdjustment.objects.update_or_create(
        date=adjustment_date,
        original_entry=entry,
        defaults={
            "timetable": entry.timetable,
            "teacher_status": teacher_status,
            "original_teacher": entry.teacher,
            "proxy_teacher_id": payload.get("proxy_teacher_id") or None,
            "class_section": entry.class_section,
            "subject": entry.subject,
            "room": entry.room,
            "day_id_value": entry.day_id_value,
            "day_name": entry.day_name,
            "period_id_value": entry.period_id_value,
            "period_name": entry.period_name,
            "status": payload.get("status", "ASSIGNED"),
            "reason": payload.get("reason", ""),
            "admin_note": payload.get("admin_note", ""),
            "is_locked": bool(payload.get("is_locked", False)),
        },
    )


@csrf_exempt
def save_lecture_adjustment(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})

    data = json.loads(request.body)
    entry = get_object_or_404(
        TimetableEntry.objects.select_related("timetable", "teacher", "class_section", "subject", "room"),
        id=data.get("entry_id"),
    )
    adjustment_date = _parse_adjustment_date(data.get("date"))
    status_value = data.get("status", "ASSIGNED")
    proxy_teacher_id = data.get("proxy_teacher_id")

    if status_value not in {"PENDING", "ASSIGNED", "CANCELLED"}:
        return JsonResponse({"success": False, "message": "Invalid adjustment status."})

    if status_value == "ASSIGNED":
        if not proxy_teacher_id:
            return JsonResponse({"success": False, "message": "Please select a proxy teacher."})

        proxy_teacher = get_object_or_404(Teacher, id=proxy_teacher_id, school=entry.timetable.school, is_active=True)
        statuses = list(TeacherDailyStatus.objects.filter(
            school=entry.timetable.school,
            date=adjustment_date,
        ).prefetch_related("unavailable_periods"))

        if _teacher_unavailable_status(statuses, proxy_teacher.id, entry.period_id_value):
            return JsonResponse({"success": False, "message": "Selected proxy teacher is unavailable in this period."})

        if not _teacher_static_available(proxy_teacher.id, entry.day_id_value, entry.period_id_value):
            return JsonResponse({"success": False, "message": "Selected proxy teacher is marked unavailable in weekly availability."})

        if _teacher_has_period_conflict(
            entry.timetable,
            adjustment_date,
            proxy_teacher.id,
            entry.day_id_value,
            entry.period_id_value,
            entry.id,
        ):
            return JsonResponse({"success": False, "message": "Selected proxy teacher already has a lecture in this period."})

    teacher_status = TeacherDailyStatus.objects.filter(
        teacher=entry.teacher,
        date=adjustment_date,
    ).first()

    adjustment, _ = _create_or_update_adjustment(entry, adjustment_date, data, teacher_status)

    return JsonResponse({
        "success": True,
        "message": "Lecture adjustment saved.",
        "adjustment": _adjustment_data(adjustment),
    })


@csrf_exempt
def delete_lecture_adjustment(request, adjustment_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})

    adjustment = get_object_or_404(LectureAdjustment, id=adjustment_id)
    adjustment.delete()

    return JsonResponse({"success": True, "message": "Lecture adjustment deleted."})


def export_proxy_adjustments(request):
    timetable_id = request.GET.get("timetable_id")
    adjustment_date = _parse_adjustment_date(request.GET.get("date"))

    if not timetable_id:
        return JsonResponse({"success": False, "message": "Timetable is required."}, status=400)

    timetable = get_object_or_404(Timetable.objects.select_related("school", "academic_year"), id=timetable_id)
    adjustments = LectureAdjustment.objects.filter(
        timetable=timetable,
        date=adjustment_date,
    ).select_related(
        "class_section",
        "class_section__class_level",
        "class_section__division",
        "subject",
        "original_teacher",
        "proxy_teacher",
    ).order_by("period_id_value", "class_section__class_level__sort_order", "class_section__division__sort_order")

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Adjusted Lectures"

    sheet.merge_cells("A1:F1")
    sheet.merge_cells("A2:F2")
    sheet["A1"] = timetable.school.name
    sheet["A2"] = f"Adjusted Lectures - {adjustment_date.strftime('%d-%m-%Y')} ({_date_day_name(adjustment_date)})"

    headers = [
        "Period",
        "Original Teacher",
        "Class-Division",
        "Subject",
        "Adjusted Teacher",
        "Signature",
    ]
    sheet.append([])
    sheet.append(headers)

    for adjustment in adjustments:
        class_level = adjustment.class_section.class_level.name if adjustment.class_section else ""
        division = adjustment.class_section.division.name if adjustment.class_section else ""
        class_division = f"{class_level} {division}".strip()
        teacher_name = adjustment.proxy_teacher.name if adjustment.proxy_teacher else ""

        sheet.append([
            adjustment.period_name,
            adjustment.original_teacher.name if adjustment.original_teacher else "",
            class_division,
            adjustment.subject.name if adjustment.subject else "",
            teacher_name,
            "",
        ])

    school_fill = PatternFill("solid", fgColor="0F172A")
    subtitle_fill = PatternFill("solid", fgColor="DBEAFE")
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    sheet["A1"].fill = school_fill
    sheet["A1"].font = Font(color="FFFFFF", bold=True, size=18)
    sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
    sheet["A2"].fill = subtitle_fill
    sheet["A2"].font = Font(color="0F172A", bold=True, size=12)
    sheet["A2"].alignment = Alignment(horizontal="center", vertical="center")

    for row_index in (1, 2):
        for col_index in range(1, 7):
            cell = sheet.cell(row=row_index, column=col_index)
            cell.border = border
            if row_index == 1:
                cell.fill = school_fill
            else:
                cell.fill = subtitle_fill

    for cell in sheet[4]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for row in sheet.iter_rows(min_row=5):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    for row_index in range(5, sheet.max_row + 1):
        sheet.row_dimensions[row_index].height = 32

    widths = [18, 28, 20, 24, 28, 26]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    sheet.row_dimensions[1].height = 30
    sheet.row_dimensions[2].height = 24
    sheet.freeze_panes = "A5"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)

    filename = f"adjusted-lectures-{adjustment_date.strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _safe_sheet_title(title, existing_titles):
    clean = re.sub(r"[\[\]\:\*\?\/\\]", " ", str(title)).strip() or "Timetable"
    clean = re.sub(r"\s+", " ", clean)[:31]
    candidate = clean
    index = 2

    while candidate in existing_titles:
        suffix = f" {index}"
        candidate = f"{clean[:31 - len(suffix)]}{suffix}"
        index += 1

    existing_titles.add(candidate)
    return candidate


def _ordered_export_days(periods_data):
    days = []
    seen = set()

    for period in periods_data:
        key = str(period["day_id"])
        if key in seen:
            continue

        seen.add(key)
        days.append({
            "id": period["day_id"],
            "name": period["day_name"],
            "type": period["day_type"],
        })

    return days


def _ordered_export_period_rows(periods_data):
    rows = []
    seen = set()

    for period in periods_data:
        key = (
            period["period_number"],
            period["period_name"],
            period["period_type"],
            period["is_teaching_period"],
        )

        if key in seen:
            continue

        seen.add(key)
        rows.append({
            "number": period["period_number"],
            "name": period["period_name"],
            "type": period["period_type"],
            "is_teaching_period": period["is_teaching_period"],
            "start_time": period["start_time"],
            "end_time": period["end_time"],
        })

    return sorted(rows, key=lambda item: item["number"])


def _period_for_day_row(periods_data, day_id, row):
    for period in periods_data:
        if (
            str(period["day_id"]) == str(day_id) and
            period["period_number"] == row["number"] and
            period["period_name"] == row["name"] and
            period["period_type"] == row["type"]
        ):
            return period

    return None


def _export_entities(scope, timetable):
    if scope == "class":
        return ClassSection.objects.select_related(
            "class_level",
            "division",
            "class_teacher",
            "default_room",
        ).filter(
            school=timetable.school,
            is_active=True,
        ).order_by("class_level__sort_order", "division__sort_order", "id")

    return Teacher.objects.filter(
        school=timetable.school,
        is_active=True,
    ).order_by("name", "id")


def _export_entry_lookup(timetable, scope):
    entries = TimetableEntry.objects.filter(
        timetable=timetable
    ).select_related(
        "class_section",
        "teacher",
        "subject",
        "room",
    )
    lookup = {}

    for entry in entries:
        if scope == "class":
            key = (str(entry.class_section_id), str(entry.day_id_value), str(entry.period_id_value))
        else:
            if not entry.teacher_id:
                continue
            key = (str(entry.teacher_id), str(entry.day_id_value), str(entry.period_id_value))

        lookup[key] = entry

    return lookup


def _entry_text(entry, scope):
    if not entry:
        return ""

    parts = []

    if scope == "class":
        parts.append(entry.subject.name if entry.subject else "Subject")
        parts.append(entry.teacher.name if entry.teacher else "Teacher")
    else:
        parts.append(str(entry.class_section) if entry.class_section else "Class")
        parts.append(entry.subject.name if entry.subject else "Subject")

    if entry.room:
        parts.append(f"Room: {entry.room.name}")

    if entry.is_locked:
        parts.append("Locked")

    return "\n".join(parts)


def _entity_title(entity, scope):
    if scope == "class":
        return str(entity)

    return entity.name


def _entity_subtitle(entity, scope):
    if scope == "class":
        teacher = entity.class_teacher.name if entity.class_teacher else "Not assigned"
        room = entity.default_room.name if entity.default_room else "Not assigned"
        return f"Class Teacher: {teacher} | Default Room: {room}"

    bits = []
    if entity.employee_id:
        bits.append(f"Employee ID: {entity.employee_id}")
    if entity.department:
        bits.append(f"Department: {entity.department}")
    bits.append(f"Max Load: {entity.max_periods_per_day}/day, {entity.max_periods_per_week}/week")
    return " | ".join(bits)


def _export_filename(timetable, scope, extension):
    school = re.sub(r"[^A-Za-z0-9]+", "-", timetable.school.short_name or timetable.school.name).strip("-")
    name = re.sub(r"[^A-Za-z0-9]+", "-", timetable.name).strip("-")
    return f"{school}-{name}-{scope}-wise-timetable.{extension}"


def _build_excel_timetable(timetable, scope):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    periods_data = _builder_periods_data(timetable)
    days = _ordered_export_days(periods_data)
    rows = _ordered_export_period_rows(periods_data)
    entities = _export_entities(scope, timetable)
    entries = _export_entry_lookup(timetable, scope)

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"

    navy = "0F172A"
    blue = "1D4ED8"
    light_blue = "DBEAFE"
    soft = "F8FAFC"
    border_color = "CBD5E1"
    break_fill = "FFF7ED"
    teaching_fill = "FFFFFF"
    title_fill = PatternFill("solid", fgColor=navy)
    header_fill = PatternFill("solid", fgColor=blue)
    sub_fill = PatternFill("solid", fgColor=light_blue)
    thin = Side(style="thin", color=border_color)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_heading(sheet, title, subtitle):
        last_col = max(2, len(days) + 1)
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        sheet.merge_cells(start_row=3, start_column=1, end_row=3, end_column=last_col)

        sheet["A1"] = timetable.school.name
        sheet["A2"] = title
        sheet["A3"] = subtitle

        for row in range(1, 4):
            cell = sheet.cell(row=row, column=1)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.font = Font(color="FFFFFF" if row == 1 else navy, bold=True, size=18 if row == 1 else 12)
            cell.fill = title_fill if row == 1 else sub_fill

        sheet.row_dimensions[1].height = 30
        sheet.row_dimensions[2].height = 24
        sheet.row_dimensions[3].height = 34

    summary["A1"] = timetable.school.name
    summary["A2"] = "Timetable Export Summary"
    summary["A4"] = "Timetable"
    summary["B4"] = timetable.name
    summary["A5"] = "Academic Year"
    summary["B5"] = timetable.academic_year.name
    summary["A6"] = "School Code"
    summary["B6"] = timetable.school.school_code
    summary["A7"] = "Contact"
    summary["B7"] = timetable.school.contact_number
    summary["A8"] = "Email"
    summary["B8"] = timetable.school.email
    summary["A9"] = "Export Type"
    summary["B9"] = "Class-wise Timetable" if scope == "class" else "Teacher-wise Timetable"
    summary["A10"] = "Generated On"
    summary["B10"] = timezone.localtime().strftime("%d %b %Y, %I:%M %p")
    summary["A12"] = "Total Sheets"
    summary["B12"] = len(entities)

    summary.merge_cells("A1:D1")
    summary.merge_cells("A2:D2")
    summary["A1"].fill = title_fill
    summary["A1"].font = Font(color="FFFFFF", bold=True, size=20)
    summary["A1"].alignment = Alignment(horizontal="center")
    summary["A2"].fill = sub_fill
    summary["A2"].font = Font(color=navy, bold=True, size=14)
    summary["A2"].alignment = Alignment(horizontal="center")

    for row in range(4, 13):
        summary.cell(row=row, column=1).font = Font(bold=True, color=navy)
        summary.cell(row=row, column=1).fill = PatternFill("solid", fgColor=soft)
        summary.cell(row=row, column=1).border = border
        summary.cell(row=row, column=2).border = border

    summary.column_dimensions["A"].width = 24
    summary.column_dimensions["B"].width = 42
    summary.sheet_view.showGridLines = False

    existing_titles = {"Summary"}

    for entity in entities:
        sheet = workbook.create_sheet(_safe_sheet_title(_entity_title(entity, scope), existing_titles))
        sheet.sheet_view.showGridLines = False
        style_heading(sheet, f"{'Class' if scope == 'class' else 'Teacher'} Timetable: {_entity_title(entity, scope)}", _entity_subtitle(entity, scope))

        sheet.cell(row=5, column=1, value="Period / Day")
        for col, day in enumerate(days, start=2):
            sheet.cell(row=5, column=col, value=day["name"])

        for col in range(1, len(days) + 2):
            cell = sheet.cell(row=5, column=col)
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        for row_index, period_row in enumerate(rows, start=6):
            label = f"{period_row['name']}\n{period_row['start_time']} - {period_row['end_time']}"
            period_cell = sheet.cell(row=row_index, column=1, value=label)
            period_cell.font = Font(bold=True, color=navy)
            period_cell.fill = sub_fill
            period_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            period_cell.border = border

            for col, day in enumerate(days, start=2):
                period = _period_for_day_row(periods_data, day["id"], period_row)
                cell = sheet.cell(row=row_index, column=col)
                cell.border = border
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

                if not period:
                    cell.fill = PatternFill("solid", fgColor="E5E7EB")
                    continue

                if not period["is_teaching_period"]:
                    cell.value = period["period_name"]
                    cell.fill = PatternFill("solid", fgColor=break_fill)
                    cell.font = Font(bold=True, color="9A3412")
                    continue

                entry = entries.get((str(entity.id), str(period["day_id"]), str(period["period_id"])))
                cell.value = _entry_text(entry, scope)
                cell.fill = PatternFill("solid", fgColor=teaching_fill)
                cell.font = Font(color=navy, bold=bool(entry))

        sheet.freeze_panes = "B6"
        sheet.column_dimensions["A"].width = 22

        for col in range(2, len(days) + 2):
            sheet.column_dimensions[get_column_letter(col)].width = 26

        for row_index in range(6, len(rows) + 6):
            sheet.row_dimensions[row_index].height = 58

        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_margins.left = 0.25
        sheet.page_margins.right = 0.25
        sheet.page_margins.top = 0.35
        sheet.page_margins.bottom = 0.35

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream.getvalue()


def _build_pdf_timetable(timetable, scope):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    periods_data = _builder_periods_data(timetable)
    days = _ordered_export_days(periods_data)
    rows = _ordered_export_period_rows(periods_data)
    entities = list(_export_entities(scope, timetable))
    entries = _export_entry_lookup(timetable, scope)
    stream = BytesIO()

    doc = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=0.28 * inch,
        rightMargin=0.28 * inch,
        topMargin=0.25 * inch,
        bottomMargin=0.25 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "ExportSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=7,
        leading=8,
        textColor=colors.HexColor("#0F172A"),
    )
    header_style = ParagraphStyle(
        "HeaderCell",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    period_style = ParagraphStyle(
        "PeriodCell",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )

    story = []

    for index, entity in enumerate(entities):
        if index:
            story.append(PageBreak())

        contact_bits = [
            timetable.academic_year.name,
            timetable.name,
            timetable.school.address,
            timetable.school.contact_number,
            timetable.school.email,
        ]
        contact_text = " | ".join([bit for bit in contact_bits if bit])

        story.append(Paragraph(timetable.school.name, title_style))
        story.append(Paragraph(contact_text, subtitle_style))
        story.append(Paragraph(f"{'Class' if scope == 'class' else 'Teacher'} Timetable: {_entity_title(entity, scope)}", title_style))
        story.append(Paragraph(_entity_subtitle(entity, scope), subtitle_style))
        story.append(Spacer(1, 5))

        table_data = [[Paragraph("Period / Day", header_style)] + [Paragraph(day["name"], header_style) for day in days]]

        for period_row in rows:
            label = f"{period_row['name']}<br/>{period_row['start_time']} - {period_row['end_time']}"
            row = [Paragraph(label, period_style)]

            for day in days:
                period = _period_for_day_row(periods_data, day["id"], period_row)

                if not period:
                    row.append("")
                    continue

                if not period["is_teaching_period"]:
                    row.append(Paragraph(f"<b>{period['period_name']}</b>", period_style))
                    continue

                entry = entries.get((str(entity.id), str(period["day_id"]), str(period["period_id"])))
                row.append(Paragraph(_entry_text(entry, scope).replace("\n", "<br/>"), cell_style))

            table_data.append(row)

        usable_width = landscape(A4)[0] - doc.leftMargin - doc.rightMargin
        first_width = 1.35 * inch
        day_width = (usable_width - first_width) / max(1, len(days))
        table = Table(table_data, colWidths=[first_width] + [day_width] * len(days), repeatRows=1)
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#DBEAFE")),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ])

        for row_index, period_row in enumerate(rows, start=1):
            if not period_row["is_teaching_period"]:
                style.add("BACKGROUND", (1, row_index), (-1, row_index), colors.HexColor("#FFF7ED"))
                style.add("TEXTCOLOR", (1, row_index), (-1, row_index), colors.HexColor("#9A3412"))

        table.setStyle(style)
        story.append(table)

    doc.build(story)
    stream.seek(0)
    return stream.getvalue()


def export_timetable(request, timetable_id, scope, file_format):
    if scope not in {"class", "teacher"}:
        return JsonResponse({"success": False, "message": "Invalid export scope"}, status=400)

    if file_format not in {"xlsx", "pdf"}:
        return JsonResponse({"success": False, "message": "Invalid export format"}, status=400)

    timetable = get_object_or_404(
        Timetable.objects.select_related("school", "academic_year"),
        id=timetable_id,
    )

    if file_format == "xlsx":
        content = _build_excel_timetable(timetable, scope)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = _build_pdf_timetable(timetable, scope)
        content_type = "application/pdf"

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{_export_filename(timetable, scope, file_format)}"'
    return response
