import functools
import traceback
from pathlib import Path

from django.http import HttpRequest
from django.http import HttpResponse
from django.template.loader import render_to_string


def _request_from_call(args, kwargs):
    request = kwargs.get("request")
    if isinstance(request, HttpRequest):
        return request

    for arg in args:
        if isinstance(arg, HttpRequest):
            return arg

    return None


def _is_response_handler(func):
    module_name = func.__module__ or ""
    function_name = func.__name__
    qualified_name = func.__qualname__

    return (
        module_name.endswith(".views")
        or module_name.endswith(".views_builder")
        or function_name == "__call__"
        or ".View." in qualified_name
        or "LoginView" in qualified_name
    )


def _error_context(error, qualified_name):
    traceback_frames = traceback.extract_tb(error.__traceback__)
    source_frame = traceback_frames[-1] if traceback_frames else None

    if not source_frame:
        return {
            "error": str(error),
            "error_message": str(error),
            "error_type": error.__class__.__name__,
            "error_source": qualified_name,
            "error_explanation": f"{error.__class__.__name__} occurred in {qualified_name}.",
        }

    filename = Path(source_frame.filename).name
    return {
        "error": str(error),
        "error_message": str(error),
        "error_type": error.__class__.__name__,
        "error_source": qualified_name,
        "error_file": filename,
        "error_path": source_frame.filename,
        "error_line": source_frame.lineno,
        "error_function": source_frame.name,
        "error_code": source_frame.line or "",
        "error_explanation": (
            f"{error.__class__.__name__} occurred in {filename} "
            f"at line {source_frame.lineno}, inside {source_frame.name}."
        ),
    }


def log_exceptions(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        qualified_name = f"{func.__module__}.{func.__qualname__}"

        try:
            result = func(*args, **kwargs)
        except Exception as error:
            request = _request_from_call(args, kwargs)
            if not request or not _is_response_handler(func):
                raise

            content = render_to_string(
                "accounts/404.html",
                _error_context(error, qualified_name),
            )
            return HttpResponse(content, status=404)

        return result

    return wrapper
