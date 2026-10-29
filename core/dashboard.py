"""
The dashboard's four sections (US 55-58), each a read-only query over existing data, with no
time-based rules and no job filter. The number of queries doesn't grow with the data.

- Active applications are the five active stages, on open and closed jobs. An archived candidate
  never has one, so archive status needs no separate rule.
- Total hires counts every Hired application, whatever its job's status or its candidate's
  archive status.
"""

from dataclasses import dataclass

from django.db.models import Count, Q
from django.urls import reverse

from jobs.models import JobOpening, JobStatus
from pipeline.models import ACTIVE_STAGES, Application, Stage, StageChange

RECENT_ACTIVITY_SIZE = 10


@dataclass(frozen=True)
class Summary:
    open_jobs: int
    closed_jobs: int
    active: int
    hires: int


@dataclass(frozen=True)
class PipelineCard:
    stage: Stage
    count: int
    url: str


def summary_and_pipeline():
    """The stat tiles and the five stage cards, from one query per table."""
    jobs = JobOpening.objects.aggregate(
        open=Count("pk", filter=Q(status=JobStatus.OPEN)),
        closed=Count("pk", filter=Q(status=JobStatus.CLOSED)),
    )
    stages = (*ACTIVE_STAGES, Stage.HIRED)
    counts = Application.objects.aggregate(
        **{stage.value: Count("pk", filter=Q(stage=stage)) for stage in stages}
    )
    list_url = reverse("pipeline:application_list")
    pipeline = [
        PipelineCard(stage, counts[stage.value], f"{list_url}?stage={stage.value}")
        for stage in ACTIVE_STAGES
    ]
    summary = Summary(
        open_jobs=jobs["open"],
        closed_jobs=jobs["closed"],
        active=sum(card.count for card in pipeline),
        hires=counts[Stage.HIRED.value],
    )
    return summary, pipeline


def closed_jobs_with_active_applications():
    """Needs Attention: most active applications first, then by title."""
    return (
        JobOpening.objects.filter(status=JobStatus.CLOSED)
        .annotate(
            active_count=Count("applications", filter=Q(applications__stage__in=ACTIVE_STAGES))
        )
        .filter(active_count__gt=0)
        .order_by("-active_count", "title", "pk")
    )


def applications_at_offer():
    """Needs Attention: the longest at Offer first."""
    return (
        Application.objects.filter(stage=Stage.OFFER)
        .select_related("candidate", "job_opening")
        .order_by("stage_changed_at", "pk")
    )


def recent_activity():
    """The newest StageChanges, newest first, read straight from the append-only history."""
    return StageChange.objects.select_related(
        "application__candidate", "application__job_opening", "changed_by"
    ).order_by("-changed_at", "-pk")[:RECENT_ACTIVITY_SIZE]


def dashboard_context():
    summary, pipeline = summary_and_pipeline()
    return {
        "summary": summary,
        "pipeline": pipeline,
        "pipeline_max": max(card.count for card in pipeline) or 1,  # progress bars need max > 0
        "closed_jobs": closed_jobs_with_active_applications(),
        "offers": applications_at_offer(),
        "recent_activity": recent_activity(),
    }
