from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from debates.api_contract import ContractResponseMixin
from debates.models import Category


def category_item(row):
    return {"id": str(row.pk), "name": row.name, "sortOrder": row.sort_order}


class Categories(ContractResponseMixin, APIView):
    def get(self, request):
        rows = Category.objects.filter(is_active=True).order_by("sort_order", "pk")
        return Response({"data": {"categories": [category_item(row) for row in rows]}})


urlpatterns = [path("categories", Categories.as_view())]
