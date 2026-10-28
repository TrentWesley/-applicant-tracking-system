from django.contrib.auth.models import User

from candidates.tests.utils import make_candidate
from core.tests.utils import make_recruiter
from jobs.tests.utils import make_job
from pipeline.models import Application
from pipeline.services import create_application


def default_creator():
    """One shared recruiter, so helpers don't clash with users a test made itself."""
    return User.objects.filter(username="creator").first() or make_recruiter("creator")


def make_application(candidate=None, job=None, created_by=None, stage=None, **extra):
    """
    Create an application through the service. A `stage` is then set directly, standing in for
    the stage moves that arrive in Phases 5 and 6.
    """
    application = create_application(
        candidate=candidate or make_candidate(),
        job_opening=job or make_job(),
        created_by=created_by or default_creator(),
        **extra,
    )
    if stage:
        Application.objects.filter(pk=application.pk).update(stage=stage)
        application.refresh_from_db()
    return application
