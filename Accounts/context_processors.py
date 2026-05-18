from .utils import school_context_for_request
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


@log_exceptions
def school_context(request):
    if not request.user.is_authenticated:
        return {}

    return school_context_for_request(request)
