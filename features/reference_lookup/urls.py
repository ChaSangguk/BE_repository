from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from debates.api_contract import ContractError, ContractResponseMixin
from debates.models import Debate
from discussions.models import Opinion, OpinionReference
from features.common import identifier


class ReferenceLookup(ContractResponseMixin, APIView):
    def get(self, request, reference_id):
        reference_id = identifier(reference_id)
        ref = get_object_or_404(
            OpinionReference.objects.filter(
                opinion__status=Opinion.Status.VISIBLE,
                opinion__debate__status__in=[Debate.Status.OPEN, Debate.Status.CLOSED],
            ),
            pk=reference_id,
        )
        if ref.safe_browsing_status == OpinionReference.SafetyStatus.PENDING:
            raise ContractError(409, "REFERENCE_CHECK_PENDING", "The reference is still being checked.")
        if ref.safe_browsing_status != OpinionReference.SafetyStatus.SAFE:
            raise ContractError(403, "REFERENCE_UNSAFE", "The reference is unavailable.")
        try:
            URLValidator(schemes=["http", "https"])(ref.url)
        except ValidationError as exc:
            raise ContractError(403, "REFERENCE_UNSAFE", "The reference is unavailable.") from exc
        return Response({"data": {"url": ref.url}})


urlpatterns = [path("references/<str:reference_id>", ReferenceLookup.as_view())]
