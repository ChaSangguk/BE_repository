from django.db import transaction
from django.urls import path
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response

from accounts.models import User
from debates.api_contract import ContractError
from debates.serializers import utc
from features.common import MemberView


class DemographicInput(serializers.Serializer):
    gender = serializers.ChoiceField(choices=User.Gender.values, allow_null=True)
    birthYear = serializers.IntegerField(allow_null=True, min_value=-(2**31), max_value=2**31 - 1)
    region = serializers.CharField(allow_null=True, max_length=30)
    statisticsConsent = serializers.BooleanField()


class Demographic(MemberView):
    @transaction.atomic
    def put(self, request):
        form = DemographicInput(data=request.data)
        birth_year = request.data.get("birthYear")
        region = request.data.get("region")
        if (
            not form.is_valid()
            or type(request.data.get("statisticsConsent")) is not bool
            or (birth_year is not None and type(birth_year) is not int)
            or (region is not None and not isinstance(region, str))
        ):
            raise ContractError(400, "DEMOGRAPHIC_INVALID", "Check the demographic fields.", details=form.errors)
        data = form.validated_data
        User.objects.select_for_update().get(pk=request.user.pk)
        changed_at = timezone.now()
        User.objects.filter(pk=request.user.pk).update(
            gender=data["gender"], birth_year=data["birthYear"], region=data["region"],
            statistics_consent=data["statisticsConsent"], statistics_consent_updated_at=changed_at,
        )
        return Response({"data": {"demographic": {**data, "consentUpdatedAt": utc(changed_at)}}})


class WithdrawConsent(MemberView):
    @transaction.atomic
    def delete(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        User.objects.filter(pk=request.user.pk, statistics_consent=True).update(
            statistics_consent=False, statistics_consent_updated_at=timezone.now(),
        )
        return Response(status=204)


urlpatterns = [
    path("me/demographic", Demographic.as_view()),
    path("me/demographic/consent", WithdrawConsent.as_view()),
]
