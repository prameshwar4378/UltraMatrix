import threading
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .models import ContactEnquiry
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def index(request):
    return render(request, "index.html")


@log_exceptions
def features(request):
    return render(request, "web_features.html")


@log_exceptions
def ai_engine(request):
    return render(request, "web_ai_engine.html")


@log_exceptions
def pricing(request):
    return render(request, "web_pricing.html")


@log_exceptions
def send_email_in_background(email_message):
    try:
        email_message.send()
    except Exception as e:
        print(f"Error sending email: {e}")


@log_exceptions
def contact_us(request):
    if request.method == "POST":
        required_fields = ("name", "school", "phone", "email", "enquiry_type")
        missing_fields = [field for field in required_fields if not request.POST.get(field, "").strip()]

        if missing_fields:
            messages.error(request, "Please fill all required fields.")
            return render(request, "web_contact_us.html", {"form_data": request.POST})

        email = request.POST.get("email", "").strip()
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, "web_contact_us.html", {"form_data": request.POST})

        enquiry_type = request.POST.get("enquiry_type", "").strip()
        institution_size = request.POST.get("teacher_count", "").strip()

        if enquiry_type not in dict(ContactEnquiry.ENQUIRY_TYPE_CHOICES):
            messages.error(request, "Please select a valid enquiry type.")
            return render(request, "web_contact_us.html", {"form_data": request.POST})

        if institution_size and institution_size not in dict(ContactEnquiry.INSTITUTION_SIZE_CHOICES):
            messages.error(request, "Please select a valid institution size.")
            return render(request, "web_contact_us.html", {"form_data": request.POST})

        name = request.POST.get("name", "").strip()
        school = request.POST.get("school", "").strip()
        phone = request.POST.get("phone", "").strip()
        message = request.POST.get("message", "").strip()

        enquiry = ContactEnquiry.objects.create(
            name=name,
            school=school,
            phone=phone,
            email=email,
            enquiry_type=enquiry_type,
            institution_size=institution_size,
            message=message,
        )

        email_body = render_to_string("Enquiry_Mail.html", {
            "enquiry": enquiry,
            "full_name": name,
            "name": name,
            "school": school,
            "phone": phone,
            "email": email,
            "enquiry_type": enquiry.get_enquiry_type_display(),
            "institution_size": enquiry.get_institution_size_display() if enquiry.institution_size else "N/A",
            "message": message or "No message provided.",
            "submitted_on": datetime.now().strftime("%d %B %Y, %I:%M %p"),
        })

        email_message = EmailMessage(
            subject="New Enquiry Received from UltraMatrix AI Timetable",
            body=email_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
            to=["prameshwar4378@gmail.com"],
            reply_to=[email],
        )
        email_message.content_subtype = "html"
        threading.Thread(target=send_email_in_background, args=(email_message,)).start()

        messages.success(request, "Thank you. Your enquiry has been submitted successfully.")
        return redirect("contact_us")

    return render(request, "web_contact_us.html")
