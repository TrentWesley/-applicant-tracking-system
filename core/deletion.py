"""
Admin permanent deletes (Phase 10). A delete runs in one transaction and is refused, with a
clear message, when the database's own protections stop it:

- PROTECT foreign keys refuse deleting a candidate or job that still has applications; if
  another request commits a new application after Django's PROTECT lookup, SQLite's deferred
  foreign-key check fails the commit instead (IntegrityError).
- The stage-history trigger (pipeline/0005) refuses deleting any StageChange except the creation
  entry of an application still at Applied, so moved history is never erased.
"""

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

ALREADY_DELETED_MESSAGE = "{name} was already deleted."
CANT_DELETE_MESSAGE = "{name} can't be deleted."


class DeleteRefused(Exception):
    """A delete that removed nothing. `gone` means the record no longer exists."""

    def __init__(self, message, gone=False):
        super().__init__(message)
        self.gone = gone


def delete_or_refuse(instance, refusal):
    """
    Delete `instance` (and what CASCADE takes with it) in one transaction. `refusal()` gives the
    message when the database refuses; it runs afterwards, so it sees the current data.
    """
    name, label, pk = str(instance), instance._meta.label, instance.pk
    try:
        with transaction.atomic():
            _count, per_model = instance.delete()
    except ProtectedError, IntegrityError:
        instance.pk = pk  # delete() clears pk even when the commit then fails
        raise DeleteRefused(refusal() or CANT_DELETE_MESSAGE.format(name=name)) from None
    if not per_model.get(label):
        raise DeleteRefused(ALREADY_DELETED_MESSAGE.format(name=name), gone=True)
