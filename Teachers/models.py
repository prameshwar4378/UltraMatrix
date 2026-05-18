from django.db import models
from Schools.models import School
from Academic.models import Day, Period
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class Teacher(models.Model):

    TEACHER_TYPE_CHOICES = (
        ("FULL_TIME", "Full Time"),
        ("PART_TIME", "Part Time"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=255)

    short_name = models.CharField(
        max_length=50,
        blank=True
    )

    employee_id = models.CharField(
        max_length=100,
        blank=True
    )

    mobile_number = models.CharField(
        max_length=20,
        blank=True
    )

    email = models.EmailField(blank=True)

    teacher_type = models.CharField(
        max_length=20,
        choices=TEACHER_TYPE_CHOICES,
        default="FULL_TIME"
    )

    department = models.CharField(
        max_length=100,
        blank=True
    )

    max_periods_per_day = models.PositiveIntegerField(default=6)
    max_periods_per_week = models.PositiveIntegerField(default=30)

    is_active = models.BooleanField(default=True)

    @log_exceptions
    def __str__(self):
        return self.name


class TeacherAvailability(models.Model):

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE
    )

    day = models.ForeignKey(
        Day,
        on_delete=models.CASCADE
    )

    period = models.ForeignKey(
        Period,
        on_delete=models.CASCADE
    )

    is_available = models.BooleanField(default=True)

    note = models.CharField(
        max_length=255,
        blank=True
    )

    @log_exceptions
    def __str__(self):
        return f"{self.teacher} - {self.day}"