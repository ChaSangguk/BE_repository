from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class InterestContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)


    def test_api_8_replacement_limit_and_missing_category(self):
        categories = apps.get_model("debates", "Category").objects
        ids = [str(categories.create(name=f"Interest {index}").pk) for index in range(6)]
        path = "/v1/me/interests"
        response = self.client.put(path, {"categoryIds": ids[:5]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([row["id"] for row in response.json()["data"]["interests"]], ids[:5])
        for invalid, status, code in (
            (ids, 400, "INTEREST_LIMIT_EXCEEDED"),
            ([ids[-1], "9223372036854775807"], 404, "CATEGORY_NOT_FOUND"),
        ):
            response = self.client.put(path, {"categoryIds": invalid}, format="json")
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["error"]["code"], code)
            links = apps.get_model("accounts", "UserInterestCategory").objects.filter(user=self.user)
            self.assertCountEqual([str(pk) for pk in links.values_list("category_id", flat=True)], ids[:5])
        response = self.client.put(path, {"categoryIds": []}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"interests": []}})
        self.assertFalse(links.exists())
