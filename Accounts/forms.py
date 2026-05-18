from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from Schools.models import School
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class SchoolSignupForm(forms.Form):
    school_name = forms.CharField(max_length=255)
    school_code = forms.CharField(max_length=100, required=False)
    contact_name = forms.CharField(max_length=255)
    contact_number = forms.CharField(max_length=20, required=False)
    email = forms.EmailField()
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput,
    )

    @log_exceptions
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "school_name": "Green Valley Public School",
            "school_code": "GVPS",
            "contact_name": "Admin name",
            "contact_number": "Phone number",
            "email": "admin@school.com",
            "username": "school_admin",
            "password1": "Create password",
            "password2": "Confirm password",
        }

        for name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control",
                "placeholder": placeholders.get(name, field.label),
            })

    @log_exceptions
    def clean_school_code(self):
        value = self.cleaned_data.get("school_code", "").strip()
        if not value:
            value = slugify(self.cleaned_data.get("school_name", ""))[:90].upper()

        if School.objects.using("default").filter(school_code__iexact=value).exists():
            raise ValidationError("This school code is already used.")

        return value

    @log_exceptions
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()

        if User.objects.using("default").filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")

        return email

    @log_exceptions
    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()

        if User.objects.using("default").filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")

        return username

    @log_exceptions
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        if password1:
            try:
                validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data
