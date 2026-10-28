from django.db import migrations

from core.roles import grant_permissions


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Recruiter")
    Group.objects.get_or_create(name="Admin")
    # Staff Management works on Django's User. Staff are deactivated, never deleted.
    # Each ATS model's permissions are attached by the migration that adds the model.
    grant_permissions(apps, "Admin", "auth", "user", ["view", "add", "change"])


def remove_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=["Recruiter", "Admin"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
