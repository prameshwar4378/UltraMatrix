from contextvars import ContextVar

from django.conf import settings
from django.http import HttpResponseBadRequest


_current_tenant_db = ContextVar("current_tenant_db", default=None)


def get_current_tenant_db():
    return _current_tenant_db.get()


def set_current_tenant_db(alias):
    return _current_tenant_db.set(alias)


def reset_current_tenant_db(token):
    _current_tenant_db.reset(token)


def configured_tenant_databases():
    return set(getattr(settings, "SCHOOL_TENANT_DATABASES", ()))


class SchoolTenantMiddleware:
    """
    Select the active school database for the current request.

    In development with SQLite, pass ?school_db=<alias> once to save it in the
    session, or send X-School-Db for API-style requests. Without an alias, the
    app keeps using the default database.
    """

    header_name = "HTTP_X_SCHOOL_DB"
    query_param = "school_db"
    session_key = "school_db_alias"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        alias = (
            request.GET.get(self.query_param)
            or request.META.get(self.header_name)
            or request.session.get(self.session_key)
        )
        tenant_databases = configured_tenant_databases()

        if alias and alias not in tenant_databases:
            return HttpResponseBadRequest(f"Unknown school database alias: {alias}")

        if request.GET.get(self.query_param):
            request.session[self.session_key] = alias

        request.school_db_alias = alias
        token = set_current_tenant_db(alias)

        try:
            return self.get_response(request)
        finally:
            reset_current_tenant_db(token)
