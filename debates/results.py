from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from discussions.models import Opinion

from .models import Debate, DebateParticipant, DebateStatistics, Stance


def summarize_stances(groups):
    final_counts = dict.fromkeys(Stance.values, 0)
    kept = 0
    transitions = []
    for group in groups:
        initial = group["initial_stance"]
        current = group["current_stance"]
        count = group["count"]
        final_counts[current] += count
        if initial == current:
            kept += count
        transitions.append({"from": initial, "to": current, "count": count})

    total = sum(final_counts.values())
    return {
        "total_participants": total,
        "final_pro": final_counts[Stance.PRO],
        "final_con": final_counts[Stance.CON],
        "final_neutral": final_counts[Stance.NEUTRAL],
        "stance_changed_count": total - kept,
        "stance_kept_count": kept,
        "sankey_data": transitions,
    }


@transaction.atomic
def compute_debate_result(debate_id):
    debate = Debate.objects.select_for_update().filter(
        pk=debate_id, status=Debate.Status.CLOSED,
    ).first()
    if debate is None or DebateStatistics.objects.filter(debate=debate).exists():
        return False

    groups = (
        DebateParticipant.objects.filter(debate=debate)
        .values("initial_stance", "current_stance")
        .annotate(count=Count("id"))
        .order_by("initial_stance", "current_stance")
    )
    posts = Opinion.objects.filter(debate=debate, status=Opinion.Status.VISIBLE)
    counts = posts.aggregate(
        opinion_count=Count("id", filter=Q(parent__isnull=True)),
        rebuttal_count=Count("id", filter=Q(parent__isnull=False)),
    )
    DebateStatistics.objects.create(
        debate=debate,
        gender_hidden=True,
        age_hidden=True,
        computed_at=timezone.now(),
        **counts,
        **summarize_stances(groups),
    )
    return True
