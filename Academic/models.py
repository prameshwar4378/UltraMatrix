from django.db import models
from Schools.models import School


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Day(models.Model):
    DAY_TYPE_CHOICES = (
        ("WEEKDAY", "Weekday"),
        ("SATURDAY", "Saturday"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    short_name = models.CharField(max_length=10)
    sort_order = models.PositiveIntegerField(default=1)
    day_type = models.CharField(max_length=20, choices=DAY_TYPE_CHOICES, default="WEEKDAY")
    is_working = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class BellSchedule(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Period(models.Model):
    DAY_TYPE_CHOICES = (
        ("WEEKDAY", "Monday to Friday"),
        ("SATURDAY", "Saturday"),
    )

    PERIOD_TYPE_CHOICES = (
        ("TEACHING", "Teaching"),
        ("BREAK", "Break"),
        ("LUNCH", "Lunch"),
        ("ASSEMBLY", "Assembly"),
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    bell_schedule = models.ForeignKey(BellSchedule, on_delete=models.CASCADE, related_name="periods")

    day_type = models.CharField(max_length=20, choices=DAY_TYPE_CHOICES, default="WEEKDAY")
    name = models.CharField(max_length=100)
    period_number = models.PositiveIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default="TEACHING")
    is_teaching_period = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.day_type}"