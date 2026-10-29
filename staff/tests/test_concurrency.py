import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

LAST_ADMIN = "refused: {name} is the last active Admin"


class LastActiveAdminConcurrencyTests(SimpleTestCase):
    """
    The only two active Admins, Ada and Grace, act on each other at the same moment, as two real
    requests on two threads and connections to a SQLite file (see
    candidates/tests/concurrency_worker.py). Ada's request pauses inside its transaction just
    after its last-active-Admin check; Grace's runs during the pause. Each check and its write
    are one transaction, so Grace's waits, sees Ada's change, and is refused: one active Admin
    always remains.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with tempfile.TemporaryDirectory() as directory:
            env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "candidates.tests.concurrency_worker",
                    str(Path(directory) / "race.sqlite3"),
                    "staff",
                ],
                cwd=settings.BASE_DIR,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
        if completed.returncode != 0:
            raise AssertionError(f"worker failed:\n{completed.stderr}")
        cls.report = json.loads(completed.stdout.strip().splitlines()[-1])

    def assertOneAdminRemains(self, scenario, second_refusal):
        result = self.report[scenario]
        self.assertEqual(result["first"], "ok")
        self.assertTrue(result["second"].startswith(second_refusal), result["second"])
        self.assertEqual(result["active_admins"], ["ada"])

    def test_two_admins_deactivating_each_other(self):
        self.assertOneAdminRemains("deactivate_both", LAST_ADMIN.format(name="Ada"))

    def test_two_admins_demoting_each_other(self):
        self.assertOneAdminRemains("demote_both", LAST_ADMIN.format(name="Ada"))

    def test_a_deactivate_and_a_demote_at_the_same_time(self):
        self.assertOneAdminRemains("deactivate_and_demote", LAST_ADMIN.format(name="Ada"))
