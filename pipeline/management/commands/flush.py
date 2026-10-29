"""
Django's flush, for a database whose stage history is guarded (migration 0005).

Flush empties every table, stage history included, in an order that varies between runs, so
the history delete guard would refuse it. This copies that trigger's SQL, drops it for the flush,
and puts the same trigger back afterwards, even if the flush fails or is cancelled.
TransactionTestCase teardown runs this command too (call_command uses an app's override).
"""

from django.core.management.commands.flush import Command as FlushCommand
from django.db import connections

GUARD_TRIGGER = "pipeline_stagechange_delete_guard"


class Command(FlushCommand):
    def handle(self, **options):
        connection = connections[options["database"]]
        if connection.vendor != "sqlite":
            return super().handle(**options)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = %s",
                [GUARD_TRIGGER],
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(f'DROP TRIGGER "{GUARD_TRIGGER}"')
        try:
            return super().handle(**options)
        finally:
            if row:
                with connection.cursor() as cursor:
                    cursor.execute(row[0])
