from django.template.loader import render_to_string
from django.test import SimpleTestCase

from pipeline.models import ACTIVE_STAGES, Stage


def badge(stage):
    return render_to_string(
        "core/_stage_badge.html", {"stage": stage, "label": stage.label}
    ).strip()


class StageBadgeTests(SimpleTestCase):
    """One badge partial, styled by stage group: active, Offer, Hired, Rejected and Withdrawn."""

    def test_badge_shows_the_stage_label(self):
        for stage in Stage:
            with self.subTest(stage=stage):
                self.assertIn(f">{stage.label}</span>", badge(stage))

    def test_active_stages_before_offer_share_one_style(self):
        early = [s for s in ACTIVE_STAGES if s != Stage.OFFER]
        self.assertEqual(
            {badge(s).replace(s.label, "") for s in early},
            {badge(Stage.APPLIED).replace("Applied", "")},
        )

    def test_offer_hired_and_closed_out_stages_each_look_different(self):
        groups = {
            badge(Stage.APPLIED).replace("Applied", ""),
            badge(Stage.OFFER).replace("Offer", ""),
            badge(Stage.HIRED).replace("Hired", ""),
            badge(Stage.REJECTED).replace("Rejected", ""),
        }
        self.assertEqual(len(groups), 4)
        self.assertEqual(
            badge(Stage.REJECTED).replace("Rejected", ""),
            badge(Stage.WITHDRAWN).replace("Withdrawn", ""),
        )
