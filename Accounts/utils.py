from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from Subscriptions.models import SchoolSubscription

from .models import SchoolUser
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def get_current_school(request):
    if not request.user.is_authenticated:
        return None

    school_id = request.session.get("current_school_id")

    if school_id:
        school_user = SchoolUser.objects.select_related("school").filter(
            school_id=school_id,
            user=request.user,
            is_active=True,
            school__is_active=True,
        ).first()
        if school_user:
            return school_user.school

    school_user = SchoolUser.objects.select_related("school").filter(
        user=request.user,
        is_active=True,
        school__is_active=True,
    ).order_by("id").first()
    if school_user:
        request.session["current_school_id"] = school_user.school_id
        return school_user.school

    return None


@log_exceptions
def get_current_school_user(request):
    school = get_current_school(request)
    if not school:
        return None

    return SchoolUser.objects.select_related("school", "user").filter(
        school=school,
        user=request.user,
        is_active=True,
        school__is_active=True,
    ).first()


@log_exceptions
def require_current_school(request):
    school = get_current_school(request)
    if school:
        return school

    messages.error(request, "No active school is linked with your session.")
    return None


@log_exceptions
def redirect_if_no_current_school(request, redirect_to="login"):
    if require_current_school(request):
        return None

    return redirect(redirect_to)


@log_exceptions
def school_queryset(request, queryset):
    school = get_current_school(request)
    if not school:
        return queryset.none()

    return queryset.filter(school=school)


@log_exceptions
def timetable_scope_from_request(request):
    from Timetables.models import Timetable

    school = get_current_school(request)
    timetable_id = (
        request.GET.get("timetable_id")
        or request.POST.get("timetable_id")
        or request.GET.get("timetable")
        or request.POST.get("timetable")
    )

    if not school or not timetable_id:
        return None

    return Timetable.objects.filter(pk=timetable_id, school=school).first()


@log_exceptions
def scoped_redirect_url(url_name, timetable=None):
    from django.urls import reverse

    url = reverse(url_name)
    if not timetable:
        return url

    return f"{url}?timetable_id={timetable.id}"


@log_exceptions
def get_school_object_or_404(request, queryset, **lookup):
    return get_object_or_404(school_queryset(request, queryset), **lookup)


@log_exceptions
def get_current_subscription(school):
    if not school:
        return None

    return SchoolSubscription.objects.select_related("plan", "school").filter(
        school=school,
        is_active=True,
    ).order_by("-end_date", "-id").first()


@log_exceptions
def subscription_context_for_school(school):
    today = timezone.localdate()
    subscription = get_current_subscription(school)

    trial_days_remaining = 0
    is_trial_active = False
    is_subscription_active = False

    if subscription:
        is_trial_active = subscription.status == "TRIALING" and subscription.end_date >= today
        is_subscription_active = subscription.status == "ACTIVE" and subscription.end_date >= today

        if subscription.status == "TRIALING":
            trial_days_remaining = max((subscription.end_date - today).days, 0)

    return {
        "current_subscription": subscription,
        "trial_days_remaining": trial_days_remaining,
        "is_trial_active": is_trial_active,
        "is_subscription_active": is_subscription_active,
        "has_billing_access": is_trial_active or is_subscription_active,
    }


@log_exceptions
def sync_school_session_context(request, school, subscription_context):
    if not school:
        return

    request.session["current_school_id"] = school.id

    subscription = subscription_context["current_subscription"]
    if subscription:
        request.session["subscription_status"] = subscription.status
        request.session["trial_days_remaining"] = subscription_context["trial_days_remaining"]
    else:
        request.session.pop("subscription_status", None)
        request.session.pop("trial_days_remaining", None)


@log_exceptions
def school_context_for_request(request):
    school = get_current_school(request)
    school_user = get_current_school_user(request) if school else None
    subscription_context = subscription_context_for_school(school)
    sync_school_session_context(request, school, subscription_context)

    context = {
        "current_school": school,
        "current_school_user": school_user,
    }
    context.update(subscription_context)
    return context
