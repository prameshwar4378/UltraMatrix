from django.db import models
from django.utils import timezone
from Schools.models import School


class SubscriptionPlan(models.Model):

    BILLING_CYCLE_CHOICES = (
        ("MONTHLY", "Monthly"),
        ("YEARLY", "Yearly"),
        ("CUSTOM", "Custom"),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    currency = models.CharField(max_length=10, default="INR")
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default="MONTHLY"
    )

    max_teachers = models.PositiveIntegerField(default=0)
    max_classes = models.PositiveIntegerField(default=0)
    max_timetables = models.PositiveIntegerField(default=0)

    allow_pdf_export = models.BooleanField(default=True)
    allow_excel_export = models.BooleanField(default=True)
    allow_ai_generation = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SchoolSubscription(models.Model):

    STATUS_CHOICES = (
        ("TRIALING", "Trialing"),
        ("ACTIVE", "Active"),
        ("PAST_DUE", "Past Due"),
        ("CANCELLED", "Cancelled"),
        ("EXPIRED", "Expired"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="TRIALING"
    )

    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)
    provider = models.CharField(max_length=50, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school} - {self.plan}"


class BillingCustomer(models.Model):

    school = models.OneToOneField(
        School,
        on_delete=models.CASCADE,
        related_name="billing_customer"
    )

    billing_name = models.CharField(max_length=255)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    gst_number = models.CharField(max_length=30, blank=True)

    provider = models.CharField(max_length=50, blank=True)
    provider_customer_id = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school} billing profile"


class Invoice(models.Model):

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
        ("OVERDUE", "Overdue"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="invoices"
    )
    subscription = models.ForeignKey(
        SchoolSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices"
    )

    invoice_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    currency = models.CharField(max_length=10, default="INR")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_invoice_id = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-issue_date", "-id")

    def __str__(self):
        return f"{self.invoice_number} - {self.school}"


class Payment(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    )

    METHOD_CHOICES = (
        ("MANUAL", "Manual"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("NET_BANKING", "Net Banking"),
        ("CASH", "Cash"),
        ("CHEQUE", "Cheque"),
        ("BANK_TRANSFER", "Bank Transfer"),
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )
    subscription = models.ForeignKey(
        SchoolSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    method = models.CharField(max_length=30, choices=METHOD_CHOICES, default="MANUAL")

    paid_at = models.DateTimeField(null=True, blank=True)
    reference_number = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_payment_id = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-paid_at", "-created_at", "-id")

    def __str__(self):
        return f"{self.school} - {self.amount} {self.currency} - {self.status}"
