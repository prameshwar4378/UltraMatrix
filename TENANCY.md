# School Database Isolation

The project supports optional school-level database isolation.

For production, the recommended direction is PostgreSQL tenant schemas or
separate tenant databases. SQLite does not support multiple schemas inside one
database file, so development mode uses one SQLite file per school/tenant.

## Development With SQLite

Set the tenant aliases before running Django:

```powershell
$env:SCHOOL_SQLITE_TENANTS = "school_1,school_2"
```

Then create the tenant database tables:

```powershell
venv\Scripts\python.exe manage.py migrate_school_databases
```

This creates files like:

```text
tenant_dbs/school_1.sqlite3
tenant_dbs/school_2.sqlite3
```

To use a tenant database in the browser, open any app URL with the tenant alias
once:

```text
http://127.0.0.1:8000/?school_db=school_1
```

The selected alias is saved in the session. API-style requests can also send:

```text
X-School-Db: school_1
```

Without a selected tenant alias, Django continues to use the existing
`db.sqlite3` database.

## What Is Isolated

The core school setup and timetable apps are routed to the selected school
database:

- `Schools`
- `Academic`
- `Classes`
- `Teachers`
- `Subjects`
- `Rooms`
- `Timetables`

Auth-adjacent apps stay central because they reference Django's shared user
tables.
