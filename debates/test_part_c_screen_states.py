from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase


Category = apps.get_model("debates", "Category")
Debate = apps.get_model("debates", "Debate")
DebateParticipant = apps.get_model("debates", "DebateParticipant")


class PartCScreenStateTests(APITestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ends_at = self.now + timedelta(minutes=1)
        self.user = get_user_model().objects.create(
            email="partc-participant@example.invalid",
            nickname="partc-participant",
        )
        self.debate = Debate.objects.create(
            creator=self.user,
            category=Category.objects.create(name="Screen state"),
            type="QUICK",
            title="Debate screen state",
            content="Verify the Part C screen state.",
            status="OPEN",
            started_at=self.ends_at - timedelta(minutes=5),
            ends_at=self.ends_at,
            duration_minutes=5,
            participant_count=1,
            opinion_count=4,
        )
        DebateParticipant.objects.create(
            debate=self.debate,
            user=self.user,
            anonymous_no=1,
            initial_stance="PRO",
            current_stance="CON",
            joined_at=self.now - timedelta(minutes=2),
        )
        self.base_url = f"/v1/debates/{self.debate.pk}"

    def pass_deadline(self, *, closed=False):
        self.ends_at = self.now - timedelta(minutes=1)
        Debate.objects.filter(pk=self.debate.pk).update(
            started_at=self.ends_at - timedelta(minutes=5),
            ends_at=self.ends_at,
            status="CLOSED" if closed else "OPEN",
            closed_at=self.ends_at if closed else None,
        )

    def test_stance_popup_shows_original_current_and_other_options(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{self.base_url}/me/stance")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["initialStance"], "PRO")
        self.assertEqual(response.data["currentStance"], "CON")
        self.assertCountEqual(response.data["selectableStances"], ["PRO", "NEUTRAL"])

    def test_stance_popup_retains_stances_but_disables_choices_after_deadline(self):
        self.client.force_authenticate(user=self.user)
        for closed in (False, True):
            with self.subTest(persisted_closed=closed):
                self.pass_deadline(closed=closed)
                response = self.client.get(f"{self.base_url}/me/stance")

                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["initialStance"], "PRO")
                self.assertEqual(response.data["currentStance"], "CON")
                self.assertEqual(response.data["selectableStances"], [])

    def test_timing_switches_open_screen_to_read_only_after_deadline(self):
        self.client.force_authenticate(user=self.user)
        before = self.client.get(f"{self.base_url}/timing")
        self.assertEqual(before.status_code, 200, before.data)
        self.assertEqual(before.data["status"], "OPEN")
        self.assertIs(before.data["isReadOnly"], False)
        self.assertGreater(before.data["remainingSeconds"], 0)

        self.pass_deadline()
        after = self.client.get(f"{self.base_url}/timing")
        self.assertEqual(after.status_code, 200, after.data)
        self.assertEqual(after.data["status"], "CLOSED")
        self.assertIs(after.data["isReadOnly"], True)
        self.assertEqual(after.data["remainingSeconds"], 0)
        self.assertEqual(parse_datetime(after.data["endsAt"]), self.ends_at)

    def test_pending_result_gives_public_header_without_provisional_counts(self):
        for closed in (False, True):
            with self.subTest(persisted_closed=closed):
                self.pass_deadline(closed=closed)
                response = self.client.get(f"{self.base_url}/result")

                self.assertEqual(response.status_code, 409, response.data)
                error = response.data["error"]
                self.assertEqual(error["code"], "RESULT_NOT_READY")
                details = error["details"]
                self.assertEqual(details["status"], "PENDING")
                self.assertEqual(details["title"], self.debate.title)
                self.assertEqual(parse_datetime(details["closedAt"]), self.ends_at)
                for payload in (response.data, error, details):
                    self.assertNotIn("counts", payload)
                self.assertNotIn("data", response.data)
