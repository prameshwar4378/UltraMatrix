from django import forms
from Accounts.form_mixins import CurrentSchoolFormMixin
from .models import ClassLevel, Division
from Timetables.models import ClassSection


class ClassLevelForm(CurrentSchoolFormMixin, forms.ModelForm):
    class Meta:
        model = ClassLevel
        fields = [
            "school",
            "name",
            "short_name",
            "sort_order",
            "section_type",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Class 1 / Nursery"}),
            "short_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "1st / Nur"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "section_type": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class DivisionForm(CurrentSchoolFormMixin, forms.ModelForm):
    class Meta:
        model = Division
        fields = [
            "school",
            "name",
            "sort_order",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "A / B / C"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ClassSectionForm(CurrentSchoolFormMixin, forms.ModelForm):
    school_related_fields = ("class_level", "division", "class_teacher", "default_room")

    class Meta:
        model = ClassSection
        fields = [
            "school",
            "class_level",
            "division",
            "class_teacher",
            "default_room",
            "capacity",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "class_level": forms.Select(attrs={"class": "form-select"}),
            "division": forms.Select(attrs={"class": "form-select"}),
            "class_teacher": forms.Select(attrs={"class": "form-select"}),
            "default_room": forms.Select(attrs={"class": "form-select"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "40"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
