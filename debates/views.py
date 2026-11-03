from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated

from .models import Debate, DebateParticipant
from .serializers import JoinedDebateSerializer


class JoinedDebatePagination(CursorPagination):
    page_size = 20
    ordering = "-id"


class JoinedDebateListView(ListAPIView):
    visible_statuses = (Debate.Status.OPEN, Debate.Status.CLOSED)
    serializer_class = JoinedDebateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JoinedDebatePagination

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
