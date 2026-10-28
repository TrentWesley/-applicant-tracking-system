from jobs.models import EmploymentType, JobOpening, Skill, WorkMode


def make_skill(name="Python"):
    return Skill.objects.create(name=name)


def make_job(title="Data Analyst", skills=(), **extra):
    fields = {"employment_type": EmploymentType.FULL_TIME, "work_mode": WorkMode.HYBRID} | extra
    job = JobOpening.objects.create(title=title, **fields)
    job.skills.set(skills)
    return job
