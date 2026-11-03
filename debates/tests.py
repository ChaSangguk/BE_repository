from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User

from .models import Category, Debate, DebateParticipant, Stance


class JoinedDebateListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("member@example.com", "Member")
        self.other = User.objects.create_user("other@example.com", "Other")
        self.category = Category.objects.create(name="Society")
        self.client = APIClient()
        self.url = reverse("joined-debate-list")

    def join_debate(self, user, status=Debate.Status.OPEN):
        debate = Debate.objects.create(
            creator=self.other,
            category=self.category,
            type=Debate.Type.ENDLESS,
            title="Debate",
            content="Topic",
            started_at=timezone.now(),
            status=status,
        )
        DebateParticipant.objects.create(
            debate=debate,
            user=user,
            anonymous_no=1,
            initial_stance=Stance.PRO,
            current_stance=Stance.NEUTRAL,
        )
        return debate

    def test_requires_authentication(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_filters_status_and_returns_only_my_participation(self):
        open_debate = self.join_debate(self.user)
        self.join_debate(self.user, Debate.Status.CLOSED)
        self.join_debate(self.other)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url, {"status": "OPEN"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [{
            "debateId": open_debate.id,
            "title": open_debate.title,
            "status": "OPEN",
            "currentStance": "NEUTRAL",
        }])
        self.assertEqual(self.client.get(self.url, {"status": "bad"}).status_code, 400)

    def test_paginates_twenty_items_without_duplicates(self):
        ids = [self.join_debate(self.user).id for _ in range(21)]
        self.client.force_authenticate(user=self.user)

        first = self.client.get(self.url)
        second = self.client.get(first.data["next"])
        self.assertEqual(
            [item["debateId"] for item in first.data["results"]],
            ids[:0:-1],
        )
        self.assertEqual([item["debateId"] for item in second.data["results"]], ids[:1])
        self.assertIsNone(second.data["next"])

    def test_empty_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_excludes_drafts_and_canceled_debates(self):
        self.join_debate(self.user, Debate.Status.DRAFT)
        self.join_debate(self.user, Debate.Status.CANCELED)
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self.client.get(self.url).data["results"], [])
        self.assertEqual(self.client.get(self.url, {"status": "DRAFT"}).status_code, 400)
