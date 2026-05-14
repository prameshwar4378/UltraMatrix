from django.db import models
from Schools.models import School


class ClassLevel(models.Model):

    SECTION_CHOICES = (
        ("Pre-Primary", "Pre-Primary"),
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary"),
        (" Senior-Secondary", " Senior-Secondary"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=50)

    short_name = models.CharField(
        max_length=20,
        blank=True
    )

    sort_order = models.PositiveIntegerField(default=1)

    section_type = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Division(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=20)

    sort_order = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name