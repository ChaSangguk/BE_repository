from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Debate, DebateStatistics, Stance
from .results import summarize_stances
from .tasks import close_due_debates, compute_pending_results
from .test_stance import StanceFixture


class SummarizeStancesTests(SimpleTestCase):
    def test_counts_unchanged_and_changed_by_final_stance(self):
        result = summarize_stances([
            {"initial_stance": Stance.PRO, "current_stance": Stance.PRO, "count": 2},
            {"initial_stance": Stance.PRO, "current_stance": Stance.CON, "count": 1},
        ])
        self.assertEqual(result["total_participants"], 3)
        self.assertEqual(result["final_pro"], 2)
        self.assertEqual(result["final_con"], 1)
        self.assertEqual(result["final_neutral"], 0)
        self.assertEqual(result["stance_kept_count"], 2)
        self.assertEqual(result["stance_changed_count"], 1)


class DebateFlowTests(StanceFixture, TestCase):
    def test_change_close_aggregate_and_read_result(self):
        result_url = reverse("debate-result", args=[self.debate.id])
        self.assertEqual(self.client.get(result_url).status_code, 409)
        self.write_opinion(self.participant, parent=self.opinion, root=self.opinion)
        self.assertEqual(self.patch_stance().status_code, 200)
        self.debate.ends_at = timezone.now()
        self.debate.save(update_fields=["ends_at"])

        self.assertEqual(close_due_debates(), 1)
        self.assertEqual(self.patch_stance(version=1, stance=Stance.NEUTRAL).status_code, 409)
        pending = self.client.get(result_url)
        self.assertEqual(pending.status_code, 202)
        self.assertEqual(pending.data["resultStatus"], "PENDING")

        self.assertEqual(compute_pending_results(), 1)
        self.assertEqual(compute_pending_results(), 0)
        self.assertEqual(DebateStatistics.objects.count(), 1)
        self.assertEqual(DebateStatistics.objects.get().stance_changed_count, 1)

        joined = self.client.get(reverse("joined-debate-list"), {"status": "CLOSED"})
        self.assertEqual(joined.data["results"][0]["status"], Debate.Status.CLOSED)
        self.client.force_authenticate(user=None)
        result = self.client.get(result_url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["participantCount"], 2)
        self.assertEqual(result.data["opinionCount"], 1)
        self.assertEqual(result.data["rebuttalCount"], 1)
        self.assertEqual(result.data["finalStances"][Stance.CON], {"count": 2, "percentage": 100.0})

    def test_draft_and_canceled_debates_have_no_public_result(self):
        url = reverse("debate-result", args=[self.debate.id])
        self.client.force_authenticate(user=None)
        self.debate.status = Debate.Status.DRAFT
        self.debate.save(update_fields=["status"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.debate.status = Debate.Status.CANCELED
        self.debate.save(update_fields=["status"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "debate_canceled")
        self.assertEqual(compute_pending_results(), 0)
