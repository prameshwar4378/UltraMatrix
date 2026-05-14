from django.db import models
from Schools.models import School


class SubscriptionPlan(models.Model):

    name = models.CharField(max_length=100)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    max_teachers = models.PositiveIntegerField(default=0)
    max_classes = models.PositiveIntegerField(default=0)
    max_timetables = models.PositiveIntegerField(default=0)

    allow_pdf_export = models.BooleanField(default=True)
    allow_excel_export = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SchoolSubscription(models.Model):

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True
    )

    start_date = models.DateField()
    end_date = models.DateField()

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.school} - {self.plan}"