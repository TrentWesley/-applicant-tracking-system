"""
Run by test_archive_concurrency and pipeline's test_delete_concurrency in a separate process:
real requests on two threads, each with its own connection to a fresh SQLite file migrated with
the project's settings. (The test database is in-memory and shared between threads, so it can't
show file locking.)

    python -m candidates.tests.concurrency_worker <database file> [archive|delete]

Prints one JSON object: for each scenario, what each request returned and the final state.
"""

import json
import sys
import threading
import time
from unittest import mock


def configure(db_path):
    import django
    from django.conf import settings

    import config.settings as base

    values = {name: getattr(base, name) for name in dir(base) if name.isupper()}
    values["DATABASES"] = {"default": base.DATABASES["default"] | {"NAME": db_path}}
    settings.configure(**values)
    django.setup()
    from django.core.management import call_command

    call_command("migrate", verbosity=0)


def attempt(call):
    from django.core.exceptions import ObjectDoesNotExist
    from django.db import connection

    from candidates.services import CandidateStatusRefused
    from core.deletion import DeleteRefused
    from pipeline.services import StageChangeRefused

    try:
        call()
        return "ok"
    except (CandidateStatusRefused, DeleteRefused, StageChangeRefused) as refusal:
        return f"refused: {refusal}"
    except ObjectDoesNotExist:
        return "missing"  # the view turns this into a 404
    except Exception as error:  # noqa: BLE001 - reported to the test, e.g. "database is locked"
        return f"error: {type(error).__name__}: {error}"
    finally:
        connection.close()


def race(first, second, pause_target):
    """Run `first`, pausing it inside its transaction just after its guard check, then run
    `second` on another thread during that pause."""
    checked = threading.Event()
    results = {}
    module_name, name = pause_target.rsplit(".", 1)
    real = getattr(sys.modules[module_name], name)

    def check_then_pause(*args, **kwargs):
        value = real(*args, **kwargs)
        checked.set()
        time.sleep(0.5)  # the other request runs now
        return value

    def run_first():
        with mock.patch(pause_target, check_then_pause):
            results["first"] = attempt(first)

    def run_second():
        checked.wait(10)
        results["second"] = attempt(second)

    threads = [threading.Thread(target=run_first), threading.Thread(target=run_second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    return results


def delete_scenarios(user, job):
    """An Admin delete racing a stage move on the same never-moved application."""
    from candidates.models import Candidate, Source
    from pipeline.models import Application
    from pipeline.services import change_stage, create_application, delete_application

    report = {}
    for scenario in ("advance_first", "delete_first"):
        candidate = Candidate.objects.create(
            first_name="Del",
            last_name=scenario,
            email=f"del-{scenario}@example.com",
            source=Source.OTHER,
        )
        pk = create_application(candidate=candidate, job_opening=job, created_by=user).pk

        def advance(pk=pk):
            application = Application.objects.get(pk=pk)
            change_stage(
                application=application,
                action="advance",
                expected_stage="applied",
                changed_by=user,
            )

        def delete(pk=pk):
            delete_application(Application.objects.get(pk=pk))

        if scenario == "advance_first":
            results = race(advance, delete, "pipeline.services.current_stage")
        else:
            results = race(delete, advance, "pipeline.services.application_deletion_blocker")
        remaining = Application.objects.filter(pk=pk).first()
        results["stage"] = remaining.stage if remaining else None
        results["history"] = remaining.stage_changes.count() if remaining else 0
        report[scenario] = results
    return report


def main(db_path, group="archive"):
    configure(db_path)
    from django.contrib.auth.models import User

    from candidates.models import Candidate, Source
    from candidates.services import archive_candidate
    from jobs.models import EmploymentType, JobOpening, WorkMode
    from pipeline.services import create_application

    user = User.objects.create_user("worker")
    job = JobOpening.objects.create(
        title="Data Analyst", employment_type=EmploymentType.FULL_TIME, work_mode=WorkMode.HYBRID
    )
    if group == "delete":
        print(json.dumps(delete_scenarios(user, job)))
        return
    report = {}
    for scenario in ("create_first", "archive_first"):
        candidate = Candidate.objects.create(
            first_name="Ann",
            last_name=scenario,
            email=f"{scenario}@example.com",
            source=Source.OTHER,
        )

        def create(candidate=candidate):
            create_application(candidate=candidate, job_opening=job, created_by=user)

        def archive(candidate=candidate):
            archive_candidate(Candidate.objects.get(pk=candidate.pk))

        if scenario == "create_first":
            results = race(create, archive, "pipeline.services.candidate_is_archived")
        else:
            results = race(archive, create, "candidates.services.active_applications")
        candidate.refresh_from_db()
        results["archived"] = candidate.archived_at is not None
        results["applications"] = candidate.applications.count()
        report[scenario] = results
    print(json.dumps(report))


if __name__ == "__main__":
    main(*sys.argv[1:])
