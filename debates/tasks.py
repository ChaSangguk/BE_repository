from celery import shared_task
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import Debate
from .results import compute_debate_result


@shared_task
@transaction.atomic
def close_due_debates():
    now = timezone.now()
    due_ids = list(
        Debate.objects.with_deadline().select_for_update(skip_locked=True)
        .filter(status=Debate.Status.OPEN, deadline__lte=now)
        .order_by("deadline", "id")
        .values_list("id", flat=True)[:100]
    )
    return Debate.objects.with_deadline().filter(pk__in=due_ids).update(
        status=Debate.Status.CLOSED, closed_at=F("deadline"), ends_at=F("deadline"),
    )


@shared_task
def compute_pending_results():
    debate_ids = list(
        Debate.objects.filter(
            status=Debate.Status.CLOSED, debatestatistics__isnull=True,
        ).filter(
            Q(result_retry_at__isnull=True) | Q(result_retry_at__lte=timezone.now()),
        ).order_by(
            F("result_retry_at").asc(nulls_first=True), "closed_at", "id",
        ).values_list("id", flat=True)[:100]
    )
    return sum(compute_debate_result(debate_id) for debate_id in debate_ids)
