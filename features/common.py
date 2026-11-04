from django.core import signing
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from debates.api_contract import MAX_ID, ContractError, ContractResponseMixin, IsActiveMember


class MemberView(ContractResponseMixin, APIView):
    permission_classes = [IsActiveMember]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"POST", "PUT", "PATCH"} and not isinstance(request.data, dict):
            raise ContractError(400, "VALIDATION_ERROR", "Use a JSON object.")


def identifier(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdecimal()
            or len(value) > 19 or not 1 <= int(value) <= MAX_ID):
        raise ContractError(400, "VALIDATION_ERROR", "Use a positive decimal string ID.")
    return int(value)


def optional_id(value):
    return str(value) if value is not None else None


def page(request, rows, key, project, **extra):
    token = request.query_params.get("cursor")
    salt = f"features.page.{key}"
    if token is not None:
        try:
            date, pk = signing.loads(token, salt=salt)
            date = parse_datetime(date)
            if date is None or date.utcoffset() is None or type(pk) is not int or not 1 <= pk <= MAX_ID:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError) as exc:
            raise ContractError(400, "CURSOR_INVALID", "Invalid cursor.") from exc
        rows = rows.filter(Q(created_at__lt=date) | Q(created_at=date, pk__lt=pk))
    items = list(rows.order_by("-created_at", "-pk")[:21])
    cursor = None
    if len(items) == 21:
        items.pop()
        last = items[-1]
        cursor = signing.dumps([last.created_at.isoformat(), last.pk], salt=salt)
    return Response({
        "data": {key: [project(item) for item in items], **extra},
        "meta": {"nextCursor": cursor},
    })
