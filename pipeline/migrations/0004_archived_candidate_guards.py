from django.db import migrations

# An archived candidate never has an active application. These triggers hold that rule for
# every write, including two requests that each passed their own checks: SQLite has a single
# writer and a trigger runs inside the writing statement, so it always sees the latest committed
# rows, and the second of the two conflicting writes is refused. Each message starts with
# "archived-candidate guard" (candidates.services.ARCHIVED_GUARD), which the services turn back
# into their normal refusal messages.
ACTIVE_STAGE_VALUES = ("applied", "screening", "interview", "final_review", "offer")
ACTIVE = ", ".join(f"'{value}'" for value in ACTIVE_STAGE_VALUES)
CANDIDATE_IS_ARCHIVED = (
    "(SELECT archived_at FROM candidates_candidate WHERE id = NEW.candidate_id) IS NOT NULL"
)

CREATE_TRIGGERS = [
    f"""
    CREATE TRIGGER pipeline_application_insert_archived_guard
    BEFORE INSERT ON pipeline_application
    WHEN {CANDIDATE_IS_ARCHIVED}
    BEGIN
        SELECT RAISE(ABORT, 'archived-candidate guard: an archived candidate cannot get new applications.');
    END;
    """,
    f"""
    CREATE TRIGGER pipeline_application_update_archived_guard
    BEFORE UPDATE OF stage, candidate_id ON pipeline_application
    WHEN NEW.stage IN ({ACTIVE}) AND {CANDIDATE_IS_ARCHIVED}
    BEGIN
        SELECT RAISE(ABORT, 'archived-candidate guard: an archived candidate cannot have active applications.');
    END;
    """,
    f"""
    CREATE TRIGGER candidates_candidate_archive_guard
    BEFORE UPDATE OF archived_at ON candidates_candidate
    WHEN NEW.archived_at IS NOT NULL AND EXISTS (
        SELECT 1 FROM pipeline_application WHERE candidate_id = NEW.id AND stage IN ({ACTIVE})
    )
    BEGIN
        SELECT RAISE(ABORT, 'archived-candidate guard: a candidate with active applications cannot be archived.');
    END;
    """,
]
DROP_TRIGGERS = [
    "DROP TRIGGER IF EXISTS pipeline_application_insert_archived_guard;",
    "DROP TRIGGER IF EXISTS pipeline_application_update_archived_guard;",
    "DROP TRIGGER IF EXISTS candidates_candidate_archive_guard;",
]


class Migration(migrations.Migration):
    dependencies = [
        ("candidates", "0002_candidate_group_permissions"),
        ("pipeline", "0003_application_group_permissions"),
    ]

    operations = [
        migrations.RunSQL(CREATE_TRIGGERS, DROP_TRIGGERS),
    ]
