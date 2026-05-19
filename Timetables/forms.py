from django import forms
from django.db.models import Sum
from Accounts.form_mixins import CurrentSchoolFormMixin
from .models import LessonAllocation, Timetable
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = [
            "name",
            "academic_year",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Primary Timetable 2026",
            }),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
        }

    @log_exceptions
    def __init__(self, *args, current_school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_school = current_school
        if current_school:
            self.fields["academic_year"].queryset = self.fields["academic_year"].queryset.filter(
                school=current_school
            ).order_by("-start_date", "-id")

    @log_exceptions
    def clean_academic_year(self):
        academic_year = self.cleaned_data["academic_year"]
        if self.current_school and academic_year.school_id != self.current_school.id:
            raise forms.ValidationError("Select an academic year from the current school.")
        return academic_year

    @log_exceptions
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.current_school:
            instance.school = self.current_school
        if not instance.timetable_type:
            instance.timetable_type = "PRIMARY"
        if commit:
            instance.save()
        return instance


class LessonAllocationForm(CurrentSchoolFormMixin, forms.ModelForm):
    school_related_fields = (
        "academic_year",
        "timetable",
        "class_section",
        "subject",
        "teacher",
        "default_room",
    )

    class Meta:
        model = LessonAllocation

        fields = [
            "school",
            "timetable",
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
            "timetable": forms.HiddenInput(),
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
        timetable = cleaned_data.get("timetable")
        academic_year = cleaned_data.get("academic_year")
        class_section = cleaned_data.get("class_section")
        subject = cleaned_data.get("subject")
        teacher = cleaned_data.get("teacher")
        default_room = cleaned_data.get("default_room")
        weekly_periods = cleaned_data.get("weekly_periods")
        is_active = cleaned_data.get("is_active")

        if timetable and school and timetable.school_id != school.id:
            self.add_error("timetable", "Select a timetable from the same school.")

        if timetable and academic_year and timetable.academic_year_id != academic_year.id:
            self.add_error("academic_year", "Academic year must match the selected timetable.")

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

        if timetable and class_section and subject:
            duplicate = LessonAllocation.objects.filter(
                timetable=timetable,
                class_section=class_section,
                subject=subject,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("subject", "This subject is already allocated for the selected class section and academic year.")

        if timetable and teacher and weekly_periods and is_active:
            existing_load = LessonAllocation.objects.filter(
                timetable=timetable,
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
