from django.urls import path
from rest_framework.response import Response

from debates.serializers import utc
from economy.models import CoinTransaction
from features.common import MemberView, optional_id, page


class Wallet(MemberView):
    def get(self, request):
        return Response({"data": {"coinBalance": request.user.coin_balance}})


def transaction_item(row):
    return {
        "id": str(row.pk), "amount": row.amount, "type": row.type,
        "balanceAfter": row.balance_after, "refType": row.ref_type,
        "refId": optional_id(row.ref_id),
        "reversesTransactionId": optional_id(row.reverses_transaction_id),
        "createdAt": utc(row.created_at),
    }


class Transactions(MemberView):
    def get(self, request):
        return page(request, CoinTransaction.objects.filter(user=request.user), "transactions", transaction_item)


urlpatterns = [
    path("me/wallet", Wallet.as_view()),
    path("me/coin-transactions", Transactions.as_view()),
]
