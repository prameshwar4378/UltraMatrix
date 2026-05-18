from django import forms
from Accounts.form_mixins import CurrentSchoolFormMixin
from .models import Teacher, TeacherAvailability


class TeacherForm(CurrentSchoolFormMixin, forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            "school",
            "name",
            "short_name",
            "employee_id",
            "mobile_number",
            "email",
            "teacher_type",
            "max_periods_per_day",
            "max_periods_per_week",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teacher full name"}),
            "short_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Short name"}),
            "employee_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "EMP001"}),
            "mobile_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Mobile number"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "teacher@example.com"}),
            "teacher_type": forms.Select(attrs={"class": "form-select"}),
            "max_periods_per_day": forms.NumberInput(attrs={"class": "form-control"}),
            "max_periods_per_week": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class TeacherAvailabilityForm(forms.ModelForm):
    class Meta:
        model = TeacherAvailability
        fields = [
            "teacher",
            "day",
            "period",
            "is_available",
            "note",
        ]

        widgets = {
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "day": forms.Select(attrs={"class": "form-select"}),
            "period": forms.Select(attrs={"class": "form-select"}),
            "is_available": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional note"}),
        }
