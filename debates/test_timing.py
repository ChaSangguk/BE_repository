from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Debate
from .test_stance import StanceFixture


class DebateTimingTests(StanceFixture, TestCase):
    def test_uses_server_time_and_derives_deadline_for_public_timer(self):
        self.client.force_authenticate(user=None)
        url = reverse("debate-timing", args=[self.debate.id])
        self.debate.duration_minutes = 5
        self.debate.save(update_fields=["duration_minutes"])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Debate.Status.OPEN)
        ends_at = parse_datetime(response.data["endsAt"])
        self.assertEqual(ends_at, self.debate.started_at + timedelta(minutes=5))
        self.assertLess(parse_datetime(response.data["serverTime"]), ends_at)

        self.debate.ends_at = timezone.now()
        self.debate.save(update_fields=["ends_at"])
        self.assertEqual(self.client.get(url).data["status"], Debate.Status.CLOSED)
        result = self.client.get(reverse("debate-result", args=[self.debate.id]))
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.data["error"]["code"], "RESULT_NOT_READY")
        self.assertEqual(result.data["error"]["details"]["status"], "PENDING")
        self.debate.refresh_from_db()
        self.assertEqual(self.debate.status, Debate.Status.OPEN)

    def test_hides_drafts(self):
        self.debate.status = Debate.Status.DRAFT
        self.debate.save(update_fields=["status"])
        self.assertEqual(
            self.client.get(reverse("debate-timing", args=[self.debate.id])).status_code, 404,
        )
