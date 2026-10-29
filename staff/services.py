"""
Deactivate, Reactivate and Change role: the only ways the app changes an existing staff account.
Each changes `is_active` or the Admin/Recruiter group and nothing else; accounts are never
deleted, so every Application and StageChange keeps its user.

Nobody can lock out administration: an Admin can't deactivate or demote themselves, and nobody can
deactivate or demote the last active Admin (an active superuser counts as an Admin). Each check
runs on the stored account inside the same transaction as its write, and
`transaction_mode = "IMMEDIATE"` (config/settings.py) takes the write lock at BEGIN. Two Admins
acting on each other at once are therefore serialised: the second waits, sees the first's change,
and is refused.
"""

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q

from core.roles import ADMIN, RECRUITER, role_name

SELF_DEACTIVATE_MESSAGE = "You can't deactivate your own account."
SELF_DEMOTE_MESSAGE = "You can't remove your own Admin role."
LAST_ADMIN_MESSAGE = (
    "{user} is the last active Admin, so they can't be {change}. Make another account an Admin "
    "first."
)
SUPERUSER_MESSAGE = (
    "{user} is a superuser, so they're always an Admin. Their role can't be changed here."
)
ALREADY_INACTIVE_MESSAGE = "{user} is already inactive, so nothing was changed."
ALREADY_ACTIVE_MESSAGE = "{user} is already active, so nothing was changed."
ALREADY_ROLE_MESSAGE = "{user} is already {role}, so nothing was changed."
UNKNOWN_ROLE_MESSAGE = "Choose Admin or Recruiter."
ROLES = (ADMIN, RECRUITER)


class StaffChangeRefused(Exception):
    """A Deactivate, Reactivate or Change role that changed nothing. The message says why."""


def display_name(user):
    return user.get_full_name() or user.get_username()


def with_article(role):
    return f"an {role}" if role == ADMIN else f"a {role}"


def active_admin_ids():
    admins = Q(is_superuser=True) | Q(groups__name=ADMIN)
    return set(User.objects.filter(admins, is_active=True).values_list("pk", flat=True))


def is_last_active_admin(user, admin_ids=None):
    admin_ids = active_admin_ids() if admin_ids is None else admin_ids
    return admin_ids == {user.pk}


def deactivation_blocker(user, by, admin_ids=None):
    """Why `by` can't deactivate `user` now, or None. `admin_ids` saves a query per list row."""
    if user.pk == by.pk:
        return SELF_DEACTIVATE_MESSAGE
    if not user.is_active:
        return ALREADY_INACTIVE_MESSAGE.format(user=display_name(user))
    if is_last_active_admin(user, admin_ids):
        return LAST_ADMIN_MESSAGE.format(user=display_name(user), change="deactivated")
    return None


def role_change_blocker(user, role, by, admin_ids=None):
    """Why `by` can't give `user` this role now, or None."""
    if role not in ROLES:
        return UNKNOWN_ROLE_MESSAGE
    if role == RECRUITER and user.pk == by.pk:
        return SELF_DEMOTE_MESSAGE
    if role == role_name(user):
        return ALREADY_ROLE_MESSAGE.format(user=display_name(user), role=with_article(role))
    if role == RECRUITER and user.is_superuser:
        return SUPERUSER_MESSAGE.format(user=display_name(user))
    if role == RECRUITER and is_last_active_admin(user, admin_ids):
        return LAST_ADMIN_MESSAGE.format(user=display_name(user), change="made a Recruiter")
    return None


def _refuse_if(blocker):
    if blocker:
        raise StaffChangeRefused(blocker)


def deactivate_staff(user, by):
    """They can no longer log in; their history stays. Refreshes `user` in place."""
    with transaction.atomic():
        stored = User.objects.get(pk=user.pk)
        _refuse_if(deactivation_blocker(stored, by))
        User.objects.filter(pk=user.pk).update(is_active=False)
    user.refresh_from_db()


def reactivate_staff(user):
    """They can log in again, with the same role and history. Refreshes `user` in place."""
    with transaction.atomic():
        updated = User.objects.filter(pk=user.pk, is_active=False).update(is_active=True)
    user.refresh_from_db()
    if updated != 1:
        raise StaffChangeRefused(ALREADY_ACTIVE_MESSAGE.format(user=display_name(user)))


def set_role(user, role):
    """Put `user` in exactly one of the two role groups; any other groups are left alone."""
    user.groups.remove(*Group.objects.filter(name__in=ROLES).exclude(name=role))
    user.groups.add(Group.objects.get(name=role))


def change_role(user, role, by):
    """Make `user` an Admin or a Recruiter."""
    with transaction.atomic():
        stored = User.objects.get(pk=user.pk)
        _refuse_if(role_change_blocker(stored, role, by))
        set_role(stored, role)
