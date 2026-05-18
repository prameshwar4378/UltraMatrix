from django.db import models
from django.conf import settings
from Schools.models import School
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class Notification(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    @log_exceptions
    def __str__(self):
        return self.title