from django.db import migrations

from core.roles import grant_permissions


def grant_candidate_permissions(apps, schema_editor):
    grant_permissions(apps, "Recruiter", "candidates", "candidate", ["view", "add", "change"])
    grant_permissions(apps, "Admin", "candidates", "candidate", ["view", "add", "change", "delete"])


def revoke_candidate_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    candidate_perms = Permission.objects.filter(content_type__app_label="candidates")
    for group in Group.objects.filter(name__in=["Recruiter", "Admin"]):
        group.permissions.remove(*candidate_perms)


class Migration(migrations.Migration):
    dependencies = [
        ("candidates", "0001_initial"),
        ("core", "0001_create_role_groups"),
    ]

    operations = [
        migrations.RunPython(grant_candidate_permissions, revoke_candidate_permissions),
    ]
