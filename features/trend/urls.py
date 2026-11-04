from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from debates.api_contract import ContractError, ContractResponseMixin
from debates.models import Debate, DebateParticipantSnapshot
from debates.serializers import utc
from features.common import identifier


class Trend(ContractResponseMixin, APIView):
    def get(self, request, trend_debate_id):
        debate_id = identifier(trend_debate_id)
        public_statuses = (Debate.Status.OPEN, Debate.Status.CLOSED)
        if not Debate.objects.filter(pk=debate_id, status__in=public_statuses).exists():
            raise ContractError(404, "DEBATE_NOT_FOUND", "Debate not found.")
        snapshots = DebateParticipantSnapshot.objects.filter(
            debate_id=debate_id, debate__status__in=public_statuses,
        ).order_by("recorded_at", "pk")
        return Response({"data": {"points": [{
            "recordedAt": utc(row.recorded_at), "total": row.total_count, "pro": row.pro_count,
            "con": row.con_count, "neutral": row.neutral_count,
        } for row in snapshots]}})


urlpatterns = [path("debates/<str:trend_debate_id>/trend", Trend.as_view())]
