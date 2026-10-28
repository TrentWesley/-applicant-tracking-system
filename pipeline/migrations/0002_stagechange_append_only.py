from django.db import migrations

# StageChange rows are immutable. The model refuses save() on an existing row and queryset
# update(); this trigger also refuses UPDATEs that bypass the ORM. Deletes stay possible so that
# deleting an application can remove its history (the model refuses direct deletes).
CREATE_TRIGGER = """
CREATE TRIGGER pipeline_stagechange_no_update
BEFORE UPDATE ON pipeline_stagechange
BEGIN
    SELECT RAISE(ABORT, 'Stage history is append-only: entries cannot be changed.');
END;
"""
DROP_TRIGGER = "DROP TRIGGER IF EXISTS pipeline_stagechange_no_update;"


class Migration(migrations.Migration):
    dependencies = [
        ("pipeline", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(CREATE_TRIGGER, DROP_TRIGGER),
    ]
