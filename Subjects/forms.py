from django import forms
from .models import Subject, TeacherSubjectCapability


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            "school",
            "name",
            "short_name",
            "code",
            "section_type",
            "subject_type",
            "color_code",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Mathematics / Science / English"}),
            "short_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Maths / Sci / Eng"}),
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "MATH101"}),
            "section_type": forms.Select(attrs={"class": "form-select"}),
            "subject_type": forms.Select(attrs={"class": "form-select"}),
            "color_code": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_short_name(self):
        return self.cleaned_data.get("short_name", "").strip()

    def clean_code(self):
        return self.cleaned_data.get("code", "").strip().upper()

    def clean_color_code(self):
        color_code = self.cleaned_data.get("color_code", "").strip()
        if not color_code.startswith("#") or len(color_code) not in (4, 7):
            raise forms.ValidationError("Use a valid hex color, for example #0d6efd.")
        return color_code

    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        name = cleaned_data.get("name")
        code = cleaned_data.get("code")

        if school and name:
            duplicate_name = Subject.objects.filter(
                school=school,
                name__iexact=name,
            )
            if self.instance.pk:
                duplicate_name = duplicate_name.exclude(pk=self.instance.pk)
            if duplicate_name.exists():
                self.add_error("name", "This subject already exists for the selected school.")

        if school and code:
            duplicate_code = Subject.objects.filter(
                school=school,
                code__iexact=code,
            )
            if self.instance.pk:
                duplicate_code = duplicate_code.exclude(pk=self.instance.pk)
            if duplicate_code.exists():
                self.add_error("code", "This subject code is already used for the selected school.")

        return cleaned_data


class TeacherSubjectCapabilityForm(forms.ModelForm):
    class Meta:
        model = TeacherSubjectCapability
        fields = [
            "school",
            "teacher",
            "subject",
            "class_levels",
            "priority",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "class_levels": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        teacher = cleaned_data.get("teacher")
        subject = cleaned_data.get("subject")

        if teacher and school and teacher.school_id != school.id:
            self.add_error("teacher", "Select a teacher from the same school.")

        if subject and school and subject.school_id != school.id:
            self.add_error("subject", "Select a subject from the same school.")

        if school and teacher and subject:
            duplicate_mapping = TeacherSubjectCapability.objects.filter(
                school=school,
                teacher=teacher,
                subject=subject,
            )
            if self.instance.pk:
                duplicate_mapping = duplicate_mapping.exclude(pk=self.instance.pk)
            if duplicate_mapping.exists():
                self.add_error("subject", "This teacher is already mapped to this subject.")

        return cleaned_data
