from django.db import models

from Schools.models import School
from Academic.models import AcademicYear, Day, Period, BellSchedule
from Classes.models import ClassLevel, Division
from Teachers.models import Teacher
from Subjects.models import Subject
from Rooms.models import Room
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class ClassSection(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    timetable = models.ForeignKey(
        "Timetables.Timetable",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="class_sections"
    )

    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE
    )

    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE
    )

    class_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_teacher_sections"
    )

    default_room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    capacity = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    @log_exceptions
    def __str__(self):
        return f"{self.class_level} {self.division}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "class_level", "division"],
                name="unique_class_section_per_school_level_division",
            ),
        ]


class LessonAllocation(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    timetable = models.ForeignKey(
        "Timetables.Timetable",
        on_delete=models.CASCADE,
        related_name="lesson_allocations",
        null=True,
        blank=True
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE
    )

    class_section = models.ForeignKey(
        ClassSection,
        on_delete=models.CASCADE
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE
    )

    default_room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    weekly_periods = models.PositiveIntegerField(default=1)

    requires_double_period = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    @log_exceptions
    def __str__(self):
        return f"{self.class_section} - {self.subject}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["timetable", "class_section", "subject"],
                condition=models.Q(timetable__isnull=False),
                name="unique_lesson_allocation_per_timetable_class_subject",
            ),
        ]


class Timetable(models.Model):

    TIMETABLE_TYPE_CHOICES = (
        ("PRE-PRIMARY", "Pre-Primary"),
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary"),
        ("SENIOR-SECONDARY", "Senior-Secondary"),
    )

    school = models.ForeignKey(
        "Schools.School",
        on_delete=models.CASCADE
    )

    academic_year = models.ForeignKey(
        "Academic.AcademicYear",
        on_delete=models.CASCADE,
        related_name="timetables"
    )

    name = models.CharField(max_length=255)

    timetable_type = models.CharField(
        max_length=20,
        choices=TIMETABLE_TYPE_CHOICES
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @log_exceptions
    def __str__(self):
        return self.name
    


class TimetableConfiguration(models.Model):

    timetable = models.OneToOneField(
        Timetable,
        on_delete=models.CASCADE,
        related_name="configuration"
    )

    class_sections = models.ManyToManyField(
        ClassSection,
        blank=True,
        related_name="timetable_configurations"
    )

    bell_schedule = models.ForeignKey(
        BellSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_configurations"
    )

    working_days = models.ManyToManyField(
        Day,
        blank=True,
        related_name="timetable_configurations"
    )

    periods = models.ManyToManyField(
        Period,
        blank=True,
        related_name="timetable_configurations"
    )

    teachers = models.ManyToManyField(
        Teacher,
        blank=True,
        related_name="timetable_configurations"
    )

    rooms = models.ManyToManyField(
        Room,
        blank=True,
        related_name="timetable_configurations"
    )

    updated_at = models.DateTimeField(auto_now=True)

    @log_exceptions
    def __str__(self):
        return f"Configuration - {self.timetable}"


class TimetableVersion(models.Model):

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    name = models.CharField(max_length=100)

    version_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @log_exceptions
    def __str__(self):
        return f"{self.timetable} - v{self.version_number}"


class TimetableSlot(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE
    )

    version = models.ForeignKey(
        TimetableVersion,
        on_delete=models.CASCADE
    )

    class_section = models.ForeignKey(
        ClassSection,
        on_delete=models.CASCADE
    )

    lesson_allocation = models.ForeignKey(
        LessonAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    day = models.ForeignKey(
        Day,
        on_delete=models.CASCADE
    )

    period = models.ForeignKey(
        Period,
        on_delete=models.CASCADE
    )

    is_locked = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @log_exceptions
    def __str__(self):
        return f"{self.class_section} - {self.day} - {self.period}"
    
 





class TimetableEntry(models.Model):
    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="entries"
    )

    class_section = models.ForeignKey(
        ClassSection,
        on_delete=models.CASCADE
    )

    day_id_value = models.CharField(max_length=50)
    day_name = models.CharField(max_length=50)

    period_id_value = models.CharField(max_length=50)
    period_name = models.CharField(max_length=100)

    subject = models.ForeignKey(
        "Subjects.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    teacher = models.ForeignKey(
        "Teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    room = models.ForeignKey(
        "Rooms.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    is_locked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "timetable",
            "class_section",
            "day_id_value",
            "period_id_value",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["timetable", "teacher", "day_id_value", "period_id_value"],
                condition=models.Q(teacher__isnull=False),
                name="unique_teacher_per_timetable_period",
            ),
            models.UniqueConstraint(
                fields=["timetable", "room", "day_id_value", "period_id_value"],
                condition=models.Q(room__isnull=False),
                name="unique_room_per_timetable_period",
            ),
        ]

    @log_exceptions
    def __str__(self):
        return f"{self.timetable} - {self.class_section} - {self.day_name} {self.period_name}"


class TeacherDailyStatus(models.Model):

    STATUS_TYPE_CHOICES = (
        ("LEAVE", "On Leave"),
        ("IN_SCHOOL_UNAVAILABLE", "In School But Unavailable"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="daily_statuses"
    )

    date = models.DateField()

    status_type = models.CharField(
        max_length=30,
        choices=STATUS_TYPE_CHOICES,
        default="LEAVE"
    )

    full_day = models.BooleanField(default=True)

    unavailable_periods = models.ManyToManyField(
        Period,
        blank=True,
        related_name="teacher_daily_statuses"
    )

    reason = models.CharField(
        max_length=255,
        blank=True
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("teacher", "date")
        ordering = ("-date", "teacher__name")

    @log_exceptions
    def __str__(self):
        return f"{self.teacher} - {self.date} - {self.get_status_type_display()}"

    @log_exceptions
    def covers_period(self, period_id):
        if self.full_day:
            return True

        return self.unavailable_periods.filter(id=period_id).exists()


class LectureAdjustment(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("ASSIGNED", "Assigned"),
        ("CANCELLED", "Cancelled"),
    )

    date = models.DateField()

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="lecture_adjustments"
    )

    original_entry = models.ForeignKey(
        TimetableEntry,
        on_delete=models.CASCADE,
        related_name="daily_adjustments"
    )

    teacher_status = models.ForeignKey(
        TeacherDailyStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lecture_adjustments"
    )

    original_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="original_daily_adjustments"
    )

    proxy_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proxy_daily_adjustments"
    )

    class_section = models.ForeignKey(
        ClassSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    day_id_value = models.CharField(max_length=50)
    day_name = models.CharField(max_length=50)
    period_id_value = models.CharField(max_length=50)
    period_name = models.CharField(max_length=100)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    reason = models.CharField(
        max_length=255,
        blank=True
    )

    admin_note = models.TextField(blank=True)

    is_locked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("date", "original_entry")
        ordering = ("date", "day_name", "period_id_value", "class_section__class_level__sort_order")

    @log_exceptions
    def __str__(self):
        return f"{self.date} - {self.original_entry} - {self.status}"
