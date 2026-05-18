from django import forms
from Accounts.form_mixins import CurrentSchoolFormMixin
from .models import Subject, TeacherSubjectCapability
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class SubjectForm(CurrentSchoolFormMixin, forms.ModelForm):
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

    @log_exceptions
    def clean_name(self):
        return self.cleaned_data["name"].strip()

    @log_exceptions
    def clean_short_name(self):
        return self.cleaned_data.get("short_name", "").strip()

    @log_exceptions
    def clean_code(self):
        return self.cleaned_data.get("code", "").strip().upper()

    @log_exceptions
    def clean_color_code(self):
        color_code = self.cleaned_data.get("color_code", "").strip()
        if not color_code.startswith("#") or len(color_code) not in (4, 7):
            raise forms.ValidationError("Use a valid hex color, for example #0d6efd.")
        return color_code

    @log_exceptions
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


class TeacherSubjectCapabilityForm(CurrentSchoolFormMixin, forms.ModelForm):
    school_related_fields = ("teacher", "subject", "class_levels", "class_sections")

    class Meta:
        model = TeacherSubjectCapability
        fields = [
            "school",
            "teacher",
            "subject",
            "class_sections",
            "class_levels",
            "priority",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "class_sections": forms.SelectMultiple(attrs={"class": "form-select", "size": "10"}),
            "class_levels": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    @log_exceptions
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_sections"].queryset = self.fields["class_sections"].queryset.select_related(
            "class_level",
            "division",
            "school",
        ).order_by("class_level__sort_order", "division__sort_order")
        self.fields["class_sections"].label_from_instance = lambda section: f"{section.class_level.name}-{section.division.name}"

    @log_exceptions
    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        teacher = cleaned_data.get("teacher")
        subject = cleaned_data.get("subject")
        class_sections = cleaned_data.get("class_sections")
        class_levels = cleaned_data.get("class_levels")

        if teacher and school and teacher.school_id != school.id:
            self.add_error("teacher", "Select a teacher from the same school.")

        if subject and school and subject.school_id != school.id:
            self.add_error("subject", "Select a subject from the same school.")

        if school and teacher and subject:
            duplicate_mappings = TeacherSubjectCapability.objects.filter(
                school=school,
                teacher=teacher,
                subject=subject,
            )
            if self.instance.pk:
                duplicate_mappings = duplicate_mappings.exclude(pk=self.instance.pk)

            selected_section_ids = {section.id for section in class_sections or []}
            selected_level_ids = {level.id for level in class_levels or []}

            for mapping in duplicate_mappings.prefetch_related("class_sections", "class_levels"):
                existing_section_ids = set(mapping.class_sections.values_list("id", flat=True))
                existing_level_ids = set(mapping.class_levels.values_list("id", flat=True))

                both_broad = not selected_section_ids and not selected_level_ids and not existing_section_ids and not existing_level_ids
                section_overlap = bool(selected_section_ids and existing_section_ids and selected_section_ids & existing_section_ids)
                level_overlap = bool(selected_level_ids and existing_level_ids and selected_level_ids & existing_level_ids)
                existing_broad_for_selected = not existing_section_ids and not existing_level_ids and (selected_section_ids or selected_level_ids)
                selected_broad_for_existing = not selected_section_ids and not selected_level_ids and (existing_section_ids or existing_level_ids)

                if both_broad or section_overlap or level_overlap or existing_broad_for_selected or selected_broad_for_existing:
                    self.add_error("subject", "This teacher already has an overlapping mapping for this subject.")
                    break

        if school and subject and class_sections and cleaned_data.get("priority") == "PRIMARY":
            conflicting_primary = TeacherSubjectCapability.objects.filter(
                school=school,
                subject=subject,
                priority="PRIMARY",
                class_sections__in=class_sections,
            )
            if teacher:
                conflicting_primary = conflicting_primary.exclude(teacher=teacher)
            if self.instance.pk:
                conflicting_primary = conflicting_primary.exclude(pk=self.instance.pk)
            if conflicting_primary.exists():
                self.add_error("class_sections", "One or more selected class sections already have a primary teacher for this subject.")

        return cleaned_data
