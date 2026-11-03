from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Debate, DebateParticipant, StanceHistory
from .serializers import (
    JoinedDebateSerializer,
    StanceChangeInput,
    StanceEventSerializer,
    StanceStateSerializer,
)
from .stance import change_stance


class DebateCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-id"


class JoinedDebateListView(ListAPIView):
    visible_statuses = (Debate.Status.OPEN, Debate.Status.CLOSED)
    serializer_class = JoinedDebateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DebateCursorPagination

    def get_queryset(self):
        queryset = DebateParticipant.objects.filter(
            user=self.request.user,
            debate__status__in=self.visible_statuses,
        ).select_related("debate")

        status = self.request.query_params.get("status")
        if status is None:
            return queryset
        if status not in self.visible_statuses:
            raise ValidationError({"status": "Use OPEN or CLOSED."})
        return queryset.filter(debate__status=status)


class MyStanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, debate_id):
        participant = get_object_or_404(
            DebateParticipant.objects.exclude(debate__status=Debate.Status.DRAFT),
            debate_id=debate_id, user=request.user,
        )
        return Response(StanceStateSerializer(participant).data)

    def patch(self, request, debate_id):
        payload = StanceChangeInput(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        result = change_stance(
            debate_id=debate_id, user=request.user, stance=data["stance"],
            opinion_id=data["opinionId"], version=data["version"],
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response(result)


class MyStanceEventListView(ListAPIView):
    serializer_class = StanceEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DebateCursorPagination

    def get_queryset(self):
        participant = get_object_or_404(
            DebateParticipant.objects.exclude(debate__status=Debate.Status.DRAFT),
            debate_id=self.kwargs["debate_id"], user=self.request.user,
        )
        return StanceHistory.objects.filter(participant=participant).select_related("persuasion")
