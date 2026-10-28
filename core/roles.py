"""Recruiter and Admin roles, shared by views, templates and migrations."""

from functools import wraps

from django.core.exceptions import PermissionDenied

RECRUITER = "Recruiter"
ADMIN = "Admin"


def is_admin(user):
    """Admins are members of the Admin group. Superusers count as Admins too."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=ADMIN).exists()


def role_name(user):
    """Return "Admin", "Recruiter", or "" for a user with neither role."""
    if is_admin(user):
        return ADMIN
    if user.is_authenticated and user.groups.filter(name=RECRUITER).exists():
        return RECRUITER
    return ""


def admin_required(view):
    """Refuse non-Admins with 403. Login is already enforced by LoginRequiredMiddleware."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def grant_permissions(apps, group_name, app_label, model_name, actions):
    """
    Give a group model permissions such as ["view", "add", "change"], from a data migration.

    Django creates model permissions in a post_migrate signal, after *all* migrations have run,
    so on a fresh database they don't exist yet when a data migration runs. This creates any
    missing content type and permission rows first, matching what Django would create (same
    codename and name), so the signal later finds them and adds no duplicates.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    opts = apps.get_model(app_label, model_name)._meta
    content_type, _ = ContentType.objects.get_or_create(
        app_label=opts.app_label, model=opts.model_name
    )
    group = Group.objects.get(name=group_name)
    for action in actions:
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_{opts.model_name}",
            defaults={"name": f"Can {action} {opts.verbose_name_raw}"},
        )
        group.permissions.add(permission)
