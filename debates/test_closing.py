from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import Debate
from .tasks import close_due_debates
from .test_fixtures import DebateFixture


class CloseDebateTests(DebateFixture, TestCase):
    def test_closes_due_debate_once(self):
        self.debate.ends_at = timezone.now()
        self.debate.save(update_fields=["ends_at"])

        self.assertEqual(close_due_debates(), 1)
        self.debate.refresh_from_db()
        closed_at = self.debate.closed_at
        self.assertEqual(self.debate.status, Debate.Status.CLOSED)
        self.assertEqual(closed_at, self.debate.ends_at)

        self.assertEqual(close_due_debates(), 0)
        self.debate.refresh_from_db()
        self.assertEqual(self.debate.closed_at, closed_at)

    def test_leaves_open_debates_without_a_due_deadline(self):
        self.assertEqual(close_due_debates(), 0)
        self.debate.ends_at = timezone.now() + timedelta(minutes=5)
        self.debate.save(update_fields=["ends_at"])
        self.assertEqual(close_due_debates(), 0)
        self.debate.refresh_from_db()
        self.assertEqual(self.debate.status, Debate.Status.OPEN)

    def test_derives_missing_deadlines_and_only_closes_open_debates(self):
        for debate_type, duration, elapsed in (
            (Debate.Type.QUICK, 5, timedelta(minutes=5)),
            (Debate.Type.ENDLESS, None, timedelta(hours=72)),
        ):
            with self.subTest(debate_type=debate_type):
                started = timezone.now() - elapsed
                debate = Debate.objects.create(
                    creator=self.other, category=self.category, type=debate_type,
                    title="Past debate", content="Topic", started_at=started,
                    duration_minutes=duration, status=Debate.Status.OPEN,
                )
                self.assertEqual(close_due_debates(), 1)
                debate.refresh_from_db()
                self.assertEqual(debate.ends_at, started + elapsed)
                self.assertEqual(debate.status, Debate.Status.CLOSED)

        self.debate.ends_at = timezone.now()
        for status in (Debate.Status.DRAFT, Debate.Status.CANCELED):
            self.debate.status = status
            self.debate.save(update_fields=["status", "ends_at"])
            self.assertEqual(close_due_debates(), 0)
