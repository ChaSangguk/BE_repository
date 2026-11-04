from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase


class TrendContractTests(APITestCase):
    def test_api_24_distinguishes_empty_from_zero_and_sorts_points(self):
        owner = get_user_model().objects.create(email="owner@example.test", nickname="owner")
        category = apps.get_model("debates", "Category").objects.create(name="Trend")
        now = timezone.now()
        debate = apps.get_model("debates", "Debate").objects.create(
            creator=owner, category=category, type="ENDLESS", title="Trend", content="Question",
            status="OPEN", started_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=71),
        )
        path = f"/v1/debates/{debate.pk}/trend"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"points": []}})
        snapshots = apps.get_model("debates", "DebateParticipantSnapshot").objects
        snapshots.create(debate=debate, recorded_at=now, total_count=3, pro_count=2, con_count=1)
        snapshots.create(debate=debate, recorded_at=now - timedelta(minutes=15))
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        first, second = response.json()["data"]["points"]
        self.assertLess(first["recordedAt"], second["recordedAt"])
        self.assertEqual([first[k] for k in ("total", "pro", "con", "neutral")], [0, 0, 0, 0])
        self.assertEqual([second[k] for k in ("total", "pro", "con", "neutral")], [3, 2, 1, 0])
