from django import forms
from django.db.models import Sum
from Accounts.form_mixins import CurrentSchoolFormMixin
from .models import LessonAllocation
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class LessonAllocationForm(CurrentSchoolFormMixin, forms.ModelForm):
    school_related_fields = (
        "academic_year",
        "class_section",
        "subject",
        "teacher",
        "default_room",
    )

    class Meta:
        model = LessonAllocation

        fields = [
            "school",
            "academic_year",
            "class_section",
            "subject",
            "teacher",
            "default_room",
            "weekly_periods",
            "requires_double_period",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "class_section": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "default_room": forms.Select(attrs={"class": "form-select"}),

            "weekly_periods": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "5"
            }),

            "requires_double_period": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),

            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }

    @log_exceptions
    def clean_weekly_periods(self):
        weekly_periods = self.cleaned_data["weekly_periods"]
        if weekly_periods < 1:
            raise forms.ValidationError("Weekly periods must be at least 1.")
        return weekly_periods

    @log_exceptions
    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        academic_year = cleaned_data.get("academic_year")
        class_section = cleaned_data.get("class_section")
        subject = cleaned_data.get("subject")
        teacher = cleaned_data.get("teacher")
        default_room = cleaned_data.get("default_room")
        weekly_periods = cleaned_data.get("weekly_periods")
        is_active = cleaned_data.get("is_active")

        if academic_year and school and academic_year.school_id != school.id:
            self.add_error("academic_year", "Select an academic year from the same school.")

        if class_section and school and class_section.school_id != school.id:
            self.add_error("class_section", "Select a class section from the same school.")

        if subject and school and subject.school_id != school.id:
            self.add_error("subject", "Select a subject from the same school.")

        if teacher and school and teacher.school_id != school.id:
            self.add_error("teacher", "Select a teacher from the same school.")

        if default_room and school and default_room.school_id != school.id:
            self.add_error("default_room", "Select a room from the same school.")

        if academic_year and class_section and subject:
            duplicate = LessonAllocation.objects.filter(
                academic_year=academic_year,
                class_section=class_section,
                subject=subject,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("subject", "This subject is already allocated for the selected class section and academic year.")

        if academic_year and teacher and weekly_periods and is_active:
            existing_load = LessonAllocation.objects.filter(
                academic_year=academic_year,
                teacher=teacher,
                is_active=True,
            )
            if self.instance.pk:
                existing_load = existing_load.exclude(pk=self.instance.pk)

            current_weekly_load = existing_load.aggregate(total=Sum("weekly_periods"))["total"] or 0
            teacher_week_limit = teacher.max_periods_per_week or 0
            new_weekly_load = current_weekly_load + weekly_periods

            if teacher_week_limit and new_weekly_load > teacher_week_limit:
                self.add_error(
                    "weekly_periods",
                    (
                        f"This allocation would take {teacher.name} to {new_weekly_load} periods/week, "
                        f"above the teacher limit of {teacher_week_limit}. Current active allocation load is {current_weekly_load}."
                    )
                )

        return cleaned_data
