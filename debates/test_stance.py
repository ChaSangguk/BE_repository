from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from discussions.models import Opinion, Persuasion

from .models import Category, Debate, DebateParticipant, Stance, StanceHistory
from .stance import change_stance


class StanceFixture:
    def setUp(self):
        self.user = User.objects.create_user("member@example.com", "Member")
        self.other = User.objects.create_user("other@example.com", "Other")
        self.category = Category.objects.create(name="Society")
        self.debate = Debate.objects.create(
            creator=self.other, category=self.category, type=Debate.Type.QUICK,
            title="Debate", content="Topic", started_at=timezone.now(), status=Debate.Status.OPEN,
        )
        self.participant = self.join(self.user, 1, Stance.PRO)
        self.author = self.join(self.other, 2, Stance.CON)
        self.opinion = self.write_opinion(self.author)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def join(self, user, number, stance):
        return DebateParticipant.objects.create(
            debate=self.debate, user=user, anonymous_no=number,
            initial_stance=stance, current_stance=stance,
        )

    def write_opinion(self, participant, **kwargs):
        return Opinion.objects.create(
            debate=self.debate, participant=participant,
            stance_at_write=participant.current_stance, content="Reason",
            content_plain="Reason", **kwargs,
        )

    def patch_stance(self, *, key=None, **overrides):
        data = {"stance": Stance.CON, "opinionId": self.opinion.id, "version": 0}
        data.update(overrides)
        headers = {"Idempotency-Key": key} if key is not None else {}
        return self.client.patch(
            reverse("my-stance", args=[self.debate.id]), data, format="json", headers=headers,
        )


class ChangeStanceServiceTests(StanceFixture, TestCase):
    def test_rejects_own_and_hidden_opinions_without_creating_history(self):
        own = self.write_opinion(self.participant)
        hidden = self.write_opinion(self.author, status=Opinion.Status.FILTERED)

        for opinion in (own, hidden):
            with self.subTest(opinion=opinion.pk), self.assertRaises(ValidationError):
                change_stance(
                    debate_id=self.debate.id, user=self.user, stance=Stance.CON,
                    opinion_id=opinion.id, version=0,
                )
        self.assertFalse(StanceHistory.objects.exists())
        self.assertFalse(Persuasion.objects.exists())


class ChangeStanceAPITests(StanceFixture, TestCase):
    def test_changes_stance_and_rejects_a_stale_retry(self):
        original = self.write_opinion(self.participant)
        state = self.client.get(reverse("my-stance", args=[self.debate.id]))
        self.assertEqual(state.data["version"], 0)

        response = self.patch_stance()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            "initialStance": Stance.PRO, "currentStance": Stance.CON, "version": 1,
        })
        original.refresh_from_db()
        self.assertEqual(original.stance_at_write, Stance.PRO)
        history = StanceHistory.objects.get(participant=self.participant)
        self.assertEqual(history.persuasion.opinion_id, self.opinion.id)

        conflict = self.patch_stance(stance=Stance.NEUTRAL)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data["version"], 1)
        self.assertEqual(StanceHistory.objects.count(), 1)
        self.assertEqual(Persuasion.objects.count(), 1)

    def test_rejects_expired_debate_before_worker_closes_it(self):
        self.debate.ends_at = timezone.now()
        self.debate.save(update_fields=["ends_at"])

        response = self.patch_stance()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "debate_closed")
        self.assertFalse(StanceHistory.objects.exists())

    def test_idempotency_replays_success_and_rejects_different_payload(self):
        first = self.patch_stance(key="mobile-1")
        repeated = self.patch_stance(key="mobile-1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.data, first.data)
        conflict = self.patch_stance(key="mobile-1", stance=Stance.NEUTRAL)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data["code"], "idempotency_key_reused")
        self.assertEqual(StanceHistory.objects.count(), 1)

    def test_draft_is_hidden_and_canceled_debate_cannot_be_changed(self):
        self.debate.status = Debate.Status.DRAFT
        self.debate.save(update_fields=["status"])
        self.assertEqual(self.patch_stance().status_code, 404)
        self.debate.status = Debate.Status.CANCELED
        self.debate.save(update_fields=["status"])
        result = self.patch_stance()
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.data["code"], "debate_canceled")
