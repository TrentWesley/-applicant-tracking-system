from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse

DUPLICATE_SKILL_MESSAGE = "A skill with this name already exists."


class Skill(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = [Lower("name"), "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="skill_name_unique_ignoring_case",
                violation_error_message=DUPLICATE_SKILL_MESSAGE,
            ),
        ]

    def __str__(self):
        return self.name


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Full-time"
    PART_TIME = "part_time", "Part-time"
    CONTRACT = "contract", "Contract"
    INTERNSHIP = "internship", "Internship"


class WorkMode(models.TextChoices):
    ON_SITE = "on_site", "On-site"
    REMOTE = "remote", "Remote"
    HYBRID = "hybrid", "Hybrid"


class JobStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class JobOpening(models.Model):
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    employment_type = models.CharField(max_length=20, choices=EmploymentType)
    work_mode = models.CharField(max_length=20, choices=WorkMode)
    # Not on any form: it changes only through the Close and Reopen actions (Phase 7).
    status = models.CharField(
        max_length=10, choices=JobStatus, default=JobStatus.OPEN, editable=False
    )
    # The skills the job requires, through JobSkill so a skill in use can't be deleted.
    skills = models.ManyToManyField(Skill, through="JobSkill", blank=True, related_name="jobs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("jobs:job_detail", args=[self.pk])


class JobSkill(models.Model):
    """
    One skill required by one job. Django's automatic many-to-many table would delete these rows
    along with the skill; PROTECT refuses that instead, and the database foreign key refuses it
    too if another request assigns the skill while it is being deleted.
    """

    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)

    class Meta:
        default_permissions = ()  # managed through the job form, never on its own
        constraints = [
            models.UniqueConstraint(fields=["job", "skill"], name="job_skill_unique"),
        ]

    def __str__(self):
        return f"{self.job} needs {self.skill}"
