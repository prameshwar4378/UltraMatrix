from django.db import models
from Schools.models import School
from Teachers.models import Teacher
from Classes.models import ClassLevel


class Subject(models.Model):

    SECTION_CHOICES = (
        ("Pre-Primary", "Pre-Primary"),
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary"),
        ("Senior-Secondary", " Senior-Secondary"),
        ("BOTH", "Both"),
    )

    SUBJECT_TYPE_CHOICES = (
        ("THEORY", "Theory"),
        ("PRACTICAL", "Practical"),
        ("ACTIVITY", "Activity"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=100)

    short_name = models.CharField(
        max_length=30,
        blank=True
    )

    code = models.CharField(
        max_length=50,
        blank=True
    )

    section_type = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default="BOTH"
    )

    subject_type = models.CharField(
        max_length=20,
        choices=SUBJECT_TYPE_CHOICES,
        default="THEORY"
    )

    color_code = models.CharField(
        max_length=20,
        default="#0d6efd"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TeacherSubjectCapability(models.Model):

    PRIORITY_CHOICES = (
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary"),
        ("BACKUP", "Backup"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    class_levels = models.ManyToManyField(
        ClassLevel,
        blank=True
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="PRIMARY"
    )

    def __str__(self):
        return f"{self.teacher} - {self.subject}"