from django.db import transaction
from django.urls import path
from django.utils import timezone
from rest_framework.response import Response

from accounts.models import Term, User, UserTermAgreement
from debates.api_contract import ContractError
from debates.serializers import utc
from features.common import MemberView, identifier


class Agreements(MemberView):
    @transaction.atomic
    def post(self, request):
        values = request.data.get("agreements")
        if not isinstance(values, list):
            raise ContractError(400, "VALIDATION_ERROR", "agreements must be an array.")
        choices = {}
        for item in values:
            if not isinstance(item, dict) or type(item.get("agreed")) is not bool:
                raise ContractError(400, "VALIDATION_ERROR", "Each agreement requires a boolean agreed.")
            term_id = identifier(item.get("termId"))
            if term_id in choices:
                raise ContractError(400, "VALIDATION_ERROR", "Duplicate terms are not allowed.")
            choices[term_id] = item["agreed"]

        terms = Term.objects.filter(effective_at__lte=timezone.now()).in_bulk(choices)
        if len(terms) != len(choices):
            raise ContractError(404, "TERM_NOT_FOUND", "One or more terms are unavailable.")
        if any(terms[pk].is_required and not agreed for pk, agreed in choices.items()):
            raise ContractError(400, "REQUIRED_TERM_NOT_AGREED", "Required terms must be accepted.")

        User.objects.select_for_update().get(pk=request.user.pk)
        result = []
        for pk, agreed in choices.items():
            state, _ = UserTermAgreement.objects.update_or_create(
                user=request.user, term_id=pk,
                defaults={"agreed": agreed, "agreed_at": timezone.now()},
            )
            result.append({"termId": str(pk), "agreed": state.agreed, "agreedAt": utc(state.agreed_at)})
        return Response({"data": {"agreements": result}})


urlpatterns = [path("me/agreements", Agreements.as_view())]
