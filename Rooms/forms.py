from django import forms
from .models import Room


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = [
            "school",
            "name",
            "short_name",
            "room_type",
            "capacity",
            "is_active",
        ]

        widgets = {
            "school": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Room 101 / Computer Lab"}),
            "short_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "R101 / Lab"}),
            "room_type": forms.Select(attrs={"class": "form-select"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "40"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }