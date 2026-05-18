from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import BillingCustomer, Invoice, Payment, SchoolSubscription, SubscriptionPlan
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@admin.action(description="Extend selected subscriptions by 14 days")
@log_exceptions
def extend_trial_14_days(modeladmin, request, queryset):
    for subscription in queryset:
        base_date = max(subscription.end_date, timezone.localdate())
        subscription.end_date = base_date + timedelta(days=14)
        subscription.status = "TRIALING"
        subscription.is_active = True
        subscription.save(update_fields=["end_date", "status", "is_active", "updated_at"])


@admin.action(description="Activate selected subscriptions for 30 days")
@log_exceptions
def activate_for_30_days(modeladmin, request, queryset):
    today = timezone.localdate()
    queryset.update(
        status="ACTIVE",
        is_active=True,
        start_date=today,
        end_date=today + timedelta(days=30),
        updated_at=timezone.now(),
    )


@admin.action(description="Activate selected subscriptions for 365 days")
@log_exceptions
def activate_for_365_days(modeladmin, request, queryset):
    today = timezone.localdate()
    queryset.update(
        status="ACTIVE",
        is_active=True,
        start_date=today,
        end_date=today + timedelta(days=365),
        updated_at=timezone.now(),
    )


@admin.action(description="Mark selected subscriptions as expired")
@log_exceptions
def mark_subscriptions_expired(modeladmin, request, queryset):
    queryset.update(status="EXPIRED", is_active=False, updated_at=timezone.now())


@admin.action(description="Mark selected invoices as paid")
@log_exceptions
def mark_invoices_paid(modeladmin, request, queryset):
    queryset.update(status="PAID", paid_at=timezone.now(), updated_at=timezone.now())


@admin.action(description="Mark selected invoices as void")
@log_exceptions
def mark_invoices_void(modeladmin, request, queryset):
    queryset.update(status="VOID", updated_at=timezone.now())


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "currency",
        "billing_cycle",
        "max_teachers",
        "max_classes",
        "max_timetables",
        "allow_pdf_export",
        "allow_excel_export",
        "allow_ai_generation",
        "is_active",
    )
    list_filter = ("is_active", "billing_cycle", "currency")
    search_fields = ("name",)
    fieldsets = (
        ("Plan", {"fields": ("name", "description", "is_active")}),
        ("Pricing", {"fields": ("price", "currency", "billing_cycle")}),
        ("Limits", {"fields": ("max_teachers", "max_classes", "max_timetables")}),
        ("Features", {"fields": ("allow_pdf_export", "allow_excel_export", "allow_ai_generation")}),
    )


@admin.register(SchoolSubscription)
class SchoolSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "plan",
        "status",
        "start_date",
        "end_date",
        "days_remaining",
        "auto_renew",
        "is_active",
    )
    list_filter = ("status", "is_active", "auto_renew", "plan", "provider")
    search_fields = ("school__name", "school__school_code", "plan__name")
    date_hierarchy = "end_date"
    autocomplete_fields = ("school", "plan")
    actions = (
        extend_trial_14_days,
        activate_for_30_days,
        activate_for_365_days,
        mark_subscriptions_expired,
    )
    fieldsets = (
        ("School & Plan", {"fields": ("school", "plan", "status", "is_active")}),
        ("Period", {"fields": ("start_date", "end_date", "auto_renew")}),
        ("Provider", {"fields": ("provider", "provider_subscription_id")}),
        ("Internal Notes", {"fields": ("notes",)}),
    )

    @admin.display(description="Days left")
    @log_exceptions
    def days_remaining(self, obj):
        return max((obj.end_date - timezone.localdate()).days, 0)


@admin.register(BillingCustomer)
class BillingCustomerAdmin(admin.ModelAdmin):
    list_display = ("school", "billing_name", "billing_email", "billing_phone", "gst_number", "provider")
    search_fields = (
        "school__name",
        "school__school_code",
        "billing_name",
        "billing_email",
        "billing_phone",
        "gst_number",
        "provider_customer_id",
    )
    list_filter = ("provider",)
    autocomplete_fields = ("school",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "school",
        "status",
        "total_amount",
        "currency",
        "issue_date",
        "due_date",
        "paid_at",
    )
    list_filter = ("status", "currency", "provider", "issue_date")
    search_fields = (
        "invoice_number",
        "school__name",
        "school__school_code",
        "provider_invoice_id",
    )
    date_hierarchy = "issue_date"
    autocomplete_fields = ("school", "subscription")
    actions = (mark_invoices_paid, mark_invoices_void)
    fieldsets = (
        ("Invoice", {"fields": ("invoice_number", "school", "subscription", "status")}),
        ("Amounts", {"fields": ("currency", "subtotal", "tax_amount", "total_amount")}),
        ("Dates", {"fields": ("issue_date", "due_date", "paid_at")}),
        ("Provider", {"fields": ("provider", "provider_invoice_id")}),
        ("Notes", {"fields": ("notes",)}),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "amount",
        "currency",
        "status",
        "method",
        "paid_at",
        "reference_number",
    )
    list_filter = ("status", "method", "currency", "provider")
    search_fields = (
        "school__name",
        "school__school_code",
        "reference_number",
        "provider_payment_id",
    )
    date_hierarchy = "paid_at"
    autocomplete_fields = ("school", "invoice", "subscription")
    fieldsets = (
        ("Payment", {"fields": ("school", "invoice", "subscription", "status")}),
        ("Amount", {"fields": ("amount", "currency", "method", "paid_at")}),
        ("Reference", {"fields": ("reference_number", "provider", "provider_payment_id")}),
        ("Notes", {"fields": ("notes",)}),
    )
