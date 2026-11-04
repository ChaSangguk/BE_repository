from datetime import timedelta
from math import ceil, floor

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from debates.models import Category, Debate, DebateStatistics


class PartCP1ContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = get_user_model().objects.create(
            email="part-c-contract@example.com",
            nickname="Part C contract",
        )
        cls.category = Category.objects.create(name="Part C contract")

    def make_debate(self, *, ends_at, status="OPEN", closed_at=None):
        return Debate.objects.create(
            creator=self.creator,
            category=self.category,
            type="QUICK",
            title="Distinct Part C test title",
            content="A short debate for the public endpoint checks.",
            duration_minutes=10,
            started_at=ends_at - timedelta(minutes=10),
            ends_at=ends_at,
            status=status,
            closed_at=closed_at,
        )

    def test_closed_result_exposes_header_and_final_stance_breakdown(self):
        # FC-DB-300-001 and FC-DB-300-004. Expected percentages for
        # 4/2/1 participants out of 7 are 57.1, 28.6, and 14.3.
        ends_at = timezone.now() - timedelta(minutes=2)
        debate = self.make_debate(ends_at=ends_at, status="CLOSED", closed_at=ends_at)
        DebateStatistics.objects.create(
            debate=debate,
            total_participants=7,
            opinion_count=0,
            rebuttal_count=0,
            stance_changed_count=0,
            computed_at=timezone.now(),
            final_pro=4,
            final_con=2,
            final_neutral=1,
            stance_kept_count=7,
            sankey_data={},
        )

        response = self.client.get(f"/v1/debates/{debate.pk}/result")
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["data"]

        # P1 specifies the values and precision. These keys map those
        # expectations to the observed public response.
        self.assertEqual(result["title"], debate.title)
        self.assertEqual(result["status"], "CLOSED")
        self.assertEqual(parse_datetime(result["closedAt"]), debate.closed_at)
        self.assertEqual(result["counts"]["finalPro"], 4)
        self.assertEqual(result["counts"]["finalCon"], 2)
        self.assertEqual(result["counts"]["finalNeutral"], 1)
        self.assertEqual(
            result["finalStancePercentages"],
            {"PRO": 57.1, "CON": 28.6, "NEUTRAL": 14.3},
        )

    def test_open_result_is_not_ready(self):
        # API #44 requires CLOSED and a completed aggregate.
        debate = self.make_debate(ends_at=timezone.now() + timedelta(minutes=2))
        response = self.client.get(f"/v1/debates/{debate.pk}/result")

        self.assertEqual(response.status_code, 409, response.content)

    def test_closed_result_without_aggregate_is_not_ready(self):
        ends_at = timezone.now() - timedelta(minutes=2)
        debate = self.make_debate(ends_at=ends_at, status="CLOSED", closed_at=ends_at)

        response = self.client.get(f"/v1/debates/{debate.pk}/result")

        self.assertEqual(response.status_code, 409, response.content)

    def test_open_timing_supports_server_clock_countdown(self):
        # FC-DB-200-002. A QUICK debate two minutes from its deadline
        # has a positive countdown close to 120 seconds.
        ends_at = timezone.now() + timedelta(minutes=2)
        debate = self.make_debate(ends_at=ends_at)

        response = self.client.get(f"/v1/debates/{debate.pk}/timing")
        self.assertEqual(response.status_code, 200, response.content)
        timing = response.json()
        self.assertEqual(timing["status"], "OPEN")
        self.assertEqual(parse_datetime(timing["endsAt"]), ends_at)
        self.assertGreater(timing["remainingSeconds"], 0)
        remaining = (ends_at - parse_datetime(timing["serverTime"])).total_seconds()
        self.assertIn(timing["remainingSeconds"], (floor(remaining), ceil(remaining)))

    def test_elapsed_deadline_is_reported_as_closed(self):
        # FC-DB-200-014. The client must be able to detect closure even
        # when the persisted status has yet to catch up to the deadline.
        debate = self.make_debate(ends_at=timezone.now() - timedelta(seconds=1))

        response = self.client.get(f"/v1/debates/{debate.pk}/timing")
        self.assertEqual(response.status_code, 200, response.content)
        timing = response.json()
        self.assertEqual(timing["status"], "CLOSED")
        self.assertEqual(timing["remainingSeconds"], 0)
