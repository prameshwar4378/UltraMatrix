from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Run migrations for every configured school tenant database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            action="append",
            dest="databases",
            help="Run migrations for a specific tenant database alias. Can be used more than once.",
        )

    def handle(self, *args, **options):
        tenant_databases = tuple(options["databases"] or settings.SCHOOL_TENANT_DATABASES)

        if not tenant_databases:
            self.stdout.write(
                self.style.WARNING(
                    "No school tenant databases configured. Set SCHOOL_SQLITE_TENANTS=school_1,school_2 first."
                )
            )
            return

        for alias in tenant_databases:
            if alias not in settings.DATABASES:
                self.stderr.write(self.style.ERROR(f"Unknown database alias: {alias}"))
                continue

            database_name = settings.DATABASES[alias].get("NAME")
            if database_name:
                Path(database_name).parent.mkdir(parents=True, exist_ok=True)

            self.stdout.write(self.style.MIGRATE_HEADING(f"Running migrations for {alias}"))
            call_command("migrate", database=alias, interactive=False, verbosity=options["verbosity"])
