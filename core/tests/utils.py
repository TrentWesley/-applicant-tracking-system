from django.contrib.auth.models import Group, User

from core.roles import ADMIN, RECRUITER

PASSWORD = "correct-horse-battery"


def make_user(username, role=None, **extra):
    """Create a staff user, optionally in the Recruiter or Admin group."""
    user = User.objects.create_user(username=username, password=PASSWORD, **extra)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_recruiter(username="recruiter", **extra):
    return make_user(username, RECRUITER, **extra)


def make_admin(username="admin", **extra):
    return make_user(username, ADMIN, **extra)
