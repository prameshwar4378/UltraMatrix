# School Data Isolation Rules

Every school-owned feature must follow these rules:

1. Read the active school from the logged-in user's session with `get_current_school(request)`.
2. Never trust a `school` id from `GET`, `POST`, CSV, Excel, or a URL when a user is logged in.
3. List pages, exports, counts, dashboards, and reports must use `school_queryset(request, queryset)`.
4. Update, delete, toggle, and detail views must use `get_school_object_or_404(request, queryset, pk=pk)`.
5. Create forms must receive `current_school=current_school`; the school field should be locked/read-only.
6. Related dropdown fields must only contain records from the current school.
7. Bulk imports must reject rows for any school other than the current school.
8. Admin/developer global controls can remain in Django admin, but normal software views must never show another school's records.

Use these helpers from `Accounts.utils`:

- `get_current_school(request)`
- `require_current_school(request)`
- `redirect_if_no_current_school(request)`
- `school_queryset(request, queryset)`
- `get_school_object_or_404(request, queryset, **lookup)`
