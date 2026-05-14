from .utils import school_context_for_request


def school_context(request):
    if not request.user.is_authenticated:
        return {}

    return school_context_for_request(request)
