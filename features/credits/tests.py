from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class CreditContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)


    def test_apis_47_and_49_return_credit_and_earned_badge(self):
        get_user_model().objects.filter(pk=self.user.pk).update(credit="30.125001")
        self.user.refresh_from_db()
        badge = apps.get_model("economy", "Badge").objects.create(
            name="Test Badge", icon_url="https://example.test/badge.png", required_credit="30.125001",
        )
        apps.get_model("economy", "UserBadge").objects.create(user=self.user, badge=badge)
        credit = self.client.get("/v1/me/credits")
        badges = self.client.get("/v1/me/badges")
        self.assertEqual(credit.status_code, 200)
        self.assertEqual(badges.status_code, 200)
        self.assertEqual(credit.json()["data"]["credit"], "30.125001")
        awards = badges.json()["data"]["badges"]
        self.assertEqual(credit.json()["data"]["badges"], awards)
        award, = awards
        self.assertEqual(award["id"], str(badge.pk))
        self.assertEqual(award["name"], badge.name)
        self.assertEqual(award["iconUrl"], badge.icon_url)
        self.assertIsInstance(award["acquiredAt"], str)
        self.assertIs(award["isRepresentative"], False)

    def test_api_48_returns_exact_amount_and_only_own_history(self):
        histories = apps.get_model("economy", "CreditHistory").objects
        history = histories.create(user=self.user, amount="-0.125001", reason="TEST")
        histories.create(user=self.other, amount="0.250000", reason="TEST")
        path = "/v1/me/credits/history"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["meta"], {"nextCursor": None})
        row, = body["data"]["histories"]
        self.assertEqual(row["id"], str(history.pk))
        self.assertEqual(row["amount"], "-0.125001")
        self.assertIsNone(row["refId"])
        response = self.client.get(path, {"cursor": "invalid cursor !"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "CURSOR_INVALID")
