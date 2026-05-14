from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from Schools.models import School
from Subscriptions.models import SchoolSubscription, SubscriptionPlan

from .forms import SchoolSignupForm
from .models import SchoolUser
from .utils import school_context_for_request


def _school_user_for_user(user):
    if not user.is_authenticated:
        return None

    return SchoolUser.objects.select_related("school").filter(
        user=user,
        is_active=True,
    ).first()


def _next_page_for_user(user):
    school_user = _school_user_for_user(user)
    if school_user and not school_user.has_completed_onboarding:
        return "feature_onboarding"

    return "school_dashboard"


class SchoolLoginView(LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        return reverse(_next_page_for_user(self.request.user))

    def form_valid(self, form):
        response = super().form_valid(form)
        school_context = school_context_for_request(self.request)
        school = school_context["current_school"]
        if school:
            self.request.session["current_school_id"] = school.id
            subscription = school_context["current_subscription"]
            if subscription:
                self.request.session["subscription_status"] = subscription.status
                self.request.session["trial_days_remaining"] = school_context["trial_days_remaining"]
        return response


def _trial_plan():
    plan, _ = SubscriptionPlan.objects.db_manager("default").get_or_create(
        name="14 Day Free Trial",
        defaults={
            "price": 0,
            "max_teachers": 30,
            "max_classes": 25,
            "max_timetables": 3,
            "allow_pdf_export": True,
            "allow_excel_export": True,
            "is_active": True,
        },
    )
    return plan


@login_required
def feature_onboarding(request):
    school_user = _school_user_for_user(request.user)

    if not school_user:
        messages.error(request, "Your school profile is not linked yet. Please contact support.")
        return redirect("login")

    if school_user.has_completed_onboarding:
        return redirect("school_dashboard")

    features = [
        {
            "label": "Step 1",
            "title": "Institute profile",
            "description": "Keep school name, contact details, academic identity, and ownership information ready for daily operations.",
            "points": ["Confirm institute details", "Review admin ownership", "Keep school context locked"],
        },
        {
            "label": "Step 2",
            "title": "Academic setup",
            "description": "Create academic years, working days, periods, classes, divisions, and sections before timetable planning.",
            "points": ["Add academic year", "Define periods", "Prepare classes and divisions"],
        },
        {
            "label": "Step 3",
            "title": "Teachers and subjects",
            "description": "Add teachers, subjects, rooms, and teacher-subject capabilities so the builder understands your constraints.",
            "points": ["Create teacher profiles", "Map subjects", "Assign capabilities"],
        },
        {
            "label": "Step 4",
            "title": "Lesson allocation",
            "description": "Set weekly subject load for each class section so generated timetables match your required teaching hours.",
            "points": ["Allocate weekly periods", "Balance subject load", "Mark active rules"],
        },
        {
            "label": "Step 5",
            "title": "Timetable builder",
            "description": "Build, review, lock, and improve timetable slots with school-aware data isolation and setup validation.",
            "points": ["Generate timetable", "Review coverage", "Lock confirmed slots"],
        },
        {
            "label": "Step 6",
            "title": "Proxy adjustment",
            "description": "Manage teacher unavailability and same-day proxy adjustments once the timetable is live.",
            "points": ["Mark unavailable teachers", "Assign proxy lectures", "Track daily changes"],
        },
    ]

    if request.method == "POST":
        school_user.has_completed_onboarding = True
        school_user.save(update_fields=["has_completed_onboarding"])
        messages.success(request, "Setup walkthrough completed. Welcome to your dashboard.")
        return redirect("school_dashboard")

    return render(
        request,
        "accounts/feature_onboarding.html",
        {
            "features": features,
            "school_user": school_user,
            "school": school_user.school,
        },
    )


def school_signup(request):
    if request.user.is_authenticated:
        return redirect(_next_page_for_user(request.user))

    if request.method == "POST":
        form = SchoolSignupForm(request.POST)

        if form.is_valid():
            today = timezone.localdate()
            User = get_user_model()

            with transaction.atomic(using="default"):
                user = User.objects.db_manager("default").create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                    first_name=form.cleaned_data["contact_name"],
                )

                school = School.objects.db_manager("default").create(
                    name=form.cleaned_data["school_name"],
                    short_name=form.cleaned_data["school_code"],
                    school_code=form.cleaned_data["school_code"],
                    principal_name=form.cleaned_data["contact_name"],
                    contact_number=form.cleaned_data["contact_number"],
                    email=form.cleaned_data["email"],
                    is_active=True,
                )

                SchoolUser.objects.db_manager("default").create(
                    school=school,
                    user=user,
                    role="OWNER",
                    is_active=True,
                )

                SchoolSubscription.objects.db_manager("default").create(
                    school=school,
                    plan=_trial_plan(),
                    start_date=today,
                    end_date=today + timedelta(days=14),
                    status="TRIALING",
                    is_active=True,
                )

            login(request, user)
            request.session["current_school_id"] = school.id
            request.session["subscription_status"] = "TRIALING"
            request.session["trial_days_remaining"] = 14
            request.session.pop("school_db_alias", None)
            messages.success(request, "School account created. Your 14-day free trial has started.")
            return redirect("feature_onboarding")
    else:
        form = SchoolSignupForm()

    return render(request, "accounts/signup.html", {"form": form})
