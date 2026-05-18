from django.conf import settings

from .tenancy import get_current_tenant_db
from AI_TIMETABLE_SAAS.logging_utils import log_exceptions


class SchoolTenantDatabaseRouter:
    """
    Route school-owned project apps to the currently selected school database.

    The default database remains the central/dev fallback. When a tenant alias is
    selected, project app reads and writes use that database so one school's data
    lives in its own SQLite file during development.
    """

    @log_exceptions
    def _is_tenant_app(self, app_label):
        return app_label in getattr(settings, "SCHOOL_TENANT_APPS", ())

    @log_exceptions
    def _tenant_db(self):
        alias = get_current_tenant_db()
        if alias in getattr(settings, "SCHOOL_TENANT_DATABASES", ()):
            return alias
        return None

    @log_exceptions
    def db_for_read(self, model, **hints):
        if self._is_tenant_app(model._meta.app_label):
            return self._tenant_db()
        return None

    @log_exceptions
    def db_for_write(self, model, **hints):
        if self._is_tenant_app(model._meta.app_label):
            return self._tenant_db()
        return None

    @log_exceptions
    def allow_relation(self, obj1, obj2, **hints):
        if self._is_tenant_app(obj1._meta.app_label) and self._is_tenant_app(obj2._meta.app_label):
            return obj1._state.db == obj2._state.db
        return None

    @log_exceptions
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        tenant_databases = getattr(settings, "SCHOOL_TENANT_DATABASES", ())
        if db in tenant_databases:
            return self._is_tenant_app(app_label)
        return None
