from django.urls import path
from rest_framework.response import Response

from debates.serializers import utc
from economy.models import CreditHistory, UserBadge
from features.common import MemberView, optional_id, page


def badges(user):
    awards = UserBadge.objects.filter(user=user).select_related("badge").order_by("-acquired_at", "badge_id")
    return [{
        "id": str(award.badge_id), "name": award.badge.name, "iconUrl": award.badge.icon_url,
        "acquiredAt": utc(award.acquired_at), "isRepresentative": award.is_representative,
    } for award in awards]


def history_item(row):
    return {
        "id": str(row.pk), "amount": format(row.amount, ".6f"), "reason": row.reason,
        "refId": optional_id(row.ref_id), "createdAt": utc(row.created_at),
    }


class Credits(MemberView):
    def get(self, request):
        return Response({"data": {"credit": format(request.user.credit, ".6f"), "badges": badges(request.user)}})


class History(MemberView):
    def get(self, request):
        return page(request, CreditHistory.objects.filter(user=request.user), "histories", history_item)


class Badges(MemberView):
    def get(self, request):
        return Response({"data": {"badges": badges(request.user)}})


urlpatterns = [
    path("me/credits", Credits.as_view()),
    path("me/credits/history", History.as_view()),
    path("me/badges", Badges.as_view()),
]
