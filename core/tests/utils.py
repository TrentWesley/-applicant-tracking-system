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


def database_state():
    """Every candidate, job, skill, application, history and user row, so a test can show a
    request wrote nothing."""
    from candidates.models import Candidate
    from jobs.models import JobOpening, Skill
    from pipeline.models import Application, StageChange

    models = (Candidate, JobOpening, Skill, Application, StageChange, User, Group)
    state = [list(model.objects.order_by("pk").values_list()) for model in models]
    state.append(sorted(User.groups.through.objects.values_list("user_id", "group_id")))
    state.append(sorted(JobOpening.skills.through.objects.values_list("job_id", "skill_id")))
    return state


def queries_for(client, url):
    """How many queries one GET of `url` runs (after a first GET warms the session)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client.get(url)
    with CaptureQueriesContext(connection) as queries:
        client.get(url)
    return len(queries)
