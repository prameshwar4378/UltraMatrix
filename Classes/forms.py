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

    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        class_level = cleaned_data.get("class_level")
        division = cleaned_data.get("division")
        class_teacher = cleaned_data.get("class_teacher")
        default_room = cleaned_data.get("default_room")

        if class_level and school and class_level.school_id != school.id:
            self.add_error("class_level", "Select a class level from the same school.")

        if division and school and division.school_id != school.id:
            self.add_error("division", "Select a division from the same school.")

        if class_teacher and school and class_teacher.school_id != school.id:
            self.add_error("class_teacher", "Select a class teacher from the same school.")

        if default_room and school and default_room.school_id != school.id:
            self.add_error("default_room", "Select a room from the same school.")

        if school and class_level and division:
            duplicate = ClassSection.objects.filter(
                school=school,
                timetable=getattr(self.instance, "timetable", None),
                class_level=class_level,
                division=division,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "division",
                    "This class section already exists. Please edit the existing section instead of creating a duplicate.",
                )

        return cleaned_data
