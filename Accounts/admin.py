from django.contrib import admin

from .models import SchoolUser


@admin.register(SchoolUser)
class SchoolUserAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role", "is_active", "has_completed_onboarding", "created_at")
    list_filter = ("role", "is_active", "has_completed_onboarding")
    search_fields = ("user__username", "user__email", "school__name", "school__school_code")
    autocomplete_fields = ("user", "school")
    list_select_related = ("user", "school")
