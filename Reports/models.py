from django.db import models
from django.conf import settings

from Schools.models import School
from Timetables.models import Timetable


class ExportLog(models.Model):

    EXPORT_TYPE_CHOICES = (
        ("PDF", "PDF"),
        ("EXCEL", "Excel"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE
    )

    export_type = models.CharField(
        max_length=20,
        choices=EXPORT_TYPE_CHOICES
    )

    exported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timetable} - {self.export_type}"