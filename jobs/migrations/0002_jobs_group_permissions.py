from django.db import migrations

from core.roles import grant_permissions


def grant_jobs_permissions(apps, schema_editor):
    grant_permissions(apps, "Recruiter", "jobs", "jobopening", ["view", "add", "change"])
    grant_permissions(apps, "Recruiter", "jobs", "skill", ["view"])
    grant_permissions(apps, "Admin", "jobs", "jobopening", ["view", "add", "change", "delete"])
    grant_permissions(apps, "Admin", "jobs", "skill", ["view", "add", "change", "delete"])


def revoke_jobs_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    jobs_perms = Permission.objects.filter(content_type__app_label="jobs")
    for group in Group.objects.filter(name__in=["Recruiter", "Admin"]):
        group.permissions.remove(*jobs_perms)


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0001_initial"),
        ("core", "0001_create_role_groups"),
    ]

    operations = [
        migrations.RunPython(grant_jobs_permissions, revoke_jobs_permissions),
    ]
