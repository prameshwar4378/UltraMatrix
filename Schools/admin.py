from django.contrib import admin

from .models import School 
from Accounts.models import SchoolUser
from Subscriptions.models import BillingCustomer, Invoice, Payment, SchoolSubscription
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class SchoolUserInline(admin.TabularInline):
    model = SchoolUser
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "is_active", "created_at")
    readonly_fields = ("created_at",)


class SchoolSubscriptionInline(admin.TabularInline):
    model = SchoolSubscription
    extra = 0
    autocomplete_fields = ("plan",)
    fields = ("plan", "status", "start_date", "end_date", "is_active", "auto_renew")


class BillingCustomerInline(admin.StackedInline):
    model = BillingCustomer
    extra = 0
    max_num = 1
    fields = (
        "billing_name",
        "billing_email",
        "billing_phone",
        "billing_address",
        "gst_number",
        "provider",
        "provider_customer_id",
    )


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ("invoice_number", "status", "total_amount", "currency", "issue_date", "due_date", "paid_at")
    readonly_fields = ("invoice_number", "status", "total_amount", "currency", "issue_date", "due_date", "paid_at")
    can_delete = False
    show_change_link = True

    @log_exceptions
    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("amount", "currency", "status", "method", "paid_at", "reference_number")
    readonly_fields = ("amount", "currency", "status", "method", "paid_at", "reference_number")
    can_delete = False
    show_change_link = True

    @log_exceptions
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "school_code",
        "email",
        "contact_number",
        "is_active",
        "current_subscription_status",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "short_name", "school_code", "email", "contact_number", "principal_name")
    readonly_fields = ("created_at",)
    inlines = (
        SchoolUserInline,
        SchoolSubscriptionInline,
        BillingCustomerInline,
        InvoiceInline,
        PaymentInline,
    )
    fieldsets = (
        ("School", {"fields": ("name", "short_name", "school_code", "is_active")}),
        ("Branding", {"fields": ("logo",)}),
        ("Contact", {"fields": ("principal_name", "email", "contact_number", "address")}),
        ("System", {"fields": ("created_at",)}),
    )

    @admin.display(description="Subscription")
    @log_exceptions
    def current_subscription_status(self, obj):
        subscription = obj.schoolsubscription_set.order_by("-end_date", "-id").first()
        if not subscription:
            return "No subscription"
        return f"{subscription.get_status_display()} until {subscription.end_date}"
