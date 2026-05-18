from AI_TIMETABLE_SAAS.logging_utils import log_exceptions
class CurrentSchoolFormMixin:
    school_field_name = "school"
    school_related_fields = ()

    @log_exceptions
    def __init__(self, *args, current_school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_school = current_school

        if current_school:
            self._lock_school_field(current_school)
            self._filter_school_related_fields(current_school)

    @log_exceptions
    def _lock_school_field(self, school):
        field = self.fields.get(self.school_field_name)
        if not field:
            return

        field.queryset = field.queryset.filter(pk=school.pk)
        field.initial = school.pk
        field.disabled = True
        field.widget.attrs["class"] = field.widget.attrs.get("class", "form-select")
        field.widget.attrs["aria-readonly"] = "true"
        self.initial[self.school_field_name] = school.pk

    @log_exceptions
    def _filter_school_related_fields(self, school):
        for field_name in self.school_related_fields:
            field = self.fields.get(field_name)
            if not field or not hasattr(field, "queryset"):
                continue

            model_fields = {model_field.name for model_field in field.queryset.model._meta.fields}
            if "school" in model_fields:
                field.queryset = field.queryset.filter(school=school)
