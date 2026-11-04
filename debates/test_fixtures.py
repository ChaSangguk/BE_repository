from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from discussions.models import Opinion

from .models import Category, Debate, DebateParticipant, Stance


class DebateFixture:
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
