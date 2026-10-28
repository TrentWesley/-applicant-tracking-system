import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ArchiveVersusCreateConcurrencyTests(SimpleTestCase):
    """
    Two real requests on two threads and two connections to a SQLite file: one pauses inside
    its transaction right after its guard check, and the other runs during that pause. Exactly
    one must win, the other must be refused with its normal message (not a "database is
    locked" error), and the candidate must never end up archived with an active application.
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

    def test_a_create_already_in_progress_wins_and_the_archive_is_refused(self):
        result = self.report["create_first"]
        self.assertEqual(result["first"], "ok")
        self.assertTrue(result["second"].startswith("refused: "), result["second"])
        self.assertIn("active applications: Data Analyst (Applied)", result["second"])
        self.assertEqual((result["archived"], result["applications"]), (False, 1))

    def test_an_archive_already_in_progress_wins_and_the_create_is_refused(self):
        result = self.report["archive_first"]
        self.assertEqual(result["first"], "ok")
        self.assertEqual(
            result["second"],
            "refused: This candidate is archived and can't get new applications.",
        )
        self.assertEqual((result["archived"], result["applications"]), (True, 0))
