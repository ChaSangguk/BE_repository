from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class WalletContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)


    def test_api_45_requires_authentication_and_returns_own_balance(self):
        get_user_model().objects.filter(pk=self.user.pk).update(coin_balance=23)
        self.user.refresh_from_db()
        path = "/v1/me/wallet"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"coinBalance": 23}})
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(path).status_code, 401)

    def test_api_46_scopes_ledger_and_returns_refund_reference(self):
        transactions = apps.get_model("economy", "CoinTransaction").objects
        original = transactions.create(user=self.user, amount=-1, type="DEBATE_CREATE", balance_after=9)
        refund = transactions.create(user=self.user, amount=1, type="REFUND", balance_after=10, reverses_transaction=original)
        transactions.create(user=self.other, amount=9, type="ADMIN_GRANT", balance_after=19)
        path = "/v1/me/coin-transactions"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["meta"], {"nextCursor": None})
        rows = body["data"]["transactions"]
        self.assertCountEqual([row["id"] for row in rows], [str(original.pk), str(refund.pk)])
        row, = [row for row in rows if row["type"] == "REFUND"]
        self.assertEqual(row["reversesTransactionId"], str(original.pk))
        self.assertEqual(row["balanceAfter"], 10)
        self.assertIsNone(row["refId"])
        self.assertIsNone(row["refType"])
        response = self.client.get(path, {"cursor": "invalid cursor !"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "CURSOR_INVALID")
