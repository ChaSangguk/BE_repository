from django.db import transaction
from django.urls import path
from rest_framework.response import Response

from accounts.models import User, UserInterestCategory
from debates.api_contract import ContractError
from debates.models import Category
from features.common import MemberView, identifier


class Interests(MemberView):
    @transaction.atomic
    def put(self, request):
        values = request.data.get("categoryIds")
        if not isinstance(values, list):
            raise ContractError(400, "VALIDATION_ERROR", "categoryIds must be an array.")
        if len(values) > 5:
            raise ContractError(400, "INTEREST_LIMIT_EXCEEDED", "Choose at most five categories.")
        ids = set(map(identifier, values))
        categories = list(Category.objects.filter(pk__in=ids, is_active=True).order_by("sort_order", "pk"))
        if len(categories) != len(ids):
            raise ContractError(404, "CATEGORY_NOT_FOUND", "One or more categories are unavailable.")
        User.objects.select_for_update().get(pk=request.user.pk)
        UserInterestCategory.objects.filter(user=request.user).delete()
        UserInterestCategory.objects.bulk_create([
            UserInterestCategory(user=request.user, category=category) for category in categories
        ])
        return Response({"data": {"interests": [
            {"id": str(row.pk), "name": row.name, "sortOrder": row.sort_order} for row in categories
        ]}})


urlpatterns = [path("me/interests", Interests.as_view())]
