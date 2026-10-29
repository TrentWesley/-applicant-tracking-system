from django.db import migrations

# Stage history is never erased (AC31). A StageChange row may be deleted only when its
# application still exists, is at Applied, and has exactly one entry, this row, which is its
# creation entry (no from-stage). That is the single CASCADE an Admin's delete of a never-moved
# application makes: Django deletes an application's StageChanges before the application itself.
# Everything else is refused, including history whose application row was deleted first.
#
# Django's flush also deletes history (in any table order), so the project's `flush` command
# (pipeline/management/commands/flush.py) lifts this trigger for the flush and restores it.
CREATE_TRIGGER = """
CREATE TRIGGER pipeline_stagechange_delete_guard
BEFORE DELETE ON pipeline_stagechange
WHEN OLD.from_stage IS NOT NULL
    OR NOT EXISTS (
        SELECT 1 FROM pipeline_application
        WHERE id = OLD.application_id AND stage = 'applied'
    )
    OR (SELECT COUNT(*) FROM pipeline_stagechange WHERE application_id = OLD.application_id) <> 1
BEGIN
    SELECT RAISE(ABORT, 'Stage history is kept: only the creation entry of an application that never moved can be deleted.');
END;
"""
DROP_TRIGGER = "DROP TRIGGER IF EXISTS pipeline_stagechange_delete_guard;"


class Migration(migrations.Migration):
    dependencies = [
        ("pipeline", "0004_archived_candidate_guards"),
    ]

    operations = [
        migrations.RunSQL([CREATE_TRIGGER], [DROP_TRIGGER]),
    ]
