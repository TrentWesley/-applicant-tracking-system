from django.db import migrations

from core.roles import grant_permissions


def grant_application_permissions(apps, schema_editor):
    grant_permissions(apps, "Recruiter", "pipeline", "application", ["view", "add", "change"])
    grant_permissions(apps, "Admin", "pipeline", "application", ["view", "add", "change", "delete"])


def revoke_application_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    pipeline_perms = Permission.objects.filter(content_type__app_label="pipeline")
    for group in Group.objects.filter(name__in=["Recruiter", "Admin"]):
        group.permissions.remove(*pipeline_perms)


class Migration(migrations.Migration):
    dependencies = [
        ("pipeline", "0002_stagechange_append_only"),
        ("core", "0001_create_role_groups"),
    ]

    operations = [
        migrations.RunPython(grant_application_permissions, revoke_application_permissions),
    ]
