from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class DemographicContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)


    def test_api_9_validates_required_nullable_fields(self):
        path = "/v1/me/demographic"
        payload = dict(gender=None, birthYear=None, region=None, statisticsConsent=False)
        response = self.client.put(path, payload, format="json")
        self.assertEqual(response.status_code, 200)
        for key, value in payload.items():
            self.assertEqual(response.json()["data"]["demographic"][key], value)
        for invalid in (
            dict(gender=None, birthYear=None, statisticsConsent=False),
            dict(payload, gender="UNKNOWN"),
            dict(payload, region="r" * 31),
            dict(payload, statisticsConsent="false"),
        ):
            with self.subTest(invalid=invalid):
                response = self.client.put(path, invalid, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "DEMOGRAPHIC_INVALID")

    def test_api_10_repeated_withdrawal_preserves_demographics(self):
        get_user_model().objects.filter(pk=self.user.pk).update(
            gender="OTHER", birth_year=1999, region="Seoul", statistics_consent=True,
        )
        for _ in range(2):
            response = self.client.delete("/v1/me/demographic/consent")
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.content, b"")
            self.user.refresh_from_db()
            self.assertFalse(self.user.statistics_consent)
            self.assertEqual((self.user.gender, self.user.birth_year, self.user.region), ("OTHER", 1999, "Seoul"))
