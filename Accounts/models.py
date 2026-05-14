from django.db import models
from django.conf import settings
from Schools.models import School


class SchoolUser(models.Model):

    ROLE_CHOICES = (
        ("OWNER", "Owner"),
        ("ADMIN", "Admin"),
        ("TEACHER", "Teacher"),
        ("STAFF", "Staff"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="school_users"
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="ADMIN"
    )

    is_active = models.BooleanField(default=True)

    has_completed_onboarding = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.school}"
