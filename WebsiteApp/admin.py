from django.contrib import admin

from .models import ContactEnquiry


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "phone", "email", "enquiry_type", "status", "created_at")
    list_filter = ("status", "enquiry_type", "institution_size", "created_at")
    search_fields = ("name", "school", "phone", "email", "message")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 25

    fieldsets = (
        ("Enquiry details", {
            "fields": ("name", "school", "phone", "email", "enquiry_type", "institution_size", "message"),
        }),
        ("Follow up", {
            "fields": ("status", "admin_note"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )
