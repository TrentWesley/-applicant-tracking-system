import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

MOVED = "This application can't be deleted because it has moved from Applied."


class DeleteVersusStageChangeConcurrencyTests(SimpleTestCase):
    """
    An Admin delete and a stage move on the same never-moved application, as two real requests on
    two threads and connections to a SQLite file (see candidates/tests/concurrency_worker.py). The
    first pauses inside its transaction just after its check; the second runs during the pause.
    The delete's eligibility check and the delete itself are one transaction, so exactly one wins.
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
                    "delete",
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

    def test_an_advance_in_progress_wins_and_the_delete_is_refused(self):
        result = self.report["advance_first"]
        self.assertEqual(result["first"], "ok")
        self.assertTrue(result["second"].startswith(f"refused: {MOVED}"), result["second"])
        self.assertEqual((result["stage"], result["history"]), ("screening", 2))

    def test_a_delete_in_progress_wins_and_the_advance_finds_nothing(self):
        result = self.report["delete_first"]
        self.assertEqual(result["first"], "ok")
        self.assertEqual(result["second"], "missing")
        self.assertEqual((result["stage"], result["history"]), (None, 0))
