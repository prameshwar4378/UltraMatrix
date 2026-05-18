from django.db import models
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class School(models.Model):

    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=100, blank=True)

    logo = models.ImageField(
        upload_to="school_logos/",
        null=True,
        blank=True
    )

    address = models.TextField(blank=True)

    contact_number = models.CharField(
        max_length=20,
        blank=True
    )

    email = models.EmailField(blank=True)

    principal_name = models.CharField(
        max_length=255,
        blank=True
    )

    school_code = models.CharField(
        max_length=100,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @log_exceptions
    def __str__(self):
        return self.name
    

 