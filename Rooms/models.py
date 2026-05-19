from django.db import models
from Schools.models import School
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class Room(models.Model):

    ROOM_TYPE_CHOICES = (
        ("CLASSROOM", "Classroom"),
        ("COMPUTER_LAB", "Computer Lab"),
        ("SCIENCE_LAB", "Science Lab"),
        ("LIBRARY", "Library"),
        ("PLAYGROUND", "Playground"),
        ("ACTIVITY_ROOM", "Activity Room"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    timetable = models.ForeignKey(
        "Timetables.Timetable",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="rooms"
    )

    name = models.CharField(max_length=100)

    short_name = models.CharField(
        max_length=30,
        blank=True
    )

    room_type = models.CharField(
        max_length=30,
        choices=ROOM_TYPE_CHOICES,
        default="CLASSROOM"
    )

    capacity = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    @log_exceptions
    def __str__(self):
        return self.name
